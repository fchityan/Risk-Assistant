from functools import lru_cache
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _BACKEND_DIR.parent
_ROOT_ENV_FILE = _REPO_ROOT / ".env"
_BACKEND_ENV_FILE = _BACKEND_DIR / ".env"

# Placeholder values from the old env template — treated as "not configured"
PLACEHOLDER_API_KEYS = frozenset(
    {
        "YOUR_BRIGHT_DATA_API_KEY_HERE",
        "YOUR_BRIGHT_DATA_SERP_API_KEY_HERE",
    }
)
PLACEHOLDER_PASSWORDS = frozenset(
    {
        "YOUR_BRIGHT_DATA_BROWSER_PASSWORD_HERE",
    }
)
PLACEHOLDER_SERP_ZONES = frozenset(
    {
        "your_serp_zone_name",
    }
)

DEFAULT_BROWSER_CDP_HOST = "brd.superproxy.io:9222"


def _is_real_api_key(value: str) -> bool:
    return bool(value) and value not in PLACEHOLDER_API_KEYS and not value.startswith("YOUR_")


def _is_real_password(value: str) -> bool:
    return bool(value) and value not in PLACEHOLDER_PASSWORDS and not value.startswith("YOUR_")


def _is_real_zone(value: str, placeholders: frozenset[str] = frozenset()) -> bool:
    return bool(value) and value not in placeholders and not value.startswith("your_")


class Settings(BaseSettings):
    # Bright Data account API key (Bearer token for SERP API /request calls).
    bright_data_api_key: str = ""
    bright_data_serp_api_key: str = ""
    bright_data_serp_zone: str = ""

    # Browser API (Playwright CDP) — zone username + password from zone Overview tab.
    # Username format: brd-customer-{CUSTOMER_ID}-zone-{ZONE_NAME}
    # Or set BRIGHT_DATA_CUSTOMER_ID + BRIGHT_DATA_BROWSER_ZONE to auto-build username.
    bright_data_browser_zone: str = ""
    bright_data_browser_username: str = ""
    bright_data_browser_password: str = ""
    bright_data_customer_id: str = ""
    bright_data_browser_cdp_host: str = DEFAULT_BROWSER_CDP_HOST

    daytona_api_key: str = ""
    daytona_server_url: str = ""
    daytona_target: str = "local"

    # LLM Stage 4 — provider: tokenrouter (default), openrouter, or kimi
    llm_provider: str = "tokenrouter"
    tokenrouter_api_key: str = ""
    tokenrouter_base_url: str = "https://api.tokenrouter.com/v1"
    tokenrouter_model: str = "MiniMax-M3"
    openrouter_api_key: str = ""
    openrouter_model: str = "minimax-v3"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_http_referer: str = "https://github.com/hackathon-dd-agent"
    openrouter_app_title: str = "Reputation Screening Agent"
    sensenova_api_key: str = ""
    sensenova_base_url: str = "https://api.sensenova.cn/compatible-mode/v1"
    sensenova_model: str = "SenseNova-5"
    kimi_api_key: str = ""
    kimi_base_url: str = "https://api.moonshot.ai/v1"
    kimi_model: str = "moonshot-v1-auto"
    llm_max_output_tokens: int = 4096

    # Stage 1.5 entity resolution
    clarification_enabled: bool = True
    discovery_serp_results: int = 5

    runs_dir: str = "./runs"
    agent_version: str = "0.1.0-hackathon"

    # Logging
    log_level: str = "INFO"
    log_file: str = "logs/pipeline.log"

    model_config = SettingsConfigDict(
        env_file=(str(_ROOT_ENV_FILE), str(_BACKEND_ENV_FILE)),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def resolve_bright_data_keys(self) -> "Settings":
        if not self.bright_data_serp_api_key and self.bright_data_api_key:
            self.bright_data_serp_api_key = self.bright_data_api_key

        if not self.bright_data_browser_username:
            if self.bright_data_customer_id and self.bright_data_browser_zone:
                self.bright_data_browser_username = self.build_browser_username(
                    self.bright_data_customer_id,
                    self.bright_data_browser_zone,
                )

        return self

    @staticmethod
    def build_browser_username(customer_id: str, browser_zone: str) -> str:
        return f"brd-customer-{customer_id}-zone-{browser_zone}"

    @property
    def serp_configured(self) -> bool:
        return _is_real_api_key(self.bright_data_serp_api_key) and _is_real_zone(
            self.bright_data_serp_zone, PLACEHOLDER_SERP_ZONES
        )

    @property
    def browser_configured(self) -> bool:
        return bool(self.bright_data_browser_username) and _is_real_password(
            self.bright_data_browser_password
        )

    @property
    def sensenova_configured(self) -> bool:
        return bool(self.sensenova_api_key) and bool(self.sensenova_base_url) and bool(
            self.sensenova_model
        )

    @property
    def runs_path(self) -> Path:
        runs = Path(self.runs_dir)
        if not runs.is_absolute():
            runs = _BACKEND_DIR / runs
        return runs.resolve()


@lru_cache
def get_settings() -> Settings:
    return Settings()
