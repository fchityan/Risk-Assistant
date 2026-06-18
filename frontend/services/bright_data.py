import os
from urllib.parse import quote_plus

import httpx

from env_shared import load_shared_env

load_shared_env()

REQUEST_URL = "https://api.brightdata.com/request"


def _api_key() -> str:
    return (os.getenv("BRIGHT_DATA_API_KEY") or os.getenv("BRIGHTDATA_API_KEY") or "").strip()


def _serp_zone() -> str:
    return (os.getenv("BRIGHT_DATA_SERP_ZONE") or "").strip()


def bright_data_configured() -> bool:
    return bool(_api_key()) and bool(_serp_zone())


def _google_search_url(query: str, gl: str = "sg", hl: str = "en", num_results: int = 8) -> str:
    return f"https://www.google.com/search?q={quote_plus(query)}&hl={hl}&gl={gl}&num={num_results}"


def _parse_results(payload: dict | list) -> list[dict]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload.get("organic"), list):
        return payload["organic"]
    if isinstance(payload.get("results"), list):
        return payload["results"]
    return []


def collect_public_data(subject_name: str, country: str):
    """Collect public web evidence using Bright Data SERP API with mock fallback."""
    if not bright_data_configured():
        return [
            {
                "sourceType": "Company Website",
                "sourceName": "Mock company website",
                "sourceUrl": "https://example.com/company",
                "sourceSnippet": f"{subject_name} appears as a company operating in {country}."
            },
            {
                "sourceType": "Public Review Page",
                "sourceName": "Mock review page",
                "sourceUrl": "https://example.com/reviews",
                "sourceSnippet": "Several public reviews mention delayed responses and communication issues."
            },
            {
                "sourceType": "Public Web Search",
                "sourceName": "Mock public search result",
                "sourceUrl": "https://example.com/search",
                "sourceSnippet": "A similarly named entity appears in another jurisdiction."
            }
        ]

    query_parts = [f'"{subject_name}"']
    if country:
        query_parts.append(country)
    query_parts.append("adverse OR lawsuit OR sanction OR fraud OR investigation")
    query = " ".join(query_parts)

    payload = {
        "zone": _serp_zone(),
        "url": _google_search_url(query),
        "format": "raw",
        "data_format": "parsed_light",
    }
    headers = {
        "Authorization": f"Bearer {_api_key()}",
        "Content-Type": "application/json",
    }

    try:
        response = httpx.post(REQUEST_URL, headers=headers, json=payload, timeout=40)
        if response.status_code != 200:
            raise RuntimeError(f"SERP request failed: HTTP {response.status_code}")

        data = response.json()
        results = _parse_results(data)
        if not results:
            return []

        items: list[dict] = []
        for result in results[:10]:
            url = result.get("link") or result.get("url") or ""
            title = result.get("title") or "Public web result"
            snippet = result.get("snippet") or result.get("description") or ""
            if not url and not snippet:
                continue
            items.append(
                {
                    "sourceType": "Public Web Search",
                    "sourceName": title,
                    "sourceUrl": url,
                    "sourceSnippet": snippet,
                }
            )
        return items
    except Exception:
        return [
            {
                "sourceType": "Public Web Search",
                "sourceName": "Bright Data fallback",
                "sourceUrl": "https://brightdata.com",
                "sourceSnippet": "Live Bright Data query failed. Showing fallback evidence for continuity.",
            }
        ]
