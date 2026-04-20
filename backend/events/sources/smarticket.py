"""Smarticket (eilatmuni.smarticket.co.il) — city-owned ticketing.

Public JSON at ``/api/shows`` (no auth) returns ~20-30 shows. Each show has a
nested ``events`` array with show_date / show_time per performance.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone, timedelta
from typing import List

from ..base import HEADERS, TIMEOUT, EventDict, pack

API = "https://eilatmuni.smarticket.co.il/api/shows"
_SRC = "smarticket"
# Israel Standard Time = UTC+2 (no DST handling needed for MVP)
IST = timezone(timedelta(hours=2))
log = logging.getLogger(__name__)


def _strip_html(s: str | None) -> str:
    if not s:
        return ""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s)).strip()


async def scrape_smarticket(client) -> List[EventDict]:
    r = await client.get(API, headers=HEADERS, timeout=TIMEOUT)
    if r.status_code != 200:
        log.warning("smarticket HTTP %d", r.status_code)
        return []
    try:
        shows = r.json()
    except Exception as e:
        log.warning("smarticket JSON parse: %s", e)
        return []
    if not isinstance(shows, list):
        return []

    results: List[EventDict] = []
    for show in shows:
        title = show.get("title") or ""
        if not title:
            continue
        desc = _strip_html(show.get("content") or show.get("brief") or "") or None
        image = show.get("image")
        if image and isinstance(image, str) and not image.startswith("http"):
            image = "https://eilatmuni.smarticket.co.il/" + image.lstrip("/")
        cat = show.get("category")
        base_url = show.get("url") or show.get("link")
        show_id = show.get("id")
        events = show.get("events") or show.get("show_events") or []
        if not isinstance(events, list):
            continue
        for ev in events:
            date_str = ev.get("show_date") or ev.get("date")
            time_str = ev.get("show_time") or ev.get("time") or "20:00"
            if not date_str:
                continue
            try:
                dt_local = datetime.strptime(
                    f"{date_str} {time_str}", "%Y-%m-%d %H:%M"
                )
            except Exception:
                try:
                    dt_local = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S")
                except Exception:
                    continue
            start = dt_local.replace(tzinfo=IST).astimezone(timezone.utc)
            event_id = ev.get("id") or ev.get("event_id") or f"{show_id}-{date_str}-{time_str}"
            link = ev.get("url") or base_url or f"https://eilatmuni.smarticket.co.il/event/{event_id}"
            price = ev.get("price_from") or ev.get("min_price") or show.get("price_from")
            try:
                price_val = float(price) if price is not None else None
            except Exception:
                price_val = None
            venue = ev.get("hall") or ev.get("venue") or show.get("hall") or show.get("venue")
            results.append(
                pack(
                    source=_SRC,
                    ext_id=str(event_id),
                    title=title,
                    starts_at=start,
                    venue=venue,
                    link=link,
                    image=image,
                    description=desc,
                    category=cat,
                    price_min=price_val,
                    price=(f"מ-{int(price_val)} ₪" if price_val else None),
                )
            )
    log.info("smarticket → %d events", len(results))
    return results
