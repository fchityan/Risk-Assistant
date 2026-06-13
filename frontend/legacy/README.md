# Legacy standalone agent (pre-backend)

These files are from an early hackathon prototype that ran Bright Data / LLM / SenseNova mocks outside the FastAPI pipeline.

| File | Notes |
|------|--------|
| `run_agent.py` | Original CLI entry (expects `services.*` on PYTHONPATH) |
| `../services/bright_data.py` | Mock SERP collector |
| `../services/llm_reasoning.py` | Mock OpenAI analysis |
| `../services/sensenova.py` | Memo generation stub |

**Do not use for production screening.** Use `backend/` + `frontend/app.py` instead.

Run from `frontend/` with:

```bash
PYTHONPATH=services python legacy/run_agent.py
```

(Requires env vars; no `.env` loader in legacy script.)
