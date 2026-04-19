"""Facebook Eilat.Muni page scraper — currently a no-op, awaiting a
Meta Graph API access token.
"""
from __future__ import annotations
from typing import Any, Dict, List
import httpx

from ..base import log

async def scrape_facebook_eilat_muni(client: httpx.AsyncClient) -> List[Dict[str, Any]]:
    log.warning(
        "Facebook scraping for Eilat.Muni page requires Meta Graph API Token — "
        "skipping. Configure FB_PAGE_ACCESS_TOKEN to enable."
    )
    return []

