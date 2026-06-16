# Reputation Screening Backend

FastAPI backend for the Agent Forge hackathon reputational screening agent.

## Quick start

```bash
cd backend
# Edit .env with your API keys

pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

## API

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Health check + secret presence (not values) |
| `POST /screen` | Start screening run, returns `{run_id, status}` |
| `GET /screen/{run_id}` | Poll status; returns full report when complete or clarification form when paused |
| `POST /screen/{run_id}/clarify` | Submit analyst clarification to resume a paused run |
| `POST /screen/{run_id}/memo/sensenova` | Generate full memo via SenseNova, with automatic fallback to Kimi |

### Status lifecycle

`queued` → `running` → `clarification_required` → `running` → `complete` | `error`

When entity identity is ambiguous (Stage 1.5), the pipeline pauses with `clarification_required`. Submit `POST /screen/{run_id}/clarify` to resume.

### POST /screen body (minimal input)

Only `subject_type` and `primary_name` are required. Optional fields improve entity resolution confidence:

```json
{
  "subject_type": "organization",
  "primary_name": "Atlas Global"
}
```

Full input example:

```json
{
  "subject_type": "organization",
  "primary_name": "Orion Logistics Group",
  "country": "Singapore",
  "industry": "logistics",
  "known_associations": ["Orion Trade Holdings"]
}
```

### GET /screen/{run_id} when clarification_required

```json
{
  "run_id": "RSR-...",
  "status": "clarification_required",
  "stage": "entity_resolution",
  "message": "Entity identity is ambiguous; analyst clarification required before screening continues.",
  "clarification_form": {
    "questions": [...],
    "candidate_entities": [...]
  },
  "entity_resolution": {
    "ambiguity_level": "high",
    "reason_codes": ["MULTIPLE_PLAUSIBLE_ORGS", "NO_CONFIRMED_COUNTRY"],
    "action": "clarification_required"
  }
}
```

### POST /screen/{run_id}/clarify body

```json
{
  "country": "Singapore",
  "industry": "logistics",
  "known_associations": ["Atlas Global Logistics"],
  "candidate_id": "cand_01",
  "notes": "Logistics operator in SG"
}
```

Returns `{run_id, status: "running", stage: "entity_resolution"}`. Poll `GET /screen/{run_id}` until `complete`.

## Pipeline stages

1. **Subject prep** — normalize input, generate provisional search queries
1.5. **Entity resolution** — hybrid SERP + LLM discovery; pause for clarification when ambiguity is high
2. **Bright Data** — SERP API + Browser API (Playwright) for full-page fetch
3. **Daytona Sandbox** — isolated container runtime for text cleaning and source tier classification (local fallback for development)
4. **LLM (Stage 4)** — Kimi-based rubric classification (TokenRouter/OpenRouter are also supported via env)
5. **Rule engine** — deterministic support bands, risk level, disposition

Each stage checkpoints to `runs/{run_id}/`. Entity resolution artifacts: `checkpoint_entity_resolution.json` + `clarification` block in `status.json`.

## Environment variables

See `backend/.env`. Bright Data free tier setup:

- `BRIGHT_DATA_API_KEY` — account API key for SERP API (`/request` endpoint)
- `BRIGHT_DATA_SERP_ZONE` — SERP API zone name
- `BRIGHT_DATA_BROWSER_USERNAME` + `BRIGHT_DATA_BROWSER_PASSWORD` — Browser API zone credentials (Overview tab)
- Or `BRIGHT_DATA_CUSTOMER_ID` + `BRIGHT_DATA_BROWSER_ZONE` + password to auto-build username

Entity resolution tuning:

- `CLARIFICATION_ENABLED` — pause pipeline on high ambiguity (default `true`)
- `DISCOVERY_SERP_RESULTS` — SERP results per discovery query (default `5`)

Install Playwright for Browser API page fetch:

```bash
pip install playwright
playwright install chromium
```

LLM Stage 4 providers (`LLM_PROVIDER`):

| Provider | Key env vars | Model env |
|----------|--------------|-----------|
| `tokenrouter` (default) | `TOKENROUTER_API_KEY` | `TOKENROUTER_MODEL=MiniMax-M3` |
| `openrouter` | `OPENROUTER_API_KEY` | `OPENROUTER_MODEL=minimax-v3` |
| `kimi` | `KIMI_API_KEY` + `KIMI_BASE_URL` | `KIMI_MODEL` |

Stage 5 supports memo generation via SenseNova with automatic fallback to Kimi:

- `SENSENOVA_API_KEY`
- `SENSENOVA_BASE_URL` (default: `https://api.sensenova.cn/compatible-mode/v1`)
- `SENSENOVA_MODEL` (default: `SenseNova-5`)

If SenseNova is unavailable or returns an error, the API memo endpoint falls back to Kimi generation.
If both SenseNova and Kimi fail, the endpoint returns an error with both failure details.

## Demo replay (no API credits)

```bash
python scripts/seed_demo.py
# Complete run: GET /screen/DEMO-ORION-001
# Paused run:  GET /screen/DEMO-AMBIG-001
# Resume:      POST /screen/DEMO-AMBIG-001/clarify
```

## Validation

Validates against Pydantic models in `schemas/` and the JSON Schema in `docs/schemas/reputation-screening-report-rubric.schema.v1.json`.

```bash
python validate_report.py runs/DEMO-ORION-001/final_report.json
```

## Logging

Pipeline and API logs go to stdout and `backend/logs/pipeline.log` (rotating, 5 MB).

| Env var | Default | Description |
|---------|---------|-------------|
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `LOG_FILE` | `logs/pipeline.log` | Set empty to disable file logging |

Log lines include `run_id` (e.g. `[RSR-20260613-001]`) for stage boundaries, status changes, SERP/Browser/LLM failures, and full tracebacks on pipeline errors.

TokenRouter uses the OpenAI-compatible endpoint `https://api.tokenrouter.com/v1` with `chat.completions.create` (not the legacy `tokenrouter` Python SDK).
