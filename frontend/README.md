# Frontend — Risk Assistant (Streamlit)

Evidence-grounded reputational screening UI. By default it tries the **FastAPI backend** (`backend/`) first and renders live results when reachable. If the backend is unreachable, it automatically falls back to local mock data. Set `USE_MOCK_DATA=true` to force mock mode.

## Quick start

1. Start the backend (see [backend/README.md](../backend/README.md)):

```bash
cd backend
python -m uvicorn main:app --port 8000
```

2. Install and run the UI:

```bash
cd frontend
pip install -r requirements.txt
streamlit run app.py --server.port 8501
```

Open http://localhost:8501

## Configuration (`.env` preferred)

The frontend reads environment values from the repository root `.env` file first,
and falls back to `backend/.env` for backward compatibility.

| Variable | Default | Description |
|----------|---------|-------------|
| `BACKEND_URL` | `http://127.0.0.1:8000` | FastAPI base URL |
| `USE_MOCK_DATA` | `false` | Force `mock_data/mock_data.json` instead of API |
| `POLL_INTERVAL_SECONDS` | `5` | Status poll interval |
| `POLL_TIMEOUT_SECONDS` | `900` | Max wait for pipeline completion |

Runtime data source selection:

1. If `USE_MOCK_DATA=true`: always use mock data.
2. Else: call `GET {BACKEND_URL}/health`.
3. If healthy (`status=ok`): use live API.
4. If unhealthy/unreachable: fallback to `mock_data/mock_data.json`.

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

### Full memo generation flow

1. UI requests `POST {BACKEND_URL}/screen/{run_id}/memo/sensenova` when **View Full Memo** is clicked.
2. Backend tries SenseNova first.
3. If SenseNova fails (for example `401 Forbidden`), backend automatically falls back to Kimi.
4. UI displays the returned memo and the reported source (`sensenova` or `kimi`).

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

## Notes on services folder

`services/` contains helper service stubs from early iterations. The production path is **backend pipeline + this UI**.

## Troubleshooting

- **Connection refused** — ensure backend is running on `BACKEND_URL`
- **401 on memo generation** — verify `SENSENOVA_API_KEY`; backend will fall back to Kimi if SenseNova is unauthorized
- **LLM classification/provider issues** — verify Kimi settings in `backend/.env` (`KIMI_API_KEY`, `KIMI_BASE_URL`, `KIMI_MODEL`)
- **Empty dashboard** — confirm `mock_data/mock_data.json` exists or run completed successfully

Full stack guide: [docs/integration.md](../docs/integration.md) · Architecture: [docs/architecture.md](../docs/architecture.md)
