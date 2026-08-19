#!/usr/bin/env python3
"""
Enhanced routing test suite covering actual GCP-HCP workload patterns.

Tests complexity-based routing with 40+ prompts typical of HyperShift, Kubernetes
operators, distributed systems, and GCP infrastructure work to validate tier assignments.

Usage:
    export LITELLM_VIRTUAL_KEY=$(cat ~/.config/opencode/.litellm-key)
    python3 scripts/test_routing_enhanced.py

Expected tier distribution for your workload:
  REASONING (Opus):  25-30% (architecture, ADRs, trade-off analysis)
  COMPLEX (Sonnet):  65-70% (implementation, debugging, informational)
  SIMPLE (Haiku):    <5%    (rare edge cases)
"""

import os
import sys
import json
from datetime import datetime

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

# Comprehensive test cases based on actual GCP-HCP workload
test_cases = [
    # ═══════════════════════════════════════════════════════════════════════════════
    # ARCHITECTURE & DESIGN → REASONING (Opus)
    # ═══════════════════════════════════════════════════════════════════════════════
    
    # ADRs & Design Decisions
    {
        "prompt": "Write an ADR for choosing between Firestore and Maestro for the transport layer",
        "expected_tier": "REASONING",
        "category": "ADR - Technology choice",
    },
    {
        "prompt": "Create a design decision record for etcd backup strategy in hosted control planes",
        "expected_tier": "REASONING",
        "category": "ADR - Infrastructure",
    },
    {
        "prompt": "RFC for Private Service Connect vs VPC peering for tenant isolation",
        "expected_tier": "REASONING",
        "category": "RFC - Networking",
    },
    
    # System Architecture
    {
        "prompt": "Design a multi-cluster architecture for HyperShift on GCP with regional isolation",
        "expected_tier": "REASONING",
        "category": "Architecture - Multi-cluster",
    },
    {
        "prompt": "Architecture for fault-tolerant operator system with multi-region deployment",
        "expected_tier": "REASONING",
        "category": "Architecture - Distributed systems",
    },
    {
        "prompt": "Design a kubernetes operator architecture for managing hosted control planes",
        "expected_tier": "REASONING",
        "category": "Architecture - Operators (has both 'kubernetes' AND 'architecture')",
    },
    {
        "prompt": "System architecture for zero-operator access using Cloud Workflows remediation",
        "expected_tier": "REASONING",
        "category": "Architecture - Automation",
    },
    
    # Trade-off Analysis
    {
        "prompt": "Evaluate tradeoffs between using Karpenter vs Cluster Autoscaler for GKE",
        "expected_tier": "REASONING",
        "category": "Architecture - Trade-off analysis",
    },
    {
        "prompt": "Compare Maestro and Firestore for transport layer: latency, cost, scalability",
        "expected_tier": "REASONING",
        "category": "Architecture - Comparison",
    },
    
    # Infrastructure Design
    {
        "prompt": "Design a terraform module structure for multi-region GCP infrastructure",
        "expected_tier": "REASONING",
        "category": "Architecture - Infrastructure design",
    },
    {
        "prompt": "GCP architecture for management clusters with Workload Identity Federation",
        "expected_tier": "REASONING",
        "category": "Architecture - GCP design",
    },
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # IMPLEMENTATION → COMPLEX (Sonnet)
    # ═══════════════════════════════════════════════════════════════════════════════
    
    # Terraform Implementation
    {
        "prompt": "Write a terraform module for GKE cluster with Workload Identity Federation",
        "expected_tier": "COMPLEX",
        "category": "Implementation - Terraform",
    },
    {
        "prompt": "Create terraform configuration for Private Service Connect subnet",
        "expected_tier": "COMPLEX",
        "category": "Implementation - Terraform networking",
    },
    {
        "prompt": "Implement terraform module for BigQuery data lake with Log Router sink",
        "expected_tier": "COMPLEX",
        "category": "Implementation - Terraform",
    },
    {
        "prompt": "Write terraform to provision customer GCP projects with IAM bindings",
        "expected_tier": "COMPLEX",
        "category": "Implementation - Terraform",
    },
    
    # Operator/Controller Implementation
    {
        "prompt": "Implement a kubernetes controller reconcile loop for HyperShift nodepool scaling",
        "expected_tier": "COMPLEX",
        "category": "Implementation - Controller",
    },
    {
        "prompt": "Write operator code for managing Cedar authorization policies in gecko",
        "expected_tier": "COMPLEX",
        "category": "Implementation - Operator",
    },
    {
        "prompt": "Create a controller that watches HostedCluster CRDs and creates management clusters",
        "expected_tier": "COMPLEX",
        "category": "Implementation - Controller",
    },
    {
        "prompt": "Implement placement controller logic for assigning clusters to management nodes",
        "expected_tier": "COMPLEX",
        "category": "Implementation - Controller",
    },
    
    # GitOps & Configuration
    {
        "prompt": "Create an ArgoCD application for deploying gecko platform API to region clusters",
        "expected_tier": "COMPLEX",
        "category": "Implementation - ArgoCD",
    },
    {
        "prompt": "Write a helm chart for karpenter-operator with management mode support",
        "expected_tier": "COMPLEX",
        "category": "Implementation - Helm",
    },
    {
        "prompt": "Implement Kustomize overlay for HyperShift operator in production environment",
        "expected_tier": "COMPLEX",
        "category": "Implementation - Kustomize",
    },
    {
        "prompt": "Create Cloud Workflows YAML for etcd maintenance operations",
        "expected_tier": "COMPLEX",
        "category": "Implementation - Automation",
    },
    
    # Code Refactoring & Enhancement
    {
        "prompt": "Refactor the orlop framework to support Spanner as a storage backend",
        "expected_tier": "COMPLEX",
        "category": "Implementation - Refactoring",
    },
    {
        "prompt": "Add retry logic to Cloud Workflows etcd-ops remediation flow",
        "expected_tier": "COMPLEX",
        "category": "Implementation - Enhancement",
    },
    {
        "prompt": "Implement version resolution controller using Cincinnati API",
        "expected_tier": "COMPLEX",
        "category": "Implementation - Controller",
    },
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # DEBUGGING & TROUBLESHOOTING → COMPLEX (Sonnet)
    # ═══════════════════════════════════════════════════════════════════════════════
    
    {
        "prompt": "Debug why ArgoCD sync is failing for gecko helm chart deployment",
        "expected_tier": "COMPLEX",
        "category": "Debugging - GitOps",
    },
    {
        "prompt": "Troubleshoot terraform apply error: Invalid IAM policy binding for WIF",
        "expected_tier": "COMPLEX",
        "category": "Debugging - Terraform",
    },
    {
        "prompt": "Fix HyperShift operator reconciliation loop stuck on HostedCluster status update",
        "expected_tier": "COMPLEX",
        "category": "Debugging - Operator",
    },
    {
        "prompt": "Investigate why karpenter-provider-gcp is not provisioning nodes in us-east5",
        "expected_tier": "COMPLEX",
        "category": "Debugging - Karpenter",
    },
    {
        "prompt": "Error: Vertex AI authentication failed with ACCESS_TOKEN_TYPE_UNSUPPORTED",
        "expected_tier": "COMPLEX",
        "category": "Debugging - GCP",
    },
    {
        "prompt": "Debug Cedar authorization deny policy not working for user role",
        "expected_tier": "COMPLEX",
        "category": "Debugging - Authorization",
    },
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # INFORMATIONAL QUERIES → COMPLEX (Sonnet)
    # ═══════════════════════════════════════════════════════════════════════════════
    
    {
        "prompt": "What is Private Service Connect and how does it work in GKE?",
        "expected_tier": "COMPLEX",
        "category": "Informational - GCP",
    },
    {
        "prompt": "Explain how HyperShift hosted control planes work",
        "expected_tier": "COMPLEX",
        "category": "Informational - HyperShift",
    },
    {
        "prompt": "How does the kubernetes controller-runtime reconcile loop work?",
        "expected_tier": "COMPLEX",
        "category": "Informational - Kubernetes",
    },
    {
        "prompt": "Describe the gecko orlop framework and dual API architecture",
        "expected_tier": "COMPLEX",
        "category": "Informational - gecko",
    },
    {
        "prompt": "What are the differences between Karpenter and Cluster Autoscaler?",
        "expected_tier": "COMPLEX",
        "category": "Informational - Comparison",
    },
    {
        "prompt": "Tell me about Workload Identity Federation in GCP",
        "expected_tier": "COMPLEX",
        "category": "Informational - GCP",
    },
    {
        "prompt": "Explain the controller-runtime reconcile pattern",
        "expected_tier": "COMPLEX",
        "category": "Informational - Kubernetes",
    },
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # EDGE CASES
    # ═══════════════════════════════════════════════════════════════════════════════
    
    {
        "prompt": "What is kubernetes?",
        "expected_tier": "SIMPLE or COMPLEX",
        "category": "Edge case - Very basic",
    },
    {
        "prompt": "Hello, how are you?",
        "expected_tier": "SIMPLE",
        "category": "Edge case - Greeting",
    },
    {
        "prompt": "Design and implement a terraform module for multi-region GKE with PSC",
        "expected_tier": "REASONING",
        "category": "Edge case - Design keyword should take precedence",
    },
]

print(f"LiteLLM Enhanced Routing Test Suite")
print(f"Proxy:      {PROXY_URL}")
print(f"Model:      claude-auto (optimized complexity router)")
print(f"Test cases: {len(test_cases)}")
print(f"Timestamp:  {datetime.now().isoformat()}")
print()
print(f"{'Category':<40} {'Expected':<15} {'Actual':<15} {'Status'}")
print("-" * 90)

results = {
    "SIMPLE": 0,
    "MEDIUM": 0,
    "COMPLEX": 0,
    "REASONING": 0,
    "ERRORS": 0,
}

mismatches = []
detailed_results = []

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
                "prompt": prompt[:50] + "..." if len(prompt) > 50 else prompt,
                "expected": expected,
                "actual": actual_tier,
                "category": category,
            })
        
        print(f"{category:<40} {expected:<15} {actual_tier:<15} {status}")
        
        detailed_results.append({
            "prompt": prompt,
            "expected_tier": expected,
            "actual_tier": actual_tier,
            "category": category,
            "status": status,
            "model": actual_model,
        })
        
    except Exception as e:
        print(f"{category:<40} {expected:<15} ERROR {str(e)[:20]:<10} ✗")
        results["ERRORS"] += 1
        detailed_results.append({
            "prompt": prompt,
            "expected_tier": expected,
            "actual_tier": "ERROR",
            "category": category,
            "status": "✗",
            "error": str(e),
        })

print()
print("-" * 90)
print("Results Summary:")
print(f"  SIMPLE (haiku):     {results.get('SIMPLE', 0):>3} requests")
print(f"  COMPLEX (sonnet):   {results.get('COMPLEX', 0):>3} requests")
print(f"  REASONING (opus):   {results.get('REASONING', 0):>3} requests")
print(f"  ERRORS:             {results.get('ERRORS', 0):>3} requests")
print()

if mismatches:
    print("Mismatched Routing Decisions (Fix Keywords if Needed):")
    print("-" * 90)
    for m in mismatches:
        print(f"  Prompt:   {m['prompt']}")
        print(f"  Expected: {m['expected']}")
        print(f"  Actual:   {m['actual']}")
        print(f"  Category: {m['category']}")
        print()

# Calculate percentages
total = sum(results.get(k, 0) for k in ["SIMPLE", "COMPLEX", "REASONING"])
if total > 0:
    print("Actual Tier Distribution:")
    print(f"  SIMPLE:    {results.get('SIMPLE', 0)/total*100:>5.1f}%")
    print(f"  COMPLEX:   {results.get('COMPLEX', 0)/total*100:>5.1f}%")
    print(f"  REASONING: {results.get('REASONING', 0)/total*100:>5.1f}%")
    print()
    
    print("Expected Distribution for GCP-HCP Workload:")
    print(f"  COMPLEX:   55-70% (implementation + informational)")
    print(f"  REASONING: 25-40% (architecture + design)")
    print(f"  SIMPLE:    <5%    (rare edge cases)")
    print()

# Save detailed results to JSON for analysis
results_file = "routing_test_results.json"
with open(results_file, "w") as f:
    json.dump({
        "timestamp": datetime.now().isoformat(),
        "test_count": len(test_cases),
        "summary": results,
        "distribution": {
            "SIMPLE": f"{results.get('SIMPLE', 0)/total*100:.1f}%" if total > 0 else "0%",
            "COMPLEX": f"{results.get('COMPLEX', 0)/total*100:.1f}%" if total > 0 else "0%",
            "REASONING": f"{results.get('REASONING', 0)/total*100:.1f}%" if total > 0 else "0%",
        },
        "mismatch_count": len(mismatches),
        "detailed_results": detailed_results,
    }, f, indent=2)

print(f"Detailed results saved to: {results_file}")

# Exit with error code if mismatches found
sys.exit(1 if mismatches else 0)
