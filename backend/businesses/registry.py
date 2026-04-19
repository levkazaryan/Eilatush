"""Orchestrator: list of business/professional scrapers + run_all + dedupe."""
from __future__ import annotations

from typing import Any, Dict, List

import httpx

from .base import HEADERS, TIMEOUT, log
from .sources import (
    scrape_eilat_city,
    scrape_eilat_muni,
    scrape_yomyom_professionals,
)

# Each scraper tuple: (slug, fn, priority).
# Lower `priority` = preferred when duplicates exist across sources.
#   10 — official / municipality
#   20 — local Eilat-specific
#   30 — national aggregator
SCRAPERS: List = [
    ("eilat_muni",  scrape_eilat_muni,             10),  # official, highest priority
    ("eilat_city",  scrape_eilat_city,             20),
    ("yomyom_pros", scrape_yomyom_professionals,   20),
]

SOURCE_PRIORITY: Dict[str, int] = {name: prio for name, _, prio in SCRAPERS}


def dedupe_businesses(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Collapse duplicates across sources by `fingerprint`.

    Different `type` records (business vs. professional) are NEVER merged even
    if fingerprints match — the two lists are logically separate.
    """
    by_key: Dict[str, Dict[str, Any]] = {}
    for it in items:
        fp = it.get("fingerprint")
        t = it.get("type") or "business"
        if not fp:
            by_key[it["id"]] = it
            continue
        key = f"{t}::{fp}"
        existing = by_key.get(key)
        if not existing:
            it["also_in"] = []
            by_key[key] = it
            continue
        new_prio = SOURCE_PRIORITY.get(it.get("source", ""), 99)
        old_prio = SOURCE_PRIORITY.get(existing.get("source", ""), 99)
        if new_prio < old_prio:
            it.setdefault("also_in", [])
            it["also_in"] = list(set(existing.get("also_in") or []) | {existing.get("source_name") or existing.get("source")})
            by_key[key] = it
        else:
            existing.setdefault("also_in", [])
            nm = it.get("source_name") or it.get("source")
            if nm and nm not in existing["also_in"]:
                existing["also_in"].append(nm)
    return list(by_key.values())


async def run_all_business_scrapers() -> List[Dict[str, Any]]:
    """Run every registered scraper and return de-duplicated businesses+pros."""
    all_items: List[Dict[str, Any]] = []
    async with httpx.AsyncClient(headers=HEADERS, timeout=TIMEOUT) as client:
        for name, fn, _prio in SCRAPERS:
            try:
                items = await fn(client)
                log.info("biz-scraper %s → %d items", name, len(items))
                all_items.extend(items)
            except Exception as e:
                log.exception("biz-scraper %s failed: %s", name, e)
    deduped = dedupe_businesses(all_items)
    log.info("biz dedupe: %d → %d", len(all_items), len(deduped))
    return deduped
