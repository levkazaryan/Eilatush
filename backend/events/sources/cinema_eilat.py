"""cinema-eilat.co.il — local cinema screenings schedule.

The site itself does not expose schedule data on the listing page.
Each movie has a detail page that embeds a ticket-vendor iframe pointing to
``cinema-eilat.smarticket.co.il/{movie_name}/`` — and THAT page lists the
actual screenings (date + time + hall) for the movie in the next weeks.

This scraper:
  1. Fetches the main "לוח סרטים" page → list of {title, poster, detail_url}.
  2. For each movie, fetches the detail page → extracts the smarticket
     iframe URL.
  3. Fetches the smarticket page → parses all upcoming screenings.
  4. Emits ONE event per screening (multiple showings ⇒ multiple events).

Movies with no upcoming screenings are skipped entirely (avoids ghost
"today at 20:00" placeholders that previously broke the events feed).
"""
from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..base import HEADERS, TIMEOUT, EventDict, pack

URL = "https://cinema-eilat.co.il/לוח-סרטים/"
_SRC = "cinema_eilat"
IST = timezone(timedelta(hours=2))
log = logging.getLogger(__name__)

# Hebrew month names → numeric month (with optional "ב" prefix stripped before lookup)
HEB_MONTHS = {
    "ינואר": 1, "פברואר": 2, "מרץ": 3, "מרס": 3, "אפריל": 4,
    "מאי": 5, "יוני": 6, "יולי": 7, "אוגוסט": 8, "ספטמבר": 9,
    "אוקטובר": 10, "נובמבר": 11, "דצמבר": 12,
}

# Match a Hebrew calendar date inside the smarticket schedule table.
#   Example: "ביום ראשון, 14 ביוני 2026 : בשעה 18:30"
_RE_DATE = re.compile(
    r"(\d{1,2})\s+ב?(ינואר|פברואר|מרץ|מרס|אפריל|מאי|יוני|יולי|"
    r"אוגוסט|ספטמבר|אוקטובר|נובמבר|דצמבר)\s+(\d{4})"
)
_RE_TIME = re.compile(r"בשעה\s*(\d{1,2}):(\d{2})")
_RE_HALL = re.compile(r"אולם\s*(\d+)")

# Junk headings that occasionally slip past the keyword filter on the
# listing page. They never correspond to actual movies.
_BAD_HEADING_TOKENS = (
    "פרטי", "תפריט", "צור קשר", "הזמנ", "אודות", "עקבו",
    "ליצירת", "פנו אלינו", "ברשתות", "החברתיות",
    "עכשיו ב", "מבצע", "שעות פתיחה", "הצהרת נגישות",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_screenings(html: str) -> List[tuple[datetime, Optional[str]]]:
    """Parse the smarticket page HTML and return a list of (start_utc, hall).

    The schedule lives in a table whose rows look like:
        ביום ראשון, 14 ביוני 2026 : בשעה 18:30  |  אולם 2  |  הזמן עכשיו
    We iterate by table row so each date/time/hall triple stays together.
    """
    out: List[tuple[datetime, Optional[str]]] = []
    seen: set[tuple[datetime, Optional[str]]] = set()
    soup = BeautifulSoup(html, "html.parser")

    def _add(start_utc: datetime, hall: Optional[str]) -> None:
        key = (start_utc, hall)
        if key in seen:
            return
        seen.add(key)
        out.append(key)

    for row in soup.find_all("tr"):
        text = row.get_text(" ", strip=True)
        date_m = _RE_DATE.search(text)
        time_m = _RE_TIME.search(text)
        if not date_m or not time_m:
            continue
        try:
            day = int(date_m.group(1))
            month = HEB_MONTHS.get(date_m.group(2))
            year = int(date_m.group(3))
            hh = int(time_m.group(1))
            mm = int(time_m.group(2))
            if not month:
                continue
            start_local = datetime(year, month, day, hh, mm, tzinfo=IST)
        except (ValueError, TypeError):
            continue

        hall_m = _RE_HALL.search(text)
        hall = hall_m.group(1) if hall_m else None
        _add(start_local.astimezone(timezone.utc), hall)

    # If no table rows yielded results, fall back to scanning the raw text
    # (some smarticket templates omit <table>).
    if not out:
        plain = soup.get_text(" ", strip=True)
        # Find every date occurrence and pair with the NEAREST following time.
        for m in _RE_DATE.finditer(plain):
            window = plain[m.end():m.end() + 80]
            tm = _RE_TIME.search(window)
            if not tm:
                continue
            try:
                day = int(m.group(1))
                month = HEB_MONTHS.get(m.group(2))
                year = int(m.group(3))
                hh = int(tm.group(1))
                mm = int(tm.group(2))
                if not month:
                    continue
                start_local = datetime(year, month, day, hh, mm, tzinfo=IST)
                out.append((start_local.astimezone(timezone.utc), None))
            except (ValueError, TypeError):
                continue

    return out


async def _fetch_iframe_url(client, movie_url: str) -> Optional[str]:
    """Open a movie detail page and return the smarticket iframe URL."""
    try:
        r = await client.get(movie_url, headers=HEADERS, timeout=TIMEOUT,
                             follow_redirects=True)
    except Exception as e:
        log.warning("cinema: detail fetch failed %s: %s", movie_url, e)
        return None
    if r.status_code != 200:
        return None
    # Quick string search before invoking BeautifulSoup — much faster.
    if "smarticket.co.il" not in r.text:
        return None
    soup = BeautifulSoup(r.text, "html.parser")
    for iframe in soup.find_all("iframe"):
        src = iframe.get("src") or ""
        if "smarticket.co.il" in src:
            return src
    return None


async def _fetch_smarticket(client, url: str) -> List[tuple[datetime, Optional[str]]]:
    """Fetch a smarticket page and return its parsed screenings."""
    try:
        r = await client.get(url, headers=HEADERS, timeout=TIMEOUT,
                             follow_redirects=True)
    except Exception as e:
        log.warning("cinema: smarticket fetch failed %s: %s", url, e)
        return []
    if r.status_code != 200:
        return []
    return _parse_screenings(r.text)


# ---------------------------------------------------------------------------
# Main scraper
# ---------------------------------------------------------------------------

async def scrape_cinema_eilat(client) -> List[EventDict]:
    try:
        r = await client.get(URL, headers=HEADERS, timeout=TIMEOUT,
                             follow_redirects=True)
    except Exception as e:
        log.warning("cinema fetch failed: %s", e)
        return []
    if r.status_code != 200:
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    venue = "קולנוע אילת"
    now_utc = datetime.now(timezone.utc)
    horizon_utc = now_utc + timedelta(days=30)  # only future-month screenings

    # ----- Step 1: Build {title: (poster, detail_url)} from the listing -----
    movies: dict[str, dict] = {}
    for img in soup.find_all("img"):
        src = (
            img.get("data-src")
            or img.get("src")
            or (img.get("srcset", "").split(" ") or [""])[0]
        )
        if not src or "logo" in src.lower() or "לוגו" in src:
            continue
        if not re.search(r"\.(jpe?g|png|webp)", src, re.IGNORECASE):
            continue
        if src.startswith("//"):
            src = "https:" + src

        # Find the nearest heading (movie title) by walking up.
        node = img
        heading_text: Optional[str] = None
        detail_url: Optional[str] = None
        for _ in range(6):
            if not node:
                break
            h = node.find(["h1", "h2", "h3"]) if hasattr(node, "find") else None
            if h:
                heading_text = h.get_text(strip=True)
                a = h.find("a")
                if a and a.get("href"):
                    detail_url = urljoin(URL, a["href"])
                break
            nxt = node.find_next_sibling() if hasattr(node, "find_next_sibling") else None
            if nxt:
                h2 = nxt.find(["h1", "h2", "h3"]) if hasattr(nxt, "find") else None
                if h2:
                    heading_text = h2.get_text(strip=True)
                    a = h2.find("a")
                    if a and a.get("href"):
                        detail_url = urljoin(URL, a["href"])
                    break
            node = node.parent

        if not heading_text or heading_text in movies:
            continue
        # filter junk headings
        if any(bad in heading_text for bad in _BAD_HEADING_TOKENS):
            continue
        if ":" in heading_text or "@" in heading_text:
            continue
        if len(heading_text) < 2 or len(heading_text) > 80:
            continue
        if not detail_url:
            continue
        movies[heading_text] = {"poster": src, "detail_url": detail_url}

    # ----- Step 2: For each movie, fetch detail → iframe → smarticket -----
    async def _process(title: str, meta: dict) -> List[EventDict]:
        iframe_url = await _fetch_iframe_url(client, meta["detail_url"])
        if not iframe_url:
            return []
        screenings = await _fetch_smarticket(client, iframe_url)
        if not screenings:
            return []
        events: List[EventDict] = []
        for start_utc, hall in screenings:
            # Filter past screenings and far-future ones (>30 days out)
            if start_utc < now_utc - timedelta(hours=2):
                continue
            if start_utc > horizon_utc:
                continue
            hall_suffix = f" · אולם {hall}" if hall else ""
            events.append(
                pack(
                    source=_SRC,
                    # Unique per screening — same movie at different times
                    # creates distinct event docs (no collisions).
                    ext_id=f"movie-{title}-{int(start_utc.timestamp())}",
                    title=f"🎬 {title}",
                    description=f"קולנוע אילת{hall_suffix}",
                    starts_at=start_utc,
                    ends_at=start_utc + timedelta(minutes=120),
                    venue=venue,
                    image=meta["poster"],
                    link=meta["detail_url"],
                    category="cinema",
                    tags=["cinema"],
                )
            )
        return events

    # Bounded concurrency — be polite to the cinema host.
    sem = asyncio.Semaphore(4)

    async def _bounded(title: str, meta: dict) -> List[EventDict]:
        async with sem:
            return await _process(title, meta)

    batches = await asyncio.gather(
        *(_bounded(t, m) for t, m in movies.items()),
        return_exceptions=True,
    )

    results: List[EventDict] = []
    for b in batches:
        if isinstance(b, list):
            results.extend(b)
        else:
            log.warning("cinema: per-movie task crashed: %s", b)

    log.info(
        "cinema-eilat → %d screenings across %d movies",
        len(results),
        len({e["title"] for e in results}),
    )
    return results
