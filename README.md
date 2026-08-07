# llm-homebase

A personal LiteLLM proxy gateway with complexity-based auto-routing and QoS budget
management for local use.

Sits between your AI client (OpenCode or any OpenAI-compatible tool) and Vertex AI.
The auto-router classifies each request by complexity and routes it to the cheapest
adequate model. When your weekly budget is exhausted, it falls back to cheaper tiers
rather than returning errors.

## Architecture

```
Your client (OpenCode / any OpenAI-compatible tool)
        │
        ▼ http://localhost:4000
  LiteLLM Proxy  ──►  claude-auto (auto-router)
        │                   │
        │         SIMPLE    ├──► claude-haiku  ──► Vertex AI (claude-haiku-4-5)
        │         MEDIUM    ├──► claude-sonnet ──► Vertex AI (claude-sonnet-4-5)
        │         COMPLEX   ├──► claude-sonnet
        │         REASONING └──► claude-opus   ──► Vertex AI (claude-opus-4-6)
        │
        └── granite-free ──► Models.corp / Red Hat internal (placeholder)
```

**Budget:** $100/week, tracked per virtual key in Postgres. When the weekly cap is
hit, requests fall back through the tier chain rather than being rejected.

## Prerequisites

- [Podman](https://podman.io/) + [podman-compose](https://github.com/containers/podman-compose)
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
VERTEX_LOCATION=global                # Vertex region — "global" works for most models
LITELLM_MASTER_KEY=sk-your-master-key-here  # Replace with output of the command below
```

Generate the master key:

```bash
python3 -c "import secrets; print('sk-' + secrets.token_hex(16))"
```

> **Note:** All Claude models are accessed through Vertex AI — no Anthropic API
> credentials are needed or used.

### 3. Start the stack

```bash
podman-compose up -d
```

Wait for the health check to pass (~30 seconds — Postgres starts first, then LiteLLM):

```bash
podman-compose ps          # Both services should show "healthy"
set -a; source .env; set +a
curl http://localhost:4000/health -H "Authorization: Bearer ${LITELLM_MASTER_KEY}"
```

### 4. Create a QoS virtual key

Set up a virtualenv and install the script dependencies (one-time):

```bash
python3 -m venv .venv && source .venv/bin/activate
pip3 install requests openai
```

Then load your env and run the script:

```bash
set -a; source .env; set +a  # loads KEY=value pairs into env
python3 scripts/create_qos_key.py
```

The script creates a virtual key with a **$100/week** cap and a budget fallback chain
(`claude-auto` → `claude-sonnet` → `claude-haiku` → `granite-free`), then prints the
install command. Run the printed `printf` command to install it for OpenCode:

```bash
printf '%s' 'sk-your-printed-key' > ~/.config/opencode/.litellm-key
```

### 5. Point your client at the proxy

**OpenCode** (primary client): add the `llm-homebase` provider to your
`~/.config/opencode/opencode.jsonc`:

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "enabled_providers": ["llm-homebase"],
  "model": "llm-homebase/claude-auto",
  "small_model": "llm-homebase/claude-haiku",
  "provider": {
    "llm-homebase": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "llm-homebase (local proxy)",
      "options": {
        "baseURL": "http://localhost:4000/v1",
        // Store your virtual key in a file — never hardcode it
        "apiKey": "{file:~/.config/opencode/.litellm-key}"
      },
      "models": {
        // claude-auto: complexity-based auto-router (recommended default)
        //   SIMPLE    → claude-haiku  (greetings, short prompts)
        //   MEDIUM    → claude-sonnet (general coding)
        //   COMPLEX   → claude-sonnet
        //   REASONING → claude-opus   (architecture, hard debugging)
        "claude-auto":   { "name": "Auto (proxy)" },
        "claude-opus":   { "name": "Opus (proxy)" },
        "claude-sonnet": { "name": "Sonnet (proxy)" },
        "claude-haiku":  { "name": "Haiku (proxy)" }
      }
    }
  }
}
```

> **Important:** Restart OpenCode after updating `opencode.jsonc` for changes
> to take effect.

To revert to direct Vertex AI access, restore your backup:

```bash
cp ~/.config/opencode/opencode.jsonc.backup-direct-vertex \
   ~/.config/opencode/opencode.jsonc
```

Any other OpenAI-compatible client: set base URL to `http://localhost:4000/v1`
and use your virtual key as the API key.

## LiteLLM UI

The proxy includes a web UI for managing virtual keys, viewing spend, and monitoring usage.

**URL:** http://localhost:4000/ui

**Login credentials:**
- Username: `admin`
- Password: your `LITELLM_MASTER_KEY` value from `.env`

**What you can do in the UI:**
- **Virtual Keys** — view, create, and revoke keys; see per-key spend
- **Usage** — request counts, token usage, and cost breakdown by model
- **Models** — confirm which models are registered and healthy
- **Spend** — weekly spend tracking across all models

Budget state persists in Postgres and survives proxy restarts.

## Testing the auto-router

Activate the virtualenv (if not already active):

```bash
source .venv/bin/activate
set -a; source .env; set +a
python3 scripts/test_qos.py
```

This sends 10 short requests to `claude-auto` and prints the actual model each
request was routed to. The auto-router classifies each request by complexity —
you'll see haiku for simple prompts, sonnet for general coding, and opus for
architecture or multi-step reasoning. If the weekly budget is exhausted, the model
column will show the fallback tier in use.

## Stopping the stack

```bash
podman-compose down
```

Budget state persists in `data/postgres/` and is restored when you restart.

> **Important:** Always use `podman-compose down && podman-compose up -d` after
> changing `docker-compose.yml` or `config.yaml`. `podman-compose restart` reuses
> the old container spec and won't pick up compose-level changes.

## Budget fallback behavior

When the weekly budget cap is reached, requests automatically fall back through
the model chain rather than being rejected:

```
claude-auto → claude-sonnet → claude-haiku → granite-free
```

**Important:** If all models in the chain are unavailable or the budget for every
tier is exhausted, requests return a `429` error. Check current spend in the UI:
http://localhost:4000/ui → **Spend**.

Note that `granite-free` (the final fallback) requires Models.corp credentials
to be configured. Without them it is effectively a dead end — requests to it will
fail. If you don't have Models.corp access, the practical fallback chain ends at
`claude-haiku`.

## Troubleshooting

### Proxy won't start

```bash
podman-compose ps
```

Both `postgres` and `litellm` should show `healthy`. If not:

```bash
# Check logs
podman-compose logs litellm
podman-compose logs postgres
```

Common causes:
- Missing `.env` variables — check `VERTEX_PROJECT`, `VERTEX_LOCATION`, `LITELLM_MASTER_KEY`
- Invalid `config.yaml` syntax — validate with:
  ```bash
  cd /path/to/llm-homebase && .venv/bin/python3 -c "import yaml; yaml.safe_load(open('config.yaml')); print('OK')"
  ```
- ADC credentials missing — run `gcloud auth application-default login`

### Requests fail with 401 Unauthorized

Verify your ADC credentials are valid:

```bash
gcloud auth application-default print-access-token
```

Verify your `VERTEX_PROJECT` matches your actual GCP project:

```bash
gcloud config get-value project
```

Confirm you're using a virtual key (not the master key) for client requests.

### Budget not enforcing

Budget enforcement is **key-level** — it only works when using a virtual key
created by `scripts/create_qos_key.py`. The master key bypasses budgets.

Confirm your key is loaded correctly:

```bash
cat ~/.config/opencode/.litellm-key | head -c 10  # should start with sk-
```

Check spend in the UI: http://localhost:4000/ui → **Virtual Keys** → `opencode-personal`.

### Models.corp / granite-free requests fail

The `granite-free` model is a placeholder until you configure Models.corp
credentials. If you don't have access, it's optional — comment it out in
`config.yaml` and restart:

```bash
podman-compose down && podman-compose up -d
```

### Check if a newer LiteLLM image is available

```bash
podman pull ghcr.io/berriai/litellm:main-latest
./scripts/check_litellm_version.sh
```

## Tuning budgets

Budgets are managed on the virtual key, not in `config.yaml`. Use the UI at
http://localhost:4000/ui → **Virtual Keys** → edit `opencode-personal`, or
regenerate the key with updated values:

```bash
# Delete the existing key in the UI first, then:
set -a; source .env; set +a
python3 scripts/create_qos_key.py
```

The key script is the source of truth for budget values — edit it before
regenerating if you want different limits.

> **Note:** `budget_duration: 1w` resets on a rolling 7-day clock from the
> moment the budget period started, **not** at the beginning of the calendar week.

## Adding Models.corp (Red Hat internal models)

1. Retrieve your Models.corp API key from the internal portal
2. Add to `.env`:

    ```bash
    MODELS_CORP_API_KEY=your-key
    MODELS_CORP_BASE_URL=https://models.corp.redhat.com/v1
    ```

3. Restart the stack:

    ```bash
    podman-compose down && podman-compose up -d
    ```

The `granite-free` model is already wired in `config.yaml` — it becomes active
as soon as the credentials are present.

## Adding Vertex Gemini models

Uncomment the `gemini-pro` block in `config.yaml`, then restart:

```bash
podman-compose down && podman-compose up -d
```

## Upgrading LiteLLM

The image is pinned to a specific digest in `docker-compose.yml` for stability.
To upgrade:

```bash
# Pull the latest image
podman pull ghcr.io/berriai/litellm:main-latest

# Get the new digest
podman inspect ghcr.io/berriai/litellm:main-latest --format '{{.Digest}}'

# Update the digest in docker-compose.yml, then:
podman-compose down && podman-compose up -d

# Verify everything still works before committing
podman-compose ps
curl http://localhost:4000/health -H "Authorization: Bearer ${LITELLM_MASTER_KEY}"
git add docker-compose.yml && git commit -m "chore: upgrade LiteLLM to <version>"
```
