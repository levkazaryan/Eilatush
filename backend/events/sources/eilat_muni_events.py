"""eilat.muni.il/events/ — municipality events hub.

The page renders server-side but strict bot-protection requires a desktop
browser UA + Google Referer. Many items point back to Smarticket; we still
ingest them as they sometimes carry unique municipal activities too.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone, timedelta
from typing import List, Optional

from bs4 import BeautifulSoup

from ..base import HEADERS, TIMEOUT, EventDict, pack

URL = "https://www.eilat.muni.il/events/"
_SRC = "eilat_muni"
IST = timezone(timedelta(hours=2))
log = logging.getLogger(__name__)

_HE_DAY = re.compile(r"יום\s+(ראשון|שני|שלישי|רביעי|חמישי|שישי|שבת)\s*,?\s*")


def _parse_dt(txt: str) -> Optional[datetime]:
    m = re.search(
        r"(\d{1,2})[./](\d{1,2})[./](20\d{2})(?:\s+(\d{1,2}):(\d{2}))?", txt
    )
    if not m:
        return None
    d, mo, y = int(m[1]), int(m[2]), int(m[3])
    h = int(m[4]) if m[4] else 20
    mi = int(m[5]) if m[5] else 0
    try:
        return datetime(y, mo, d, h, mi, tzinfo=IST).astimezone(timezone.utc)
    except Exception:
        return None


async def scrape_eilat_muni_events(client) -> List[EventDict]:
    try:
        r = await client.get(URL, headers=HEADERS, timeout=TIMEOUT, follow_redirects=False)
    except Exception as e:
        log.warning("muni fetch: %s", e)
        return []
    if r.status_code != 200:
        log.warning("muni status %d", r.status_code)
        return []
    soup = BeautifulSoup(r.text, "html.parser")
    results: List[EventDict] = []
    # event anchors link either to /events/<id> or to smarticket
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not ("event" in href.lower()):
            continue
        if any(x in href for x in ["#", "calendar"]):
            continue
        text = a.get_text(" ", strip=True)
        if not text or len(text) < 15:
            continue
        # text looks like:  "הצגה - הדבר העגול הזה יום שלישי, 28.04.2026 17:00 תיאטרונצ'יק לפרטים נוספים"
        cleaned = _HE_DAY.sub("", text)
        cleaned = cleaned.replace("לפרטים נוספים", "").strip()
        dt = _parse_dt(cleaned)
        if not dt:
            continue
        # split on the date portion to get title + venue
        parts = re.split(r"\d{1,2}[./]\d{1,2}[./]20\d{2}(?:\s+\d{1,2}:\d{2})?", cleaned, maxsplit=1)
        title = parts[0].strip(" -,\t") if parts else cleaned[:80]
        venue = parts[1].strip(" -,\t") if len(parts) > 1 else None
        if len(title) < 4:
            continue
        link = href if href.startswith("http") else "https://www.eilat.muni.il" + href.lstrip(".")
        results.append(
            pack(
                source=_SRC,
                ext_id=link,
                title=title,
                starts_at=dt,
                venue=venue,
                link=link,
            )
        )
    log.info("eilat_muni → %d events", len(results))
    return results
