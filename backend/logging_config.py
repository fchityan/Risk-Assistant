"""Central logging setup for pipeline and API diagnostics."""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from config import get_settings

_CONFIGURED = False

LOG_FORMAT = (
    "%(asctime)s %(levelname)s [%(name)s] %(message)s"
)


def key_prefix_hint(key: str) -> str:
    """Safe API key shape hint for logs (never log full secrets)."""
    if not key:
        return "empty"
    if key.startswith("YOUR_"):
        return "placeholder"
    prefix = key.split("-", 1)[0] if "-" in key[:12] else key[:4]
    return f"{prefix}... (len={len(key)})"


def configure_logging() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return

    settings = get_settings()
    level_name = settings.log_level.upper()
    level = getattr(logging, level_name, logging.INFO)

    root = logging.getLogger()
    root.setLevel(level)

    formatter = logging.Formatter(LOG_FORMAT)

    if not root.handlers:
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(formatter)
        root.addHandler(stream_handler)

    log_file = settings.log_file
    if log_file:
        log_path = Path(log_file)
        if not log_path.is_absolute():
            log_path = Path(__file__).resolve().parent / log_path
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)

    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    configure_logging()
    return logging.getLogger(name)
