"""Smarticket (tickets.co.il) events scraper."""
from __future__ import annotations
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin
import httpx
from bs4 import BeautifulSoup

from ..base import _fetch, _strip, _make_article, _contains_eilat, log

async def scrape_smarticket(client: httpx.AsyncClient) -> List[Dict[str, Any]]:
    base = "https://eilatmuni.smarticket.co.il"
    html = await _fetch(client, base)
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    out: List[Dict[str, Any]] = []
    seen = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/event/" not in href:
            continue
        full = urljoin(base, href)
        if full in seen:
            continue
        seen.add(full)
        title = _strip(a.get_text()) or "אירוע"
        img_tag = a.find("img")
        img = urljoin(base, img_tag["src"]) if img_tag and img_tag.get("src") else None
        out.append(
            _make_article(
                title=title,
                summary=title,
                content_html=f'<p>{title}</p><p><a href="{full}">פרטים ורכישת כרטיסים</a></p>',
                image=img,
                source_name="אירועים — עיריית אילת",
                source_url=full,
                published_at=None,
                source_type="event",
            )
        )
        if len(out) >= 12:
            break
    return out


# ---------------------------------------------------------------------------
# Ynet — Eilat topic
# ---------------------------------------------------------------------------
