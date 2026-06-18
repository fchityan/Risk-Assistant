"""Frontend configuration (env vars)."""

import os
from urllib.parse import urlparse
from functools import lru_cache

from env_shared import load_shared_env

load_shared_env()


def _get_config_value(name: str, default: str = "") -> str:
    value = os.getenv(name)
    if value is not None and str(value).strip():
        return str(value).strip()

    try:
        import streamlit as st

        secret_value = st.secrets.get(name)
        if secret_value is not None and str(secret_value).strip():
            return str(secret_value).strip()
    except Exception:
        pass

    return default


@lru_cache
def get_frontend_settings() -> dict:
    backend_url = _get_config_value("BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")
    configured_mock = _get_config_value("USE_MOCK_DATA", "false").lower() in (
        "1",
        "true",
        "yes",
    )
    host = (urlparse(backend_url).hostname or "").lower()
    localhost_backend = host in {"127.0.0.1", "localhost"}
    runtime_env = _get_config_value("STREAMLIT_RUNTIME_ENVIRONMENT", "").lower()
    running_on_streamlit_cloud = bool(
        _get_config_value("STREAMLIT_SHARING_MODE")
        or _get_config_value("STREAMLIT_CLOUD")
        or runtime_env == "cloud"
    )
    auto_mock_on_cloud_localhost = running_on_streamlit_cloud and localhost_backend

    return {
        "backend_url": backend_url,
        "use_mock_data": configured_mock or auto_mock_on_cloud_localhost,
        "use_mock_data_forced_by_cloud_localhost": auto_mock_on_cloud_localhost,
        "poll_interval_seconds": float(_get_config_value("POLL_INTERVAL_SECONDS", "5")),
        "poll_timeout_seconds": float(_get_config_value("POLL_TIMEOUT_SECONDS", "300")),
        "kimi_api_key_set": bool(_get_config_value("KIMI_API_KEY", "")),
        "daytona_api_key_set": bool(_get_config_value("DAYTONA_API_KEY", "")),
    }
