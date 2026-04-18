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


def _dt_parse(val: str) -> datetime:
    """Parse a date string. Use dayfirst=True only for non-ISO formats
    (Israeli sources often use DD/MM/YYYY)."""
    s = str(val).strip()
    # ISO 8601 always starts with 4-digit year
    is_iso = bool(re.match(r"^\d{4}[-/]", s))
    return dtparse.parse(s, dayfirst=not is_iso)


def _parse_date(val: Any) -> datetime:
    if not val:
        return datetime.now(timezone.utc)
    if isinstance(val, datetime):
        return val if val.tzinfo else val.replace(tzinfo=timezone.utc)
    try:
        dt = _dt_parse(val)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)


def _extract_date(asoup) -> Optional[datetime]:
    """Robust published-date extraction from common meta tags. Returns None if
    no date could be determined — caller should store None rather than 'now'."""
    candidates = [
        asoup.find("meta", property="article:published_time"),
        asoup.find("meta", property="og:article:published_time"),
        asoup.find("meta", property="og:published_time"),
        asoup.find("meta", attrs={"itemprop": "datePublished"}),
        asoup.find("meta", attrs={"name": "date"}),
        asoup.find("meta", attrs={"name": "pubdate"}),
        asoup.find("meta", attrs={"name": "publishdate"}),
        asoup.find("meta", attrs={"name": "dcterms.issued"}),
        asoup.find("meta", attrs={"name": "dc.date"}),
        asoup.find("meta", attrs={"property": "article:modified_time"}),
        asoup.find("meta", attrs={"property": "og:updated_time"}),
    ]
    for c in candidates:
        if c and c.get("content"):
            try:
                dt = _dt_parse(c["content"])
                return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
            except Exception:
                continue
    t = asoup.find("time")
    if t:
        raw = t.get("datetime") or t.get_text()
        if raw:
            try:
                dt = _dt_parse(raw)
                return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
            except Exception:
                pass
    return None


def _extract_title(asoup) -> Optional[str]:
    """Extract a clean article title from meta tags."""
    def _clean(t: str) -> str:
        # only strip trailing " | Site" or " - Site" when separator has whitespace on BOTH sides
        # and the tail is short (<= 30 chars) and doesn't look like part of the headline.
        t = re.sub(r"\s+[\|\-–—]\s+[^|\-–—:,.?!״]{2,30}$", "", t).strip()
        # strip leading date like "05.04.2026 " sometimes prepended (e.g. Davar)
        t = re.sub(r"^\d{1,2}[./]\d{1,2}[./]\d{2,4}\s+", "", t).strip()
        return t
    og = asoup.find("meta", property="og:title")
    if og and og.get("content"):
        t = _clean(_strip(og["content"]))
        if t and len(t) >= 8:
            return t
    h1 = asoup.find(["h1", "h2"])
    if h1:
        t = _clean(_strip(h1.get_text()))
        if t and len(t) >= 8:
            return t
    if asoup.title:
        t = _clean(_strip(asoup.title.get_text()))
        if t and len(t) >= 8:
            return t
    return None


async def _article_date(client: httpx.AsyncClient, url: str, use_browser: bool = False) -> Optional[datetime]:
    """Fetch an article URL just to extract its publication date from meta tags."""
    html = await _fetch_smart(client, url, use_browser=use_browser)
    if not html:
        return None
    try:
        return _extract_date(BeautifulSoup(html, "lxml"))
    except Exception:
        return None


async def _article_meta(client: httpx.AsyncClient, url: str, use_browser: bool = False) -> Dict[str, Any]:
    """Fetch article URL and return dict with {date, title, image}."""
    html = await _fetch_smart(client, url, use_browser=use_browser)
    if not html:
        return {}
    try:
        soup = BeautifulSoup(html, "lxml")
        out: Dict[str, Any] = {}
        d = _extract_date(soup)
        if d:
            out["published_at"] = d
        t = _extract_title(soup)
        if t:
            out["title"] = t
        og_img = soup.find("meta", property="og:image")
        if og_img and og_img.get("content"):
            out["image"] = urljoin(url, og_img["content"])
        og_d = soup.find("meta", property="og:description") or soup.find(
            "meta", attrs={"name": "description"}
        )
        if og_d and og_d.get("content"):
            out["summary"] = _strip(og_d["content"])[:400]
        return out
    except Exception:
        return {}


async def _enrich_dates(client: httpx.AsyncClient, articles: List[Dict[str, Any]], use_browser: bool = False, concurrency: int = 5) -> None:
    """Populate published_at, title (if breadcrumb/noisy) and image by fetching
    each article URL in parallel. Mutates in-place."""
    if not articles:
        return
    sem = asyncio.Semaphore(concurrency)

    def _title_looks_bad(t: str) -> bool:
        if not t:
            return True
        # breadcrumb trails ("site>tag>..."), or very long/short
        if ">" in t and t.count(">") >= 2:
            return True
        # date prefix like "05.04.2026 ..." (Davar listing titles)
        if re.match(r"^\d{1,2}[./]\d{1,2}[./]\d{2,4}\s", t):
            return True
        if len(t) < 10 or len(t) > 250:
            return True
        return False

    async def run(a: Dict[str, Any]):
        needs_date = not a.get("published_at")
        needs_title = _title_looks_bad(a.get("title", ""))
        needs_image = not a.get("image")
        if not (needs_date or needs_title or needs_image):
            return
        async with sem:
            try:
                meta = await _article_meta(client, a["source_url"], use_browser=False)
                if not meta and use_browser:
                    meta = await _article_meta(client, a["source_url"], use_browser=True)
                if meta.get("published_at") and needs_date:
                    a["published_at"] = meta["published_at"]
                if meta.get("title") and needs_title:
                    a["title"] = meta["title"][:300]
                if meta.get("image") and needs_image:
                    a["image"] = meta["image"]
                if meta.get("summary") and (not a.get("summary") or len(a.get("summary", "")) < 30):
                    a["summary"] = meta["summary"]
            except Exception:
                pass

    await asyncio.gather(*[run(a) for a in articles])


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


# Cache a single Playwright browser per process — reused across fetches.
_PW_CTX: Dict[str, Any] = {"browser": None, "pw": None, "lock": asyncio.Lock()}


async def _pw_fetch(url: str) -> Optional[str]:
    """Fetch a URL via headless Chromium + stealth patches. Used for sites that
    block httpx/bots (kan, gov.il, tiuli, etc.). Renders JS and returns final HTML."""
    try:
        from playwright.async_api import async_playwright
    except Exception as e:
        log.warning("playwright not installed: %s", e)
        return None
    # stealth patches (anti-detection for headless Chromium)
    try:
        from playwright_stealth import Stealth  # type: ignore
        stealth = Stealth()
    except Exception:
        stealth = None
    async with _PW_CTX["lock"]:
        if _PW_CTX["browser"] is None:
            try:
                pw = await async_playwright().start()
                browser = await pw.chromium.launch(
                    headless=True,
                    args=[
                        "--no-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-blink-features=AutomationControlled",
                        "--disable-features=IsolateOrigins,site-per-process",
                    ],
                )
                _PW_CTX["pw"] = pw
                _PW_CTX["browser"] = browser
            except Exception as e:
                log.warning("playwright launch failed: %s", e)
                return None
    browser = _PW_CTX["browser"]
    context = None
    try:
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="he-IL",
            timezone_id="Asia/Jerusalem",
            viewport={"width": 1366, "height": 820},
            ignore_https_errors=True,
        )
        if stealth is not None:
            try:
                await stealth.apply_stealth_async(context)
            except Exception as e:
                log.debug("stealth apply failed: %s", e)
        page = await context.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            # Wait for SPA content to hydrate — required for Kan, Gov.il, Tiuli
            try:
                await page.wait_for_load_state("networkidle", timeout=12000)
            except Exception:
                pass
            await page.wait_for_timeout(4000)
            html = await page.content()
            return html
        except Exception as e:
            log.warning("pw nav failed %s: %s", url, e)
            return None
    except Exception as e:
        log.warning("pw context failed %s: %s", url, e)
        return None
    finally:
        if context is not None:
            try:
                await context.close()
            except Exception:
                pass


async def _fetch_smart(client: httpx.AsyncClient, url: str, use_browser: bool = False) -> Optional[str]:
    """Try fast httpx first; fall back to Playwright on failure or when use_browser=True."""
    if not use_browser:
        html = await _fetch(client, url)
        if html:
            return html
    # use browser fallback
    return await _pw_fetch(url)


def _make_article(
    title: str,
    summary: str,
    content_html: str,
    image: Optional[str],
    source_name: str,
    source_url: str,
    published_at: Optional[datetime],
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
                published_at=None,
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
    """Ynet — scrape the Eilat topic page (requires stealth browser)."""
    topic_url = "https://www.ynet.co.il/topics/%D7%90%D7%99%D7%9C%D7%AA"
    html = await _pw_fetch(topic_url)
    if not html:
        html = await _fetch(client, topic_url)
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    out: List[Dict[str, Any]] = []
    seen = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/article/" not in href:
            continue
        full = urljoin("https://www.ynet.co.il", href)
        if full in seen:
            continue
        # Walk up the DOM to find the article title context
        context = _strip(a.get_text())
        node = a
        for _ in range(6):
            if node is None:
                break
            t = _strip(node.get_text())
            if len(t) > len(context):
                context = t
            node = node.parent
        if len(context) < 10:
            continue
        if not _contains_eilat(context):
            continue
        # Best title candidate
        title = ""
        for tag_name in ("h2", "h3", "h1"):
            el = a.find(tag_name) or (a.parent.find(tag_name) if a.parent else None)
            if el:
                tt = _strip(el.get_text())
                if tt:
                    title = tt
                    break
        if not title:
            title = context[:150]
        if len(title) < 8:
            continue
        img_tag = a.find("img")
        img = img_tag.get("src") if img_tag else None
        if img and img.startswith("//"):
            img = "https:" + img
        seen.add(full)
        out.append(
            _make_article(
                title=title,
                summary=context[:300],
                content_html=f'<p>{title}</p><p><a href="{full}">קרא את הכתבה המלאה ב-Ynet</a></p>',
                image=img,
                source_name="Ynet",
                source_url=full,
                published_at=None,
                source_type="news",
            )
        )
        if len(out) >= 25:
            break
    await _enrich_dates(client, out, use_browser=False, concurrency=5)
    return out


async def scrape_kan_eilat(client: httpx.AsyncClient) -> List[Dict[str, Any]]:
    """Kan — Eilat tag page (requires stealth browser)."""
    tag_url = "https://www.kan.org.il/tags/generaltags/%D7%90%D7%99%D7%9C%D7%AA/"
    html = await _pw_fetch(tag_url)
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    out: List[Dict[str, Any]] = []
    seen = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        full = urljoin("https://www.kan.org.il", href)
        # Kan article URLs live under /content/kan-news/
        if "/content/kan-news/" not in full:
            continue
        if full in seen:
            continue
        title = _strip(a.get_text())
        if len(title) < 10:
            continue
        # walk up to enrich context if needed
        if not _contains_eilat(title):
            node = a
            ctx = title
            for _ in range(4):
                if node is None:
                    break
                t = _strip(node.get_text())
                if len(t) > len(ctx):
                    ctx = t
                node = node.parent
            if not _contains_eilat(ctx):
                # Since we're on the Eilat tag page, treat listed links as Eilat-related
                # even without explicit keyword in title, but prefer ones we're sure about
                pass
        img_tag = a.find("img")
        img = img_tag.get("src") if img_tag else None
        if img and img.startswith("//"):
            img = "https:" + img
        seen.add(full)
        out.append(
            _make_article(
                title=title,
                summary=title,
                content_html=f'<p>{title}</p><p><a href="{full}">קרא/צפה בכתבה המלאה בכאן חדשות</a></p>',
                image=img,
                source_name="כאן חדשות",
                source_url=full,
                published_at=None,
                source_type="news",
            )
        )
        if len(out) >= 25:
            break
    await _enrich_dates(client, out, use_browser=False, concurrency=5)
    return out


# ---------------------------------------------------------------------------
# Israel Hayom — Eilat tag
# ---------------------------------------------------------------------------

async def _scrape_tag_page(
    client: httpx.AsyncClient,
    tag_url: str,
    source_name: str,
    base_host: str,
    link_pattern: re.Pattern,
    host_whitelist: Optional[List[str]] = None,
    max_items: int = 25,
    use_browser: bool = False,
    enrich_use_browser: bool = False,
    require_eilat_in_context: bool = False,
) -> List[Dict[str, Any]]:
    """Generic tag-page scraper: fetch the tag page, discover article links
    matching `link_pattern`, then enrich each with real publish dates."""
    html = await _fetch_smart(client, tag_url, use_browser=use_browser)
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    out: List[Dict[str, Any]] = []
    seen = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        full = urljoin(tag_url, href)
        if not full.startswith(("http://", "https://")):
            continue
        host = urlparse(full).netloc.lower()
        if host_whitelist and not any(h in host for h in host_whitelist):
            continue
        if not link_pattern.search(full):
            continue
        if full in seen:
            continue
        # Build a title candidate by walking up the DOM
        context = _strip(a.get_text())
        title = context
        node = a
        for _ in range(5):
            if node is None:
                break
            t = _strip(node.get_text())
            if len(t) > len(title):
                title = t
            node = node.parent
        for tag_name in ("h2", "h3", "h1"):
            el = a.find(tag_name) or (a.parent.find(tag_name) if a.parent else None)
            if el:
                tt = _strip(el.get_text())
                if tt and len(tt) >= 8:
                    title = tt
                    break
        if not title or len(title) < 8:
            continue
        if require_eilat_in_context:
            if not (_contains_eilat(title) or _contains_eilat(context)):
                continue
        img_tag = a.find("img")
        img = img_tag.get("src") if img_tag else None
        if img and img.startswith("//"):
            img = "https:" + img
        seen.add(full)
        out.append(
            _make_article(
                title=title[:250],
                summary=context[:300] if context else title,
                content_html=f'<p>{title}</p><p><a href="{full}">קרא את הכתבה המלאה ב-{source_name}</a></p>',
                image=img,
                source_name=source_name,
                source_url=full,
                published_at=None,
                source_type="news",
            )
        )
        if len(out) >= max_items:
            break
    await _enrich_dates(client, out, use_browser=enrich_use_browser, concurrency=4)
    return out


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

async def scrape_mako_eilat(client: httpx.AsyncClient) -> List[Dict[str, Any]]:
    url = "https://www.mako.co.il/Tagit/%D7%90%D7%99%D7%9C%D7%AA"
    # Use stealth browser first — Mako blocks httpx bots
    html = await _pw_fetch(url) or await _fetch(client, url)
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
        # Walk up ancestors to find the article title/context text
        context = _strip(a.get_text())
        node = a
        for _ in range(6):
            if node is None:
                break
            t = _strip(node.get_text())
            if len(t) > len(context):
                context = t
            node = node.parent
        if not _contains_eilat(context):
            continue
        # Pick the best available title
        title = ""
        for cls in ("title-wrap", "title", "titleArea", "h2", "h3"):
            el = a.find(cls) or (a.parent.find(cls) if a.parent else None)
            if el:
                tt = _strip(el.get_text())
                if tt:
                    title = tt
                    break
        if not title:
            # fallback to longest contextual text < 200 chars
            title = context[:150]
        if len(title) < 8:
            continue
        img_tag = a.find("img")
        img = img_tag.get("src") if img_tag else None
        if img and img.startswith("//"):
            img = "https:" + img
        seen.add(full)
        out.append(
            _make_article(
                title=title,
                summary=context[:300],
                content_html=f'<p>{title}</p><p><a href="{full}">קרא את הכתבה המלאה ב-Mako</a></p>',
                image=img,
                source_name="Mako",
                source_url=full,
                published_at=None,
                source_type="news",
            )
        )
        if len(out) >= 25:
            break
    await _enrich_dates(client, out, use_browser=True, concurrency=3)
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
            published_at=None,
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
                published_at=None,
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
    use_browser: bool = False,
) -> List[Dict[str, Any]]:
    """Scan a site's homepage, discover article links, fetch each and extract content.
    When use_browser=True, uses Playwright headless Chromium (for sites that block bots).
    """
    html = await _fetch_smart(client, base_url, use_browser=use_browser)
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
        path = urlparse(full).path
        if patterns:
            if not any(p.search(full) for p in patterns):
                continue
        else:
            segs = [s for s in path.split("/") if s]
            if len(segs) < 1:
                continue
            if any(bad in path.lower() for bad in [
                "/tag/", "/category/", "/author/", "/search", "/login", "/register",
                "/wp-admin", "/wp-login", "/contact", "/about", "/privacy", "/terms",
                "/cart", "/checkout", "/account", ".pdf", ".jpg", ".png", ".gif", ".xml",
            ]):
                continue
        # Eilat keyword pre-filter: check anchor text + parent context
        if require_eilat_keyword:
            anchor_text = _strip(a.get_text())
            parent_text = _strip(a.parent.get_text() if a.parent else "")
            url_text = full  # Eilat might be in the URL slug
            if not (
                _contains_eilat(anchor_text)
                or _contains_eilat(parent_text)
                or _contains_eilat(url_text)
            ):
                continue
        seen.add(full)
        candidates.append(full)

    out: List[Dict[str, Any]] = []
    for url in candidates:
        if len(out) >= max_items:
            break
        art = await _fetch_smart(client, url, use_browser=use_browser)
        if not art:
            continue
        asoup = BeautifulSoup(art, "lxml")
        # title
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

        # body
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

        # post-filter by Eilat keyword
        if require_eilat_keyword:
            if not _contains_eilat(title + " " + summary + " " + body_text):
                continue

        pub = _extract_date(asoup)

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
# Format: (base_url, source_name, source_type, link_patterns, max_items, require_eilat_keyword, use_browser)
FULL_SITE_SOURCES = [
    # Eilat-only domains → no keyword filter (everything IS Eilat)
    ("https://eilat.city/", "אילת סיטי", "news", None, 50, False, False),
    ("https://eilatport.co.il/", "נמל אילת", "news", None, 40, False, False),
    ("https://icemalleilat.co.il/", "אייס מול אילת", "event", None, 40, False, False),
    ("https://biz.eilat.muni.il/", "עסקים — עיריית אילת", "news", None, 40, False, False),
    # יום יום (regional)
    ("https://www.yomyom.net/", "יום יום", "news", None, 40, True, False),
    # Ynet / Mako / Kan: handled by dedicated topic/tag scrapers (SCRAPERS list)
    # Tiuli, SBA, Parks, Gov.il: deactivated per user (low value vs. effort)
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

        for url, src, stype, patterns, max_items, req_eilat, use_browser in FULL_SITE_SOURCES:
            try:
                items = await scrape_site_articles(
                    client,
                    base_url=url,
                    source_name=src,
                    source_type=stype,
                    link_patterns=patterns,
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
