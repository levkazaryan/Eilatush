"""Per-article enrichment: fetch a single article URL and extract the
full metadata bundle (date, title, image, summary, body, content_html).
"""
from __future__ import annotations

import asyncio
import re
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import httpx
import trafilatura
from bs4 import BeautifulSoup

from .base import _fetch_smart, _strip, log
from .cleaners import (
    _extract_date,
    _extract_title,
    _strip_leading_date,
    _strip_title_prefix,
)

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
    """Fetch article URL and return dict with {date, title, image, summary, body_head, content_html}."""
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
            raw_sum = _strip_leading_date(_strip(og_d["content"]))
            raw_sum = _strip_title_prefix(raw_sum, out.get("title") or t)
            if raw_sum:
                out["summary"] = raw_sum[:1500]
        # Clean article body via trafilatura — extracts ONLY the main article,
        # discarding comments, ads, related-articles, newsletter CTAs, etc.
        try:
            clean_html = trafilatura.extract(
                html,
                include_formatting=True,
                include_images=True,
                include_links=False,
                include_tables=False,
                include_comments=False,
                output_format="html",
                favor_recall=False,
                url=url,
            )
            if clean_html:
                # trafilatura wraps output with <html><body>…</body></html> — strip it
                inner = re.sub(r"^<html>\s*<body>\s*", "", clean_html)
                inner = re.sub(r"\s*</body>\s*</html>\s*$", "", inner)
                out["content_html"] = inner[:25000]
                # build body_head from the extracted text (post-cleanup)
                body_txt = _strip(BeautifulSoup(inner, "lxml").get_text())
                if body_txt:
                    cleaned = _strip_leading_date(body_txt)
                    cleaned = _strip_title_prefix(cleaned, out.get("title") or t)
                    if cleaned:
                        out["body_head"] = cleaned[:800]
        except Exception:
            pass

        # Detect garbage content: trafilatura sometimes extracts the site's
        # breadcrumb + "recent articles" sidebar instead of the actual body
        # (happens on Maariv when the real body is short or wrapped in an
        # unusual layout). If we detect this, try a selector-based extraction.
        def _looks_like_noise(text: str) -> bool:
            if not text:
                return True
            # breadcrumb like "מעריב>תגיות>..." or "לייף סטייל>" very early in text
            head = text[:120]
            if re.search(r">\s*\S+\s*>", head):
                return True
            if "תגיות>" in head or "תגיות <" in head:
                return True
            # lots of "DD/MM/YYYY | HH:MM" stamps in first 400 chars = article list
            stamps = re.findall(r"\d{1,2}[./]\d{1,2}[./]\d{2,4}\s*[|•]\s*\d{1,2}:\d{2}", text[:600])
            if len(stamps) >= 2:
                return True
            return False

        body_head = out.get("body_head") or ""
        if _looks_like_noise(body_head):
            # Prefer selector-based extraction targeting the real article body.
            selector_candidates = [
                "[itemprop='articleBody']",
                "[class*='article-body']",
                "[class*='articleBody']",
                "[class*='article_body']",
                "[class*='article-content']",
                "div.content-article",
                "section.article-body",
            ]
            chosen_html = None
            chosen_text = ""
            for sel in selector_candidates:
                for el in soup.select(sel):
                    # drop ads / noise blocks
                    for bad in el.find_all(["script", "style", "nav", "aside", "footer", "header", "form",
                                              "iframe", "ins", "noscript"]):
                        bad.decompose()
                    txt = _strip(el.get_text(" "))
                    if _looks_like_noise(txt):
                        continue
                    if len(txt) > len(chosen_text):
                        chosen_text = txt
                        chosen_html = str(el)
                if chosen_text and len(chosen_text) > 150:
                    break
            if chosen_text:
                cleaned = _strip_leading_date(chosen_text)
                cleaned = _strip_title_prefix(cleaned, out.get("title") or t)
                if cleaned:
                    out["body_head"] = cleaned[:800]
            if chosen_html:
                # Rebuild a clean paragraph-based HTML from the selected block
                node = BeautifulSoup(chosen_html, "lxml")
                for bad in node.find_all(["script", "style", "nav", "aside", "footer", "header", "form",
                                           "iframe", "ins", "noscript"]):
                    bad.decompose()
                # Wrap bare text into a single <p> and retain existing <p>/<img>
                # tags for readability.
                out["content_html"] = str(node)[:25000]

        # Fallback body_head if trafilatura failed and no selector worked
        if not out.get("body_head"):
            main = (
                soup.find("article")
                or soup.find("main")
                or soup.find("div", class_=re.compile("content|article|post|main", re.I))
            )
            if main:
                for bad in main.find_all(["script", "style", "nav", "aside", "footer", "header", "form"]):
                    bad.decompose()
                body_text = _strip(main.get_text())
                cleaned = _strip_leading_date(body_text)
                cleaned = _strip_title_prefix(cleaned, out.get("title") or t)
                if cleaned:
                    out["body_head"] = cleaned[:800]
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
        # trailing date ("...כל הפרטים מאיה כהן 08.03.2026") — card-meta leaking
        if re.search(r"\d{1,2}[./]\d{1,2}[./]\d{2,4}\s*$", t):
            return True
        # listing-card bullets like " • כל הפרטים" — subtitle appended to title
        if "•" in t:
            return True
        if len(t) < 10 or len(t) > 150:
            return True
        return False

    async def run(a: Dict[str, Any]):
        needs_date = not a.get("published_at")
        needs_title = _title_looks_bad(a.get("title", ""))
        needs_image = not a.get("image")
        # always fetch so we can populate _body_head for off-topic filter
        async with sem:
            try:
                # Fetch with browser up-front when requested — many JS-rendered
                # sites (Maariv / Globes) return a minimal server-rendered
                # shell to plain httpx that lacks the real article body, so
                # the Eilat filter would incorrectly drop the article.
                meta = await _article_meta(
                    client, a["source_url"], use_browser=use_browser
                )
                # Last-resort fallback: if we requested browser but it somehow
                # failed, try the httpx path too.
                if not meta:
                    meta = await _article_meta(
                        client, a["source_url"], use_browser=not use_browser
                    )
                if meta.get("published_at") and needs_date:
                    a["published_at"] = meta["published_at"]
                if meta.get("title") and needs_title:
                    a["title"] = meta["title"][:300]
                if meta.get("image") and needs_image:
                    a["image"] = meta["image"]
                if meta.get("summary") and (not a.get("summary") or len(a.get("summary", "")) < 30):
                    a["summary"] = meta["summary"]
                if meta.get("body_head"):
                    a["_body_head"] = meta["body_head"]
                if meta.get("content_html"):
                    # Always prefer trafilatura's clean article body over whatever
                    # the scraper grabbed initially — drops comments/ads/related.
                    a["content_html"] = meta["content_html"]
            except Exception:
                pass

        # --- Final universal cleanup of summary/body_head/content_html ---
        # Run REGARDLESS of where the summary came from (listing card, og:description,
        # article body) so we consistently strip leading dates and title duplication.
        try:
            title = a.get("title") or ""
            if a.get("summary"):
                s = _strip_leading_date(a["summary"]) or ""
                s = _strip_title_prefix(s, title) or ""
                a["summary"] = s[:1500]
            if a.get("_body_head"):
                bh = _strip_leading_date(a["_body_head"]) or ""
                bh = _strip_title_prefix(bh, title) or ""
                a["_body_head"] = bh[:800]
            # Also clean the first paragraph inside content_html — removes leading
            # "DATE " / "TITLE " noise that sometimes survives inside <p>..</p>.
            ch = a.get("content_html")
            if ch and title:
                # Only attempt replacement on the first <p> block
                m = re.match(r"^(\s*<p[^>]*>)(.*?)(</p>)", ch, flags=re.S)
                if m:
                    head_open, inner, head_close = m.group(1), m.group(2), m.group(3)
                    # strip tags to compare/clean text, but keep markup intact if no change
                    inner_text = re.sub(r"<[^>]+>", "", inner)
                    cleaned_text = _strip_leading_date(inner_text) or ""
                    cleaned_text = _strip_title_prefix(cleaned_text, title) or ""
                    # If cleanup actually stripped content, rebuild the first <p> with
                    # just the cleaned text (acceptable tradeoff — the first paragraph
                    # rarely contains inline formatting).
                    if cleaned_text and cleaned_text != inner_text.strip():
                        a["content_html"] = head_open + cleaned_text + head_close + ch[m.end():]
                    elif not cleaned_text:
                        # first paragraph was pure noise — drop it entirely
                        a["content_html"] = ch[m.end():]
        except Exception:
            pass

    await asyncio.gather(*[run(a) for a in articles])
