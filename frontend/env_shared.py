from pathlib import Path

from dotenv import load_dotenv

_REPO_ROOT = Path(__file__).resolve().parents[1]
_ROOT_ENV_FILE = _REPO_ROOT / ".env"
_BACKEND_ENV_FILE = _REPO_ROOT / "backend" / ".env"


def load_shared_env() -> None:
    # Prefer repository root .env for Streamlit/local runs, while keeping
    # backend/.env as a compatibility fallback for older setups.
    if _ROOT_ENV_FILE.exists():
        load_dotenv(_ROOT_ENV_FILE, override=False)
    if _BACKEND_ENV_FILE.exists():
        load_dotenv(_BACKEND_ENV_FILE, override=False)
