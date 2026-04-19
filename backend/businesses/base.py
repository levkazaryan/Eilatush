"""Shared primitives for business/professional scrapers:
HTTP fetch, text helpers, phone normalize, fingerprint for dedup, and the
`_make_business` / `_make_professional` record builders.

A "business" is a location-based establishment (restaurant, hotel, cafe, shop...).
A "professional" is a service provider (plumber, electrician, lawyer, contractor...).

Both share the same base record shape, differentiated by the `type` field.
"""
from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

log = logging.getLogger("businesses")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "he-IL,he;q=0.9,en;q=0.8",
}

TIMEOUT = httpx.Timeout(25.0, connect=10.0)


# ---------------------------------------------------------------------------
# Fetch
# ---------------------------------------------------------------------------
async def _fetch(client: httpx.AsyncClient, url: str) -> Optional[str]:
    try:
        r = await client.get(url, timeout=TIMEOUT, follow_redirects=True)
        r.raise_for_status()
        return r.text
    except Exception as e:
        log.warning("biz fetch failed %s: %s", url, e)
        return None


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------
def _strip(s: Optional[str]) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


def _hash_url(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:20]


_STOP_WORDS_RE = re.compile(
    r"\b(?:ה|ב|ל|של|את|על|עם|ו|מסעדת|מסעדה|פאב|בר|בית|קפה|אילת|the|cafe|restaurant|bar|pub|eilat)\b",
    re.IGNORECASE,
)
_NON_HEBREW_ALPHANUM = re.compile(r"[^\u0590-\u05ff\w\s]+", re.UNICODE)


def _normalize_for_fingerprint(s: str) -> str:
    if not s:
        return ""
    t = s.strip().lower()
    t = re.sub(r"'|\"|׳|״", "", t)
    t = _NON_HEBREW_ALPHANUM.sub(" ", t)
    t = _STOP_WORDS_RE.sub(" ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _fingerprint_business(name: str, phone: Optional[str] = None) -> str:
    """Stable fingerprint used to dedupe across sources.

    We prefer normalized name + last 7 digits of phone when phone is
    available — same name at same phone = same place.
    """
    digits = re.sub(r"[^0-9]", "", phone or "")
    phone_key = digits[-7:] if len(digits) >= 7 else ""
    key = _normalize_for_fingerprint(name) + "|" + phone_key
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Phone / WhatsApp
# ---------------------------------------------------------------------------
def _normalize_phone(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    s = re.sub(r"[^0-9+]", "", raw)
    if not s:
        return None
    if s.startswith("0"):
        s = "+972" + s[1:]
    elif s.startswith("972"):
        s = "+" + s
    elif not s.startswith("+"):
        return None
    digits = re.sub(r"[^0-9]", "", s)
    if len(digits) < 9 or len(digits) > 15:
        return None
    return s


# ---------------------------------------------------------------------------
# Record builders
# ---------------------------------------------------------------------------
def _make_business(
    name: str,
    source_url: str,
    source: str,
    source_name: str,
    description: str = "",
    subtitle: Optional[str] = None,
    category_hint: Optional[str] = None,
    address: Optional[str] = None,
    phone: Optional[str] = None,
    whatsapp: Optional[str] = None,
    email: Optional[str] = None,
    website: Optional[str] = None,
    open_hours: Optional[str] = None,
    image: Optional[str] = None,
    tags: Optional[List[str]] = None,
) -> Dict[str, Any]:
    name_clean = _strip(name)[:200]
    desc_clean = _strip(description)[:2000]
    subtitle_clean = _strip(subtitle or "")[:250] or None
    addr_clean = _strip(address or "")[:200] or None
    phone_n = _normalize_phone(phone)
    return {
        "id": _hash_url(source_url),
        "type": "business",
        "name": name_clean,
        "subtitle": subtitle_clean,
        "description": desc_clean,
        "address": addr_clean,
        "phone": phone_n,
        "whatsapp": _normalize_phone(whatsapp) or phone_n,
        "email": (email or None),
        "website": website,
        "open_hours": _strip(open_hours or "")[:120] or None,
        "image": image,
        "source": source,
        "source_name": source_name,
        "source_url": source_url,
        "category_hint": category_hint,          # raw label from the source
        "tags": tags or [],                      # AI-assigned category slugs
        "fetched_at": datetime.now(timezone.utc),
        "fingerprint": _fingerprint_business(name_clean, phone_n),
    }


def _make_professional(
    name: str,
    source_url: str,
    source: str,
    source_name: str,
    description: str = "",
    subtitle: Optional[str] = None,
    category_hint: Optional[str] = None,
    phone: Optional[str] = None,
    whatsapp: Optional[str] = None,
    email: Optional[str] = None,
    image: Optional[str] = None,      # stored for professionals too (but UI may ignore)
    tags: Optional[List[str]] = None,
) -> Dict[str, Any]:
    name_clean = _strip(name)[:200]
    desc_clean = _strip(description)[:2000]
    phone_n = _normalize_phone(phone)
    return {
        "id": _hash_url(source_url),
        "type": "professional",
        "name": name_clean,
        "subtitle": _strip(subtitle or "")[:250] or None,
        "description": desc_clean,
        "address": None,
        "phone": phone_n,
        "whatsapp": _normalize_phone(whatsapp) or phone_n,
        "email": (email or None),
        "website": None,
        "open_hours": None,
        "image": image,
        "source": source,
        "source_name": source_name,
        "source_url": source_url,
        "category_hint": category_hint,
        "tags": tags or [],
        "fetched_at": datetime.now(timezone.utc),
        "fingerprint": _fingerprint_business(name_clean, phone_n),
    }
