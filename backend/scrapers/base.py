"""Shared primitives: HTTP fetching (httpx + Playwright), primitive text
helpers, and _make_article record builder. Every source scraper depends
on these.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from dateutil import parser as dtparse

log = logging.getLogger("scrapers")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "he-IL,he;q=0.9,en;q=0.8",
}

TIMEOUT = httpx.Timeout(20.0, connect=10.0)


def _hash_url(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:20]


def _dt_parse(val: str) -> datetime:
    """Parse a date string. Use dayfirst=True only for non-ISO formats
    (Israeli sources often use DD/MM/YYYY)."""
    s = str(val).strip()
    # ISO 8601 always starts with 4-digit year
    is_iso = bool(re.match(r"^\d{4}[-/]", s))
    return dtparse.parse(s, dayfirst=not is_iso)


def _parse_date(val: Any) -> datetime:
    if not val:
        return datetime.now(timezone.utc)
    if isinstance(val, datetime):
        return val if val.tzinfo else val.replace(tzinfo=timezone.utc)
    try:
        dt = _dt_parse(val)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)


def _contains_eilat(text: str) -> bool:
    if not text:
        return False
    t = text.lower()
    return "אילת" in text or "eilat" in t or "עיריית אילת" in text


def _strip(s: Optional[str]) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())

async def _fetch(client: httpx.AsyncClient, url: str) -> Optional[str]:
    try:
        r = await client.get(url, timeout=TIMEOUT, follow_redirects=True)
        r.raise_for_status()
        return r.text
    except Exception as e:
        log.warning("fetch failed %s: %s", url, e)
        return None


# Cache a single Playwright browser per process — reused across fetches.
_PW_CTX: Dict[str, Any] = {"browser": None, "pw": None, "lock": asyncio.Lock()}


async def _pw_fetch(url: str) -> Optional[str]:
    """Fetch a URL via headless Chromium + stealth patches. Used for sites that
    block httpx/bots (kan, gov.il, tiuli, etc.). Renders JS and returns final HTML."""
    try:
        from playwright.async_api import async_playwright
    except Exception as e:
        log.warning("playwright not installed: %s", e)
        return None
    # stealth patches (anti-detection for headless Chromium)
    try:
        from playwright_stealth import Stealth  # type: ignore
        stealth = Stealth()
    except Exception:
        stealth = None
    async with _PW_CTX["lock"]:
        if _PW_CTX["browser"] is None:
            try:
                pw = await async_playwright().start()
                browser = await pw.chromium.launch(
                    headless=True,
                    args=[
                        "--no-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-blink-features=AutomationControlled",
                        "--disable-features=IsolateOrigins,site-per-process",
                    ],
                )
                _PW_CTX["pw"] = pw
                _PW_CTX["browser"] = browser
            except Exception as e:
                log.warning("playwright launch failed: %s", e)
                return None
    browser = _PW_CTX["browser"]
    context = None
    try:
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="he-IL",
            timezone_id="Asia/Jerusalem",
            viewport={"width": 1366, "height": 820},
            ignore_https_errors=True,
        )
        if stealth is not None:
            try:
                await stealth.apply_stealth_async(context)
            except Exception as e:
                log.debug("stealth apply failed: %s", e)
        page = await context.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            # Wait for SPA content to hydrate — required for Kan, Gov.il, Tiuli
            try:
                await page.wait_for_load_state("networkidle", timeout=12000)
            except Exception:
                pass
            await page.wait_for_timeout(4000)
            html = await page.content()
            return html
        except Exception as e:
            log.warning("pw nav failed %s: %s", url, e)
            return None
    except Exception as e:
        log.warning("pw context failed %s: %s", url, e)
        return None
    finally:
        if context is not None:
            try:
                await context.close()
            except Exception:
                pass


async def _fetch_smart(client: httpx.AsyncClient, url: str, use_browser: bool = False) -> Optional[str]:
    """Try fast httpx first; fall back to Playwright on failure or when use_browser=True."""
    if not use_browser:
        html = await _fetch(client, url)
        if html:
            return html
    # use browser fallback
    return await _pw_fetch(url)


def _make_article(
    title: str,
    summary: str,
    content_html: str,
    image: Optional[str],
    source_name: str,
    source_url: str,
    published_at: Optional[datetime],
    source_type: str = "news",
) -> Dict[str, Any]:
    return {
        "id": _hash_url(source_url),
        "title": _strip(title)[:300],
        "summary": _strip(summary)[:1500],
        "content_html": content_html or "",
        "image": image or None,
        "source_name": source_name,
        "source_url": source_url,
        "source_type": source_type,  # "news" | "event" | "alert"
        "published_at": published_at,
        "fetched_at": datetime.now(timezone.utc),
    }


# ---------------------------------------------------------------------------
# Eilat Municipality
# ---------------------------------------------------------------------------
