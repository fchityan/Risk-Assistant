# Risk Assistant

Risk Assistant is an automated **public-source reputational screening** pipeline. Submit a person or organization name, the backend searches open web sources, classifies findings with a fixed rubric, and returns a structured **v1 screening report** JSON. A **Streamlit UI** (`frontend/`) calls the API and presents assessment, evidence, rules, and memo views.

## What it does

1. **Subject prep** — normalize input and build search queries
2. **Entity resolution** — infer country/industry from SERP + LLM; pause for analyst clarification when identity is ambiguous
3. **Collection** — Bright Data SERP + Browser API (Playwright) for adverse hits
4. **Processing** — text cleanup and source-tier hints (Daytona sandbox or local fallback)
5. **LLM classification** — rubric scoring per evidence item (TokenRouter / OpenRouter / Kimi)
6. **Rule engine** — deterministic support bands, risk level, disposition, final report

Reports conform to [`docs/schemas/reputation-screening-report-rubric.schema.v1.json`](docs/schemas/reputation-screening-report-rubric.schema.v1.json). See [`docs/examples/example-profile.json`](docs/examples/example-profile.json) for a sample output shape.

## Quick start (full stack)

**Backend** (port 8000):

```bash
cd backend
pip install -r requirements.txt
playwright install chromium
python -m uvicorn main:app --reload --port 8000
```

**Frontend** (port 8501):

```bash
cd frontend
pip install -r requirements.txt
streamlit run app.py --server.port 8501
```

On **Windows PowerShell**, use `;` instead of `&&`, and `Copy-Item` instead of `cp`:

```powershell
cd frontend
pip install -r requirements.txt
streamlit run app.py --server.port 8501
```

Open http://localhost:8501 and click **Run**, or use the API directly:

```bash
curl -X POST http://localhost:8000/screen \
  -H "Content-Type: application/json" \
  -d '{"subject_type":"organization","primary_name":"Singapore Airlines","country":"Singapore"}'
```

Poll: `GET http://localhost:8000/screen/{run_id}`

Mock UI only (no API): set `USE_MOCK_DATA=true` in `backend/.env`.

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
├── README.md
├── docs/
│   ├── README.md                    # documentation index
│   ├── architecture.md              # pipeline design
│   ├── integration.md               # frontend ↔ backend
│   ├── schemas/
│   │   └── reputation-screening-report-rubric.schema.v1.json
│   └── examples/
│       └── example-profile.json
├── backend/                         # FastAPI screening pipeline
│   ├── main.py
│   ├── orchestrator.py
│   ├── stages/
│   └── runs/                        # checkpoints (gitignored)
└── frontend/                        # Streamlit Risk Assistant UI
    ├── app.py
    ├── api_client.py                # calls backend /screen
    ├── report_adapter.py            # v1 report → UI model
    ├── mock_data/mock_data.json
    ├── legacy/                      # early prototype scripts
    └── services/                    # legacy mock services
```

## Configuration

- **Shared runtime config** — `backend/.env` (Bright Data, LLM, and frontend `BACKEND_URL` / `USE_MOCK_DATA` / polling settings)

See [backend/README.md](backend/README.md) and [frontend/README.md](frontend/README.md).

## Documentation

- [docs/README.md](docs/README.md) — index of all docs, schemas, and examples
- [docs/integration.md](docs/integration.md) — run both services, API contract, report mapping
- [docs/architecture.md](docs/architecture.md) — pipeline stages and checkpoints
- [backend/README.md](backend/README.md) — endpoints, env, demo, logging
- [frontend/README.md](frontend/README.md) — UI setup and modules

Validate a report:

```bash
cd backend
python validate_report.py runs/DEMO-ORION-001/final_report.json
```
