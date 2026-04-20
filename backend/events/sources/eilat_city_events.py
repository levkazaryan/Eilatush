"""eilat.city/events — listing of community / sport events.

Cards are linked via ``/event/<slug>``. We fetch the listing page and each
individual event page to extract date, venue and image.
"""
from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timezone, timedelta
from typing import List, Optional

from bs4 import BeautifulSoup

from ..base import HEADERS, TIMEOUT, EventDict, pack

BASE = "https://eilat.city"
LIST_URL = f"{BASE}/events"
_SRC = "eilat_city"
IST = timezone(timedelta(hours=2))
log = logging.getLogger(__name__)

_HE_MONTHS = {
    "ינואר": 1, "פברואר": 2, "מרץ": 3, "מרס": 3, "אפריל": 4,
    "מאי": 5, "יוני": 6, "יולי": 7, "אוגוסט": 8,
    "ספטמבר": 9, "אוקטובר": 10, "נובמבר": 11, "דצמבר": 12,
}


def _parse_date(text: str) -> Optional[datetime]:
    """Parse strings like '08.05.2026', '08/05/2026 20:00', '8 במאי 2026 20:00'."""
    if not text:
        return None
    t = text.strip()
    # dd.mm.yyyy [HH:MM]
    m = re.search(r"(\d{1,2})[./](\d{1,2})[./](20\d{2})(?:[ ,]+(\d{1,2}):(\d{2}))?", t)
    if m:
        day, month, year = int(m[1]), int(m[2]), int(m[3])
        hour = int(m[4]) if m[4] else 20
        minute = int(m[5]) if m[5] else 0
        try:
            dt = datetime(year, month, day, hour, minute, tzinfo=IST)
            return dt.astimezone(timezone.utc)
        except Exception:
            return None
    # Hebrew month
    m = re.search(r"(\d{1,2})\s+ב?(" + "|".join(_HE_MONTHS) + r")\s+(20\d{2})", t)
    if m:
        day, month, year = int(m[1]), _HE_MONTHS[m[2]], int(m[3])
        hm = re.search(r"(\d{1,2}):(\d{2})", t)
        hour, minute = (int(hm[1]), int(hm[2])) if hm else (20, 0)
        try:
            return datetime(year, month, day, hour, minute, tzinfo=IST).astimezone(timezone.utc)
        except Exception:
            return None
    return None


async def _fetch_detail(client, href: str) -> dict:
    try:
        r = await client.get(href, headers=HEADERS, timeout=TIMEOUT)
        if r.status_code != 200:
            return {}
    except Exception:
        return {}
    soup = BeautifulSoup(r.text, "html.parser")
    title_el = soup.find(["h1", "h2"])
    img_el = soup.find("meta", property="og:image") or soup.find("img")
    img = None
    if img_el:
        img = img_el.get("content") or img_el.get("src") or img_el.get("data-src")
        if img:
            # guard against the site's rendered "../eventItem/<eventItem-URL>" double-prefix
            if img.count("http") > 1:
                img = "http" + img.rsplit("http", 1)[1]
            if img.startswith("//"):
                img = "https:" + img
            elif img.startswith("/"):
                img = BASE + img
    body_text = soup.get_text(" ", strip=True)
    return {
        "title": title_el.get_text(strip=True) if title_el else "",
        "image": img,
        "text": body_text,
    }


async def scrape_eilat_city_events(client) -> List[EventDict]:
    try:
        r = await client.get(LIST_URL, headers=HEADERS, timeout=TIMEOUT)
    except Exception as e:
        log.warning("eilat.city list fail: %s", e)
        return []
    if r.status_code != 200:
        return []
    soup = BeautifulSoup(r.text, "html.parser")
    seen: set[str] = set()
    hrefs: list[str] = []
    for a in soup.find_all("a", href=True):
        h = a["href"]
        if "/event/" in h and h not in seen:
            seen.add(h)
            hrefs.append(h if h.startswith("http") else BASE + h)

    tasks = [_fetch_detail(client, h) for h in hrefs[:30]]
    details = await asyncio.gather(*tasks, return_exceptions=True)

    results: List[EventDict] = []
    for href, det in zip(hrefs, details):
        if isinstance(det, Exception) or not isinstance(det, dict):
            continue
        title = det.get("title") or ""
        text = det.get("text") or ""
        if not title:
            continue
        start = _parse_date(text)
        if not start:
            continue
        # venue is often the last line after a time pattern
        venue = None
        m_v = re.search(r"\d{1,2}:\d{2}\s+([^\n\r]{4,80})", text)
        if m_v:
            venue = m_v.group(1).strip()
        results.append(
            pack(
                source=_SRC,
                ext_id=href,
                title=title,
                starts_at=start,
                venue=venue,
                link=href,
                image=det.get("image"),
            )
        )
    log.info("eilat.city/events → %d events", len(results))
    return results
