# llm-homebase Scaffold Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Scaffold a complete, working local LiteLLM proxy gateway with Vertex AI backends, SQLite budget tracking, QoS model downgrading, and standard GitHub repo files.

**Architecture:** Single Docker Compose service running LiteLLM Proxy backed by SQLite for persistent spend tracking. Vertex AI is the sole backend for all models (Claude + Gemini), authenticated via Google Application Default Credentials bind-mounted into the container. Budget fallbacks are configured natively in LiteLLM so that hitting 75% of a tier's daily cap silently routes to the next cheaper tier.

**Tech Stack:** LiteLLM Proxy (`ghcr.io/berriai/litellm:main-latest`), Docker Compose, SQLite, Python 3 (`requests`, `openai` packages), Google ADC, YAML.

## Global Constraints

- Repo root: `/Users/jdagosti/git/jimdaga/llm-homebase/`
- All Claude models route through Vertex AI — no direct Anthropic API key
- SQLite database path inside container: `/app/data/litellm.db`
- ADC file host path: `~/.config/gcloud/application_default_credentials.json`
- ADC file container path: `/gcp/adc.json` (read-only bind mount)
- LiteLLM proxy port: `4000`
- GitHub owner: `jimdaga`
- Budget math: $500/month ÷ 22 workdays = ~$22.73/day; Sonnet cap = $17.00/day, Haiku cap = $5.00/day
- `budget_duration: 1d` (LiteLLM resets daily on a 24h rolling clock)
- `.env` and `data/` are gitignored; `.env.example` is committed
- No Postgres, no deploy pipeline, no direct Anthropic credentials
- Models.corp and Vertex Gemini are placeholder commented blocks only

---

### Task 1: Repo skeleton and gitignore

**Files:**
- Create: `.gitignore`
- Create: `data/.gitkeep`

**Interfaces:**
- Produces: ignored paths that all subsequent tasks rely on (`data/`, `.env`)

- [ ] **Step 1: Create `.gitignore`**

```
# Secrets
.env

# SQLite database
data/*.db

# Python
__pycache__/
*.pyc
*.pyo
.venv/
venv/

# macOS
.DS_Store

# Editor
.idea/
.vscode/
*.swp
```

Write this to `/Users/jdagosti/git/jimdaga/llm-homebase/.gitignore`.

- [ ] **Step 2: Create `data/.gitkeep` so the directory is tracked**

Create an empty file at `/Users/jdagosti/git/jimdaga/llm-homebase/data/.gitkeep`.

- [ ] **Step 3: Verify `.gitignore` works**

```bash
cd /Users/jdagosti/git/jimdaga/llm-homebase
touch .env data/litellm.db
git status
```

Expected: `.env` and `data/litellm.db` do NOT appear in untracked files. `data/.gitkeep` DOES appear.

- [ ] **Step 4: Remove test files**

```bash
rm /Users/jdagosti/git/jimdaga/llm-homebase/.env
rm /Users/jdagosti/git/jimdaga/llm-homebase/data/litellm.db
```

- [ ] **Step 5: Commit**

```bash
cd /Users/jdagosti/git/jimdaga/llm-homebase
git add .gitignore data/.gitkeep
git commit -m "chore: add gitignore and data directory"
```

---

### Task 2: Environment template

**Files:**
- Create: `.env.example`

**Interfaces:**
- Produces: credential variable names consumed by `docker-compose.yml` (Task 3) and scripts (Tasks 5–6)

- [ ] **Step 1: Create `.env.example`**

```bash
# .env.example — copy to .env and fill in your values
# Never commit .env to git

# GCP project that has Vertex AI API enabled
VERTEX_PROJECT=your-gcp-project-id

# Vertex AI region — us-central1 is the most capable
VERTEX_LOCATION=us-central1

# Master key for the LiteLLM proxy admin API
# Generate one: python3 -c "import secrets; print('sk-' + secrets.token_hex(16))"
LITELLM_MASTER_KEY=sk-your-master-key-here

# Red Hat internal models — leave commented until you retrieve your key
# MODELS_CORP_API_KEY=
# MODELS_CORP_BASE_URL=
```

Write this to `/Users/jdagosti/git/jimdaga/llm-homebase/.env.example`.

- [ ] **Step 2: Verify it is not gitignored**

```bash
cd /Users/jdagosti/git/jimdaga/llm-homebase
git status .env.example
```

Expected: `.env.example` shows as untracked (not ignored).

- [ ] **Step 3: Commit**

```bash
cd /Users/jdagosti/git/jimdaga/llm-homebase
git add .env.example
git commit -m "chore: add env template"
```

---

### Task 3: LiteLLM `config.yaml`

**Files:**
- Create: `config.yaml`

**Interfaces:**
- Consumes: `VERTEX_PROJECT`, `VERTEX_LOCATION`, `LITELLM_MASTER_KEY` env vars (defined in Task 2)
- Produces: model aliases `claude-sonnet`, `claude-haiku`, `granite-free` consumed by scripts (Tasks 5–6)

- [ ] **Step 1: Create `config.yaml`**

```yaml
# config.yaml — LiteLLM Proxy configuration
# Docs: https://docs.litellm.ai/docs/proxy/configs

model_list:
  # ──────────────────────────────────────────────
  # TIER 1 — Premium: Claude Sonnet via Vertex AI
  # Daily budget cap: $17.00 (75% of ~$22.73/day workday allocation)
  # ──────────────────────────────────────────────
  - model_name: claude-sonnet
    litellm_params:
      model: vertex_ai/claude-sonnet-4-5
      vertex_project: os.environ/VERTEX_PROJECT
      vertex_location: os.environ/VERTEX_LOCATION
    model_info:
      max_budget: 17.00
      budget_duration: 1d

  # ──────────────────────────────────────────────
  # TIER 2 — Standard: Claude Haiku via Vertex AI
  # Daily budget cap: $5.00 (75% of remaining workday allocation)
  # Fallback destination when Sonnet budget is exhausted
  # ──────────────────────────────────────────────
  - model_name: claude-haiku
    litellm_params:
      model: vertex_ai/claude-haiku-4-5
      vertex_project: os.environ/VERTEX_PROJECT
      vertex_location: os.environ/VERTEX_LOCATION
    model_info:
      max_budget: 5.00
      budget_duration: 1d

  # ──────────────────────────────────────────────
  # TIER 3 — Free: IBM Granite via Models.corp (Red Hat internal)
  # PLACEHOLDER — non-functional until MODELS_CORP_API_KEY and
  # MODELS_CORP_BASE_URL are configured in .env
  # ──────────────────────────────────────────────
  - model_name: granite-free
    litellm_params:
      model: openai/ibm-granite/granite-3.3-8b-instruct
      api_key: os.environ/MODELS_CORP_API_KEY
      api_base: os.environ/MODELS_CORP_BASE_URL

  # ──────────────────────────────────────────────
  # PLACEHOLDER — Gemini via Vertex AI
  # Uncomment and set model variant when ready
  # ──────────────────────────────────────────────
  # - model_name: gemini-pro
  #   litellm_params:
  #     model: vertex_ai/gemini-2.0-flash-001
  #     vertex_project: os.environ/VERTEX_PROJECT
  #     vertex_location: os.environ/VERTEX_LOCATION

router_settings:
  # QoS budget fallback chain:
  # When claude-sonnet hits its max_budget, route to claude-haiku.
  # When claude-haiku hits its max_budget, route to granite-free.
  # Requests complete transparently — no 429 errors returned to client.
  budget_fallbacks:
    - claude-sonnet:
        fallback: claude-haiku
    - claude-haiku:
        fallback: granite-free

  # Retry on provider errors (not budget fallbacks — those are separate)
  num_retries: 2
  retry_after: 5

general_settings:
  # SQLite for persistent spend and key tracking
  # Path must match the volume mount in docker-compose.yml
  database_url: "sqlite:////app/data/litellm.db"

  # Master key secures the /key/generate and /spend admin endpoints
  master_key: os.environ/LITELLM_MASTER_KEY

  # Store spend data so budget tracking survives restarts
  store_model_in_db: true
```

Write this to `/Users/jdagosti/git/jimdaga/llm-homebase/config.yaml`.

- [ ] **Step 2: Validate YAML syntax**

```bash
python3 -c "import yaml, sys; yaml.safe_load(open('/Users/jdagosti/git/jimdaga/llm-homebase/config.yaml')); print('YAML valid')"
```

Expected: prints `YAML valid` with no errors.

- [ ] **Step 3: Commit**

```bash
cd /Users/jdagosti/git/jimdaga/llm-homebase
git add config.yaml
git commit -m "feat: add LiteLLM config with Vertex AI backends and QoS budget fallbacks"
```

---

### Task 4: `docker-compose.yml`

**Files:**
- Create: `docker-compose.yml`

**Interfaces:**
- Consumes: `config.yaml` (Task 3), `data/` directory (Task 1), env vars from `.env` (Task 2)
- Produces: running proxy at `http://localhost:4000` consumed by scripts (Tasks 5–6)

- [ ] **Step 1: Create `docker-compose.yml`**

```yaml
# docker-compose.yml — Local LiteLLM proxy stack
# Usage: docker compose up -d

services:
  litellm:
    image: ghcr.io/berriai/litellm:main-latest
    ports:
      - "4000:4000"
    volumes:
      # LiteLLM proxy config
      - ./config.yaml:/app/config.yaml:ro
      # SQLite database persistence — survives container restarts
      - ./data:/app/data
      # Google Application Default Credentials (read-only)
      # Run once on host: gcloud auth application-default login
      - ${HOME}/.config/gcloud/application_default_credentials.json:/gcp/adc.json:ro
    environment:
      # Vertex AI auth via ADC
      GOOGLE_APPLICATION_CREDENTIALS: /gcp/adc.json
      # Forwarded from .env
      VERTEX_PROJECT: ${VERTEX_PROJECT}
      VERTEX_LOCATION: ${VERTEX_LOCATION}
      LITELLM_MASTER_KEY: ${LITELLM_MASTER_KEY}
      # Models.corp — leave unset until credentials available
      MODELS_CORP_API_KEY: ${MODELS_CORP_API_KEY:-placeholder}
      MODELS_CORP_BASE_URL: ${MODELS_CORP_BASE_URL:-http://localhost}
    command: ["--config", "/app/config.yaml", "--port", "4000", "--detailed_debug"]
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:4000/health"]
      interval: 15s
      timeout: 5s
      retries: 5
      start_period: 20s
    restart: unless-stopped
```

Write this to `/Users/jdagosti/git/jimdaga/llm-homebase/docker-compose.yml`.

- [ ] **Step 2: Validate compose syntax (does not require `.env` to exist)**

```bash
cd /Users/jdagosti/git/jimdaga/llm-homebase
docker compose config --quiet 2>&1 | head -5
```

Expected: exits 0. If it exits non-zero due to missing `.env`, that is acceptable at this stage — the syntax check still validates structure. Missing variable warnings are not errors.

- [ ] **Step 3: Commit**

```bash
cd /Users/jdagosti/git/jimdaga/llm-homebase
git add docker-compose.yml
git commit -m "feat: add docker-compose with LiteLLM, ADC mount, and SQLite volume"
```

---

### Task 5: `scripts/create_qos_key.py`

**Files:**
- Create: `scripts/create_qos_key.py`

**Interfaces:**
- Consumes: running proxy at `http://localhost:4000` (Task 4), `LITELLM_MASTER_KEY` env var (Task 2)
- Produces: a virtual key printed to stdout, used as input to Task 6

- [ ] **Step 1: Create `scripts/` directory**

```bash
mkdir -p /Users/jdagosti/git/jimdaga/llm-homebase/scripts
```

- [ ] **Step 2: Create `scripts/create_qos_key.py`**

```python
#!/usr/bin/env python3
"""
create_qos_key.py — Generate a LiteLLM virtual key with QoS budget limits.

The key is configured with:
  - A daily budget on claude-sonnet ($17.00 — 75% of workday allocation)
  - Automatic fallback to claude-haiku when budget is exhausted
  - A smaller daily budget on claude-haiku ($5.00)

Usage:
    export LITELLM_MASTER_KEY=sk-your-master-key
    python3 scripts/create_qos_key.py

Output:
    Prints the generated virtual key to stdout. Save it to .env or
    pass it directly to test_qos.py.
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
    "key_alias": "local-qos-key",

    # Models this key is allowed to call
    "models": ["claude-sonnet", "claude-haiku", "granite-free"],

    # Per-model daily budget caps (75% of workday allocation)
    # When claude-sonnet hits $17, the router falls back to claude-haiku.
    # When claude-haiku hits $5, the router falls back to granite-free.
    "model_max_budget": {
        "claude-sonnet": {
            "max_budget": 17.00,
            "budget_duration": "1d",
        },
        "claude-haiku": {
            "max_budget": 5.00,
            "budget_duration": "1d",
        },
    },

    # Overall daily cap as a safety net
    "max_budget": 22.00,
    "budget_duration": "1d",

    # Key never expires — this is a personal local key
    "duration": None,
}

print(f"Creating QoS virtual key on {PROXY_URL} ...")

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
except requests.exceptions.HTTPError as e:
    print(f"ERROR: HTTP {e.response.status_code} — {e.response.text}", file=sys.stderr)
    sys.exit(1)

data = response.json()
key = data.get("key")

if not key:
    print("ERROR: Unexpected response — no 'key' field returned.", file=sys.stderr)
    print(json.dumps(data, indent=2), file=sys.stderr)
    sys.exit(1)

print()
print("Virtual key created successfully.")
print()
print(f"  Key:   {key}")
print(f"  Alias: {data.get('key_alias', 'local-qos-key')}")
print()
print("Add to your environment:")
print(f"  export LITELLM_VIRTUAL_KEY={key}")
print()
print("Or pass directly to test_qos.py:")
print(f"  LITELLM_VIRTUAL_KEY={key} python3 scripts/test_qos.py")
```

Write this to `/Users/jdagosti/git/jimdaga/llm-homebase/scripts/create_qos_key.py`.

- [ ] **Step 3: Make it executable**

```bash
chmod +x /Users/jdagosti/git/jimdaga/llm-homebase/scripts/create_qos_key.py
```

- [ ] **Step 4: Validate Python syntax**

```bash
python3 -m py_compile /Users/jdagosti/git/jimdaga/llm-homebase/scripts/create_qos_key.py && echo "Syntax OK"
```

Expected: prints `Syntax OK`.

- [ ] **Step 5: Commit**

```bash
cd /Users/jdagosti/git/jimdaga/llm-homebase
git add scripts/create_qos_key.py
git commit -m "feat: add create_qos_key.py script for virtual key generation"
```

---

### Task 6: `scripts/test_qos.py`

**Files:**
- Create: `scripts/test_qos.py`

**Interfaces:**
- Consumes: running proxy at `http://localhost:4000` (Task 4), virtual key from `create_qos_key.py` (Task 5), model alias `claude-sonnet` (Task 3)
- Produces: console output showing `response.model` per call, demonstrating the downgrade moment

- [ ] **Step 1: Create `scripts/test_qos.py`**

```python
#!/usr/bin/env python3
"""
test_qos.py — Demonstrate QoS budget-aware model downgrading.

Sends a loop of chat requests to claude-sonnet via the local LiteLLM proxy
and prints the actual model returned in each response. When the daily budget
cap is hit, LiteLLM silently routes to claude-haiku — this script makes
that transition visible.

Usage:
    # First, generate a key (optional — master key works too):
    export LITELLM_VIRTUAL_KEY=$(python3 scripts/create_qos_key.py | grep "Key:" | awk '{print $2}')

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
ITERATIONS = int(os.environ.get("TEST_ITERATIONS", "10"))

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
```

Write this to `/Users/jdagosti/git/jimdaga/llm-homebase/scripts/test_qos.py`.

- [ ] **Step 2: Make it executable**

```bash
chmod +x /Users/jdagosti/git/jimdaga/llm-homebase/scripts/test_qos.py
```

- [ ] **Step 3: Validate Python syntax**

```bash
python3 -m py_compile /Users/jdagosti/git/jimdaga/llm-homebase/scripts/test_qos.py && echo "Syntax OK"
```

Expected: prints `Syntax OK`.

- [ ] **Step 4: Commit**

```bash
cd /Users/jdagosti/git/jimdaga/llm-homebase
git add scripts/test_qos.py
git commit -m "feat: add test_qos.py to demonstrate QoS model downgrade"
```

---

### Task 7: GitHub repo files

**Files:**
- Create: `.github/CODEOWNERS`
- Create: `.github/PULL_REQUEST_TEMPLATE.md`
- Create: `.github/workflows/lint.yml`

**Interfaces:**
- Produces: standard GitHub automation; no code dependencies

- [ ] **Step 1: Create `.github/CODEOWNERS`**

```
# All files require review from the repo owner
* @jimdaga
```

Write to `/Users/jdagosti/git/jimdaga/llm-homebase/.github/CODEOWNERS`.

- [ ] **Step 2: Create `.github/PULL_REQUEST_TEMPLATE.md`**

```markdown
## Summary

<!-- What does this PR do? One paragraph. -->

## Changes

- 

## Testing

- [ ] Ran `docker compose up -d` and proxy started healthy
- [ ] Validated `config.yaml` YAML syntax
- [ ] Ran `docker compose config` without errors

## Checklist

- [ ] `.env` is not committed
- [ ] `data/` SQLite files are not committed
- [ ] `.env.example` updated if new env vars were added
- [ ] README updated if setup steps changed
```

Write to `/Users/jdagosti/git/jimdaga/llm-homebase/.github/PULL_REQUEST_TEMPLATE.md`.

- [ ] **Step 3: Create `.github/workflows/lint.yml`**

```yaml
# lint.yml — Validate config files on pull requests
name: Lint

on:
  pull_request:
    paths:
      - "config.yaml"
      - "docker-compose.yml"
      - ".github/workflows/**"

jobs:
  lint:
    name: Validate configs
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Validate config.yaml syntax
        run: python3 -c "import yaml, sys; yaml.safe_load(open('config.yaml')); print('config.yaml: valid')"

      - name: Validate docker-compose.yml syntax
        run: |
          # docker compose config validates structure without requiring .env values
          # We supply dummy values for required vars to allow syntax validation
          VERTEX_PROJECT=test \
          VERTEX_LOCATION=us-central1 \
          LITELLM_MASTER_KEY=sk-test \
          docker compose config --quiet
          echo "docker-compose.yml: valid"
```

Write to `/Users/jdagosti/git/jimdaga/llm-homebase/.github/workflows/lint.yml`.

- [ ] **Step 4: Validate lint workflow YAML syntax**

```bash
python3 -c "import yaml; yaml.safe_load(open('/Users/jdagosti/git/jimdaga/llm-homebase/.github/workflows/lint.yml')); print('lint.yml: valid')"
```

Expected: prints `lint.yml: valid`.

- [ ] **Step 5: Commit**

```bash
cd /Users/jdagosti/git/jimdaga/llm-homebase
git add .github/
git commit -m "chore: add CODEOWNERS, PR template, and lint workflow"
```

---

### Task 8: `README.md`

**Files:**
- Create: `README.md`

**Interfaces:**
- Consumes: all prior tasks (documents the full setup)
- Produces: user-facing documentation

- [ ] **Step 1: Create `README.md`**

```markdown
# llm-homebase

A personal LiteLLM proxy gateway with QoS budget-aware model downgrading for local use.

Sits between your AI client (e.g. OpenCode) and Vertex AI. When you burn through a
premium model's daily budget cap, it silently routes subsequent requests to a cheaper
model — no errors, no client changes needed.

## Architecture

```
Your client (OpenCode / any OpenAI-compatible tool)
        │
        ▼ http://localhost:4000
  LiteLLM Proxy (Docker)
        │
        ├─ claude-sonnet ──► Vertex AI (claude-sonnet-4-5)  $17/day cap
        ├─ claude-haiku  ──► Vertex AI (claude-haiku-4-5)   $5/day cap
        └─ granite-free  ──► Models.corp (placeholder)
```

Budget math: $500/month ÷ 22 workdays = ~$22.73/day. Caps are set at 75% of
allocation so you get a safety margin before hard limits.

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (or Docker Engine + Compose plugin)
- [gcloud CLI](https://cloud.google.com/sdk/docs/install) authenticated with ADC
- A GCP project with Vertex AI API enabled
- Python 3.9+ (for the helper scripts)

## Setup

### 1. Authenticate with Google Cloud

```bash
gcloud auth application-default login
```

This creates `~/.config/gcloud/application_default_credentials.json`, which is
bind-mounted read-only into the LiteLLM container.

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and fill in:

```bash
VERTEX_PROJECT=your-gcp-project-id   # GCP project with Vertex AI enabled
VERTEX_LOCATION=us-central1           # Vertex region
LITELLM_MASTER_KEY=sk-...             # Generate: python3 -c "import secrets; print('sk-' + secrets.token_hex(16))"
```

### 3. Start the stack

```bash
docker compose up -d
```

Wait for the health check to pass (~20 seconds):

```bash
docker compose ps          # Status should show "healthy"
curl http://localhost:4000/health
```

### 4. Create a QoS virtual key

```bash
pip3 install requests      # one-time
source .env
python3 scripts/create_qos_key.py
```

Copy the printed key and export it:

```bash
export LITELLM_VIRTUAL_KEY=sk-...
```

### 5. Point your client at the proxy

In OpenCode (or any OpenAI-compatible client), set:

```
Base URL: http://localhost:4000/v1
API Key:  <your LITELLM_VIRTUAL_KEY>
Model:    claude-sonnet
```

## Testing the QoS downgrade

```bash
pip3 install openai        # one-time
python3 scripts/test_qos.py
```

This sends 10 short requests to `claude-sonnet` and prints the actual model
returned for each. When the daily budget is exhausted, you will see the model
field switch from `claude-sonnet-4-5` to `claude-haiku-4-5` — that is the
QoS downgrade in action.

## Stopping the stack

```bash
docker compose down
```

Budget state persists in `data/litellm.db` and is restored when you restart.

## Adding Models.corp (Red Hat internal models)

1. Retrieve your Models.corp API key from the internal portal
2. Add to `.env`:
   ```bash
   MODELS_CORP_API_KEY=your-key
   MODELS_CORP_BASE_URL=https://models.corp.redhat.com/v1
   ```
3. Restart the stack: `docker compose restart litellm`

The `granite-free` model is already wired in `config.yaml` — it becomes active
as soon as the credentials are present.

## Adding Vertex Gemini models

Uncomment the `gemini-pro` block in `config.yaml` and restart:

```bash
docker compose restart litellm
```

## Tuning budgets

Edit `config.yaml` and adjust `max_budget` values under each model's `model_info`
block. Restart the proxy to apply changes. Budget counters reset every 24 hours
on a rolling clock (not at midnight).
```

Write this to `/Users/jdagosti/git/jimdaga/llm-homebase/README.md`.

- [ ] **Step 2: Commit**

```bash
cd /Users/jdagosti/git/jimdaga/llm-homebase
git add README.md
git commit -m "docs: add README with setup, usage, and tuning guide"
```

---

### Task 9: End-to-end smoke test

This task verifies the stack actually starts before pushing. No code is written.

**Files:** none

**Interfaces:**
- Consumes: all prior tasks

- [ ] **Step 1: Copy `.env.example` to `.env` and fill in real values**

```bash
cp /Users/jdagosti/git/jimdaga/llm-homebase/.env.example \
   /Users/jdagosti/git/jimdaga/llm-homebase/.env
```

Edit `.env` with your actual `VERTEX_PROJECT`, `VERTEX_LOCATION`, and `LITELLM_MASTER_KEY`.

- [ ] **Step 2: Verify ADC credentials exist**

```bash
ls ~/.config/gcloud/application_default_credentials.json
```

If missing, run: `gcloud auth application-default login`

- [ ] **Step 3: Start the stack**

```bash
cd /Users/jdagosti/git/jimdaga/llm-homebase
docker compose up -d
```

- [ ] **Step 4: Wait for healthy status**

```bash
docker compose ps
```

Expected: `litellm` service shows `healthy` after ~20–30 seconds.

- [ ] **Step 5: Hit the health endpoint**

```bash
curl -s http://localhost:4000/health | python3 -m json.tool
```

Expected: JSON response with status fields, no connection errors.

- [ ] **Step 6: Verify models list**

```bash
source /Users/jdagosti/git/jimdaga/llm-homebase/.env
curl -s http://localhost:4000/v1/models \
  -H "Authorization: Bearer ${LITELLM_MASTER_KEY}" | python3 -m json.tool
```

Expected: JSON list containing `claude-sonnet`, `claude-haiku`, `granite-free`.

- [ ] **Step 7: Stop the stack**

```bash
cd /Users/jdagosti/git/jimdaga/llm-homebase
docker compose down
```

- [ ] **Step 8: Push to GitHub**

```bash
cd /Users/jdagosti/git/jimdaga/llm-homebase
git log --oneline
git push origin main
```

Expected: all commits from Tasks 1–8 push cleanly.
