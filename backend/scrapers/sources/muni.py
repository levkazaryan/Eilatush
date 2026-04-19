"""Eilat Municipality scrapers (articles + "mivzak" bulletins)."""
from __future__ import annotations
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin
import httpx
from bs4 import BeautifulSoup

from ..base import _fetch, _strip, _make_article, _parse_date, log
from ..cleaners import _extract_date

async def scrape_eilat_muni_articles(client: httpx.AsyncClient) -> List[Dict[str, Any]]:
    """Municipality main articles listing."""
    base = "https://www.eilat.muni.il"
    list_url = f"{base}/articles/"
    html = await _fetch(client, list_url)
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    results: List[Dict[str, Any]] = []
    seen = set()
    # heuristic: look for links to /articles/item/<id>/
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/articles/item/" not in href:
            continue
        full = urljoin(base, href)
        if full in seen:
            continue
        seen.add(full)
        title = _strip(a.get_text())
        if not title or len(title) < 5:
            continue
        img = None
        img_tag = a.find("img")
        if img_tag and img_tag.get("src"):
            img = urljoin(base, img_tag["src"])
        results.append((full, title, img))
        if len(results) >= 15:
            break

    articles: List[Dict[str, Any]] = []
    # fetch each article for full content
    for full, title, img in results:
        art_html = await _fetch(client, full)
        content_html = ""
        summary = ""
        pub = datetime.now(timezone.utc)
        hero = img
        if art_html:
            asoup = BeautifulSoup(art_html, "lxml")
            # main content
            main = (
                asoup.find("article")
                or asoup.find("div", class_=re.compile("content|article|main", re.I))
                or asoup.find("main")
            )
            if main:
                for bad in main.find_all(["script", "style", "nav", "aside"]):
                    bad.decompose()
                content_html = str(main)
                summary = _strip(main.get_text())[:400]
            # og image
            og = asoup.find("meta", property="og:image")
            if og and og.get("content"):
                hero = urljoin(base, og["content"])
            # date
            tdate = asoup.find("time")
            if tdate:
                pub = _parse_date(tdate.get("datetime") or tdate.get_text())
        articles.append(
            _make_article(
                title=title,
                summary=summary or title,
                content_html=content_html,
                image=hero,
                source_name="עיריית אילת",
                source_url=full,
                published_at=pub,
                source_type="news",
            )
        )
    return articles


async def scrape_eilat_muni_mivzak(client: httpx.AsyncClient) -> List[Dict[str, Any]]:
    """Municipality alerts/mivzak."""
    base = "https://www.eilat.muni.il"
    list_url = f"{base}/news/"
    html = await _fetch(client, list_url)
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    out: List[Dict[str, Any]] = []
    seen = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/mivzak/" not in href:
            continue
        full = urljoin(base, href)
        if full in seen:
            continue
        seen.add(full)
        title = _strip(a.get_text())
        if len(title) < 5:
            continue
        art = await _fetch(client, full)
        content_html = ""
        summary = title
        pub = datetime.now(timezone.utc)
        hero = None
        if art:
            asoup = BeautifulSoup(art, "lxml")
            main = asoup.find("article") or asoup.find("main") or asoup.find("body")
            if main:
                for bad in main.find_all(["script", "style", "nav", "aside"]):
                    bad.decompose()
                content_html = str(main)
                summary = _strip(main.get_text())[:400]
            og = asoup.find("meta", property="og:image")
            if og and og.get("content"):
                hero = urljoin(base, og["content"])
        out.append(
            _make_article(
                title=title,
                summary=summary,
                content_html=content_html,
                image=hero,
                source_name="עיריית אילת — מבזקים",
                source_url=full,
                published_at=pub,
                source_type="alert",
            )
        )
        if len(out) >= 10:
            break
    return out


# ---------------------------------------------------------------------------
# Smarticket (events)
# ---------------------------------------------------------------------------
