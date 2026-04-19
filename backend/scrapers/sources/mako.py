"""Mako — Eilat tag page scraper (li-card based)."""
from __future__ import annotations
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin
import httpx
from bs4 import BeautifulSoup

from ..base import _fetch, _pw_fetch, _strip, _make_article, _contains_eilat, log
from ..enrichment import _enrich_dates

async def scrape_mako_eilat(client: httpx.AsyncClient) -> List[Dict[str, Any]]:
    """Mako — scrape the Eilat tag page.

    Mako lays out each article inside a `<li>` card inside
    `<div class="itemsWrap"> <ul> <li>…</li> </ul> </div>`. The card text
    follows the pattern:

        "<TITLE> [<category>] <DD.MM.YY> זמן קריאה: <N> דק'"

    The previous implementation walked up the DOM and picked the LARGEST
    text in the ancestor chain, which often landed on a container holding
    several cards — hence identical concatenated titles across different
    articles. Scoping to the `<li>` card + stripping the date/read-time
    suffix fixes that.
    """
    url = "https://www.mako.co.il/Tagit/%D7%90%D7%99%D7%9C%D7%AA"
    html = await _pw_fetch(url) or await _fetch(client, url)
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    out: List[Dict[str, Any]] = []
    seen: set = set()

    cards = soup.select("div.itemsWrap ul li, div[class*=itemsWrap] ul li")

    # Strip trailing "<category> DD.MM.YY זמן קריאה: N דק'"
    # and other noise tails that Mako appends after the real title.
    _TAIL_RE = re.compile(
        r"\s*(?:חופש|ספורט|מזג\s*אויר|טכנולוגיה|בריאות|אוכל|תרבות|בידור|"
        r"חדשות|נדל\"?ן|כלכלה|רכב|צרכנות|נשים|גברים|טיולים|דעות)?\s*"
        r"\d{1,2}[./-]\d{1,2}[./-]\d{2,4}.*$",
        re.S,
    )
    _READ_TIME_RE = re.compile(r"\s*זמן\s*קריאה.*$", re.S)

    def _clean_title(t: str) -> str:
        t = _READ_TIME_RE.sub("", t)
        t = _TAIL_RE.sub("", t)
        return _strip(t).rstrip(" |-–—:,")

    for li in cards:
        link_el = None
        for a in li.find_all("a", href=True):
            href = a["href"]
            if "/Article-" in href or "/news/" in href:
                link_el = a
                break
        if not link_el:
            continue
        full = urljoin("https://www.mako.co.il", link_el["href"].split("#")[0])
        if full in seen:
            continue
        # Skip obvious nav/help links
        low = full.lower()
        if any(seg in low for seg in ("/help-", "/spirituality-popular_culture",
                                       "/mako-weather", "/mako-social")):
            continue

        card_text = _strip(li.get_text(" "))
        if len(card_text) < 10:
            continue
        title = _clean_title(card_text)
        if not title or len(title) < 8:
            continue

        img_tag = li.find("img")
        img = None
        if img_tag:
            img = img_tag.get("src") or img_tag.get("data-src")
            if img and img.startswith("//"):
                img = "https:" + img

        seen.add(full)
        out.append(
            _make_article(
                title=title[:250],
                summary=title[:300],
                content_html=f'<p>{title}</p><p><a href="{full}">קרא את הכתבה המלאה ב-Mako</a></p>',
                image=img,
                source_name="Mako",
                source_url=full,
                published_at=None,
                source_type="news",
            )
        )
        if len(out) >= 25:
            break

    await _enrich_dates(client, out, use_browser=True, concurrency=3)

    # Same post-scrape filters we apply in _scrape_tag_page: drop anything
    # that isn't clearly Eilat-focused (Eilat must appear in title or the
    # first 300 chars of summary/body).
    kept: List[Dict[str, Any]] = []
    for a in out:
        title = a.get("title", "") or ""
        summary = a.get("summary", "") or ""
        body_head = a.get("_body_head", "") or ""
        if not (
            _contains_eilat(title)
            or _contains_eilat(summary[:300])
            or _contains_eilat(body_head[:300])
        ):
            log.info("dropping off-topic Mako (Eilat not near top): %s", title[:60])
            continue
        a.pop("_body_head", None)
        kept.append(a)
    return kept


# ---------------------------------------------------------------------------
# Generic simple page scrapers (short descriptive pages)
# ---------------------------------------------------------------------------
