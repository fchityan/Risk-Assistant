from pathlib import Path
import os

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


def get_config_value(name: str, default: str = "") -> str:
    """Read config from env first, then Streamlit secrets (including nested tables)."""
    value = os.getenv(name)
    if value is not None and str(value).strip():
        return str(value).strip()

    try:
        import streamlit as st

        direct = st.secrets.get(name)
        if direct is not None and str(direct).strip():
            return str(direct).strip()

        key_norm = _normalize_key(name)
        nested = _find_secret_value(st.secrets, key_norm)
        if nested is not None and str(nested).strip():
            return str(nested).strip()
    except Exception:
        pass

    return default


def _normalize_key(key: str) -> str:
    return "".join(ch.lower() for ch in key if ch.isalnum())


def _find_secret_value(container, key_norm: str):
    if isinstance(container, dict):
        for key, value in container.items():
            if _normalize_key(str(key)) == key_norm:
                return value
            nested = _find_secret_value(value, key_norm)
            if nested is not None:
                return nested
    elif isinstance(container, list):
        for value in container:
            nested = _find_secret_value(value, key_norm)
            if nested is not None:
                return nested
    return None
