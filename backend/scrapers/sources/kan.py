"""Kan 11 scraper + image-fetch-via-Playwright helpers (their CDN blocks the app)."""
from __future__ import annotations
import asyncio
import base64 as _b64
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse
import httpx
from bs4 import BeautifulSoup

from ..base import _fetch, _pw_fetch, _PW_CTX, _strip, _make_article, _contains_eilat, log
from ..enrichment import _enrich_dates

async def _pw_fetch_bytes(url: str, timeout_ms: int = 15000) -> Optional[bytes]:
    """Fetch raw bytes (e.g. image) through headless Chromium to bypass bot
    blocks on CDNs that 403 regular httpx requests."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return None
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled"],
            )
            ctx = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 720},
            )
            page = await ctx.new_page()
            try:
                resp = await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
                if not resp or resp.status >= 400:
                    return None
                return await resp.body()
            finally:
                await browser.close()
    except Exception:
        return None


async def _fetch_image_as_data_uri(url: str) -> Optional[str]:
    """For restricted image hosts (like kan.org.il which returns 403 to httpx),
    fetch bytes via Playwright and return as `data:image/...;base64,...` URI."""
    body = await _pw_fetch_bytes(url)
    if not body:
        return None
    mime = "image/jpeg"
    if body[:8] == b"\x89PNG\r\n\x1a\n":
        mime = "image/png"
    elif body[:6] in (b"GIF87a", b"GIF89a"):
        mime = "image/gif"
    elif body[:4] == b"RIFF" and body[8:12] == b"WEBP":
        mime = "image/webp"
    import base64 as _b64
    return f"data:{mime};base64,{_b64.b64encode(body).decode()}"



async def scrape_kan_eilat(client: httpx.AsyncClient) -> List[Dict[str, Any]]:
    """Kan — Eilat tag page (requires stealth browser)."""
    tag_url = "https://www.kan.org.il/tags/generaltags/%D7%90%D7%99%D7%9C%D7%AA/"
    html = await _pw_fetch(tag_url)
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    out: List[Dict[str, Any]] = []
    seen = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        full = urljoin("https://www.kan.org.il", href)
        # Kan article URLs live under /content/kan-news/
        if "/content/kan-news/" not in full:
            continue
        if full in seen:
            continue
        title = _strip(a.get_text())
        if len(title) < 10:
            continue
        # walk up to enrich context if needed
        if not _contains_eilat(title):
            node = a
            ctx = title
            for _ in range(4):
                if node is None:
                    break
                t = _strip(node.get_text())
                if len(t) > len(ctx):
                    ctx = t
                node = node.parent
            if not _contains_eilat(ctx):
                # Since we're on the Eilat tag page, treat listed links as Eilat-related
                # even without explicit keyword in title, but prefer ones we're sure about
                pass
        img_tag = a.find("img")
        img = img_tag.get("src") if img_tag else None
        if img:
            img = urljoin("https://www.kan.org.il", img)
        seen.add(full)
        out.append(
            _make_article(
                title=title,
                summary=title,
                content_html=f'<p>{title}</p><p><a href="{full}">קרא/צפה בכתבה המלאה בכאן חדשות</a></p>',
                image=img,
                source_name="כאן חדשות",
                source_url=full,
                published_at=None,
                source_type="news",
            )
        )
        if len(out) >= 25:
            break
    # Kan article pages return 403 to httpx — use Playwright to fetch each
    # article for date + og:image extraction.
    await _enrich_dates(client, out, use_browser=True, concurrency=3)
    # Kan's image CDN also 403s httpx. Convert image URLs to inline data URIs
    # by fetching via Playwright (serial to stay light on resources).
    for a in out:
        img = a.get("image")
        if img and img.startswith("http") and "kan.org.il" in img:
            data_uri = await _fetch_image_as_data_uri(img)
            if data_uri:
                a["image"] = data_uri
    return out


# ---------------------------------------------------------------------------
# Israel Hayom — Eilat tag
# ---------------------------------------------------------------------------
