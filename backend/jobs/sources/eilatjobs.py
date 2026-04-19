"""Scraper for https://www.eilatjobs.com/ (עבודה עם מגורים באילת).

Structure: WordPress + Elementor. Homepage has ~35 <article class="elementor-post">
entries; each links to /jobs/<slug>/ and the article's post classes contain
`job-type-<slug>` which we use as a coarse hint (e.g. `job-type-hotels`).
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from ..base import _fetch, _make_job, _strip, log

_BASE = "https://www.eilatjobs.com"
_LIST_URL = "https://www.eilatjobs.com/"

# Map the `job-type-<X>` WP class hints → our taxonomy slugs.
_CLASS_TAG_MAP = {
    "hotels": "hotels",
    "hotel": "hotels",
    "restaurants": "restaurants",
    "restaurant": "restaurants",
    "sales": "sales",
    "retail": "retail",
    "cashiers": "retail",
    "security": "security",
    "cleaning": "cleaning",
    "logistics": "logistics",
    "driver": "logistics",
    "office": "office",
    "health": "health",
    "medical": "health",
    "education": "education",
    "construction": "construction",
    "tech": "tech",
    "tourism": "tourism",
}


def _extract_hint_tags(classes: List[str]) -> List[str]:
    """Parse `job-type-hotels` / `job-type-without-shabbat` → ["hotels"]."""
    out: List[str] = []
    for c in classes or []:
        if not c.startswith("job-type-"):
            continue
        suffix = c[len("job-type-") :].lower()
        for key, slug in _CLASS_TAG_MAP.items():
            if key in suffix and slug not in out:
                out.append(slug)
    return out


async def _fetch_detail(
    client: httpx.AsyncClient, url: str
) -> Dict[str, Optional[str]]:
    """Follow the article link to grab full description + company/phone if listed."""
    html = await _fetch(client, url)
    if not html:
        return {"description": "", "phone": None, "company": None, "image": None}
    soup = BeautifulSoup(html, "lxml")
    # Main body: WP "entry-content" / article body
    body = soup.find("div", class_=re.compile(r"entry-content|elementor-widget-theme-post-content", re.I))
    desc = ""
    if body:
        for bad in body.find_all(["script", "style", "nav", "aside", "iframe"]):
            bad.decompose()
        desc = _strip(body.get_text(" "))
    # phone: look for any tel: link
    phone = None
    tel = soup.find("a", href=re.compile(r"^tel:", re.I))
    if tel and tel.get("href"):
        phone = tel["href"].split(":", 1)[-1]
    # hero image
    img = None
    og = soup.find("meta", property="og:image")
    if og and og.get("content"):
        img = og["content"]
    return {"description": desc, "phone": phone, "company": None, "image": img}


async def scrape_eilatjobs(client: httpx.AsyncClient) -> List[Dict[str, Any]]:
    html = await _fetch(client, _LIST_URL)
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    results: List[Dict[str, Any]] = []
    seen = set()
    for art in soup.find_all("article"):
        cls = art.get("class") or []
        if "elementor-post" not in cls:
            continue
        link = art.find("a", href=True)
        title_el = art.find(["h2", "h3", "h4"])
        if not link or not title_el:
            continue
        href = urljoin(_BASE, link["href"])
        if href in seen:
            continue
        seen.add(href)
        title = _strip(title_el.get_text())
        if not title or len(title) < 3:
            continue
        # description preview from the card itself
        preview = _strip(art.get_text(" "))
        # follow the link for full body + phone (but cap total to avoid long runs)
        detail = await _fetch_detail(client, href)
        description = detail["description"] or preview
        hint_tags = _extract_hint_tags(cls)
        job = _make_job(
            title=title,
            company=None,  # eilatjobs rarely names the company in listing
            description=description,
            source_url=href,
            source="eilatjobs",
            source_name="עובדים באילת",
            phone=detail["phone"],
            image=detail["image"],
            tags=hint_tags,  # will be enriched later by LLM
        )
        results.append(job)
        if len(results) >= 40:
            break
    log.info("eilatjobs → %d jobs", len(results))
    return results
