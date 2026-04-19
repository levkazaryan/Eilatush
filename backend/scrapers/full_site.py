"""Homepage-crawling scrapers: walk a site's front page, discover
article URLs, enrich and filter. Used for Yomyom et al.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

import httpx
import trafilatura
from bs4 import BeautifulSoup

from .base import (
    _fetch,
    _fetch_smart,
    _make_article,
    _contains_eilat,
    _strip,
    log,
)
from .cleaners import _extract_date, _extract_title

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
    exclude_patterns: Optional[List[str]] = None,
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
    excludes = [re.compile(p) for p in (exclude_patterns or [])]
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
        # per-source exclusion patterns
        if excludes and any(ex.search(full) for ex in excludes):
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

    # ---- Yomyom gap-fill: probe article IDs beyond the highest found on
    # the homepage. Yomyom sometimes publishes articles that aren't yet
    # featured on the home/front page, so relying on homepage links alone
    # misses fresh stories. We probe up to +20 consecutive IDs and stop after
    # 5 consecutive misses (empty/404 responses). Found IDs are *prepended*
    # to the candidates list so they're not starved by the max_items cap.
    if "yomyom.net" in base_url:
        existing_ids = []
        for u in candidates:
            m = re.search(r"article\.asp\?id=(\d+)", u)
            if m:
                existing_ids.append(int(m.group(1)))
        if existing_ids:
            max_id = max(existing_ids)
            gapfill: List[str] = []
            miss_streak = 0
            for probe_id in range(max_id + 1, max_id + 21):
                if miss_streak >= 5:
                    break
                probe_url = f"https://www.yomyom.net/article.asp?id={probe_id}"
                if probe_url in seen:
                    continue
                try:
                    body = await _fetch(client, probe_url)
                except Exception:
                    body = None
                if not body or len(body) < 2000:
                    miss_streak += 1
                    continue
                # quick relevance check before queueing full enrichment
                if "אילת" not in body:
                    miss_streak += 1
                    continue
                miss_streak = 0
                seen.add(probe_url)
                gapfill.append(probe_url)
                log.info("yomyom gap-fill added id=%d", probe_id)
            # Prepend so newest-discovered articles are processed ahead of the
            # (already-scraped) homepage URLs and aren't dropped by max_items.
            if gapfill:
                candidates = gapfill + candidates

    out: List[Dict[str, Any]] = []
    for url in candidates:
        if len(out) >= max_items:
            break
        art = await _fetch_smart(client, url, use_browser=use_browser)
        if not art:
            continue
        asoup = BeautifulSoup(art, "lxml")
        # Extract date FIRST — before any decomposing, because some sites
        # (yomyom.net) put <meta itemprop="datePublished"> inside a <header>
        # tag which we decompose when cleaning the content body below.
        pub = _extract_date(asoup)
        # title — use shared extractor so trailing " - SiteName" gets stripped
        title = _extract_title(asoup) or ""
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

        # Prefer trafilatura-extracted clean article HTML — strips comments,
        # related articles, newsletter CTAs, ads, etc.
        try:
            clean = trafilatura.extract(
                art,
                include_formatting=True,
                include_images=True,
                include_links=False,
                include_tables=False,
                include_comments=False,
                output_format="html",
                url=url,
            )
            if clean:
                inner = re.sub(r"^<html>\s*<body>\s*", "", clean)
                inner = re.sub(r"\s*</body>\s*</html>\s*$", "", inner)
                content_html = inner[:25000]
        except Exception:
            pass

        # post-filter by Eilat keyword
        if require_eilat_keyword:
            if not _contains_eilat(title + " " + summary + " " + body_text):
                continue

        # Skip yomyom section/column/classifieds aggregator pages that aren't
        # real articles: "מדור ..." / "מותק - מדור ..." / "לוח הנדל״ן" /
        # "לוח מודעות דרושים" / "לוח הדרושים" etc.
        if source_name == "יום יום" and re.search(r"\b(?:מדור|לוח)\b", title):
            continue

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
