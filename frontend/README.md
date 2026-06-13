# Frontend — Risk Assistant (Streamlit)

Evidence-grounded reputational screening UI. By default it calls the **FastAPI backend** (`backend/`) and renders the v1 screening report. Set `USE_MOCK_DATA=true` to load local sample JSON only.

## Quick start

1. Start the backend (see [backend/README.md](../backend/README.md)):

```bash
cd backend
python -m uvicorn main:app --port 8000
```

2. Install and run the UI:

```bash
cd frontend
cp .env.example .env
pip install -r requirements.txt
streamlit run app.py --server.port 8501
```

Open http://localhost:8501

## Configuration (`frontend/.env`)

| Variable | Default | Description |
|----------|---------|-------------|
| `BACKEND_URL` | `http://127.0.0.1:8000` | FastAPI base URL |
| `USE_MOCK_DATA` | `false` | Load `mock_data/mock_data.json` instead of API |
| `POLL_INTERVAL_SECONDS` | `5` | Status poll interval |
| `POLL_TIMEOUT_SECONDS` | `900` | Max wait for pipeline completion |

## Backend integration

```
┌─────────────┐     POST /screen          ┌──────────────────┐
│  Streamlit  │ ────────────────────────► │  FastAPI backend │
│  app.py     │     GET /screen/{run_id}  │  (orchestrator)  │
└─────────────┘ ◄──────────────────────── └──────────────────┘
       │                                              │
       │  report_adapter.v1_report_to_ui()          │
       ▼                                              ▼
   Dashboard tabs                          runs/{id}/final_report.json
```

### API flow (Run button)

1. `POST {BACKEND_URL}/screen` with `{ subject_type, primary_name, country?, ... }`
2. Poll `GET {BACKEND_URL}/screen/{run_id}` until `complete`, `error`, or `clarification_required`
3. On `complete`, map `report` via `report_adapter.py` and refresh the dashboard
4. On `clarification_required`, show a warning; resume with `POST /screen/{run_id}/clarify` (API or future UI)

Subject type mapping (UI label → API):

| UI select | API `subject_type` |
|-----------|-------------------|
| Company, Private Company, Vendor | `organization` |
| Individual, HNW Prospect, Key Person | `individual` |

### Modules

| File | Role |
|------|------|
| `app.py` | Streamlit UI |
| `api_client.py` | HTTP client for `/screen` endpoints |
| `report_adapter.py` | v1 report JSON → UI view model |
| `settings.py` | Env configuration |
| `mock_data/mock_data.json` | Sample v1 report for offline demo |

## Legacy prototype

`legacy/run_agent.py` and `services/` contain an early standalone agent (mock Bright Data + OpenAI). The production path is **backend pipeline + this UI**. See `legacy/README.md`.

## Troubleshooting

- **Connection refused** — ensure backend is running on `BACKEND_URL`
- **401 on screening** — check `backend/.env` LLM keys (`TOKENROUTER_BASE_URL`, `MiniMax-M3`)
- **Empty dashboard** — confirm `mock_data/mock_data.json` exists or run completed successfully

Full stack guide: [docs/integration.md](../docs/integration.md)
