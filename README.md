# Reputation Screening Agent

Hackathon project: an automated **public-source reputational screening** pipeline. Submit a person or organization name, the backend searches open web sources, classifies findings with a fixed rubric, and returns a structured **v1 screening report** JSON.

## What it does

1. **Subject prep** — normalize input and build search queries
2. **Entity resolution** — infer country/industry from SERP + LLM; pause for analyst clarification when identity is ambiguous
3. **Collection** — Bright Data SERP + Browser API (Playwright) for adverse hits
4. **Processing** — text cleanup and source-tier hints (Daytona sandbox or local fallback)
5. **LLM classification** — rubric scoring per evidence item (TokenRouter / OpenRouter / Kimi)
6. **Rule engine** — deterministic support bands, risk level, disposition, final report

Reports conform to `reputation-screening-report-rubric.schema.v1.json`. See `example-profile.json` for a sample output shape.

## Quick start

```bash
cd backend
cp .env.example .env
# Add API keys (Bright Data, LLM provider, optional Daytona)

pip install -r requirements.txt
playwright install chromium   # Browser API page fetch

python -m uvicorn main:app --reload --port 8000
```

Health check: `GET http://localhost:8000/health`

Start a run:

```bash
curl -X POST http://localhost:8000/screen \
  -H "Content-Type: application/json" \
  -d '{"subject_type":"individual","primary_name":"Jane Doe"}'
```

Poll: `GET http://localhost:8000/screen/{run_id}` until `complete`, `clarification_required`, or `error`.

Demo without live API credits:

```bash
cd backend
python scripts/seed_demo.py
# GET /screen/DEMO-ORION-001   — complete run
# GET /screen/DEMO-AMBIG-001   — paused for clarification
```

## API summary

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Service health and configured integrations |
| `POST /screen` | Start run (`subject_type` + `primary_name` required) |
| `GET /screen/{run_id}` | Status, clarification form, or final report |
| `POST /screen/{run_id}/clarify` | Resume after `clarification_required` |

Status flow: `queued` → `running` → `clarification_required` → `running` → `complete` | `error`

## Repository layout

```
hackathon-dd-agent/
├── README.md                          # this file
├── backend-architecture.md              # pipeline design (detailed)
├── reputation-screening-report-rubric.schema.v1.json
├── example-profile.json
└── backend/
    ├── README.md                        # API, env vars, logging
    ├── main.py                          # FastAPI app
    ├── orchestrator.py                  # checkpointed pipeline
    ├── stages/                          # stage 1–5 + entity resolution
    ├── schemas/                         # Pydantic models
    ├── config/                          # rules_v1.json, source tiers
    ├── scripts/seed_demo.py
    └── runs/                            # per-run checkpoints (gitignored)
```

## Configuration

Copy `backend/.env.example` to `backend/.env`. Minimum for a live run:

- **Bright Data** — `BRIGHT_DATA_API_KEY`, `BRIGHT_DATA_SERP_ZONE`, Browser credentials
- **LLM** — `LLM_PROVIDER` + `TOKENROUTER_API_KEY` (OpenAI-compatible API at `api.tokenrouter.com`)

Full variable list and troubleshooting: [backend/README.md](backend/README.md).

Pipeline logs: `backend/logs/pipeline.log` (and stdout).

## Documentation

- [backend/README.md](backend/README.md) — endpoints, env, demo, validation
- [backend-architecture.md](backend-architecture.md) — stages, checkpointing, ambiguity rubric
- [reputation-screening-report-rubric.schema.v1.json](reputation-screening-report-rubric.schema.v1.json) — report JSON schema

Validate a report:

```bash
cd backend
python validate_report.py runs/DEMO-ORION-001/final_report.json
```
