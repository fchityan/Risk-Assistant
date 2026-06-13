Two things to add to the architecture:

## Deploying the FastAPI App Inside a Daytona Sandbox

Daytona provides built-in preview URLs for any port inside a sandbox — no manual tunneling needed. Any HTTP process listening on any port 1–65535 is reachable via a generated URL in the format `https://{port}-{sandboxId}.{daytonaProxyDomain}`. [daytona](https://www.daytona.io/docs/en/preview/)

**Setting `public: true`** on the sandbox makes that preview URL accessible to your teammate's frontend without any auth header. [daytona](https://www.daytona.io/docs/en/preview/)

```python
from daytona_sdk import Daytona, CreateSandboxParams

daytona = Daytona()

# Create a long-lived sandbox for the demo deployment
sandbox = daytona.create(CreateSandboxParams(
    language="python",
    public=True         # preview URLs are unauthenticated — frontend can hit them directly
))

# Upload your backend files
sandbox.fs.upload_file("main.py", open("backend/main.py", "rb").read())
sandbox.fs.upload_file("requirements.txt", open("backend/requirements.txt", "rb").read())

# Install dependencies
sandbox.process.exec("pip install -r requirements.txt -q")

# Start FastAPI with uvicorn on port 8000 (non-blocking)
sandbox.process.exec(
    "uvicorn main:app --host 0.0.0.0 --port 8000 &",
    timeout=10
)

# Get the public URL for the frontend to call
preview_url = sandbox.get_preview_link(8000)
print(f"Backend URL: {preview_url}")
```

Your teammate points the frontend's API base URL at `preview_url`. No CORS proxy, no ngrok, no extra infra. [daytona](https://www.daytona.io/docs/en/preview/)

***

## Managing Secrets

There are three layers to think about here: your **local dev machine**, the **Daytona workspace** (where you're coding), and the **deployed sandbox** (where the app runs). They need slightly different approaches.

### Layer 1 — Local dev (`.env` file + `python-dotenv`)

Keep a `.env` file that never gets committed (add it to `.gitignore`). Use `pydantic-settings` to load and validate settings at startup. [fastapi.tiangolo](https://fastapi.tiangolo.com/advanced/settings/)

```python
# backend/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    bright_data_api_key: str
    daytona_api_key: str
    kimi_api_key: str
    kimi_base_url: str = "https://api.moonshot.cn/v1"
    kimi_model: str = "moonshotai/Kimi-K2-Instruct"
    runs_dir: str = "./runs"

    class Config:
        env_file = ".env"

settings = Settings()
```

```bash
# .env  (never commit this)
BRIGHT_DATA_API_KEY=...
DAYTONA_API_KEY=...
KIMI_API_KEY=...
```

### Layer 2 — Daytona workspace (dev environment secrets)

Use the `daytona env set` CLI command to register secrets at the workspace level. These persist across workspace restarts and are injected as environment variables into every container and terminal session — no `.env` file needed in the workspace. [daytona](https://www.daytona.io/dotfiles/using-environmental-variables-in-daytona)

```bash
daytona env set BRIGHT_DATA_API_KEY=... DAYTONA_API_KEY=... KIMI_API_KEY=...

# Verify
daytona env list
```

This is cleaner than keeping a `.env` file in the workspace because the values are stored by Daytona's server, not on disk in your project directory. [daytona](https://www.daytona.io/dotfiles/using-environmental-variables-in-daytona)

### Layer 3 — Deployed sandbox (injected at process launch)

When you spin up the demo sandbox via the SDK, pass secrets as environment variables directly to `CreateSandboxParams`. This keeps them out of your source files entirely. [developers.openai](https://developers.openai.com/cookbook/examples/agents_sdk/computer_use_with_daytona/computer_use_with_daytona)

```python
import os
from daytona_sdk import Daytona, CreateSandboxParams, EnvVar

daytona = Daytona()

sandbox = daytona.create(CreateSandboxParams(
    language="python",
    public=True,
    env_vars={
        "BRIGHT_DATA_API_KEY": os.environ["BRIGHT_DATA_API_KEY"],
        "KIMI_API_KEY":        os.environ["KIMI_API_KEY"],
        "KIMI_BASE_URL":       "https://api.moonshot.cn/v1",
        "KIMI_MODEL":          "moonshotai/Kimi-K2-Instruct",
        "RUNS_DIR":            "/app/runs"
        # Note: no DAYTONA_API_KEY here — the sandbox doesn't need to call back to Daytona
    }
))
```

The secrets come from your local env (set via `daytona env set` in Layer 2), so they're never hardcoded anywhere in the codebase. [developers.openai](https://developers.openai.com/cookbook/examples/agents_sdk/computer_use_with_daytona/computer_use_with_daytona)

***

## Summary pattern

| Layer | Method | Why |
|---|---|---|
| Local dev | `.env` + `pydantic-settings` | Type-safe, validated at startup, standard pattern  [fastapi.tiangolo](https://fastapi.tiangolo.com/advanced/settings/) |
| Daytona workspace | `daytona env set` CLI | Persisted by Daytona server, not on disk  [daytona](https://www.daytona.io/dotfiles/using-environmental-variables-in-daytona) |
| Deployed demo sandbox | `env_vars` in `CreateSandboxParams` | Injected at creation from local env, never in source  [developers.openai](https://developers.openai.com/cookbook/examples/agents_sdk/computer_use_with_daytona/computer_use_with_daytona) |
| Shared with teammate | Share `.env` out-of-band (WhatsApp/Telegram DM) | Never commit or paste into chat/docs |

One extra thing worth doing on the day: add a `/health` endpoint to FastAPI that returns the status of each key (present/missing, not the values) so you can quickly confirm the sandbox booted with all secrets correctly injected. [render](https://render.com/articles/fastapi-production-deployment-best-practices)

```python
@app.get("/health")
async def health():
    return {
        "status": "ok",
        "secrets": {
            "bright_data": bool(settings.bright_data_api_key),
            "kimi": bool(settings.kimi_api_key),
            "daytona": bool(settings.daytona_api_key),
        }
    }
```