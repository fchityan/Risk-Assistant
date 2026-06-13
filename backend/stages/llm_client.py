"""LLM provider abstraction: TokenRouter (default), OpenRouter, or direct Kimi."""

import json
import re
from enum import Enum

from openai import OpenAI

from config import get_settings
from logging_config import get_logger, key_prefix_hint

logger = get_logger(__name__)

PLACEHOLDER_LLM_KEYS = frozenset(
    {
        "YOUR_KIMI_API_KEY_HERE",
        "YOUR_OPENROUTER_API_KEY_HERE",
        "YOUR_TOKENROUTER_API_KEY_HERE",
    }
)

# Legacy env model names → TokenRouter OpenAI-compatible API model ids
TOKENROUTER_MODEL_ALIASES = {
    "minimax-v3": "MiniMax-M3",
    "minimax_m3": "MiniMax-M3",
}


class LlmProvider(str, Enum):
    tokenrouter = "tokenrouter"
    openrouter = "openrouter"
    kimi = "kimi"


def _is_real_key(key: str) -> bool:
    return bool(key) and key not in PLACEHOLDER_LLM_KEYS and not key.startswith("YOUR_")


def _provider() -> LlmProvider:
    try:
        return LlmProvider(get_settings().llm_provider.lower())
    except ValueError:
        return LlmProvider.tokenrouter


def llm_configured() -> bool:
    settings = get_settings()
    provider = _provider()
    if provider == LlmProvider.kimi:
        return _is_real_key(settings.kimi_api_key)
    if provider == LlmProvider.openrouter:
        return _is_real_key(settings.openrouter_api_key)
    return _is_real_key(settings.tokenrouter_api_key)


def _resolve_tokenrouter_model(model: str) -> str:
    key = model.strip()
    return TOKENROUTER_MODEL_ALIASES.get(key.lower(), key)


def active_llm_model() -> str:
    settings = get_settings()
    provider = _provider()
    if provider == LlmProvider.kimi:
        return settings.kimi_model
    if provider == LlmProvider.openrouter:
        return settings.openrouter_model
    return _resolve_tokenrouter_model(settings.tokenrouter_model)


def _strip_json_fence(text: str) -> str:
    stripped = text.strip()
    stripped = re.sub(
        r"<[^>]*thinking[^>]*>.*?</[^>]*thinking[^>]*>",
        "",
        stripped,
        flags=re.I | re.S,
    )
    stripped = stripped.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    return stripped.strip()


def _extract_json_text(raw: str) -> str:
    cleaned = _strip_json_fence(raw)
    try:
        json.loads(cleaned)
        return cleaned
    except json.JSONDecodeError:
        pass
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start >= 0 and end > start:
        candidate = cleaned[start : end + 1]
        try:
            json.loads(candidate)
            return candidate
        except json.JSONDecodeError:
            pass
    start = cleaned.find("[")
    end = cleaned.rfind("]")
    if start >= 0 and end > start:
        candidate = cleaned[start : end + 1]
        try:
            json.loads(candidate)
            return candidate
        except json.JSONDecodeError:
            pass
    return cleaned


def _chat_complete_json(
    base_url: str,
    api_key: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    extra_headers: dict[str, str] | None = None,
) -> str:
    settings = get_settings()
    client = OpenAI(
        base_url=base_url,
        api_key=api_key,
        default_headers=extra_headers or {},
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    common = {
        "model": model,
        "messages": messages,
        "temperature": 0.1,
        "max_tokens": settings.llm_max_output_tokens,
    }

    try:
        response = client.chat.completions.create(
            **common,
            response_format={"type": "json_object"},
        )
    except Exception as e:
        logger.warning(
            "LLM json_object mode failed (%s), retrying without response_format",
            type(e).__name__,
        )
        try:
            response = client.chat.completions.create(**common)
        except Exception:
            logger.exception("LLM chat completion failed base_url=%s model=%s", base_url, model)
            raise

    return response.choices[0].message.content or "{}"


def _complete_via_tokenrouter(system_prompt: str, user_prompt: str) -> str:
    settings = get_settings()
    model = _resolve_tokenrouter_model(settings.tokenrouter_model)
    logger.debug(
        "TokenRouter OpenAI-compatible request base_url=%s model=%s key=%s",
        settings.tokenrouter_base_url,
        model,
        key_prefix_hint(settings.tokenrouter_api_key),
    )
    try:
        return _chat_complete_json(
            base_url=settings.tokenrouter_base_url,
            api_key=settings.tokenrouter_api_key,
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
    except Exception:
        logger.exception(
            "TokenRouter API error base_url=%s model=%s key=%s",
            settings.tokenrouter_base_url,
            model,
            key_prefix_hint(settings.tokenrouter_api_key),
        )
        raise


def _complete_via_openrouter(system_prompt: str, user_prompt: str) -> str:
    settings = get_settings()
    return _chat_complete_json(
        base_url=settings.openrouter_base_url,
        api_key=settings.openrouter_api_key,
        model=settings.openrouter_model,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        extra_headers={
            "HTTP-Referer": settings.openrouter_http_referer,
            "X-Title": settings.openrouter_app_title,
        },
    )


def _complete_via_kimi(system_prompt: str, user_prompt: str) -> str:
    settings = get_settings()
    return _chat_complete_json(
        base_url=settings.kimi_base_url,
        api_key=settings.kimi_api_key,
        model=settings.kimi_model,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
    )


def complete_json(system_prompt: str, user_prompt: str) -> str:
    provider = _provider()
    model = active_llm_model()
    if not llm_configured():
        logger.error("LLM not configured for provider=%s", provider.value)
        raise RuntimeError(f"LLM not configured for provider={provider.value}")

    logger.debug(
        "LLM complete_json provider=%s model=%s prompt_chars=%d",
        provider.value,
        model,
        len(user_prompt),
    )

    try:
        if provider == LlmProvider.kimi:
            return _complete_via_kimi(system_prompt, user_prompt)
        if provider == LlmProvider.openrouter:
            return _complete_via_openrouter(system_prompt, user_prompt)
        return _complete_via_tokenrouter(system_prompt, user_prompt)
    except Exception as e:
        logger.error("LLM complete_json failed provider=%s model=%s: %s", provider.value, model, e)
        raise


def parse_json_object(raw: str) -> dict | list:
    try:
        return json.loads(_extract_json_text(raw))
    except json.JSONDecodeError as e:
        logger.error("LLM response JSON parse failed: %s preview=%s", e, raw[:200])
        raise
