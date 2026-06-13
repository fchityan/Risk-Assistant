"""Bright Data Browser API page fetching via Playwright CDP."""

import asyncio
import re
from urllib.parse import quote

from config import get_settings
from logging_config import get_logger

logger = get_logger(__name__)


def browser_auth_ready() -> bool:
    return get_settings().browser_configured


def _html_to_text(html: str) -> str:
    text = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.I | re.S)
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


async def fetch_pages(urls: list[str], max_concurrent: int = 2) -> dict[str, str | None]:
    """Fetch page content via Browser API (Playwright over CDP)."""
    if not urls:
        return {}

    settings = get_settings()
    if not settings.browser_configured:
        logger.warning("Browser API not configured; skipping %d page fetches", len(urls))
        return {url: None for url in urls}

    logger.info("Browser fetch starting count=%d", len(urls))

    username = settings.bright_data_browser_username
    password = settings.bright_data_browser_password
    cdp_host = settings.bright_data_browser_cdp_host
    auth = f"{quote(username, safe='')}:{quote(password, safe='')}"
    endpoint = f"wss://{auth}@{cdp_host}"

    from playwright.async_api import async_playwright

    results: dict[str, str | None] = {url: None for url in urls}
    semaphore = asyncio.Semaphore(max_concurrent)

    async with async_playwright() as playwright:
        browser = await playwright.chromium.connect_over_cdp(endpoint)
        try:
            async def fetch_one(url: str) -> None:
                async with semaphore:
                    page = None
                    try:
                        page = await browser.new_page()
                        page.set_default_navigation_timeout(120000)
                        await page.goto(url, wait_until="domcontentloaded")
                        html = await page.content()
                        results[url] = _html_to_text(html)
                    except Exception as e:
                        logger.warning("Browser fetch failed url=%s error=%s", url, e)
                        results[url] = None
                    finally:
                        if page is not None:
                            await page.close()

            await asyncio.gather(*(fetch_one(url) for url in urls))
        finally:
            await browser.close()

    ok = sum(1 for v in results.values() if v)
    logger.info("Browser fetch done success=%d failed=%d", ok, len(urls) - ok)
    return results
