# Documentation

| Document | Description |
|----------|-------------|
| [architecture.md](architecture.md) | Backend pipeline stages, checkpoints, API, reliability patterns |
| [integration.md](integration.md) | Running frontend + backend together, API contract, report mapping |
| [../backend/README.md](../backend/README.md) | API quick start, env vars, demo seeds, logging |
| [../frontend/README.md](../frontend/README.md) | Streamlit UI setup and modules |

## Schemas and examples

| File | Description |
|------|-------------|
| [schemas/reputation-screening-report-rubric.schema.v1.json](schemas/reputation-screening-report-rubric.schema.v1.json) | JSON Schema for v1 screening reports |
| [examples/example-profile.json](examples/example-profile.json) | Trimmed sample report (assessment + one evidence item) |

Validate a completed run against Pydantic models and JSON Schema:

```bash
cd backend
python validate_report.py runs/DEMO-ORION-001/final_report.json
```
