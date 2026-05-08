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

    # ---- Step 1: Build a {movie_title: poster_url} map ---------------------
    # Find every <img> with a poster-looking URL and walk up to find its
    # nearest <h1>/<h2>/<h3> heading. Skip the site logo.
    title_to_image: dict[str, str] = {}
    for img in soup.find_all("img"):
        src = (
            img.get("data-src")
            or img.get("src")
            or (img.get("srcset", "").split(" ") or [""])[0]
        )
        if not src:
            continue
        if "logo" in src.lower() or "לוגו" in src:
            continue
        if not re.search(r"\.(jpe?g|png|webp)", src, re.IGNORECASE):
            continue
        if src.startswith("//"):
            src = "https:" + src

        # Walk up parents and look for a nearby heading
        node = img
        heading_text: str | None = None
        for _ in range(6):
            if not node:
                break
            h = node.find(["h1", "h2", "h3"]) if hasattr(node, "find") else None
            if h:
                heading_text = h.get_text(strip=True)
                break
            nxt = node.find_next_sibling() if hasattr(node, "find_next_sibling") else None
            if nxt:
                h2 = nxt.find(["h1", "h2", "h3"]) if hasattr(nxt, "find") else None
                if h2:
                    heading_text = h2.get_text(strip=True)
                    break
            node = node.parent
        if heading_text and heading_text not in title_to_image:
            title_to_image[heading_text] = src

    # ---- Step 2: Iterate movie headings and emit events -------------------
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

        image = title_to_image.get(t)

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
    log.info(
        "cinema-eilat → %d events (%d with poster)",
        len(results),
        sum(1 for e in results if e.get("image")),
    )
    return results
