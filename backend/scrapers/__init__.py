"""Eilatush news scrapers — modular package.

Public API preserved for backward compatibility:
    from scrapers import run_all_scrapers
Most internal helpers are also re-exported so existing one-off scripts keep
working.
"""
from __future__ import annotations

# --- base primitives ---
from .base import (
    HEADERS,
    TIMEOUT,
    _hash_url,
    _dt_parse,
    _parse_date,
    _strip,
    _contains_eilat,
    _fetch,
    _pw_fetch,
    _fetch_smart,
    _make_article,
    _PW_CTX,
    log,
)

# --- cleaners ---
from .cleaners import (
    _extract_date,
    _extract_title,
    _LEADING_DATE_RE,
    _strip_leading_date,
    _META_TAIL_RE,
    _norm,
    _strip_title_prefix,
)

# --- enrichment ---
from .enrichment import _article_date, _article_meta, _enrich_dates

# --- tag-page & full-site generic scrapers ---
from .tag_page import _scrape_tag_page
from .full_site import (
    scrape_single_page,
    scrape_site_articles,
    scrape_listing_eilat_filtered,
)

# --- per-source scrapers ---
from .sources import (
    scrape_eilat_muni_articles,
    scrape_eilat_muni_mivzak,
    scrape_smarticket,
    scrape_ynet_eilat,
    YNET_RSS_CANDIDATES,
    scrape_kan_eilat,
    scrape_israelhayom_eilat,
    scrape_maariv_eilat,
    scrape_globes_eilat,
    scrape_davar_eilat,
    scrape_walla_eilat,
    scrape_mako_eilat,
    scrape_hamal,
    scrape_facebook_eilat_muni,
)

# --- orchestrator ---
from .registry import (
    SCRAPERS,
    SINGLE_PAGE_SOURCES,
    FULL_SITE_SOURCES,
    LISTING_FILTERED_SOURCES,
    run_all_scrapers,
)


__all__ = [
    "run_all_scrapers",
    "SCRAPERS",
    "FULL_SITE_SOURCES",
    "HEADERS",
    "TIMEOUT",
]
