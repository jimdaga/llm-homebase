#!/usr/bin/env python3
"""
create_qos_key.py — Generate a LiteLLM virtual key with QoS budget limits.

Budget is enforced at the key level (the supported LiteLLM path):
  - $100.00/week overall cap, resets every 7 days
  - Budget fallback chain: claude-auto → claude-sonnet → claude-haiku
    (when the key hits its daily cap, subsequent requests fall back
     to cheaper models rather than being rejected)

Usage:
    export LITELLM_MASTER_KEY=sk-your-master-key
    python3 scripts/create_qos_key.py

Output:
    Prints the generated virtual key to stdout. Save it to
    ~/.config/opencode/.litellm-key or pass directly to test_qos.py.
"""

import os
import sys
import requests
import json

PROXY_URL = os.environ.get("LITELLM_PROXY_URL", "http://localhost:4000")
MASTER_KEY = os.environ.get("LITELLM_MASTER_KEY")

if not MASTER_KEY:
    print("ERROR: LITELLM_MASTER_KEY environment variable is not set.", file=sys.stderr)
    print("  export LITELLM_MASTER_KEY=sk-your-master-key", file=sys.stderr)
    sys.exit(1)

headers = {
    "Authorization": f"Bearer {MASTER_KEY}",
    "Content-Type": "application/json",
}

payload = {
    # Human-readable label for this key in the LiteLLM UI/logs
    "key_alias": "opencode-personal",

    # Models this key is allowed to call
    "models": ["claude-auto", "claude-opus", "claude-sonnet", "claude-haiku", "granite-free"],

    # Weekly cap — $100/week, resets every 7 days
    "max_budget": 100.00,
    "budget_duration": "1w",

    # Budget fallback chain (key-level, the supported LiteLLM path):
    # When this key hits its weekly cap, route to cheaper models
    # rather than returning errors.
    "budget_fallbacks": {
        "claude-auto":   ["claude-sonnet", "claude-haiku"],
        "claude-opus":   ["claude-sonnet", "claude-haiku"],
        "claude-sonnet": ["claude-haiku"],
        "claude-haiku":  ["granite-free"],
    },

    # Key never expires — this is a personal local key
    "duration": None,
}

print(f"Creating QoS virtual key on {PROXY_URL} ...", file=sys.stderr)

try:
    response = requests.post(
        f"{PROXY_URL}/key/generate",
        headers=headers,
        json=payload,
        timeout=10,
    )
    response.raise_for_status()
except requests.exceptions.ConnectionError:
    print(f"ERROR: Could not connect to LiteLLM proxy at {PROXY_URL}", file=sys.stderr)
    print("  Make sure the stack is running: docker compose up -d", file=sys.stderr)
    sys.exit(1)
except requests.exceptions.Timeout:
    print("ERROR: Request timed out after 10s — is the proxy healthy?", file=sys.stderr)
    sys.exit(1)
except requests.exceptions.HTTPError as e:
    print(f"ERROR: HTTP {e.response.status_code} — {e.response.text}", file=sys.stderr)
    sys.exit(1)

try:
    data = response.json()
except ValueError:
    print("ERROR: Proxy returned a non-JSON response.", file=sys.stderr)
    print(f"  Status: {response.status_code}", file=sys.stderr)
    print(f"  Body:   {response.text[:200]}", file=sys.stderr)
    sys.exit(1)

key = data.get("key")

if not key:
    print("ERROR: Unexpected response — no 'key' field returned.", file=sys.stderr)
    print(json.dumps(data, indent=2), file=sys.stderr)
    sys.exit(1)

print(file=sys.stderr)
print("Virtual key created successfully.", file=sys.stderr)
print(file=sys.stderr)
print(f"  Key:   {key}", file=sys.stderr)
print(f"  Alias: {data.get('key_alias', 'local-qos-key')}", file=sys.stderr)
print(file=sys.stderr)
print("Install for OpenCode:", file=sys.stderr)
print(f"  echo -n '{key}' > ~/.config/opencode/.litellm-key", file=sys.stderr)
print(file=sys.stderr)
print("Or test directly:", file=sys.stderr)
print(f"  LITELLM_VIRTUAL_KEY={key} python3 scripts/test_qos.py", file=sys.stderr)
print(key)
