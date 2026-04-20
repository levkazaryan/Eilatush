"""Tickchak — live.tickchak.co.il/eilat.

Extracts upcoming events from the Next.js __NEXT_DATA__ JSON blob embedded in
the Eilat city page. Data layout (as of April 2026):
    props.pageProps.initialState.data.event.all   (dict id -> event)
Each event has: date (epoch seconds), endDate, image, eventName/eName, eid,
friendlyUrl, venueName/vName, artistNames, minPrice, pageUrl.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import List

from ..base import HEADERS, TIMEOUT, EventDict, pack

URL = "https://live.tickchak.co.il/eilat"
_SRC = "tickchak"
log = logging.getLogger(__name__)


def _abs_img(u) -> str | None:
    if not u:
        return None
    if isinstance(u, dict):
        u = u.get("org") or u.get("mobile") or u.get("thumb") or u.get("url") or next(iter(u.values()), None)
    if not isinstance(u, str):
        return None
    if u.startswith("//"):
        return "https:" + u
    if u.startswith("http"):
        return u
    return "https://live.tickchak.co.il/" + u.lstrip("/")


async def scrape_tickchak(client) -> List[EventDict]:
    r = await client.get(URL, headers=HEADERS, timeout=TIMEOUT)
    if r.status_code != 200:
        log.warning("tickchak HTTP %d", r.status_code)
        return []
    m = re.search(r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>', r.text, re.S)
    if not m:
        return []
    try:
        data = json.loads(m.group(1))
    except Exception as e:
        log.warning("tickchak JSON parse failed: %s", e)
        return []

    all_ev = (
        data.get("props", {})
        .get("pageProps", {})
        .get("initialState", {})
        .get("data", {})
        .get("event", {})
        .get("all", {})
    )
    if not isinstance(all_ev, dict):
        return []

    results: List[EventDict] = []
    for eid, ev in all_ev.items():
        title = (
            ev.get("eName")
            or ev.get("eventName")
            or ev.get("title")
            or ev.get("productionName")
            or ""
        )
        if not title:
            continue
        ts = ev.get("date") or ev.get("dStart") or ev.get("startDate")
        try:
            start = datetime.fromtimestamp(int(ts), tz=timezone.utc) if ts else None
        except Exception:
            start = None
        if not start:
            continue
        end_ts = ev.get("endDate") or ev.get("dEnd")
        try:
            end = datetime.fromtimestamp(int(end_ts), tz=timezone.utc) if end_ts else None
        except Exception:
            end = None
        venue = ev.get("vName") or ev.get("venueName") or ev.get("placeName")
        link_slug = ev.get("friendlyUrl") or ev.get("pageUrl")
        link = None
        if link_slug:
            link = (
                link_slug
                if str(link_slug).startswith("http")
                else f"https://live.tickchak.co.il/{str(link_slug).lstrip('/')}"
            )
        artists = ev.get("artistNames") or ev.get("artists") or []
        if isinstance(artists, list) and artists:
            names = []
            for a in artists[:3]:
                if isinstance(a, dict):
                    n = a.get("aName") or a.get("name")
                    if n:
                        names.append(str(n))
                elif a:
                    names.append(str(a))
            sub = ", ".join(names) if names else None
            desc = sub
        else:
            desc = ev.get("description") or ev.get("eTitle") or None
        price_min = ev.get("minPrice")
        try:
            price_val = float(price_min) if price_min is not None else None
        except Exception:
            price_val = None
        image = _abs_img(ev.get("image") or ev.get("mainImage") or ev.get("imgUrl"))
        results.append(
            pack(
                source=_SRC,
                ext_id=str(eid),
                title=title,
                starts_at=start,
                ends_at=end,
                venue=venue,
                link=link,
                image=image,
                description=desc,
                price_min=price_val,
                price=(f"מ-{int(price_val)} ₪" if price_val else None),
                tags=["party"] if price_val and price_val < 80 else ["concert"],
            )
        )
    log.info("tickchak → %d events", len(results))
    return results
