"""
Eilatush news scrapers — each source has its own function returning a list of
Article dicts. Only content related to Eilat is collected.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

import feedparser
import httpx
from bs4 import BeautifulSoup
from dateutil import parser as dtparse

log = logging.getLogger("scrapers")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "he-IL,he;q=0.9,en;q=0.8",
}

TIMEOUT = httpx.Timeout(20.0, connect=10.0)


def _hash_url(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:20]


def _parse_date(val: Any) -> datetime:
    if not val:
        return datetime.now(timezone.utc)
    if isinstance(val, datetime):
        return val if val.tzinfo else val.replace(tzinfo=timezone.utc)
    try:
        dt = dtparse.parse(str(val))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)


def _contains_eilat(text: str) -> bool:
    if not text:
        return False
    t = text.lower()
    return "אילת" in text or "eilat" in t or "עיריית אילת" in text


def _strip(s: Optional[str]) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


async def _fetch(client: httpx.AsyncClient, url: str) -> Optional[str]:
    try:
        r = await client.get(url, timeout=TIMEOUT, follow_redirects=True)
        r.raise_for_status()
        return r.text
    except Exception as e:
        log.warning("fetch failed %s: %s", url, e)
        return None


def _make_article(
    title: str,
    summary: str,
    content_html: str,
    image: Optional[str],
    source_name: str,
    source_url: str,
    published_at: datetime,
    source_type: str = "news",
) -> Dict[str, Any]:
    return {
        "id": _hash_url(source_url),
        "title": _strip(title)[:300],
        "summary": _strip(summary)[:500],
        "content_html": content_html or "",
        "image": image or None,
        "source_name": source_name,
        "source_url": source_url,
        "source_type": source_type,  # "news" | "event" | "alert"
        "published_at": published_at,
        "fetched_at": datetime.now(timezone.utc),
    }


# ---------------------------------------------------------------------------
# Eilat Municipality
# ---------------------------------------------------------------------------

async def scrape_eilat_muni_articles(client: httpx.AsyncClient) -> List[Dict[str, Any]]:
    """Municipality main articles listing."""
    base = "https://www.eilat.muni.il"
    list_url = f"{base}/articles/"
    html = await _fetch(client, list_url)
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    results: List[Dict[str, Any]] = []
    seen = set()
    # heuristic: look for links to /articles/item/<id>/
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/articles/item/" not in href:
            continue
        full = urljoin(base, href)
        if full in seen:
            continue
        seen.add(full)
        title = _strip(a.get_text())
        if not title or len(title) < 5:
            continue
        img = None
        img_tag = a.find("img")
        if img_tag and img_tag.get("src"):
            img = urljoin(base, img_tag["src"])
        results.append((full, title, img))
        if len(results) >= 15:
            break

    articles: List[Dict[str, Any]] = []
    # fetch each article for full content
    for full, title, img in results:
        art_html = await _fetch(client, full)
        content_html = ""
        summary = ""
        pub = datetime.now(timezone.utc)
        hero = img
        if art_html:
            asoup = BeautifulSoup(art_html, "lxml")
            # main content
            main = (
                asoup.find("article")
                or asoup.find("div", class_=re.compile("content|article|main", re.I))
                or asoup.find("main")
            )
            if main:
                for bad in main.find_all(["script", "style", "nav", "aside"]):
                    bad.decompose()
                content_html = str(main)
                summary = _strip(main.get_text())[:400]
            # og image
            og = asoup.find("meta", property="og:image")
            if og and og.get("content"):
                hero = urljoin(base, og["content"])
            # date
            tdate = asoup.find("time")
            if tdate:
                pub = _parse_date(tdate.get("datetime") or tdate.get_text())
        articles.append(
            _make_article(
                title=title,
                summary=summary or title,
                content_html=content_html,
                image=hero,
                source_name="עיריית אילת",
                source_url=full,
                published_at=pub,
                source_type="news",
            )
        )
    return articles


async def scrape_eilat_muni_mivzak(client: httpx.AsyncClient) -> List[Dict[str, Any]]:
    """Municipality alerts/mivzak."""
    base = "https://www.eilat.muni.il"
    list_url = f"{base}/news/"
    html = await _fetch(client, list_url)
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    out: List[Dict[str, Any]] = []
    seen = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/mivzak/" not in href:
            continue
        full = urljoin(base, href)
        if full in seen:
            continue
        seen.add(full)
        title = _strip(a.get_text())
        if len(title) < 5:
            continue
        art = await _fetch(client, full)
        content_html = ""
        summary = title
        pub = datetime.now(timezone.utc)
        hero = None
        if art:
            asoup = BeautifulSoup(art, "lxml")
            main = asoup.find("article") or asoup.find("main") or asoup.find("body")
            if main:
                for bad in main.find_all(["script", "style", "nav", "aside"]):
                    bad.decompose()
                content_html = str(main)
                summary = _strip(main.get_text())[:400]
            og = asoup.find("meta", property="og:image")
            if og and og.get("content"):
                hero = urljoin(base, og["content"])
        out.append(
            _make_article(
                title=title,
                summary=summary,
                content_html=content_html,
                image=hero,
                source_name="עיריית אילת — מבזקים",
                source_url=full,
                published_at=pub,
                source_type="alert",
            )
        )
        if len(out) >= 10:
            break
    return out


# ---------------------------------------------------------------------------
# Smarticket (events)
# ---------------------------------------------------------------------------

async def scrape_smarticket(client: httpx.AsyncClient) -> List[Dict[str, Any]]:
    base = "https://eilatmuni.smarticket.co.il"
    html = await _fetch(client, base)
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    out: List[Dict[str, Any]] = []
    seen = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/event/" not in href:
            continue
        full = urljoin(base, href)
        if full in seen:
            continue
        seen.add(full)
        title = _strip(a.get_text()) or "אירוע"
        img_tag = a.find("img")
        img = urljoin(base, img_tag["src"]) if img_tag and img_tag.get("src") else None
        out.append(
            _make_article(
                title=title,
                summary=title,
                content_html=f'<p>{title}</p><p><a href="{full}">פרטים ורכישת כרטיסים</a></p>',
                image=img,
                source_name="אירועים — עיריית אילת",
                source_url=full,
                published_at=datetime.now(timezone.utc),
                source_type="event",
            )
        )
        if len(out) >= 12:
            break
    return out


# ---------------------------------------------------------------------------
# Ynet — Eilat topic
# ---------------------------------------------------------------------------

YNET_RSS_CANDIDATES = [
    "https://www.ynet.co.il/Integration/StoryRss1854.xml",
    "https://www.ynet.co.il/Integration/StoryRss2.xml",
]


async def scrape_ynet_eilat(client: httpx.AsyncClient) -> List[Dict[str, Any]]:
    """Ynet — filter for Eilat-related content."""
    out: List[Dict[str, Any]] = []
    # try topic page via HTML
    topic_url = "https://www.ynet.co.il/topics/%D7%90%D7%99%D7%9C%D7%AA"
    html = await _fetch(client, topic_url)
    if html:
        soup = BeautifulSoup(html, "lxml")
        seen = set()
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/article/" not in href:
                continue
            full = urljoin("https://www.ynet.co.il", href)
            if full in seen:
                continue
            seen.add(full)
            title = _strip(a.get_text())
            if len(title) < 10:
                continue
            if not _contains_eilat(title):
                # also check parent context
                parent_text = _strip(a.parent.get_text() if a.parent else "")
                if not _contains_eilat(parent_text):
                    continue
            img_tag = a.find("img")
            img = img_tag.get("src") if img_tag else None
            out.append(
                _make_article(
                    title=title,
                    summary=title,
                    content_html=f'<p>{title}</p><p><a href="{full}">קרא את הכתבה המלאה ב-Ynet</a></p>',
                    image=img,
                    source_name="Ynet",
                    source_url=full,
                    published_at=datetime.now(timezone.utc),
                    source_type="news",
                )
            )
            if len(out) >= 10:
                break
    return out


# ---------------------------------------------------------------------------
# Mako — Eilat tag
# ---------------------------------------------------------------------------

async def scrape_mako_eilat(client: httpx.AsyncClient) -> List[Dict[str, Any]]:
    url = "https://mobile.mako.co.il/Tagit/%D7%90%D7%99%D7%9C%D7%AA"
    html = await _fetch(client, url)
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    out: List[Dict[str, Any]] = []
    seen = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/news/" not in href and "/Article-" not in href:
            continue
        full = urljoin("https://www.mako.co.il", href)
        if full in seen:
            continue
        seen.add(full)
        title = _strip(a.get_text())
        if len(title) < 10:
            continue
        if not _contains_eilat(title):
            parent_text = _strip(a.parent.get_text() if a.parent else "")
            if not _contains_eilat(parent_text):
                continue
        img_tag = a.find("img")
        img = img_tag.get("src") if img_tag else None
        out.append(
            _make_article(
                title=title,
                summary=title,
                content_html=f'<p>{title}</p><p><a href="{full}">קרא את הכתבה המלאה ב-Mako</a></p>',
                image=img,
                source_name="Mako",
                source_url=full,
                published_at=datetime.now(timezone.utc),
                source_type="news",
            )
        )
        if len(out) >= 8:
            break
    return out


# ---------------------------------------------------------------------------
# Generic simple page scrapers (short descriptive pages)
# ---------------------------------------------------------------------------

async def scrape_single_page(
    client: httpx.AsyncClient, url: str, source_name: str, source_type: str = "news"
) -> List[Dict[str, Any]]:
    html = await _fetch(client, url)
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    title = _strip(soup.title.get_text()) if soup.title else url
    og = soup.find("meta", property="og:title")
    if og and og.get("content"):
        title = _strip(og["content"])
    desc = ""
    og_desc = soup.find("meta", property="og:description") or soup.find(
        "meta", attrs={"name": "description"}
    )
    if og_desc and og_desc.get("content"):
        desc = _strip(og_desc["content"])
    img = None
    og_img = soup.find("meta", property="og:image")
    if og_img and og_img.get("content"):
        img = urljoin(url, og_img["content"])

    # main body
    main = (
        soup.find("article")
        or soup.find("main")
        or soup.find("div", class_=re.compile("content|article|main", re.I))
    )
    content_html = ""
    if main:
        for bad in main.find_all(["script", "style", "nav", "aside", "footer", "header"]):
            bad.decompose()
        content_html = str(main)[:20000]

    if not _contains_eilat(title + " " + desc + " " + (main.get_text()[:500] if main else "")):
        return []

    return [
        _make_article(
            title=title,
            summary=desc or title,
            content_html=content_html or f"<p>{desc or title}</p>",
            image=img,
            source_name=source_name,
            source_url=url,
            published_at=datetime.now(timezone.utc),
            source_type=source_type,
        )
    ]


async def scrape_listing_eilat_filtered(
    client: httpx.AsyncClient,
    url: str,
    source_name: str,
    link_pattern: str = r"",
    max_items: int = 10,
) -> List[Dict[str, Any]]:
    """Scrape a listing, keep only links whose title/context mentions Eilat."""
    html = await _fetch(client, url)
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    out: List[Dict[str, Any]] = []
    seen = set()
    pat = re.compile(link_pattern) if link_pattern else None
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not href or href.startswith("javascript:") or href.startswith("#") or href.startswith("mailto:"):
            continue
        if pat and not pat.search(href):
            continue
        full = urljoin(url, href)
        if not full.startswith(("http://", "https://")):
            continue
        if full in seen or full == url:
            continue
        seen.add(full)
        title = _strip(a.get_text())
        parent_text = _strip(a.parent.get_text() if a.parent else "")
        if len(title) < 8:
            continue
        if not _contains_eilat(title) and not _contains_eilat(parent_text):
            continue
        img_tag = a.find("img")
        img = urljoin(url, img_tag["src"]) if img_tag and img_tag.get("src") else None
        out.append(
            _make_article(
                title=title,
                summary=parent_text[:300] if parent_text else title,
                content_html=f"<p>{title}</p><p><a href='{full}'>קרא במקור</a></p>",
                image=img,
                source_name=source_name,
                source_url=full,
                published_at=datetime.now(timezone.utc),
                source_type="news",
            )
        )
        if len(out) >= max_items:
            break
    return out


async def scrape_site_articles(
    client: httpx.AsyncClient,
    base_url: str,
    source_name: str,
    source_type: str = "news",
    link_patterns: Optional[List[str]] = None,
    max_items: int = 15,
    require_eilat_keyword: bool = False,
) -> List[Dict[str, Any]]:
    """Scan a site's homepage, discover article links, fetch each and extract title/content.
    Only follow links on the same domain. When require_eilat_keyword=True, keep only
    articles whose title/content mentions Eilat (for sites that are not Eilat-only).
    """
    html = await _fetch(client, base_url)
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    base_host = urlparse(base_url).netloc
    seen: set = set()
    candidates: List[str] = []
    patterns = [re.compile(p) for p in (link_patterns or [])]
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith(("javascript:", "#", "mailto:", "tel:")):
            continue
        full = urljoin(base_url, href)
        if not full.startswith(("http://", "https://")):
            continue
        if urlparse(full).netloc.replace("www.", "") != base_host.replace("www.", ""):
            continue
        if full.rstrip("/") == base_url.rstrip("/"):
            continue
        if full in seen:
            continue
        # must look like an article/content link — either match known patterns
        # or have a "deep" path (>= 2 segments) which is a good heuristic
        path = urlparse(full).path
        if patterns:
            if not any(p.search(full) for p in patterns):
                continue
        else:
            segs = [s for s in path.split("/") if s]
            if len(segs) < 1:
                continue
            # skip obvious non-content
            if any(bad in path.lower() for bad in [
                "/tag/", "/category/", "/author/", "/search", "/login", "/register",
                "/wp-admin", "/wp-login", "/contact", "/about", "/privacy", "/terms",
                "/cart", "/checkout", "/account", ".pdf", ".jpg", ".png", ".gif", ".xml",
            ]):
                continue
        seen.add(full)
        candidates.append(full)

    out: List[Dict[str, Any]] = []
    for url in candidates:
        if len(out) >= max_items:
            break
        art = await _fetch(client, url)
        if not art:
            continue
        asoup = BeautifulSoup(art, "lxml")
        # title: og:title > article h1 > document title
        title = ""
        og_t = asoup.find("meta", property="og:title")
        if og_t and og_t.get("content"):
            title = _strip(og_t["content"])
        if not title:
            h1 = asoup.find(["h1", "h2"])
            if h1:
                title = _strip(h1.get_text())
        if not title and asoup.title:
            title = _strip(asoup.title.get_text())
        if not title or len(title) < 8:
            continue

        # description
        summary = ""
        og_d = asoup.find("meta", property="og:description") or asoup.find(
            "meta", attrs={"name": "description"}
        )
        if og_d and og_d.get("content"):
            summary = _strip(og_d["content"])

        # hero image
        hero = None
        og_img = asoup.find("meta", property="og:image")
        if og_img and og_img.get("content"):
            hero = urljoin(url, og_img["content"])

        # body: article/main/content div
        main = (
            asoup.find("article")
            or asoup.find("main")
            or asoup.find("div", class_=re.compile("content|article|post|main", re.I))
        )
        content_html = ""
        body_text = ""
        if main:
            for bad in main.find_all(["script", "style", "nav", "aside", "footer", "header", "form"]):
                bad.decompose()
            content_html = str(main)[:20000]
            body_text = _strip(main.get_text())[:800]

        # optional Eilat keyword filter
        if require_eilat_keyword:
            if not _contains_eilat(title + " " + summary + " " + body_text):
                continue

        # optional date
        pub = datetime.now(timezone.utc)
        t = asoup.find("time")
        if t:
            pub = _parse_date(t.get("datetime") or t.get_text())

        if not summary:
            summary = body_text[:300] if body_text else title

        out.append(
            _make_article(
                title=title,
                summary=summary,
                content_html=content_html or f"<p>{summary}</p>",
                image=hero,
                source_name=source_name,
                source_url=url,
                published_at=pub,
                source_type=source_type,
            )
        )
    return out


# ---------------------------------------------------------------------------
# Facebook — NOT SUPPORTED without Graph API
# ---------------------------------------------------------------------------

async def scrape_facebook_eilat_muni(client: httpx.AsyncClient) -> List[Dict[str, Any]]:
    log.warning(
        "Facebook scraping for Eilat.Muni page requires Meta Graph API Token — "
        "skipping. Configure FB_PAGE_ACCESS_TOKEN to enable."
    )
    return []


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

SCRAPERS = [
    ("eilat_muni_articles", scrape_eilat_muni_articles),
    ("eilat_muni_mivzak", scrape_eilat_muni_mivzak),
    ("smarticket_events", scrape_smarticket),
    ("ynet_eilat", scrape_ynet_eilat),
    ("mako_eilat", scrape_mako_eilat),
    ("facebook_eilat_muni", scrape_facebook_eilat_muni),
]


SINGLE_PAGE_SOURCES = [
    # These URLs are specific deep-link pages (one article each) — keep as single-page
    ("https://www.tiuli.com/articles/1925/-329", "טיולי", "news"),
    ("https://www.gov.il/he/pages/information-eilat-development", "ממשל ישראל — פיתוח אילת", "news"),
    (
        "https://www.sba.org.il/hb/MaofServices/courses/Pages/Eilat/ye-13-09-23.aspx",
        "הסוכנות לעסקים קטנים — אילת",
        "news",
    ),
    (
        "https://www.kan.org.il/content/kan-news/newstv/p-963853/s1/1020596/",
        "כאן חדשות",
        "news",
    ),
]

# Full sites — scrape homepage + follow all article links on the same domain
FULL_SITE_SOURCES = [
    # (base_url, source_name, source_type, link_patterns, max_items, require_eilat_keyword)
    ("https://eilat.city/", "אילת סיטי", "news", None, 20, False),
    ("https://eilatport.co.il/", "נמל אילת", "news", None, 15, False),
    ("https://icemalleilat.co.il/", "אייס מול אילת", "event", None, 20, False),
    ("https://biz.eilat.muni.il/", "עסקים — עיריית אילת", "news", None, 20, False),
]

LISTING_FILTERED_SOURCES = [
    ("https://www.parks.org.il/", "רשות הטבע והגנים", r""),
    ("https://www.yomyom.net/", "יום יום", r""),
]


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

        for url, src, stype, patterns, max_items, req_eilat in FULL_SITE_SOURCES:
            try:
                items = await scrape_site_articles(
                    client,
                    base_url=url,
                    source_name=src,
                    source_type=stype,
                    link_patterns=patterns,
                    max_items=max_items,
                    require_eilat_keyword=req_eilat,
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
