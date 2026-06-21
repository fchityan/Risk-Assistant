"""Frontend configuration (env vars + Streamlit secrets)."""

from urllib.parse import urlparse
from functools import lru_cache

from env_shared import get_config_value, load_shared_env

load_shared_env()


@lru_cache
def get_frontend_settings() -> dict:
    backend_url = get_config_value("BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")
    configured_mock = get_config_value("USE_MOCK_DATA", "false").lower() in (
        "1",
        "true",
        "yes",
    )
    host = (urlparse(backend_url).hostname or "").lower()
    localhost_backend = host in {"127.0.0.1", "localhost"}
    runtime_env = get_config_value("STREAMLIT_RUNTIME_ENVIRONMENT", "").lower()
    running_on_streamlit_cloud = bool(
        get_config_value("STREAMLIT_SHARING_MODE")
        or get_config_value("STREAMLIT_CLOUD")
        or runtime_env == "cloud"
    )
    auto_mock_on_cloud_localhost = running_on_streamlit_cloud and localhost_backend

    return {
        "backend_url": backend_url,
        "use_mock_data": configured_mock or auto_mock_on_cloud_localhost,
        "use_mock_data_forced_by_cloud_localhost": auto_mock_on_cloud_localhost,
        "poll_interval_seconds": float(get_config_value("POLL_INTERVAL_SECONDS", "5")),
        "poll_timeout_seconds": float(get_config_value("POLL_TIMEOUT_SECONDS", "900")),
        "kimi_api_key_set": bool(get_config_value("KIMI_API_KEY", "")),
        "daytona_api_key_set": bool(get_config_value("DAYTONA_API_KEY", "")),
    }
