"""Generic "tag page" scraper — fetch a source's per-city tag page,
collect article links matching a pattern, enrich each one, then apply
Eilat-relevance + other-city filtering.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from .base import _fetch_smart, _strip, _contains_eilat, _make_article, log
from .enrichment import _enrich_dates

# reused module-level: _is_boilerplate lives inside this function's scope

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
    # Footer/nav boilerplate — skip if the anchor text OR later the article
    # title matches any of these (static pages that happen to live under
    # /article.aspx on some sites).
    _BOILERPLATE = {
        "תנאי שימוש", "מדיניות פרטיות", "צור קשר", "אודות", "ניוזלטר",
        "ניוזלטרים", "RSS", "נגישות", "הצהרת נגישות", "הרשמה", "התחברות",
        "המערכת", "מפת האתר", "פרסום באתר", "דיווח על תקלה",
        "כלי חדש לניהול זמן",  # Globes' "my feed" promo landing
    }
    def _is_boilerplate(text: str) -> bool:
        if not text:
            return False
        t = text.strip()
        if any(b in t for b in _BOILERPLATE):
            return True
        return False

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
        # Strip Outbrain/Taboola recommender query params — links with those
        # are sidebar "recommended" articles, not real tag-page articles.
        # Also filter them out since they point to off-topic content.
        if re.search(r"[?&](obOrigUrl|tmOrigUrl|utm_source=outbrain|utm_source=taboola)", full, re.I):
            continue
        if full in seen:
            continue
        # Build a title candidate by walking up the DOM
        context = _strip(a.get_text())
        # Skip footer/nav boilerplate links (Terms of Use, Privacy, Newsletter etc.)
        if _is_boilerplate(context):
            continue
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
    # Post-enrichment filters:
    # 1) Drop boilerplate pages (Terms/Privacy/Newsletter landing)
    # 2) Drop off-topic articles — articles where "אילת" is NOT in the title,
    #    og:description (summary) or the first ~500 chars of body. These are
    #    usually sidebar/related-articles that happen to mention Eilat in a
    #    tangential sub-section.
    kept: List[Dict[str, Any]] = []
    # Major Israeli cities/regions whose presence in the article TITLE
    # (when Eilat is absent from the title) marks the article as a digest
    # / weekly-newsletter entry that we should skip — the tag-page match was
    # almost certainly due to an Eilat-related sub-section in the body.
    _OTHER_CITIES = [
        "חיפה", "תל אביב", 'ת"א', "ירושלים", "באר שבע",
        "הרצליה", "נתניה", "פתח תקווה", "ראשון לציון", "רמת גן",
        "רחובות", "אשדוד", "אשקלון", "חדרה", "רעננה", "מודיעין",
        "כפר סבא", "בת ים", "חולון", "רמת השרון", "יבנה", "לוד",
        "רמלה", "טבריה", "צפת", "קיסריה", "עפולה", "נצרת",
    ]
    def _mentions_other_city_only(text: str) -> bool:
        if not text:
            return False
        has_eilat = _contains_eilat(text)
        has_other = any(c in text for c in _OTHER_CITIES)
        return has_other and not has_eilat
    for a in out:
        if _is_boilerplate(a.get("title", "")):
            continue
        title = a.get("title", "") or ""
        summary = a.get("summary", "") or ""
        body_head = a.get("_body_head", "") or ""
        # Strengthened Eilat-relevance: Eilat must be present either in the
        # TITLE or in the first ~300 chars of summary/body (not buried at the
        # end of a long newsletter that only mentions Eilat in passing).
        eilat_near_top = (
            _contains_eilat(title)
            or _contains_eilat((summary or "")[:300])
            or _contains_eilat((body_head or "")[:300])
        )
        if not eilat_near_top:
            log.info("dropping off-topic %s (Eilat not near top): %s",
                     source_name, title[:60])
            continue
        # Skip digest pages: title explicitly names a *different* Israeli city
        # and Eilat is absent from the title → this is a weekly newsletter
        # that happens to contain an Eilat sub-item.
        if _mentions_other_city_only(title):
            log.info("dropping digest %s (title mentions other city): %s",
                     source_name, title[:60])
            continue
        # Detect Globes/newsletter digest bodies: they start with a
        # list number immediately followed by the article's own title
        # (e.g. "1 בבילינסון מנסים...").
        if re.match(r"^\s*\d{1,2}\s+\S", body_head):
            # If the numbered digest's numbered title doesn't mention Eilat,
            # drop it — we only want standalone Eilat articles.
            first_sentence = body_head.split(".")[0][:200]
            if not _contains_eilat(title) and not _contains_eilat(first_sentence):
                log.info("dropping digest %s (numbered list body, no Eilat in title/first sentence): %s",
                         source_name, title[:60])
                continue
        a.pop("_body_head", None)  # strip internal field
        kept.append(a)
    return kept
