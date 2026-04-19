"""Sources that use the generic tag-page scraper: Israel Hayom, Maariv,
Globes, Davar, Walla.
"""
from __future__ import annotations
import re
from typing import Any, Dict, List
import httpx

from ..tag_page import _scrape_tag_page

async def scrape_israelhayom_eilat(client: httpx.AsyncClient) -> List[Dict[str, Any]]:
    return await _scrape_tag_page(
        client,
        tag_url="https://www.israelhayom.co.il/tag/%D7%90%D7%99%D7%9C%D7%AA",
        source_name="ישראל היום",
        base_host="israelhayom.co.il",
        link_pattern=re.compile(r"israelhayom\.co\.il/.+/article/\d+"),
        host_whitelist=["israelhayom.co.il"],
        max_items=25,
    )


async def scrape_maariv_eilat(client: httpx.AsyncClient) -> List[Dict[str, Any]]:
    return await _scrape_tag_page(
        client,
        tag_url="https://www.maariv.co.il/tags/%D7%90%D7%99%D7%9C%D7%AA",
        source_name="מעריב",
        base_host="maariv.co.il",
        link_pattern=re.compile(r"maariv\.co\.il/.+/article-\d+"),
        host_whitelist=["maariv.co.il"],
        max_items=25,
        # Maariv article pages render the body via JS — httpx gets the
        # placeholder "חוקרי המשטרה המזועזעים…" shell while Playwright
        # gets the real opening paragraph containing Eilat context.
        enrich_use_browser=True,
    )


async def scrape_globes_eilat(client: httpx.AsyncClient) -> List[Dict[str, Any]]:
    return await _scrape_tag_page(
        client,
        tag_url="https://www.globes.co.il/news/%D7%90%D7%99%D7%9C%D7%AA.tag",
        source_name="גלובס",
        base_host="globes.co.il",
        link_pattern=re.compile(r"globes\.co\.il/news/article\.aspx\?did=\d+"),
        host_whitelist=["globes.co.il"],
        max_items=25,
        # Same JS-rendering concern as Maariv — use Playwright for enrichment.
        enrich_use_browser=True,
    )


async def scrape_davar_eilat(client: httpx.AsyncClient) -> List[Dict[str, Any]]:
    # Davar blocks httpx → use Playwright for listing + enrichment
    return await _scrape_tag_page(
        client,
        tag_url="https://www.davar1.co.il/topic/%D7%90%D7%99%D7%9C%D7%AA/",
        source_name="דבר",
        base_host="davar1.co.il",
        link_pattern=re.compile(r"davar1\.co\.il/\d+/?$|davar1\.co\.il/update/\d+"),
        host_whitelist=["davar1.co.il"],
        max_items=25,
        use_browser=True,
        enrich_use_browser=True,
    )


async def scrape_walla_eilat(client: httpx.AsyncClient) -> List[Dict[str, Any]]:
    return await _scrape_tag_page(
        client,
        tag_url="https://tags.walla.co.il/%D7%90%D7%99%D7%9C%D7%AA",
        source_name="וואלה",
        base_host="walla.co.il",
        link_pattern=re.compile(r"(news|travel|mekomi|sport|tech|finance|b)\.walla\.co\.il/item/\d+"),
        host_whitelist=["walla.co.il"],
        max_items=25,
    )


# ---------------------------------------------------------------------------
# Mako — Eilat tag
# ---------------------------------------------------------------------------
