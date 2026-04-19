"""Pure functions for cleaning / extracting metadata from article HTML.
No side effects — fetching lives in enrichment.py.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Optional

from dateutil import parser as dtparse

from .base import _strip, _dt_parse

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


_LEADING_DATE_RE = re.compile(
    r"^\s*\d{1,2}[./\-]\d{1,2}[./\-]\d{2,4}"       # dd/mm/yyyy or dd.mm.yy
    r"(?:\s*[,\-–—|]\s*|\s+[|•]\s+|\s+)"           # separator (comma, dash, pipe, bullet, or whitespace)
)


def _strip_leading_date(t: Optional[str]) -> Optional[str]:
    """Strip leading date prefixes like "17.09.2025 …" / "05/04/26 | …" that
    Davar (and occasionally others) prepend to article body / summary — the
    card already shows the date separately, so repeating it is noisy."""
    if not t:
        return t
    cleaned = _LEADING_DATE_RE.sub("", t, count=1).lstrip(" ,-–—|•:")
    return cleaned if cleaned else t


# Patterns Maariv / others use right after the title, before the actual body:
#   "<title>DD/MM/YYYY | HH:MM"
#   "<title> | DD/MM/YYYY | HH:MM"
#   "<title>HH:MM"  (e.g. just "09:41" stuck to the end of the title)
_META_TAIL_RE = re.compile(
    r"^\s*(?:[|•\-–—,:\s])?\s*"
    r"(?:\d{1,2}[./\-]\d{1,2}[./\-]\d{2,4}"          # optional date
    r"(?:\s*[|,•\-–—]\s*|\s+))?"
    r"\d{1,2}:\d{2}"                                  # HH:MM required here
    r"(?:\s*[|,•\-–—]\s*|\s+|$)"
)


def _norm(s: str) -> str:
    """Normalise text for prefix comparison: collapse whitespace."""
    return re.sub(r"\s+", " ", s).strip()


def _strip_title_prefix(text: Optional[str], title: Optional[str]) -> Optional[str]:
    """Remove a repeated article title (and any date/time suffix glued to it)
    from the very beginning of ``text``.

    Many sources (Maariv especially) set their ``og:description`` to be
    ``"<title>DD/MM/YYYY | HH:MM"`` with no actual summary text. We display
    the title and date separately in the UI, so this duplication is noise —
    strip the title prefix plus any residual "HH:MM" / "DD/MM/YYYY | HH:MM"
    tail that follows it.
    """
    if not text:
        return text

    def _clean_tail(remainder: str) -> str:
        """Strip leftover metadata like "מהיום | DD/MM/YYYY | HH:MM" that
        sometimes dangles after the title prefix."""
        remainder = remainder.lstrip(" ,-–—|•:\t\n")
        # Direct date/time tail
        remainder = _META_TAIL_RE.sub("", remainder, count=1).lstrip(" ,-–—|•:\t\n")
        # If remainder is short metadata only (e.g. "מהיום | 27/03/2026 | 11:53"),
        # strip the whole thing. We detect this by checking it's <= 60 chars AND
        # contains a date + time pattern.
        if (
            remainder
            and len(remainder) <= 60
            and re.search(r"\d{1,2}[./\-]\d{1,2}[./\-]\d{2,4}", remainder)
            and re.search(r"\d{1,2}:\d{2}", remainder)
        ):
            return ""
        return remainder

    # Always remove a plain leading "HH:MM" timestamp even when no title match
    # (covers cases where the title was already cleaned off upstream).
    if not title:
        cleaned = _META_TAIL_RE.sub("", text, count=1).lstrip(" ,-–—|•:")
        return cleaned or text

    norm_text = _norm(text)
    norm_title = _norm(title)
    if not norm_title or len(norm_title) < 8:
        return text
    if norm_text.startswith(norm_title):
        remainder = _clean_tail(norm_text[len(norm_title):])
        return remainder if remainder else ""
    # Some sources repeat the title with a slight trailing separator variant
    # (e.g. title ends with ":" but description drops the ":"). Try a looser
    # letters-only match as a fallback.
    letters_only = lambda s: re.sub(r"[^\w\u0590-\u05FF]+", "", s)
    lo_text = letters_only(norm_text)
    lo_title = letters_only(norm_title)
    if lo_title and lo_text.startswith(lo_title):
        # Map letters-only offset back to original-string offset
        idx = 0
        consumed_letters = 0
        while idx < len(norm_text) and consumed_letters < len(lo_title):
            ch = norm_text[idx]
            if letters_only(ch):
                consumed_letters += 1
            idx += 1
        remainder = _clean_tail(norm_text[idx:])
        return remainder if remainder else ""
    return text
