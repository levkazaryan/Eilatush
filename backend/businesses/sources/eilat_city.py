"""Scraper for https://eilat.city/ — the official Eilat tourism city site.

The site has a /list/<category-slug> index per business type, each listing
showing ~40 businesses as `<a class="c-media-object">` cards that link to
detail pages at `/<business-slug>`.

Detail pages expose:
  • `.c-biz-card-info__address`       → phone + street address
  • `.c-biz-card-info__opening-hours` → "08:00 - 23:00" style hours
  • `.c-biz-card__info`               → long description
"""
from __future__ import annotations

import asyncio
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from ..base import _fetch, _make_business, _strip, log

_BASE = "https://eilat.city"

# Each tuple: (path-slug in Hebrew, raw display label, soft hint for LLM)
_CATEGORIES: List[Dict[str, str]] = [
    {"slug": "מסעדות",               "label": "מסעדות",              "hint": "restaurants"},
    {"slug": "בתי-קפה",              "label": "בתי קפה",             "hint": "cafes"},
    {"slug": "פאבים-וברים",           "label": "פאבים וברים",          "hint": "bars"},
    {"slug": "מזון-מהיר",             "label": "מזון מהיר",            "hint": "fast_food"},
    {"slug": "אטרקציות",             "label": "אטרקציות",             "hint": "attractions"},
    {"slug": "בילויים",               "label": "בילויים",              "hint": "attractions"},
    {"slug": "ספא-טיפולים-ועיסויים",  "label": "ספא וטיפולים",         "hint": "spa"},
    {"slug": "אופנה",                "label": "אופנה",                "hint": "fashion"},
    {"slug": "תכשיטים",              "label": "תכשיטים",              "hint": "jewelry"},
    {"slug": "מחשבים-ואלקטרוניקה",   "label": "מחשבים ואלקטרוניקה",   "hint": "electronics"},
    {"slug": "מוצרי-חשמל-ביתיים",    "label": "מוצרי חשמל ביתיים",    "hint": "appliances"},
    {"slug": "טלפונים-סלולרים",      "label": "טלפונים סלולריים",      "hint": "phones"},
    {"slug": "סופרמרקטים",           "label": "סופרמרקטים",           "hint": "supermarket"},
    {"slug": "מרכזי-קניות",           "label": "מרכזי קניות",          "hint": "shopping_center"},
    {"slug": "משרדי-נסיעות",          "label": "משרדי נסיעות",         "hint": "travel"},
    {"slug": "שירותי-תחבורה",         "label": "שירותי תחבורה",        "hint": "transport"},
    {"slug": "קונסוליות",             "label": "קונסוליות",            "hint": "consulate"},
]


# Per-card hint → slug for quick pre-tagging (LLM still confirms afterwards).
_HINT_TAG_MAP = {
    "restaurants":     ["restaurants"],
    "cafes":           ["cafes"],
    "bars":            ["bars"],
    "fast_food":       ["fast_food"],
    "attractions":     ["attractions"],
    "spa":             ["spa"],
    "fashion":         ["fashion"],
    "jewelry":         ["jewelry"],
    "electronics":     ["electronics"],
    "appliances":      ["appliances"],
    "phones":          ["phones"],
    "supermarket":     ["supermarket"],
    "shopping_center": ["shopping_center"],
    "travel":          ["travel"],
    "transport":       ["transport"],
    "consulate":       ["consulate"],
}


async def _parse_list_page(
    client: httpx.AsyncClient, url: str
) -> List[Dict[str, Any]]:
    """Extract all c-media-object <a> cards from a /list/ page."""
    html = await _fetch(client, url)
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    cards: List[Dict[str, Any]] = []
    for a in soup.find_all("a", class_=re.compile(r"c-media-object(?:\s|$)")):
        href = a.get("href")
        if not href:
            continue
        href = urljoin(_BASE, href)
        title_el = a.find(class_="c-media-object__title")
        subtitle_el = a.find(class_="c-media-object__subtitle")
        para_el = a.find(class_=re.compile(r"c-paragraph"))
        img_el = a.find("img", class_=re.compile(r"c-media-object__figure"))
        name = _strip(title_el.get_text()) if title_el else ""
        if not name or len(name) < 2:
            continue
        subtitle = _strip(subtitle_el.get_text()) if subtitle_el else None
        description = _strip(para_el.get_text()) if para_el else ""
        image = None
        if img_el and img_el.get("src"):
            image = urljoin(_BASE, img_el["src"])
        cards.append({
            "url": href,
            "name": name,
            "subtitle": subtitle,
            "description": description,
            "image": image,
        })
    return cards


async def _fetch_detail(
    client: httpx.AsyncClient, url: str
) -> Dict[str, Optional[str]]:
    """Enhance the list card with contact info + hours from the biz page."""
    html = await _fetch(client, url)
    if not html:
        return {"phone": None, "address": None, "open_hours": None, "description": None, "email": None}
    soup = BeautifulSoup(html, "lxml")

    phone = None
    email = None
    for tag in soup.find_all("a", href=True):
        h = tag["href"]
        if not phone and h.lower().startswith("tel:"):
            phone = h.split(":", 1)[-1]
        elif not email and h.lower().startswith("mailto:"):
            email = h.split(":", 1)[-1]
        if phone and email:
            break

    address = None
    addr_el = soup.find(class_="c-biz-card-info__address")
    if addr_el:
        # The address element has phone + address concatenated. Split after phone.
        raw = _strip(addr_el.get_text(" "))
        # Remove leading phone if present
        m = re.search(r"^\s*[\d\-\s]{7,}\s*", raw)
        if m:
            raw = raw[m.end():].strip()
        address = raw or None

    hours = None
    hrs_el = soup.find(class_="c-biz-card-info__opening-hours")
    if hrs_el:
        hours = _strip(hrs_el.get_text(" "))
        # strip leading "שעות פתיחה" if present
        hours = re.sub(r"^שעות\s*פתיחה[:\s]*", "", hours).strip() or None

    description = None
    info = soup.find(class_=re.compile(r"c-biz-card__info|c-biz-card-info"))
    if info:
        # Drop nested address/hours since we already have them
        clone = BeautifulSoup(str(info), "lxml")
        for bad in clone.find_all(class_=re.compile(r"__address|__opening-hours|__contact|__rating")):
            bad.decompose()
        description = _strip(clone.get_text(" "))[:1500] or None

    return {
        "phone": phone,
        "address": address,
        "open_hours": hours,
        "description": description,
        "email": email,
    }


async def scrape_eilat_city(client: httpx.AsyncClient) -> List[Dict[str, Any]]:
    """Iterate every category listed in `_CATEGORIES` and scrape all cards.

    Detail pages are fetched concurrently (capped) to enrich phone/address.
    """
    all_cards: List[Dict[str, Any]] = []
    seen_urls: set = set()

    # 1) collect all list pages.
    list_urls = [f"{_BASE}/list/{c['slug']}" for c in _CATEGORIES]
    # For each category also check pagination (/list/<slug>/2, /3, /4).
    list_urls_with_pages = []
    for url in list_urls:
        list_urls_with_pages.append((url, None))
        for p in (2, 3, 4):
            list_urls_with_pages.append((f"{url}/{p}", None))

    for i, cat in enumerate(_CATEGORIES):
        # category base + pagination
        page_urls = [f"{_BASE}/list/{cat['slug']}"] + [
            f"{_BASE}/list/{cat['slug']}/{p}" for p in (2, 3, 4, 5)
        ]
        total_for_cat = 0
        for pu in page_urls:
            cards = await _parse_list_page(client, pu)
            if not cards:
                break  # no more pages
            for c in cards:
                if c["url"] in seen_urls:
                    continue
                seen_urls.add(c["url"])
                c["category_hint"] = cat["hint"]
                c["category_label"] = cat["label"]
                all_cards.append(c)
                total_for_cat += 1
        log.info("eilat.city %s → %d cards", cat["label"], total_for_cat)

    log.info("eilat.city list pages collected %d unique cards", len(all_cards))

    # 2) fetch detail pages concurrently (cap 8 at once).
    sem = asyncio.Semaphore(8)

    async def enrich(card: Dict[str, Any]) -> None:
        async with sem:
            try:
                detail = await _fetch_detail(client, card["url"])
            except Exception as e:
                log.warning("eilat.city detail %s: %s", card["url"], e)
                detail = {}
            card["_detail"] = detail or {}

    await asyncio.gather(*[enrich(c) for c in all_cards])

    # 3) build business records.
    results: List[Dict[str, Any]] = []
    for card in all_cards:
        detail = card.get("_detail") or {}
        biz = _make_business(
            name=card["name"],
            source_url=card["url"],
            source="eilat_city",
            source_name="אילת+",
            description=detail.get("description") or card.get("description") or "",
            subtitle=card.get("subtitle"),
            category_hint=card.get("category_hint"),
            address=detail.get("address"),
            phone=detail.get("phone"),
            email=detail.get("email"),
            open_hours=detail.get("open_hours"),
            image=card.get("image"),
            tags=list(_HINT_TAG_MAP.get(card.get("category_hint", ""), [])),
        )
        results.append(biz)
    log.info("eilat.city → %d businesses", len(results))
    return results
