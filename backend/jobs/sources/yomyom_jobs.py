"""Scraper for https://www.yomyom.net/article.asp?id=61444 (לוח דרושים יום-יום).

The page is image-based: each job is an uploaded JPG flyer paired with a
`tel:+972...` link for contact. We can't OCR the images so we extract one
entry per unique phone-link we find, titled "משרה בלוח יום-יום" with
the flyer image attached and a link back to the page for the full ad.

This keeps the scraper useful (phones = actionable contact) without
pretending to understand the job title.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, List
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from ..base import _fetch, _make_job, _strip, log

_URL = "https://www.yomyom.net/article.asp?id=61444"
_BASE = "https://www.yomyom.net"


async def scrape_yomyom_jobs(client: httpx.AsyncClient) -> List[Dict[str, Any]]:
    html = await _fetch(client, _URL)
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    # Build "blocks" — assume the page layout is image then tel link repeatedly.
    # We iterate over <a href="tel:..."> and grab the nearest preceding <img>.
    results: List[Dict[str, Any]] = []
    tel_links = [a for a in soup.find_all("a", href=True) if a["href"].lower().startswith("tel:")]
    seen_phones: set = set()
    for idx, a in enumerate(tel_links):
        phone = a["href"].split(":", 1)[1].strip()
        # Normalize out weird prefixes like "http://tel:"
        phone = re.sub(r"^[a-z]+://", "", phone, flags=re.I)
        if not phone or phone in seen_phones:
            continue
        seen_phones.add(phone)
        # Find the closest <img> preceding this link in document order
        img_src = None
        prev = a
        for _ in range(20):
            prev = prev.find_previous()
            if prev is None:
                break
            if getattr(prev, "name", None) == "img":
                src = prev.get("src") or ""
                if src and "דרושים" in src:
                    img_src = urljoin(_BASE, src)
                    break
                if src and "UploadImg" in src and ".jpg" in src.lower():
                    img_src = urljoin(_BASE, src)
                    break
        title = f"משרה בלוח יום-יום אילת #{idx + 1}"
        description = (
            "משרה לחוז אילת שפורסמה בלוח הדרושים של יום-יום אילת. "
            "לפרטי המשרה ופרטי הקשר התקשרו ישירות למפרסם."
        )
        source_url = f"{_URL}#phone-{re.sub(r'[^0-9+]','',phone)}"
        job = _make_job(
            title=title,
            company=None,
            description=description,
            source_url=source_url,
            source="yomyom",
            source_name="לוח יום-יום",
            phone=phone,
            image=img_src,
            posted_at=datetime.now(timezone.utc),
        )
        results.append(job)
    log.info("yomyom_jobs → %d jobs", len(results))
    return results
