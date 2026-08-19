#!/usr/bin/env python3
"""
test_routing.py — Test auto-routing with realistic prompts from actual workload.

Tests complexity-based routing with prompts typical of HyperShift, Kubernetes operators,
distributed systems, and GCP infrastructure work to validate tier assignments.

Usage:
    export LITELLM_VIRTUAL_KEY=$(cat ~/.config/opencode/.litellm-key)
    # OR
    export LITELLM_MASTER_KEY=sk-your-master-key

    python3 scripts/test_routing.py
"""

import os
import sys

try:
    from openai import OpenAI
except ImportError:
    print("ERROR: openai package not installed.", file=sys.stderr)
    print("  pip3 install openai", file=sys.stderr)
    sys.exit(1)

PROXY_URL = os.environ.get("LITELLM_PROXY_URL", "http://localhost:4000")
API_KEY = os.environ.get("LITELLM_VIRTUAL_KEY") or os.environ.get("LITELLM_MASTER_KEY")

if not API_KEY:
    print("ERROR: No API key found.", file=sys.stderr)
    print("  Set LITELLM_VIRTUAL_KEY or LITELLM_MASTER_KEY", file=sys.stderr)
    sys.exit(1)

client = OpenAI(
    api_key=API_KEY,
    base_url=f"{PROXY_URL}/v1",
)

# Test cases based on actual workload from gcp-hcp, gcp-hcp-infra, gecko, hypershift
test_cases = [
    # ── EXPECTED TIER: COMPLEX (sonnet) - Informational ──
    {
        "prompt": "What is a kubernetes operator?",
        "expected_tier": "COMPLEX",
        "category": "Informational - technical concept",
    },
    {
        "prompt": "Explain how hypershift hosted control planes work",
        "expected_tier": "COMPLEX",
        "category": "Informational - architecture concept",
    },
    {
        "prompt": "How does Private Service Connect work in GKE?",
        "expected_tier": "COMPLEX",
        "category": "Informational - GCP networking",
    },
    {
        "prompt": "Describe the kubernetes controller-runtime reconcile loop",
        "expected_tier": "COMPLEX",
        "category": "Informational - technical pattern",
    },
    
    # ── EXPECTED TIER: COMPLEX (sonnet) - Implementation ──
    {
        "prompt": "Implement a kubernetes controller reconcile loop for nodepool scaling",
        "expected_tier": "COMPLEX",
        "category": "Implementation - controller code",
    },
    {
        "prompt": "Write terraform for a GKE cluster with workload identity federation",
        "expected_tier": "COMPLEX",
        "category": "Implementation - infrastructure",
    },
    {
        "prompt": "Fix this operator controller that's not updating status conditions properly",
        "expected_tier": "COMPLEX",
        "category": "Implementation - debugging",
    },
    {
        "prompt": "Add retry logic to this kubernetes operator reconcile function",
        "expected_tier": "COMPLEX",
        "category": "Implementation - enhancement",
    },
    {
        "prompt": "Refactor this ArgoCD application manifest to use Kustomize overlays",
        "expected_tier": "COMPLEX",
        "category": "Implementation - refactoring",
    },
    
    # ── EXPECTED TIER: REASONING (opus) - Architecture ──
    {
        "prompt": "Design a multi-cluster architecture for hypershift on GCP with regional isolation",
        "expected_tier": "REASONING",
        "category": "Architecture - system design",
    },
    {
        "prompt": "Evaluate tradeoffs between Maestro and Firestore for the transport layer",
        "expected_tier": "REASONING",
        "category": "Architecture - technology choice",
    },
    {
        "prompt": "Architecture decision: should we use Private Service Connect or VPC peering for tenant isolation?",
        "expected_tier": "REASONING",
        "category": "Architecture - ADR",
    },
    {
        "prompt": "Design a fault-tolerant operator system for multi-region deployment with consensus",
        "expected_tier": "REASONING",
        "category": "Architecture - distributed system",
    },
    {
        "prompt": "Design decision record for etcd backup strategy in hosted control plane architecture",
        "expected_tier": "REASONING",
        "category": "Architecture - ADR",
    },
    
    # ── EDGE CASES ──
    {
        "prompt": "What is kubernetes?",
        "expected_tier": "SIMPLE or COMPLEX",
        "category": "Edge case - very basic",
    },
    {
        "prompt": "Debug why my kubernetes pod is failing",
        "expected_tier": "COMPLEX",
        "category": "Edge case - debugging",
    },
]

print(f"LiteLLM Auto-Router Optimization Test")
print(f"Proxy:      {PROXY_URL}")
print(f"Model:      claude-auto (optimized complexity router)")
print(f"Test cases: {len(test_cases)}")
print()
print(f"{'Category':<35} {'Expected':<12} {'Actual':<20} {'Status'}")
print("-" * 85)

results = {
    "SIMPLE": 0,
    "MEDIUM": 0,
    "COMPLEX": 0,
    "REASONING": 0,
    "ERRORS": 0,
}

mismatches = []

for i, test in enumerate(test_cases, 1):
    prompt = test["prompt"]
    expected = test["expected_tier"]
    category = test["category"]
    
    try:
        response = client.chat.completions.create(
            model="claude-auto",
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            max_tokens=50,  # Keep short to minimize cost
        )
        
        actual_model = response.model
        
        # Determine actual tier from model name
        if "haiku" in actual_model.lower():
            actual_tier = "SIMPLE"
        elif "sonnet" in actual_model.lower():
            actual_tier = "COMPLEX"
        elif "opus" in actual_model.lower():
            actual_tier = "REASONING"
        else:
            actual_tier = "UNKNOWN"
        
        results[actual_tier] = results.get(actual_tier, 0) + 1
        
        # Check if matches expected
        if "or" in expected:
            # Edge case with multiple acceptable outcomes
            acceptable = [t.strip() for t in expected.split("or")]
            status = "✓" if actual_tier in acceptable else "✗"
        else:
            status = "✓" if actual_tier == expected else "✗"
        
        if status == "✗":
            mismatches.append({
                "prompt": prompt[:60] + "..." if len(prompt) > 60 else prompt,
                "expected": expected,
                "actual": actual_tier,
                "category": category,
            })
        
        print(f"{category:<35} {expected:<12} {actual_tier:<20} {status}")
        
    except Exception as e:
        print(f"{category:<35} {expected:<12} ERROR: {str(e)[:30]:<20} ✗")
        results["ERRORS"] += 1

print()
print("-" * 85)
print("Results Summary:")
print(f"  SIMPLE (haiku):     {results.get('SIMPLE', 0):>3} requests")
print(f"  COMPLEX (sonnet):   {results.get('COMPLEX', 0):>3} requests")
print(f"  REASONING (opus):   {results.get('REASONING', 0):>3} requests")
print(f"  ERRORS:             {results.get('ERRORS', 0):>3} requests")
print()

if mismatches:
    print("Mismatched Routing Decisions:")
    print("-" * 85)
    for m in mismatches:
        print(f"  Prompt:   {m['prompt']}")
        print(f"  Expected: {m['expected']}")
        print(f"  Actual:   {m['actual']}")
        print(f"  Category: {m['category']}")
        print()

# Calculate percentages
total = sum(results.get(k, 0) for k in ["SIMPLE", "COMPLEX", "REASONING"])
if total > 0:
    print("Distribution:")
    print(f"  SIMPLE:    {results.get('SIMPLE', 0)/total*100:>5.1f}%")
    print(f"  COMPLEX:   {results.get('COMPLEX', 0)/total*100:>5.1f}%")
    print(f"  REASONING: {results.get('REASONING', 0)/total*100:>5.1f}%")
    print()
    print("Expected distribution for your workload:")
    print("  COMPLEX:   55-65% (implementation + informational)")
    print("  REASONING: 30-40% (architecture + design)")
    print("  SIMPLE:    <10% (rare edge cases)")
