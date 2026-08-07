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

**OpenCode** (primary client): add to your OpenCode settings:

```
Base URL: http://localhost:4000/v1
API Key:  <your LITELLM_VIRTUAL_KEY>
Model:    claude-sonnet
```

Any other OpenAI-compatible client uses the same settings.

## LiteLLM UI

The proxy includes a web UI for managing keys, viewing spend, and monitoring usage:

- **URL:** http://localhost:4000/ui
- **Username:** `admin`
- **Password:** your `LITELLM_MASTER_KEY` value

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
