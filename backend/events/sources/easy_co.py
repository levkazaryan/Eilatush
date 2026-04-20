"""easy.co.il/list/Events?region=187 — blocked by Imperva anti-bot (HTTP 403).

Kept as a stub that logs once and returns []. Re-enable when a working path is
found (residential proxy, Playwright, or an official feed).
"""
from __future__ import annotations

import logging
from typing import List

from ..base import HEADERS, TIMEOUT, EventDict

_SRC = "easy"
_URL = "https://easy.co.il/list/Events?region=187"
log = logging.getLogger(__name__)
_warned = False


async def scrape_easy(client) -> List[EventDict]:
    global _warned
    try:
        r = await client.get(_URL, headers=HEADERS, timeout=TIMEOUT)
        if r.status_code == 200:
            # TODO: parse once unblocked
            log.info("easy.co.il → 200 (parser not implemented yet)")
            return []
        if not _warned:
            log.warning("easy.co.il blocked (HTTP %d) — skipping source", r.status_code)
            _warned = True
    except Exception as e:
        if not _warned:
            log.warning("easy.co.il error: %s", e)
            _warned = True
    return []
