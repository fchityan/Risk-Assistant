# Reputation Screening Backend

FastAPI backend for the Agent Forge hackathon reputational screening agent.

## Quick start

```bash
cd backend
cp .env.example .env
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
3. **Daytona sandbox** — text cleaning, source tier classification (local fallback)
4. **LLM (Stage 4)** — rubric classification via TokenRouter (default, MiniMax v3), OpenRouter, or direct Kimi API
5. **Rule engine** — deterministic support bands, risk level, disposition

Each stage checkpoints to `runs/{run_id}/`. Entity resolution artifacts: `checkpoint_entity_resolution.json` + `clarification` block in `status.json`.

## Environment variables

See `.env.example`. Bright Data free tier setup:

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
| `tokenrouter` (default) | `TOKENROUTER_API_KEY` (`tr_...`) | `TOKENROUTER_MODEL=minimax-v3` |
| `openrouter` | `OPENROUTER_API_KEY` | `OPENROUTER_MODEL=minimax-v3` |
| `kimi` | `KIMI_API_KEY` + `KIMI_BASE_URL` | `KIMI_MODEL` |

## Demo replay (no API credits)

```bash
python scripts/seed_demo.py
# Complete run: GET /screen/DEMO-ORION-001
# Paused run:  GET /screen/DEMO-AMBIG-001
# Resume:      POST /screen/DEMO-AMBIG-001/clarify
```

## Validation

```bash
python validate_report.py runs/DEMO-ORION-001/final_report.json
```

## Logging

Pipeline and API logs go to stdout and `backend/logs/pipeline.log` (rotating, 5 MB).

| Env var | Default | Description |
|---------|---------|-------------|
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `LOG_FILE` | `logs/pipeline.log` | Set empty to disable file logging |

Log lines include `run_id` (e.g. `[RSR-20260613-001]`) for stage boundaries, status changes, SERP/Browser/LLM failures, and full tracebacks on pipeline errors. TokenRouter auth issues log a key-prefix hint (`tr_...` expected) without exposing secrets.
