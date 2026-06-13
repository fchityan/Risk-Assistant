"""Stage 2: Web data collection via Bright Data SERP API + Browser API."""

import asyncio
from datetime import datetime, timezone
from urllib.parse import quote_plus, urlparse

import httpx

from async_utils import run_coroutine_sync
from config import get_settings
from logging_config import get_logger
from source_config import get_adverse_keywords
from stages.browser_fetch import fetch_pages

logger = get_logger(__name__)

# SERP API uses the Bright Data request endpoint (zone selects the product).
REQUEST_URL = "https://api.brightdata.com/request"


def _snippet_has_adverse_keyword(text: str) -> bool:
    lower = text.lower()
    return any(kw in lower for kw in get_adverse_keywords())


def _extract_domain(url: str) -> str:
    try:
        parsed = urlparse(url)
        host = parsed.netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        return host
    except Exception:
        return ""


def _google_search_url(query: str, gl: str = "sg", hl: str = "en", num_results: int = 10) -> str:
    encoded = quote_plus(query)
    return (
        f"https://www.google.com/search?q={encoded}"
        f"&hl={hl}&gl={gl}&num={num_results}"
    )


async def _request_with_retry(
    client: httpx.AsyncClient,
    api_key: str,
    payload: dict,
    timeout: float,
) -> httpx.Response | None:
    delays = [2, 4, 8]
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    for attempt, delay in enumerate(delays):
        try:
            resp = await client.post(
                REQUEST_URL,
                headers=headers,
                json=payload,
                timeout=timeout,
            )
            if resp.status_code == 429 or resp.status_code >= 500:
                if attempt < len(delays) - 1:
                    await asyncio.sleep(delay)
                    continue
            return resp
        except (httpx.TimeoutException, httpx.RequestError):
            if attempt < len(delays) - 1:
                await asyncio.sleep(delay)
                continue
            return None
    return None


def _parse_serp_results(data: dict | list) -> list[dict]:
    if isinstance(data, list):
        return data

    for key in ("organic", "results"):
        if isinstance(data.get(key), list):
            return data[key]

    return []


async def search_serp(
    client: httpx.AsyncClient,
    query: str,
    api_key: str,
    serp_zone: str,
    num_results: int = 10,
    gl: str = "sg",
    hl: str = "en",
) -> list[dict]:
    payload = {
        "zone": serp_zone,
        "url": _google_search_url(query, gl=gl, hl=hl, num_results=num_results),
        "format": "raw",
        "data_format": "parsed_light",
    }
    resp = await _request_with_retry(client, api_key, payload, timeout=60.0)
    if resp is None:
        logger.warning("SERP request failed (no response) query=%s", query[:80])
        return []
    if resp.status_code != 200:
        logger.warning(
            "SERP request error status=%s query=%s body=%s",
            resp.status_code,
            query[:80],
            resp.text[:200],
        )
        return []

    try:
        data = resp.json()
    except Exception as e:
        logger.warning("SERP JSON parse failed query=%s error=%s", query[:80], e)
        return []

    return _parse_serp_results(data)


async def discover_candidates(name: str, num_results: int | None = None) -> list[dict]:
    """Lightweight SERP-only discovery for entity resolution (no page fetch)."""
    settings = get_settings()
    if not settings.serp_configured:
        return []

    n = num_results or settings.discovery_serp_results
    queries = [f'"{name}"', f'"{name}" company OR organization']

    async with httpx.AsyncClient() as client:
        tasks = [
            search_serp(
                client,
                q,
                settings.bright_data_serp_api_key,
                settings.bright_data_serp_zone,
                num_results=n,
            )
            for q in queries
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    seen: set[str] = set()
    items: list[dict] = []
    for result_list in results:
        if not isinstance(result_list, list):
            continue
        for result in result_list:
            url = result.get("link") or result.get("url") or ""
            if not url or url in seen:
                continue
            seen.add(url)
            title = result.get("title", "")
            snippet = result.get("snippet") or result.get("description") or ""
            items.append(
                {
                    "title": title,
                    "snippet": snippet,
                    "source_domain": _extract_domain(url),
                    "url": url,
                }
            )
    return items


async def _run_serp_queries(
    client: httpx.AsyncClient,
    search_queries: list[str],
    serp_api_key: str,
    serp_zone: str,
) -> list[dict]:
    seen_urls: set[str] = set()
    pending: list[dict] = []

    tasks = [search_serp(client, q, serp_api_key, serp_zone) for q in search_queries]
    query_results = await asyncio.gather(*tasks, return_exceptions=True)

    for query, results in zip(search_queries, query_results):
        if isinstance(results, BaseException):
            logger.warning("SERP query exception query=%s error=%s", query[:80], results)
            continue
        if not isinstance(results, list):
            continue
        for result in results:
            url = result.get("link") or result.get("url") or ""
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)

            title = result.get("title", "")
            snippet = result.get("snippet") or result.get("description") or ""
            pub_date = result.get("date") or result.get("published_date")
            needs_fetch = _snippet_has_adverse_keyword(snippet + " " + title)

            pending.append(
                {
                    "url": url,
                    "title": title,
                    "snippet": snippet,
                    "full_text": "",
                    "fetch_status": "snippet_only",
                    "source_domain": _extract_domain(url),
                    "publication_date": pub_date,
                    "query": query,
                    "needs_fetch": needs_fetch,
                }
            )

    return pending


async def collect_data(search_queries: list[str]) -> dict:
    settings = get_settings()
    serp_api_key = settings.bright_data_serp_api_key
    serp_zone = settings.bright_data_serp_zone
    browser_ready = settings.browser_configured

    if not settings.serp_configured:
        logger.warning("SERP not configured; skipping collection")
        return {
            "raw_items": [],
            "total_queries_run": len(search_queries),
            "total_results_fetched": 0,
            "collection_mode": "skipped_no_serp_config",
            "serp_configured": False,
            "browser_configured": browser_ready,
        }

    logger.info(
        "SERP collection starting queries=%d browser=%s",
        len(search_queries),
        browser_ready,
    )
    async with httpx.AsyncClient() as client:
        pending = await _run_serp_queries(client, search_queries, serp_api_key, serp_zone)

    adverse_urls = [item["url"] for item in pending if item["needs_fetch"]]
    fetched_content: dict[str, str | None] = {}

    if adverse_urls and browser_ready:
        fetched_content = await fetch_pages(adverse_urls)

    all_items: list[dict] = []
    for item in pending:
        url = item["url"]
        if item["needs_fetch"] and browser_ready:
            full_text = fetched_content.get(url)
            if full_text:
                item["full_text"] = full_text
                item["fetch_status"] = "full"
            else:
                item["fetch_status"] = "failed"
        elif item["needs_fetch"] and not browser_ready:
            item["fetch_status"] = "snippet_only"

        del item["needs_fetch"]
        all_items.append(item)

    if browser_ready and adverse_urls:
        mode = "live_serp_and_browser"
    elif adverse_urls:
        mode = "live_serp_only"
    else:
        mode = "live_serp_no_adverse"

    logger.info(
        "SERP collection done items=%d mode=%s browser_fetches=%d",
        len(all_items),
        mode,
        len(adverse_urls) if browser_ready else 0,
    )
    return {
        "raw_items": all_items,
        "total_queries_run": len(search_queries),
        "total_results_fetched": len(all_items),
        "collection_mode": mode,
        "serp_configured": True,
        "browser_configured": browser_ready,
        "browser_fetches_attempted": len(adverse_urls) if browser_ready else 0,
    }


def run_stage2(checkpoint: dict) -> dict:
    search_queries = checkpoint.get("search_queries", [])
    collection = run_coroutine_sync(collect_data(search_queries))

    return {
        "run_id": checkpoint["run_id"],
        "stage": "data_collection",
        "status": "complete",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "subject": checkpoint["subject"],
        "screening_scope": checkpoint["screening_scope"],
        **collection,
    }
