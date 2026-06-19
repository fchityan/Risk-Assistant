# Frontend — Risk Assistant (Streamlit)

Evidence-grounded reputational screening UI. By default it tries the **FastAPI backend** first. If the backend is unreachable but Kimi + Bright Data keys are configured, it falls back to a **frontend live bypass** (direct Bright Data + Kimi in Streamlit). Otherwise it loads the example profile. Set `USE_MOCK_DATA=true` to force example-profile mode.

## Quick start

1. Copy shared config and start the backend (see [backend/README.md](../backend/README.md)):

```bash
cp .env.example .env
cd backend
pip install -r requirements.txt
playwright install chromium
python -m uvicorn main:app --port 8000
```

2. Install and run the UI:

```bash
cd frontend
pip install -r requirements.txt
streamlit run app.py --server.port 8501
```

Open http://localhost:8501

## Configuration (shared `.env`)

The frontend loads environment values via `env_shared.py`: **repo root `.env` first**, then `backend/.env` overrides (same precedence as the backend).

| Variable | Default | Description |
|----------|---------|-------------|
| `BACKEND_URL` | `http://127.0.0.1:8000` | FastAPI base URL |
| `USE_MOCK_DATA` | `false` | Force example profile instead of live paths |
| `POLL_INTERVAL_SECONDS` | `5` | Status poll interval |
| `POLL_TIMEOUT_SECONDS` | `900` | Max wait for pipeline completion |
| `KIMI_API_KEY` | — | Required for frontend live bypass fallback |
| Bright Data SERP vars | — | Required for frontend live bypass fallback |

On Streamlit Cloud with a localhost `BACKEND_URL`, mock mode is forced automatically (`STREAMLIT_SHARING_MODE`, `STREAMLIT_CLOUD`, or `STREAMLIT_RUNTIME_ENVIRONMENT=cloud`).

### Runtime data source selection

1. **`USE_MOCK_DATA=true`** (or Streamlit Cloud + localhost backend) → load `docs/examples/example-profile.json`
2. **`GET {BACKEND_URL}/health` returns `status=ok`** → use full backend pipeline (preferred)
3. **Backend unreachable + Kimi + Bright Data configured** → frontend live bypass (`frontend/services/`)
4. **Otherwise** → load `docs/examples/example-profile.json`

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

### API flow (Run button — backend path)

1. `POST {BACKEND_URL}/screen` with `{ subject_type, primary_name, country?, ... }`
2. Poll `GET {BACKEND_URL}/screen/{run_id}` until `complete`, `error`, or `clarification_required`
3. On `complete`, map `report` via `report_adapter.py` and refresh the dashboard
4. On `clarification_required`, submit clarification in the UI via `POST /screen/{run_id}/clarify`

### Full memo generation flow

1. UI requests `POST {BACKEND_URL}/screen/{run_id}/memo/sensenova` when **View Full Memo** is clicked (backend runs only).
2. Backend tries SenseNova first.
3. If SenseNova fails, backend automatically falls back to Kimi.
4. UI displays the returned memo and the reported source (`sensenova` or `kimi`).

Frontend live bypass runs use memo text from Kimi directly — no backend memo endpoint.

Subject type mapping (UI label → API):

| UI select | API `subject_type` |
|-----------|-------------------|
| Company, Private Company, Vendor | `organization` |
| Individual, HNW Prospect, Key Person | `individual` |

### Modules

| File | Role |
|------|------|
| `app.py` | Streamlit UI, runtime source selection |
| `style_loader.py` | Loads `static/base.css` and `static/panels.css` |
| `static/base.css` | App shell, sidebar, forms, tabs, responsive layout |
| `static/panels.css` | Dashboard panel and table styles |

UI conventions (colors, typography, panel patterns): [docs/style-guide.md](../docs/style-guide.md)

| `api_client.py` | HTTP client for backend endpoints |
| `env_shared.py` | Loads shared root/backend `.env` |
| `report_adapter.py` | v1 report JSON → UI view model |
| `settings.py` | Env configuration |
| `services/` | Bright Data + Kimi helpers for live bypass fallback |

## Troubleshooting

- **Connection refused** — ensure backend is running on `BACKEND_URL`, or configure Kimi + Bright Data for live bypass
- **401 on memo generation** — verify `SENSENOVA_API_KEY`; backend falls back to Kimi if SenseNova is unauthorized
- **LLM issues** — verify Kimi settings in `.env` (`KIMI_API_KEY`, `KIMI_BASE_URL`, `KIMI_MODEL`)
- **Empty dashboard** — confirm `docs/examples/example-profile.json` exists or a run completed successfully

Full stack guide: [docs/integration.md](../docs/integration.md) · Architecture: [docs/architecture.md](../docs/architecture.md)
