"""Run all event scrapers, merge + deduplicate by id.

The FastAPI layer consumes :func:`run_all_event_scrapers` and then upserts
into Mongo. LLM categorization is done separately (see ``events.categorizer``).
"""
from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable, Dict, List

import httpx

from .base import EventDict, HEADERS, TIMEOUT
from .sources.tickchak import scrape_tickchak
from .sources.smarticket import scrape_smarticket
from .sources.eilat_city_events import scrape_eilat_city_events
from .sources.cinema_eilat import scrape_cinema_eilat
from .sources.eilat_muni_events import scrape_eilat_muni_events
from .sources.easy_co import scrape_easy

Scraper = Callable[[httpx.AsyncClient], Awaitable[List[EventDict]]]

SOURCES: List[Scraper] = [
    scrape_tickchak,
    scrape_smarticket,
    scrape_eilat_city_events,
    scrape_cinema_eilat,
    scrape_eilat_muni_events,
    scrape_easy,
]

log = logging.getLogger(__name__)


async def _safe(scraper: Scraper, client: httpx.AsyncClient) -> List[EventDict]:
    try:
        return await scraper(client)
    except Exception as e:  # noqa: BLE001
        log.exception("event scraper %s failed: %s", scraper.__name__, e)
        return []


async def run_all_event_scrapers() -> List[EventDict]:
    async with httpx.AsyncClient(headers=HEADERS, timeout=TIMEOUT, follow_redirects=True) as c:
        all_results = await asyncio.gather(*[_safe(s, c) for s in SOURCES])
    # flatten + dedupe
    merged: Dict[str, EventDict] = {}
    for lst in all_results:
        for ev in lst:
            merged[ev["id"]] = ev
    log.info("events: merged %d unique from %d sources", len(merged), len(SOURCES))
    return list(merged.values())
