"""Orchestrator: SCRAPERS list + run_all_scrapers entrypoint."""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List

import httpx

from .base import HEADERS, TIMEOUT, log
from .full_site import (
    scrape_single_page,
    scrape_site_articles,
    scrape_listing_eilat_filtered,
)
from .sources import (
    scrape_eilat_muni_articles,
    scrape_smarticket,
    scrape_ynet_eilat,
    scrape_mako_eilat,
    scrape_kan_eilat,
    scrape_israelhayom_eilat,
    scrape_maariv_eilat,
    scrape_globes_eilat,
    scrape_davar_eilat,
    scrape_walla_eilat,
    scrape_facebook_eilat_muni,
)


SCRAPERS = [
    ("eilat_muni_articles", scrape_eilat_muni_articles),
    # Note: eilat_muni_mivzak removed — the municipality "breaking news" bulletin
    # turned out to be operational notices (beach hours etc.), not real news.
    ("smarticket_events", scrape_smarticket),
    ("ynet_eilat", scrape_ynet_eilat),
    ("mako_eilat", scrape_mako_eilat),
    ("kan_eilat", scrape_kan_eilat),
    ("israelhayom_eilat", scrape_israelhayom_eilat),
    ("maariv_eilat", scrape_maariv_eilat),
    ("globes_eilat", scrape_globes_eilat),
    ("davar_eilat", scrape_davar_eilat),
    ("walla_eilat", scrape_walla_eilat),
    ("facebook_eilat_muni", scrape_facebook_eilat_muni),
]


SINGLE_PAGE_SOURCES: List = []  # not used any longer — all sources are full-site

# Full sites — scrape homepage + follow article links.
# Format: (base_url, source_name, source_type, link_patterns, exclude_patterns,
#          max_items, require_eilat_keyword, use_browser)
FULL_SITE_SOURCES = [
    # Eilat-only domains → no keyword filter (everything IS Eilat)
    # Note: אייס מול אילת (icemalleilat.co.il) removed per user request.
    # Note: נמל אילת (eilatport.co.il) removed — only publishes tenders.
    # Note: biz.eilat.muni.il removed — static about-us pages.
    # יום יום (regional) — exclude category listing pages (ShowCat.asp = "places")
    # and magazine/PDF bookshelf pages (vmag/mag subdomains) which aren't articles.
    ("https://www.yomyom.net/", "יום יום", "news", None,
        [r"(?i)showcat\.asp", r"(?i)://(v?mag|pdf|magazine)\.", r"(?i)/bookcase/"],
        40, True, False),
    # Ynet / Mako / Kan / Israel Hayom / Maariv / Globes / Davar / Walla:
    # handled by dedicated tag scrapers (SCRAPERS list)
    # eilat.city removed — pure tourism portal, no real news articles
]

LISTING_FILTERED_SOURCES: List = []  # merged into FULL_SITE_SOURCES above


async def run_all_scrapers() -> List[Dict[str, Any]]:
    all_articles: List[Dict[str, Any]] = []
    async with httpx.AsyncClient(headers=HEADERS, timeout=TIMEOUT) as client:
        for name, fn in SCRAPERS:
            try:
                items = await fn(client)
                log.info("scraper %s → %d articles", name, len(items))
                all_articles.extend(items)
            except Exception as e:
                log.exception("scraper %s failed: %s", name, e)

        for url, src, stype in SINGLE_PAGE_SOURCES:
            try:
                items = await scrape_single_page(client, url, src, stype)
                log.info("single %s → %d articles", src, len(items))
                all_articles.extend(items)
            except Exception as e:
                log.exception("single %s failed: %s", src, e)

        for url, src, stype, patterns, ex_patterns, max_items, req_eilat, use_browser in FULL_SITE_SOURCES:
            try:
                items = await scrape_site_articles(
                    client,
                    base_url=url,
                    source_name=src,
                    source_type=stype,
                    link_patterns=patterns,
                    exclude_patterns=ex_patterns,
                    max_items=max_items,
                    require_eilat_keyword=req_eilat,
                    use_browser=use_browser,
                )
                log.info("full-site %s → %d articles", src, len(items))
                all_articles.extend(items)
            except Exception as e:
                log.exception("full-site %s failed: %s", src, e)

        for url, src, pat in LISTING_FILTERED_SOURCES:
            try:
                items = await scrape_listing_eilat_filtered(client, url, src, pat)
                log.info("listing %s → %d articles", src, len(items))
                all_articles.extend(items)
            except Exception as e:
                log.exception("listing %s failed: %s", src, e)

    # dedup by id (hash of source_url)
    dedup: Dict[str, Dict[str, Any]] = {}
    for a in all_articles:
        dedup[a["id"]] = a
    return list(dedup.values())
