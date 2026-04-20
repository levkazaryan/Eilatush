"""Shared types + helpers for event scrapers.

Each scraper is an ``async def scrape_<name>(client) -> list[dict]`` that
returns records conforming to :class:`EventDict`. The runner in
``registry.py`` composes them.
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, TypedDict

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "he-IL,he;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://www.google.com/",
}
TIMEOUT = 25


class EventDict(TypedDict, total=False):
    id: str
    source: str
    title: str
    description: Optional[str]
    category: Optional[str]
    venue: Optional[str]
    image: Optional[str]
    link: Optional[str]
    starts_at: datetime  # UTC aware
    ends_at: Optional[datetime]
    price: Optional[str]
    price_min: Optional[float]
    phone: Optional[str]
    whatsapp: Optional[str]
    tags: List[str]
    fetched_at: datetime


def make_id(source: str, key: str) -> str:
    h = hashlib.sha1(f"{source}::{key}".encode("utf-8")).hexdigest()
    return f"ev_{h[:20]}"


def clean_text(s: Optional[str]) -> str:
    if not s:
        return ""
    return re.sub(r"\s+", " ", s).strip()


def normalize_phone(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    digits = re.sub(r"[^0-9+]", "", raw)
    if not digits:
        return None
    if digits.startswith("00"):
        digits = "+" + digits[2:]
    if digits.startswith("0"):
        digits = "+972" + digits[1:]
    return digits if digits.startswith("+") else None


def to_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def pack(
    *,
    source: str,
    ext_id: str,
    title: str,
    starts_at: datetime,
    description: Optional[str] = None,
    category: Optional[str] = None,
    venue: Optional[str] = None,
    image: Optional[str] = None,
    link: Optional[str] = None,
    ends_at: Optional[datetime] = None,
    price: Optional[str] = None,
    price_min: Optional[float] = None,
    phone: Optional[str] = None,
    whatsapp: Optional[str] = None,
    tags: Optional[List[str]] = None,
) -> EventDict:
    return {
        "id": make_id(source, ext_id),
        "source": source,
        "title": clean_text(title),
        "description": clean_text(description or "") or None,
        "category": category,
        "venue": clean_text(venue or "") or None,
        "image": image or None,
        "link": link or None,
        "starts_at": to_utc(starts_at),
        "ends_at": to_utc(ends_at) if ends_at else None,
        "price": price or None,
        "price_min": price_min,
        "phone": normalize_phone(phone),
        "whatsapp": normalize_phone(whatsapp),
        "tags": tags or [],
        "fetched_at": datetime.now(timezone.utc),
    }
