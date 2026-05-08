"""Scraper for https://www.drushim.co.il — the largest Israeli jobs aggregator.

Uses Playwright with stealth mode because the site is protected by PerimeterX
(the stormcaster script). httpx/RSS/sitemap all return a challenge page; only a
real Chromium load executes the anti-bot JS and gets through.

On the Eilat search page we get ~27 rendered cards out of ~110 total matches.
That's enough for Phase 3: we pick up everything above the fold on first load.
Each card has its own detail URL `/job/{id}/{hash}/` which we turn into an
absolute URL for the frontend's "open original" button.
"""
from __future__ import annotations

import asyncio
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from ..base import _make_job, _strip, log, is_in_eilat

_BASE = "https://www.drushim.co.il"
_SEARCH_URL = "https://www.drushim.co.il/jobs/search/%D7%90%D7%99%D7%9C%D7%AA/?ref=288"

# Relative-date pattern: "לפני 15 שעות", "לפני 3 ימים", etc.
_POSTED_RE = re.compile(r"לפני\s+(\d+)\s*(דקה|דקות|שעה|שעות|יום|ימים|חודש|חודשים|שבוע|שבועות)")


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
    if unit in ("יום", "ימים"):
        return now - timedelta(days=n)
    if unit in ("שבוע", "שבועות"):
        return now - timedelta(days=n * 7)
    if unit in ("חודש", "חודשים"):
        return now - timedelta(days=n * 30)
    return None


def _parse_card_text(raw: str) -> Dict[str, Any]:
    """Parse the concatenated card text into structured fields.

    Card format seen in the wild:
      "<TITLE> <COMPANY_LINE> <CITY> | <EXPERIENCE> | <JOB_TYPE> | ... | <POSTED>
       <DESCRIPTION> + לצפייה בפרטי המשרה שלח/י קורות חיים"
    """
    text = _strip(raw)
    # Strip trailing boilerplate
    for boiler in ["לצפייה בפרטי המשרה שלח/י קורות חיים", "לצפייה בפרטי המשרה", "שלח/י קורות חיים"]:
        idx = text.rfind(boiler)
        if idx >= 0:
            text = text[:idx].strip()
            break

    # Posted date
    posted_at = _parse_relative_date(text)

    # Split on "|" separators which Drushim uses between metadata chips
    # Typical order: City | Experience | JobType | ... | Posted
    #
    # We can't reliably split the title from the rest, but we can extract
    # signals from the whole text body.
    experience = None
    if "ללא נסיון" in text or "ללא ניסיון" in text or "לא נדרש ניסיון" in text:
        experience = "none"
    elif "ניסיון" in text and any(k in text for k in ["חובה", "נדרש", "דרוש"]):
        experience = "required"

    job_type = None
    if "משמרות" in text or "משמרת" in text:
        job_type = "shifts"
    elif "משרה מלאה" in text:
        job_type = "full_time"
    elif "משרה חלקית" in text or "חצי משרה" in text:
        job_type = "part_time"
    elif "זמני" in text or "עונתי" in text:
        job_type = "temporary"

    return {
        "text": text,
        "posted_at": posted_at,
        "experience": experience,
        "job_type": job_type,
    }


def _extract_jobs_from_html(html: str) -> List[Dict[str, Any]]:
    """Parse the rendered drushim search page into job records."""
    soup = BeautifulSoup(html, "lxml")
    results: List[Dict[str, Any]] = []
    seen_urls: set = set()

    # Each job is an <h3> inside a `.job-item-main` container.
    cards = soup.select("div.job-item-main")
    # Fallback: some renders just use <h3> directly
    if not cards:
        cards = [h3.find_parent(["article", "div"]) for h3 in soup.find_all("h3")]
        cards = [c for c in cards if c]

    for card in cards:
        h3 = card.find(["h3", "h2"])
        if not h3:
            continue
        title = _strip(h3.get_text())
        if not title or len(title) < 5:
            continue
        # --- Link
        href = None
        for a in card.find_all("a", href=True):
            if "/job/" in a["href"]:
                href = a["href"]
                break
        if not href:
            # Fallback: just point at the search page; we'll still show the card.
            href = _SEARCH_URL
        url = urljoin(_BASE, href.split("?")[0])
        if url in seen_urls:
            continue
        seen_urls.add(url)

        # --- Parse card text body (after title)
        full_text = _strip(card.get_text(" "))
        # Remove the title from the beginning to reduce noise
        body_text = full_text
        if body_text.startswith(title):
            body_text = body_text[len(title):].strip()
        parsed = _parse_card_text(body_text)

        # --- Company guess: first line after title (drushim formats company
        # right after title, typically ending before "אילת" or "|")
        company = None
        # pick first 3 words that look like a company name (Hebrew characters)
        # drushim often shows it in a span with class "company"
        company_span = card.find("a", class_=re.compile(r"company", re.I))
        if company_span:
            company = _strip(company_span.get_text())[:120]
        else:
            # heuristic: text between title and first "|" or "אילת"
            rest = body_text
            # grab up to first pipe
            first_pipe = rest.find("|")
            first_eilat = rest.find("אילת")
            cutoff = -1
            for c in (first_pipe, first_eilat):
                if c > 0 and (cutoff == -1 or c < cutoff):
                    cutoff = c
            if cutoff > 3:
                candidate = _strip(rest[:cutoff])
                if 3 < len(candidate) < 80:
                    company = candidate

        # Description: anything after the metadata chips
        description = body_text
        # Remove "לפני X שעות" tail if present
        description = _POSTED_RE.sub("", description)
        # Remove pipe separators + dates chunk from the front
        description = re.sub(r"^[^|]*\|[^|]*\|[^|]*\|", "", description, count=1).strip()
        # If description is empty/too short, fall back to body_text
        if len(description) < 15:
            description = body_text

        job = _make_job(
            title=title,
            company=company,
            description=description[:1500],
            source_url=url,
            source="drushim",
            source_name="דרושים.co.il",
            posted_at=parsed["posted_at"],
            job_type=parsed["job_type"],
            experience=parsed["experience"],
        )
        # Eilat-only filter: drop jobs that clearly belong to another city.
        if not is_in_eilat(title, company, description):
            log.debug("drushim drop non-Eilat job: %s", title[:60])
            continue
        results.append(job)
    return results


async def scrape_drushim(_client: httpx.AsyncClient) -> List[Dict[str, Any]]:
    """Drushim requires a real browser. We run the default search AND several
    Hebrew category-scoped searches so we can pull more than the 25-job cap."""
    from scrapers.base import _pw_fetch  # reuse the stealth Chromium
    import urllib.parse

    # Each category URL returns up to ~30 jobs; running a handful in parallel
    # brings the total from 25 → ~80-100+ unique Eilat jobs after dedup.
    CATEGORIES = ["", "מלונות", "מסעדנות", "מכירות", "אבטחה", "ניקיון", "נהג", "בנייה", "בריאות", "הוראה"]
    results_by_url: Dict[str, Dict[str, Any]] = {}

    async def fetch_and_parse(cat: str) -> None:
        if cat:
            url = (
                "https://www.drushim.co.il/jobs/search/"
                "%D7%90%D7%99%D7%9C%D7%AA/"
                f"{urllib.parse.quote(cat)}/?ref=288"
            )
        else:
            url = _SEARCH_URL
        try:
            html = await asyncio.wait_for(_pw_fetch(url), timeout=50)
        except asyncio.TimeoutError:
            log.warning("drushim category %r fetch timed out", cat)
            return
        except Exception as e:
            log.warning("drushim category %r fetch error: %s", cat, e)
            return
        if not html:
            return
        for job in _extract_jobs_from_html(html):
            # dedupe across categories by source_url
            results_by_url.setdefault(job["source_url"], job)

    # Cap concurrency to 3 to avoid hammering the site
    sem = asyncio.Semaphore(3)

    async def guarded(cat: str) -> None:
        async with sem:
            await fetch_and_parse(cat)

    await asyncio.gather(*[guarded(c) for c in CATEGORIES])
    jobs = list(results_by_url.values())
    log.info("drushim → %d jobs (across %d category searches)", len(jobs), len(CATEGORIES))
    return jobs
