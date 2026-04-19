"""Eilatush jobs scrapers — modular package.

Public API:
    from jobs import run_all_job_scrapers
"""
from __future__ import annotations

from .base import (
    HEADERS,
    TIMEOUT,
    log,
    _fingerprint,
    _make_job,
    _detect_job_type,
    _detect_experience,
    _normalize_phone,
    _fetch,
)
from .registry import (
    SCRAPERS,
    SOURCE_PRIORITY,
    run_all_job_scrapers,
    dedupe_jobs,
)

__all__ = [
    "run_all_job_scrapers",
    "dedupe_jobs",
    "SCRAPERS",
    "SOURCE_PRIORITY",
]
