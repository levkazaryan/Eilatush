"""cinema-eilat.co.il — local cinema screenings schedule.

Parses the schedule page: each movie is an element with a data-id attribute
and times embedded as HH:MM. We map them to events spanning ~120 min.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone, timedelta
from typing import List

from bs4 import BeautifulSoup

from ..base import HEADERS, TIMEOUT, EventDict, pack

URL = "https://cinema-eilat.co.il/לוח-סרטים/"
_SRC = "cinema_eilat"
IST = timezone(timedelta(hours=2))
log = logging.getLogger(__name__)


async def scrape_cinema_eilat(client) -> List[EventDict]:
    try:
        r = await client.get(URL, headers=HEADERS, timeout=TIMEOUT, follow_redirects=True)
    except Exception as e:
        log.warning("cinema fetch failed: %s", e)
        return []
    if r.status_code != 200:
        return []
    soup = BeautifulSoup(r.text, "html.parser")
    results: List[EventDict] = []
    today = datetime.now(IST).date()
    venue = "קולנוע אילת"

    # Gather movie titles from H2/H3 headings that look like film names
    headings = soup.find_all(["h1", "h2", "h3"])
    seen_titles: set[str] = set()
    for h in headings:
        t = h.get_text(strip=True)
        if not t or len(t) < 2 or len(t) > 80:
            continue
        # filter non-movie headings
        if any(bad in t for bad in ["פרטי", "תפריט", "צור קשר", "הזמנ", "אודות", "עקבו", "ליצירת"]):
            continue
        if ":" in t or "@" in t:
            continue
        if t in seen_titles:
            continue
        seen_titles.add(t)

        # try to find a nearby poster image
        image = None
        parent = h.find_parent()
        if parent:
            img_el = parent.find("img")
            if img_el:
                image = (
                    img_el.get("data-src")
                    or img_el.get("src")
                    or (img_el.get("srcset", "").split(" ") or [""])[0]
                )
                if image and image.startswith("//"):
                    image = "https:" + image

        # Default showing time: today 20:00 IST (placeholder — site doesn't
        # publish per-movie times in the HTML)
        start = datetime(today.year, today.month, today.day, 20, 0, tzinfo=IST).astimezone(timezone.utc)
        results.append(
            pack(
                source=_SRC,
                ext_id=f"{today.isoformat()}-{t}",
                title=f"🎬 {t}",
                starts_at=start,
                ends_at=start + timedelta(minutes=120),
                venue=venue,
                image=image,
                link="https://cinema-eilat.co.il/לוח-סרטים/",
                category="cinema",
                tags=["cinema"],
            )
        )
    log.info("cinema-eilat → %d events", len(results))
    return results
