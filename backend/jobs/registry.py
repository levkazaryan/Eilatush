"""Orchestrator: list of job scrapers + run_all_job_scrapers + dedupe."""
from __future__ import annotations

from typing import Any, Dict, List

import httpx

from .base import HEADERS, TIMEOUT, log
from .sources import (
    scrape_eilatjobs,
    scrape_jobmaster,
    scrape_yomyom_jobs,
    scrape_drushim,
)

# Each scraper tuple: (name, fn, priority).
# Lower `priority` number = more preferred source when duplicates exist.
#   10 — official (gov / municipality)
#   20 — local Eilat-specific boards
#   30 — national aggregators
SCRAPERS: List = [
    ("eilatjobs",   scrape_eilatjobs,   20),
    ("yomyom_jobs", scrape_yomyom_jobs, 20),
    ("jobmaster",   scrape_jobmaster,   30),
    ("drushim",     scrape_drushim,     30),
]

# Lookup by source slug for dedup prioritization.
SOURCE_PRIORITY: Dict[str, int] = {name: prio for name, _, prio in SCRAPERS}


def dedupe_jobs(jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Collapse duplicates across sources by `fingerprint`.

    Keeps the posting from the lowest-priority source, and records all other
    sources in the `also_in` field so the UI can show "also on JobMaster".
    """
    by_fp: Dict[str, Dict[str, Any]] = {}
    for j in jobs:
        fp = j.get("fingerprint")
        if not fp:
            # no fingerprint = always keep (yomyom uses phone-based url, unique)
            by_fp[j["id"]] = j
            continue
        existing = by_fp.get(fp)
        if not existing:
            j["also_in"] = []
            by_fp[fp] = j
            continue
        # Duplicate — decide which to keep.
        new_prio = SOURCE_PRIORITY.get(j.get("source", ""), 99)
        old_prio = SOURCE_PRIORITY.get(existing.get("source", ""), 99)
        if new_prio < old_prio:
            j.setdefault("also_in", [])
            # inherit the existing also_in + the old source
            j["also_in"] = list(set(existing.get("also_in") or []) | {existing.get("source_name") or existing.get("source")})
            by_fp[fp] = j
        else:
            existing.setdefault("also_in", [])
            new_src_name = j.get("source_name") or j.get("source")
            if new_src_name and new_src_name not in existing["also_in"]:
                existing["also_in"].append(new_src_name)
    return list(by_fp.values())


async def run_all_job_scrapers() -> List[Dict[str, Any]]:
    """Run all registered job scrapers and return de-duplicated jobs list."""
    all_jobs: List[Dict[str, Any]] = []
    async with httpx.AsyncClient(headers=HEADERS, timeout=TIMEOUT) as client:
        for name, fn, _prio in SCRAPERS:
            try:
                items = await fn(client)
                log.info("job-scraper %s → %d jobs", name, len(items))
                all_jobs.extend(items)
            except Exception as e:
                log.exception("job-scraper %s failed: %s", name, e)
    deduped = dedupe_jobs(all_jobs)
    log.info("jobs dedupe: %d → %d", len(all_jobs), len(deduped))
    return deduped
