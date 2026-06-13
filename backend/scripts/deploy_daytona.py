"""Optional: deploy FastAPI inside a Daytona public sandbox."""

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from daytona_sdk import CreateSandboxParams, Daytona

BACKEND_DIR = Path(__file__).resolve().parent.parent

BRIGHT_DATA_ENV_KEYS = (
    "BRIGHT_DATA_API_KEY",
    "BRIGHT_DATA_SERP_API_KEY",
    "BRIGHT_DATA_SERP_ZONE",
    "BRIGHT_DATA_BROWSER_USERNAME",
    "BRIGHT_DATA_BROWSER_PASSWORD",
    "BRIGHT_DATA_CUSTOMER_ID",
    "BRIGHT_DATA_BROWSER_ZONE",
    "BRIGHT_DATA_BROWSER_CDP_HOST",
)


def _bright_data_env() -> dict[str, str]:
    return {key: os.environ.get(key, "") for key in BRIGHT_DATA_ENV_KEYS}


LLM_ENV_KEYS = (
    "LLM_PROVIDER",
    "TOKENROUTER_API_KEY",
    "TOKENROUTER_MODEL",
    "TOKENROUTER_ENVIRONMENT",
    "OPENROUTER_API_KEY",
    "OPENROUTER_MODEL",
    "OPENROUTER_BASE_URL",
    "OPENROUTER_HTTP_REFERER",
    "OPENROUTER_APP_TITLE",
    "KIMI_API_KEY",
    "KIMI_BASE_URL",
    "KIMI_MODEL",
    "LLM_MAX_OUTPUT_TOKENS",
)


def _llm_env() -> dict[str, str]:
    return {key: os.environ.get(key, "") for key in LLM_ENV_KEYS}


def deploy() -> str:
    daytona = Daytona(api_key=os.environ.get("DAYTONA_API_KEY"))

    env_vars = {
        **{k: v for k, v in _bright_data_env().items() if v},
        **{k: v for k, v in _llm_env().items() if v},
        "RUNS_DIR": "/app/runs",
    }

    sandbox = daytona.create(
        CreateSandboxParams(
            language="python",
            public=True,
            env_vars=env_vars,
        )
    )

    for name in ("main.py", "config.py", "orchestrator.py", "requirements.txt"):
        sandbox.fs.upload_file(name, (BACKEND_DIR / name).read_bytes())

    for subdir in ("stages", "schemas", "config", "processing"):
        for path in (BACKEND_DIR / subdir).rglob("*"):
            if path.is_file():
                rel = path.relative_to(BACKEND_DIR).as_posix()
                sandbox.fs.upload_file(rel, path.read_bytes())

    sandbox.process.exec("pip install -r requirements.txt -q", timeout=120)
    sandbox.process.exec(
        "nohup uvicorn main:app --host 0.0.0.0 --port 8000 > /tmp/uvicorn.log 2>&1 &",
        timeout=10,
    )
    time.sleep(3)

    preview_url = sandbox.get_preview_link(8000)
    print(f"Backend deployed at: {preview_url}")
    return str(preview_url)


if __name__ == "__main__":
    deploy()
