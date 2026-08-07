#!/usr/bin/env python3
"""
test_qos.py — Demonstrate QoS budget-aware model downgrading.

Sends a loop of chat requests to claude-sonnet via the local LiteLLM proxy
and prints the actual model returned in each response. When the daily budget
cap is hit, LiteLLM silently routes to claude-haiku — this script makes
that transition visible.

Usage:
    # First, generate a key (optional — master key works too):
    export LITELLM_VIRTUAL_KEY=$(python3 scripts/create_qos_key.py)

    # Or use master key directly:
    export LITELLM_MASTER_KEY=sk-your-master-key

    python3 scripts/test_qos.py

Environment variables:
    LITELLM_VIRTUAL_KEY   — preferred: use a virtual key with budget limits
    LITELLM_MASTER_KEY    — fallback: use master key (bypasses per-key budgets)
    LITELLM_PROXY_URL     — default: http://localhost:4000
    TEST_ITERATIONS       — number of requests to send (default: 10)
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
try:
    ITERATIONS = int(os.environ.get("TEST_ITERATIONS", "10"))
except ValueError:
    print("ERROR: TEST_ITERATIONS must be a positive integer.", file=sys.stderr)
    sys.exit(1)

if not API_KEY:
    print("ERROR: No API key found.", file=sys.stderr)
    print("  Set LITELLM_VIRTUAL_KEY or LITELLM_MASTER_KEY", file=sys.stderr)
    sys.exit(1)

client = OpenAI(
    api_key=API_KEY,
    base_url=f"{PROXY_URL}/v1",
)

print(f"LiteLLM QoS Downgrade Test")
print(f"Proxy:      {PROXY_URL}")
print(f"Requesting: claude-sonnet ({ITERATIONS} iterations)")
print(f"Watch for the model name to change — that is the downgrade moment.")
print()
print(f"{'#':<5} {'Requested':<20} {'Actual model returned':<40} {'Tokens used'}")
print("-" * 80)

previous_model = None

for i in range(1, ITERATIONS + 1):
    try:
        response = client.chat.completions.create(
            model="claude-sonnet",
            messages=[
                {
                    "role": "user",
                    "content": (
                        "In exactly one sentence, what is the capital of France? "
                        "Reply with only the sentence, nothing else."
                    ),
                }
            ],
            max_tokens=30,
        )

        actual_model = response.model
        total_tokens = response.usage.total_tokens if response.usage else "?"

        # Highlight the moment the model changes
        marker = ""
        if previous_model and actual_model != previous_model:
            marker = "  <-- DOWNGRADE"

        print(f"{i:<5} {'claude-sonnet':<20} {actual_model:<40} {total_tokens}{marker}")
        previous_model = actual_model

    except Exception as e:
        print(f"{i:<5} {'claude-sonnet':<20} ERROR: {e}")

print()
print("Test complete.")
if previous_model:
    print(f"Final model in use: {previous_model}")
