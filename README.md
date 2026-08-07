# llm-homebase

A personal LiteLLM proxy gateway with QoS budget-aware model downgrading for local use.

Sits between your AI client (e.g. OpenCode) and Vertex AI. When you burn through a
premium model's daily budget cap, it silently routes subsequent requests to a cheaper
model — no errors, no client changes needed.

## Architecture

    Your client (OpenCode / any OpenAI-compatible tool)
            │
            ▼ http://localhost:4000
      LiteLLM Proxy (Docker)
            │
            ├─ claude-sonnet ──► Vertex AI (claude-sonnet-4-5)  $17/day cap
            ├─ claude-haiku  ──► Vertex AI (claude-haiku-4-5)   $5/day cap
            └─ granite-free  ──► Models.corp (placeholder)

Budget math: $500/month ÷ 22 workdays = ~$22.73/day. Caps are set at 75% of
allocation so you get a safety margin before hard limits.

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (or Podman + podman-compose)
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

Copy the printed key and export it:

```bash
export LITELLM_VIRTUAL_KEY=sk-...
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

Save your virtual key to the file OpenCode reads:

```bash
printf '%s' 'sk-your-virtual-key' > ~/.config/opencode/.litellm-key
```

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
- **Spend** — daily/monthly spend tracking across all models

The UI reads spend data from Postgres, so budget usage persists across proxy restarts.

## Testing the QoS downgrade

Activate the virtualenv created in step 4 (if not already active):

```bash
source .venv/bin/activate
python3 scripts/test_qos.py
```

This sends 10 short requests to `claude-sonnet` and prints the actual model
returned for each. When the daily budget is exhausted, you will see the model
field switch from `claude-sonnet-4-5` to `claude-haiku-4-5` — that is the
QoS downgrade in action.

## Stopping the stack

```bash
podman-compose down
```

Budget state persists in `data/postgres/` and is restored when you restart.

> **Note:** Use `podman-compose down && podman-compose up -d` (not `restart`) after
> changing `docker-compose.yml` or `config.yaml`. `restart` reuses the old container
> spec and won't pick up compose-level changes.

## Adding Models.corp (Red Hat internal models)

1. Retrieve your Models.corp API key from the internal portal
2. Add to `.env`:

    ```bash
    MODELS_CORP_API_KEY=your-key
    MODELS_CORP_BASE_URL=https://models.corp.redhat.com/v1
    ```

3. Restart the stack: `podman-compose restart litellm`

The `granite-free` model is already wired in `config.yaml` — it becomes active
as soon as the credentials are present.

## Adding Vertex Gemini models

Uncomment the `gemini-pro` block in `config.yaml` and restart:

```bash
podman-compose restart litellm
```

## Tuning budgets

Edit `config.yaml` and adjust `max_budget` values under each model's `model_info`
block. Restart the proxy to apply changes:

```bash
podman-compose restart litellm
```

> **Important:** `budget_duration` resets on a rolling 24-hour clock from the
> moment the counter starts, **not** at midnight.
