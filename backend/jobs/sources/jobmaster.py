"""Scraper for https://www.jobmaster.co.il/jobs/?l=אילת

Structure: server-rendered HTML with <article class="CardStyle JobItem"> per posting.
Each <article> contains all the info inline: title, company, city, employment type,
short description, and a permalink of the form /jobs/checknum.asp?key=<N>.
"""
from __future__ import annotations

import asyncio
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from ..base import _fetch, _make_job, _strip, log

_BASE = "https://www.jobmaster.co.il"
_LIST_URL = "https://www.jobmaster.co.il/jobs/?l=%D7%90%D7%99%D7%9C%D7%AA"  # location = Eilat

_POSTED_RE = re.compile(r"פורסם\s+לפני\s+(\d+)\s*(דקות|דקה|שעה|שעות|ימים|ימין|חודש)")


def _parse_relative_date(text: str) -> Optional[datetime]:
    m = _POSTED_RE.search(text or "")
    if not m:
        return None
    n = int(m.group(1))
    unit = m.group(2)
    now = datetime.now(timezone.utc)
    if unit in ("דקה", "דקות"):
        return now - timedelta(minutes=n)
    if unit in ("שעה", "שעות"):
        return now - timedelta(hours=n)
    if unit in ("ימים", "ימין"):
        return now - timedelta(days=n)
    if unit in ("חודש",):
        return now - timedelta(days=n * 30)
    return None


def _split_listing_text(raw: str) -> Dict[str, Any]:
    """Turn the concatenated card text into structured fields.
    Format seen in the wild:
      "<TITLE> פורסם לפני <N> <unit> ע׳׳י <COMPANY> אילת <JOB_TYPE>
       [<AUDIENCE>] <DESCRIPTION>..."
    """
    text = _strip(raw)
    # Try to cut out the "פורסם לפני ..." chunk to figure out title boundary
    m = _POSTED_RE.search(text)
    title = text
    rest = ""
    if m:
        title = _strip(text[: m.start()])
        rest = text[m.end() :]
    # Extract company after "ע׳׳י "
    company = None
    city = "אילת"
    job_type = None
    m2 = re.search(r"ע[\u05f3']׳?\s*[י']\s+(.+?)(?:\s+אילת|$)", rest)
    if m2:
        company = _strip(m2.group(1))[:120] or None
        after = rest[m2.end():].strip()
        # First few words after city often describe job type ("משרה מלאה" / "משמרות" etc.)
        for key in ["משרה מלאה", "משה חלקית", "משמרות", "פרילאנס", "שליפות"]:
            if key in after:
                if "מלאה" in key:
                    job_type = "full_time"
                elif "חלקית" in key:
                    job_type = "part_time"
                elif "משמרות" in key or "שליפות" in key:
                    job_type = "shifts"
                break
    return {
        "title": title,
        "company": company,
        "city": city,
        "job_type": job_type,
        "description": rest,
        "posted_at": _parse_relative_date(text),
    }


async def scrape_jobmaster(client: httpx.AsyncClient) -> List[Dict[str, Any]]:
    # JobMaster shows ~83 Eilat jobs in total but gates pages 2..N behind a
    # login wall, so we can only reliably pull page 1 (~10 jobs).
    html = await _fetch(client, _LIST_URL)
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    results: List[Dict[str, Any]] = []
    seen: set = set()
    for art in soup.find_all("article"):
        cls = art.get("class") or []
        if not any("JobItem" in c or "CardStyle" in c for c in cls):
            continue
        link = art.find("a", href=True)
        if not link:
            continue
        href = urljoin(_BASE, link["href"])
        if href in seen:
            continue
        seen.add(href)
        raw_text = art.get_text(" ", strip=True)
        parsed = _split_listing_text(raw_text)
        title = parsed["title"]
        if not title or len(title) < 3:
            continue
        description = parsed["description"] or title
        results.append(
            _make_job(
                title=title,
                company=parsed["company"],
                description=description,
                source_url=href,
                source="jobmaster",
                source_name="JobMaster",
                posted_at=parsed["posted_at"],
                location=parsed["city"],
                job_type=parsed["job_type"],
            )
        )
    log.info("jobmaster → %d jobs (page 1 only, deeper pages require login)", len(results))
    return results
