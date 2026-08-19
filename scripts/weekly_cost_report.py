#!/usr/bin/env python3
"""
Generate weekly cost report with tier breakdown.

Shows:
- Requests per tier
- Cost per tier
- Cost trends
- Average cost per request

Usage:
    python3 scripts/weekly_cost_report.py
    python3 scripts/weekly_cost_report.py --days 30  # 30-day report
"""

import psycopg2
import os
import sys
from datetime import datetime, timedelta
from typing import Optional, Tuple, List

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://litellm:litellm@localhost:5432/litellm")

def get_tier_name(model: str) -> str:
    """Convert model name to tier name."""
    if "opus" in model.lower():
        return "REASONING (Opus)"
    elif "sonnet" in model.lower():
        return "COMPLEX (Sonnet)"
    elif "haiku" in model.lower():
        return "SIMPLE (Haiku)"
    else:
        return "OTHER"


def format_number(num: float, decimals: int = 2) -> str:
    """Format number with proper alignment."""
    if isinstance(num, int):
        return f"{num:>10,}"
    return f"{num:>10,.{decimals}f}"


def generate_report(days: int = 7) -> None:
    """Generate weekly cost report."""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        
        start_date = datetime.now() - timedelta(days=days)
        
        # Query tier distribution
        query = """
        SELECT 
            model,
            COUNT(*) as requests,
            ROUND(SUM(spend)::numeric, 4) as total_cost,
            ROUND(AVG(total_tokens)::numeric, 0) as avg_tokens,
            ROUND(MAX(EXTRACT(EPOCH FROM (endTime - startTime)))::numeric, 2) as max_latency
        FROM "LiteLLM_SpendLogs"
        WHERE 
            startTime > %s
            AND model IN (
                'vertex_ai/claude-opus-4-6',
                'vertex_ai/claude-sonnet-4-5',
                'vertex_ai/claude-haiku-4-5',
                'architecture-tier',
                'implementation-tier',
                'quick-info'
            )
        GROUP BY model
        ORDER BY total_cost DESC;
        """
        
        cursor.execute(query, (start_date,))
        results = cursor.fetchall()
        
        # Print header
        print("\n" + "=" * 95)
        print(f"LiteLLM Cost Report - Last {days} Days ({start_date.strftime('%Y-%m-%d')} to {datetime.now().strftime('%Y-%m-%d')})")
        print("=" * 95)
        print()
        
        # Calculate totals
        total_requests = 0
        total_cost = 0.0
        tier_summary = {}
        
        # Collect data by tier
        for row in results:
            model, requests, cost, avg_tokens, max_latency = row
            tier = get_tier_name(model)
            total_requests += requests
            total_cost += float(cost)
            
            if tier not in tier_summary:
                tier_summary[tier] = {
                    "requests": 0,
                    "cost": 0.0,
                    "models": []
                }
            
            tier_summary[tier]["requests"] += requests
            tier_summary[tier]["cost"] += float(cost)
            tier_summary[tier]["models"].append({
                "model": model,
                "requests": requests,
                "cost": float(cost)
            })
        
        # Print table header
        print(f"{'Model/Tier':<35} {'Requests':>12} {'Cost ($)':>12} {'Avg Cost':>12} {'% of Total':>12}")
        print("-" * 95)
        
        # Print results by tier
        for tier in sorted(tier_summary.keys(), key=lambda x: tier_summary[x]["cost"], reverse=True):
            data = tier_summary[tier]
            tier_pct = (data["cost"] / total_cost * 100) if total_cost > 0 else 0
            
            # Print tier header
            print(f"{tier:<35} {data['requests']:>12,} ${data['cost']:>11.2f} ${data['cost']/data['requests']:>11.4f} {tier_pct:>11.1f}%")
            
            # Print individual models under tier
            for model_data in sorted(data["models"], key=lambda x: x["cost"], reverse=True):
                model_short = model_data["model"].split("/")[-1] if "/" in model_data["model"] else model_data["model"]
                model_pct = (model_data["cost"] / total_cost * 100) if total_cost > 0 else 0
                print(f"  └─ {model_short:<32} {model_data['requests']:>12,} ${model_data['cost']:>11.2f} ${model_data['cost']/model_data['requests']:>11.4f} {model_pct:>11.1f}%")
            
            print()
        
        # Print totals
        print("-" * 95)
        print(f"{'TOTAL':<35} {total_requests:>12,} ${total_cost:>11.2f} ${total_cost/total_requests:>11.4f} {'100.0%':>12}")
        print()
        
        # Print summary stats
        print("Summary Statistics:")
        print(f"  Total Requests:    {total_requests:,}")
        print(f"  Total Cost:        ${total_cost:.2f}")
        print(f"  Average Cost/Req:  ${total_cost/total_requests:.4f}")
        print()
        
        # Print per-tier percentages
        print("Tier Distribution:")
        for tier in sorted(tier_summary.keys(), key=lambda x: tier_summary[x]["cost"], reverse=True):
            data = tier_summary[tier]
            req_pct = (data["requests"] / total_requests * 100) if total_requests > 0 else 0
            cost_pct = (data["cost"] / total_cost * 100) if total_cost > 0 else 0
            print(f"  {tier:<25}: {req_pct:>5.1f}% requests, {cost_pct:>5.1f}% cost")
        
        print()
        
        # Query daily trend
        trend_query = """
        SELECT 
            DATE(startTime) as date,
            CASE 
                WHEN "model" LIKE '%opus%' THEN 'REASONING'
                WHEN "model" LIKE '%sonnet%' THEN 'COMPLEX'
                WHEN "model" LIKE '%haiku%' THEN 'SIMPLE'
                ELSE 'OTHER'
            END as tier,
            COUNT(*) as requests,
            ROUND(SUM(spend)::numeric, 2) as cost
        FROM "LiteLLM_SpendLogs"
        WHERE 
            startTime > %s
            AND model IN (
                'vertex_ai/claude-opus-4-6',
                'vertex_ai/claude-sonnet-4-5',
                'vertex_ai/claude-haiku-4-5',
                'architecture-tier',
                'implementation-tier',
                'quick-info'
            )
        GROUP BY DATE(startTime), tier
        ORDER BY date DESC, cost DESC;
        """
        
        cursor.execute(trend_query, (start_date,))
        trend_results = cursor.fetchall()
        
        if trend_results:
            print("Daily Trend (Last 7 Days):")
            print()
            
            current_date = None
            daily_total = 0.0
            
            for date, tier, requests, cost in trend_results:
                if current_date != date:
                    if current_date is not None:
                        print(f"  {current_date}: ${daily_total:>8.2f}")
                    current_date = date
                    daily_total = 0.0
                
                daily_total += float(cost)
            
            if current_date is not None:
                print(f"  {current_date}: ${daily_total:>8.2f}")
        
        print()
        print("=" * 95)
        
        cursor.close()
        conn.close()
        
    except psycopg2.Error as e:
        print(f"ERROR: Database connection failed: {e}", file=sys.stderr)
        print(f"Make sure DATABASE_URL is set: {DATABASE_URL}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate LiteLLM cost report")
    parser.add_argument("--days", type=int, default=7, help="Number of days to report (default: 7)")
    
    args = parser.parse_args()
    
    generate_report(days=args.days)
