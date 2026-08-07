# llm-homebase Design Spec

**Date:** 2026-08-07
**Repo:** `jimdaga/llm-homebase`
**Status:** Approved

## Purpose

A personal LiteLLM proxy gateway with QoS budget-aware model downgrading for local use. Runs entirely on a single machine via Docker Compose. Designed to be shareable/open-sourceable later.

## Problem Statement

You have a $500/month Vertex AI budget. Without guardrails, a single expensive model session can exhaust that budget unnoticed. The goal is transparent, automatic downgrading — when you're burning through a premium model's daily cap, subsequent requests silently route to a cheaper model without errors or client-side changes.

---

## Architecture

### Stack

- **LiteLLM Proxy** — OpenAI-compatible API gateway with budget tracking, virtual keys, and router fallbacks
- **SQLite** — Lightweight file-based database for spend tracking, virtual keys, and usage history. Persists across container restarts via a volume mount. No Postgres needed for single-user local use.
- **Docker Compose** — Single container setup

### Auth

Vertex AI authentication uses **Google Application Default Credentials (ADC)**. No API keys or service account JSON required. Run once:

```bash
gcloud auth application-default login
```

The ADC credentials file (`~/.config/gcloud/application_default_credentials.json`) is bind-mounted read-only into the LiteLLM container.

### Credentials

| Variable | Purpose |
|----------|---------|
| `VERTEX_PROJECT` | GCP project ID for Vertex AI |
| `VERTEX_LOCATION` | Vertex region (e.g. `us-central1`) |
| `LITELLM_MASTER_KEY` | Admin key to secure the proxy (you set this) |
| `MODELS_CORP_API_KEY` | Red Hat internal models — placeholder, add later |
| `MODELS_CORP_BASE_URL` | Models.corp endpoint — placeholder, add later |

---

## Model Tiers & Fallback Chain

All cloud-hosted models route through **Vertex AI**. Models.corp (Red Hat internal) is a placeholder for later.

| Tier | LiteLLM alias | Vertex model ID | Daily budget cap | Fallback at 75% |
|------|--------------|-----------------|-----------------|-----------------|
| Premium | `claude-sonnet` | `claude-sonnet-4-5` | $10.00/day | → `claude-haiku` |
| Standard | `claude-haiku` | `claude-haiku-4-5` | $5.00/day | → `granite-free` |
| Free | `granite-free` | Models.corp `ibm-granite/granite-3.3-8b-instruct` | N/A | — (placeholder — requires Models.corp key + VPN, non-functional until configured) |

**Budget math:** $500/month ÷ 30 days = ~$16.67/day total. $10 + $5 = $15/day allocated, leaving ~$1.67/day headroom.

**Fallback trigger:** LiteLLM `budget_fallbacks` in `router_settings`. The 75% threshold is implemented by setting each tier's `max_budget` to 75% of the real daily dollar cap (e.g., `max_budget: 7.50` for a $10/day tier). When spend hits that limit, LiteLLM routes subsequent requests to the next tier transparently — no 429 errors, no client changes. There is no percentage threshold config key; the cap itself is the trigger.

Vertex/Gemini models get a commented-out placeholder block in `config.yaml`, ready to enable.

---

## Directory Layout

```
~/git/jimdaga/llm-homebase/
├── config.yaml                          # LiteLLM model + router + budget config
├── docker-compose.yml                   # Single LiteLLM container
├── .env.example                         # Credential template (committed)
├── .env                                 # Actual secrets (gitignored)
├── .gitignore
├── data/                                # SQLite DB (gitignored)
│   └── litellm.db
├── scripts/
│   ├── create_qos_key.py               # Generate a virtual key with budget limits
│   └── test_qos.py                     # Demonstrate downgrade in action
├── docs/
│   └── superpowers/specs/              # This file
├── .github/
│   ├── CODEOWNERS
│   ├── PULL_REQUEST_TEMPLATE.md
│   └── workflows/
│       └── lint.yml                    # YAML lint + docker compose config check
└── README.md
```

---

## Files Produced

### `config.yaml`
- Model definitions for all three tiers via Vertex AI
- `router_settings.budget_fallbacks` mapping premium → standard → free
- `router_settings.budget_fallback_threshold: 0.75` (trigger at 75% spend)
- `database_url: sqlite:////app/data/litellm.db`
- Commented Vertex/Gemini placeholder block
- Commented Models.corp placeholder block

### `docker-compose.yml`
- Single `litellm` service on port 4000
- Bind mount: `~/.config/gcloud/application_default_credentials.json` → `/gcp/adc.json` (read-only)
- Env var: `GOOGLE_APPLICATION_CREDENTIALS=/gcp/adc.json`
- Volume: `./data:/app/data` for SQLite persistence
- Healthcheck on `GET /health`

### `.env.example`
```
VERTEX_PROJECT=your-gcp-project-id
VERTEX_LOCATION=us-central1
LITELLM_MASTER_KEY=sk-your-master-key-here
# MODELS_CORP_API_KEY=     # Add when available
# MODELS_CORP_BASE_URL=    # Add when available
```

### `scripts/create_qos_key.py`
- Uses `requests` to call `POST /key/generate` on the local proxy
- Creates a virtual key with `max_budget` and `model_max_budget` per tier
- Prints the generated key to stdout

### `scripts/test_qos.py`
- Uses `openai` SDK pointed at `http://localhost:4000/v1`
- Sends a loop of chat requests to `claude-sonnet`
- Prints `response.model` each iteration to show the moment downgrade occurs

### `.github/CODEOWNERS`
```
* @jimdaga
```

### `.github/workflows/lint.yml`
- Trigger: pull_request
- Steps: `yamllint config.yaml`, `docker compose config` validation

### `README.md`
- Prerequisites (Docker, gcloud ADC)
- Start stack
- Create test key
- Run test script
- How to add Models.corp later

---

## Constraints & Out of Scope

- **Single user only** — no multi-tenant key management
- **No Postgres** — SQLite is sufficient; if concurrency ever becomes needed, swap `DATABASE_URL`
- **No deploy pipeline** — local only; GitHub Actions is lint-only
- **Models.corp deferred** — placeholder config only; requires VPN + API key retrieval
- **Direct Anthropic deferred** — no `ANTHROPIC_API_KEY`; all Claude goes through Vertex
- **No Vertex Gemini yet** — commented placeholder; enable when credentials confirmed
