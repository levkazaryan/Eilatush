"""Ynet — Eilat topic page scraper (slotView-based)."""
from __future__ import annotations
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin
import httpx
import feedparser
from bs4 import BeautifulSoup

from ..base import _fetch, _pw_fetch, _strip, _make_article, _contains_eilat, log
from ..enrichment import _enrich_dates

YNET_RSS_CANDIDATES = [
    "https://www.ynet.co.il/Integration/StoryRss1854.xml",
    "https://www.ynet.co.il/Integration/StoryRss2.xml",
]


async def scrape_ynet_eilat(client: httpx.AsyncClient) -> List[Dict[str, Any]]:
    """Ynet — scrape the Eilat topic page (requires stealth browser).

    Ynet lays out each article inside a `<div class="slotView">` card. Inside
    the card we have:
      - `<div class="slotTitle">` → the article title (unique per card)
      - a second `<div class="title">` → the article subtitle/summary
      - one or more `<a href="…/article/…">` links → the article URL
      - an `<img src>` → the article image
    The previous implementation iterated over anchors and walked up the DOM to
    find a title, which caused all cards to share the same title (first h2 in
    a common ancestor). Scoping to the slotView card fixes that completely.
    """
    topic_url = "https://www.ynet.co.il/topics/%D7%90%D7%99%D7%9C%D7%AA"
    html = await _pw_fetch(topic_url)
    if not html:
        html = await _fetch(client, topic_url)
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    out: List[Dict[str, Any]] = []
    seen: set = set()

    cards = soup.find_all("div", class_=lambda c: c and "slotView" in c)
    for card in cards:
        # URL: first anchor that points to an article
        link_el = None
        for a in card.find_all("a", href=True):
            if "/article/" in a["href"]:
                link_el = a
                break
        if not link_el:
            continue
        raw_href = link_el["href"].split("#")[0]
        full = urljoin("https://www.ynet.co.il", raw_href)
        if full in seen:
            continue

        # Title: prefer slotTitle, then first .title, then first h2/h3
        title = ""
        slot_title = card.find(class_=lambda c: c and "slotTitle" in c)
        if slot_title:
            title = _strip(slot_title.get_text())
        if not title:
            title_divs = card.find_all(class_=lambda c: c and "title" in c.lower())
            for td in title_divs:
                t = _strip(td.get_text())
                if t and 8 <= len(t) <= 250:
                    title = t
                    break
        if not title:
            for tag_name in ("h2", "h3", "h1"):
                el = card.find(tag_name)
                if el:
                    t = _strip(el.get_text())
                    if t:
                        title = t
                        break
        if not title or len(title) < 8:
            continue

        # Summary: look for a second .title div (Ynet's subTitle), else fallback
        summary = ""
        title_divs = card.find_all(class_=lambda c: c and "title" in c.lower())
        for td in title_divs:
            t = _strip(td.get_text())
            if t and t != title and 20 <= len(t) <= 500:
                summary = t
                break
        if not summary:
            summary = title[:280]

        # Eilat relevance filter (applied to title+summary)
        combined_text = f"{title} {summary}"
        if not _contains_eilat(combined_text):
            continue

        # Image
        img = None
        img_tag = card.find("img")
        if img_tag:
            img = img_tag.get("src") or img_tag.get("data-src")
            if img and img.startswith("//"):
                img = "https:" + img

        seen.add(full)
        out.append(
            _make_article(
                title=title,
                summary=summary[:300],
                content_html=f'<p>{summary or title}</p><p><a href="{full}">קרא את הכתבה המלאה ב-Ynet</a></p>',
                image=img,
                source_name="Ynet",
                source_url=full,
                published_at=None,
                source_type="news",
            )
        )
        if len(out) >= 25:
            break

    # Fallback: if the slotView-based scrape yielded nothing (e.g. layout
    # change), try a very conservative anchor-based fallback using only the
    # anchor-local title text (no DOM walking → no cross-article bleed).
    if not out:
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/article/" not in href:
                continue
            full = urljoin("https://www.ynet.co.il", href.split("#")[0])
            if full in seen:
                continue
            title = _strip(a.get_text())
            if len(title) < 10 or not _contains_eilat(title):
                continue
            img_tag = a.find("img")
            img = img_tag.get("src") if img_tag else None
            if img and img.startswith("//"):
                img = "https:" + img
            seen.add(full)
            out.append(
                _make_article(
                    title=title,
                    summary=title[:300],
                    content_html=f'<p>{title}</p><p><a href="{full}">קרא את הכתבה המלאה ב-Ynet</a></p>',
                    image=img,
                    source_name="Ynet",
                    source_url=full,
                    published_at=None,
                    source_type="news",
                )
            )
            if len(out) >= 25:
                break

    await _enrich_dates(client, out, use_browser=False, concurrency=5)
    return out

