"""Shared source-tier and adverse-keyword configuration."""

import json
from functools import lru_cache
from pathlib import Path

_SOURCE_TIERS_PATH = Path(__file__).resolve().parent / "config" / "source_tiers.json"


@lru_cache
def load_source_tiers_config() -> dict:
    with open(_SOURCE_TIERS_PATH, encoding="utf-8") as f:
        return json.load(f)


def get_adverse_keywords() -> list[str]:
    return list(load_source_tiers_config().get("adverse_keywords", []))
