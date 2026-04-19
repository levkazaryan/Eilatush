"""Hamal (hamal.co.il) — independent war/security coverage.

The homepage surfaces roughly 25 articles inside `<article class="styles_article__…">`
cards. Each card contains:

    HH:MM  -  <relative time>   <author/source>   <TITLE>   <preview>   להמשך קריאה >

We parse the textual layout with regex (the class names are hashed by the
Next.js CSS-modules build), extract the article link (/main/<slug>-<id>), the
thumbnail image, and only keep cards that mention Eilat.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from ..base import _fetch, _pw_fetch, _strip, _make_article, _contains_eilat, log
from ..enrichment import _enrich_dates


# Cards start with:   "HH:MM - <relative time>  <author label>  <TITLE> | <body>"
# We strip each chunk in turn to isolate the title.
_TIME_RE     = re.compile(r"^\s*\d{1,2}:\d{2}\s*[-–—]\s*")
_RELTIME_RE  = re.compile(
    r"^(?:לפני\s*(?:שעה|כשעה|שעתיים|\d+\s*(?:שעות|דק(?:ות|')?|שנים|ימים)|רגע\s*קט|"
    r"זמן\s*קצר)|עכשיו|אתמול|היום)\s+"
)
# Author / source bylines typed on Hamal. Be conservative — match only the
# well-known labels rather than any Hebrew word to avoid eating the real title.
_AUTHOR_RE = re.compile(
    r"^(?:מערכת\s*חמ(?:[\"״׳\u05f4]|''|'')?ל|"
    r"מערכת\s*חמל|"
    r"עודכן(?:\s+ב)?:?|"
    r"מאת:?|"
    r"פורסם|"
    r"מדווח:?|"
    r"תגובה)\s+"
)
# End markers: "להמשך קריאה" / "Video Player is loading" / split on " | " too.
_TAIL_RE = re.compile(
    r"(?:להמשך\s*קריאה.*|Video Player is loading.*)$",
    re.S,
)


def _strip_card_preamble(text: str) -> str:
    """Remove the time + relative-time + author byline from the start of a card."""
    # up to 3 passes of each prefix stripper to handle weird doubling
    for _ in range(3):
        new = _TIME_RE.sub("", text, count=1)
        new = _RELTIME_RE.sub("", new, count=1)
        new = _AUTHOR_RE.sub("", new, count=1)
        if new == text:
            break
        text = new
    return text


def _parse_card(art, base_url: str) -> Optional[Dict[str, Any]]:
    """Given a BeautifulSoup <article> node, return an _make_article() payload
    or None if we couldn't find Eilat-relevant content."""
    text = _strip(art.get_text(" "))
    if "אילת" not in text:
        return None

    # Strip the time-stamp + relative-time + author byline preamble.
    cleaned = _strip_card_preamble(text)
    # Strip trailing "להמשך קריאה…" / video-player junk
    cleaned = _TAIL_RE.sub("", cleaned).strip(" |·-–—")

    # Split into title + body via the common " | " separator
    title: str
    summary: str
    if " | " in cleaned:
        title, _, rest = cleaned.partition(" | ")
        summary = rest.strip()
    else:
        # fallback: first sentence as title, rest as summary
        parts = re.split(r"(?<=[.?!…])\s+", cleaned, maxsplit=1)
        title = parts[0]
        summary = parts[1] if len(parts) > 1 else cleaned
    title = title.strip(" |·-–—")
    summary = summary.strip(" |·-–—")

    # Filter out video-player garbage and overly short titles
    if len(title) < 10 or "Video Player" in title:
        return None
    # Skip articles whose ONLY Eilat reference was in a stripped preamble
    # (shouldn't happen given our check above, but safe)
    if not _contains_eilat(title + " " + summary):
        return None

    # Link (same href repeats several times inside the card — take the first)
    link = art.find("a", href=True)
    if not link:
        return None
    full = urljoin(base_url, link["href"].split("#")[0])

    # Image — skip the small 100×100 avatar thumbnail, prefer the hero image
    img: Optional[str] = None
    for im in art.find_all("img"):
        src = im.get("src") or im.get("data-src") or ""
        if not src:
            continue
        # Discard the avatar/icon used for the author chip
        if "512x512" in src or "?width=100" in src or "icon" in src.lower():
            continue
        img = src
        break
    if not img:
        # fallback to first img if we didn't find a hero
        fi = art.find("img")
        if fi:
            img = fi.get("src") or fi.get("data-src")
    if img and img.startswith("//"):
        img = "https:" + img

    return _make_article(
        title=title[:250],
        summary=summary[:300] if summary else title[:280],
        content_html=(
            f"<p>{summary or title}</p>"
            f'<p><a href="{full}">קרא את הכתבה המלאה ב-חמ״ל</a></p>'
        ),
        image=img,
        source_name="חמ״ל",
        source_url=full,
        # Hamal cards only show relative time ("לפני שעה"); since the homepage
        # surfaces very-recent articles we fall back to "now" when the article
        # page itself doesn't publish a concrete date.
        published_at=datetime.now(timezone.utc),
        source_type="news",
    )


async def scrape_hamal(client: httpx.AsyncClient) -> List[Dict[str, Any]]:
    base = "https://hamal.co.il"
    url = f"{base}/main"
    html = await _pw_fetch(url)
    if not html:
        html = await _fetch(client, url)
    if not html:
        return []

    soup = BeautifulSoup(html, "lxml")
    # Hamal's CSS modules hash the class name (e.g. `styles_article__Mwzjl`),
    # but the plain `<article>` tag selector works reliably.
    cards = soup.find_all("article")
    out: List[Dict[str, Any]] = []
    seen: set = set()
    for card in cards:
        try:
            item = _parse_card(card, base)
        except Exception as e:
            log.debug("hamal parse fail: %s", e)
            continue
        if not item:
            continue
        if item["source_url"] in seen:
            continue
        seen.add(item["source_url"])
        out.append(item)
        if len(out) >= 25:
            break

    await _enrich_dates(client, out, use_browser=True, concurrency=3)

    # Post-enrichment Eilat-focus filter: title OR first 300 chars of body.
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
            log.info("dropping off-topic חמ״ל (Eilat not near top): %s", title[:60])
            continue
        a.pop("_body_head", None)
        kept.append(a)
    return kept
