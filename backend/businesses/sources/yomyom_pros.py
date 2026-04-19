"""Scraper for yomyom.net professionals listings.

Multiple source articles (all physical-flyer format):
  • 61445 — "מדור בעלי מקצוע ונותני שירותים"  (general services)
  • 61463 — "לוח הנדל"ן והתיווך"                 (real-estate brokers)

Each ad is a flyer image with contact details printed ON the flyer. A
subset of flyers also have a separate `<a href="tel:…">ליצירת קשר…</a>` link
in the DOM, but many don't — so we iterate *flyers* as the source of truth
and recover the phone from OCR or from the nearest tel: link.

Pipeline:
  flyer img → Tesseract heb+eng OCR → Claude Sonnet 4.5 JSON extraction
  (name, subtitle, description, category slug, phone, email) → professional
  record.
"""
from __future__ import annotations

import asyncio
import io
import json
import os
import re
import uuid
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import httpx
import pytesseract
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from PIL import Image

from ..base import _fetch, _make_professional, _normalize_phone, log

load_dotenv()

_BASE = "https://yomyom.net"

# (article_id, short human label)
_ARTICLES: List[Dict[str, str]] = [
    {"id": "61445", "label": "בעלי מקצוע"},
    {"id": "61463", "label": "נדל״ן ותיווך"},
]


# ---------------------------------------------------------------------------
# OCR + LLM helpers
# ---------------------------------------------------------------------------
def _ocr_image(raw: bytes) -> str:
    try:
        img = Image.open(io.BytesIO(raw))
        if min(img.size) < 600:
            ratio = 1000 / max(img.size)
            img = img.resize((int(img.size[0] * ratio), int(img.size[1] * ratio)))
        return pytesseract.image_to_string(img, lang="heb+eng", config="--psm 6")
    except Exception as e:
        log.warning("yomyom-pros OCR failed: %s", e)
        return ""


_LLM_SYSTEM = """You are a Hebrew OCR cleanup assistant for an Eilat local-services app.

You receive raw OCR output from a physical flyer that advertises a PROFESSIONAL
/ SERVICE PROVIDER in Eilat (plumber, electrician, contractor, carpenter,
renovator, lawyer, real-estate broker, tutor, cleaning service, etc.).

OCR output is often garbled. Read through it, figure out what the flyer says,
and return single-line JSON with these keys:

  {
    "name":        "<short name of the professional or business — e.g. 'דוד האינסטלטור' or 'שיפוצים מני'>",
    "subtitle":    "<short tagline or trade — e.g. 'אינסטלציה ופתיחת סתימות'>",
    "description": "<2-3 short clear Hebrew sentences about the services offered>",
    "category":    "<ONE English slug from: construction, electrician, plumber, ac, appliance_fix, carpentry, sealing, cleaning_pro, gardening, moving, locksmith, pest, auto_repair, tutor, therapy, health_pro, lawyer, accountant, tech_pro, graphics, photo, events_pro, beauty_home, realestate>",
    "phone":       "<the main contact phone number as it appears, digits only or in 05x-xxx-xxxx format. Must be an Israeli number. null if none visible.>",
    "email":       "<email if one appears on the flyer, else null>"
  }

RULES:
 - Return ONLY valid JSON (no markdown, no explanation).
 - Use clean Hebrew. Fix obvious OCR mistakes.
 - If you cannot find any coherent name, return name="" (empty string).
 - Keep name SHORT — 2-6 words.
 - Phone: choose the main one (mobile 05x preferred over landline). Strip any WhatsApp suffix.
 - Prefer a real category slug from the list; if nothing fits, set category=null.
"""


async def _llm_extract(ocr_text: str) -> Optional[Dict[str, Any]]:
    api_key = os.environ.get("EMERGENT_LLM_KEY")
    if not api_key or not ocr_text.strip():
        return None
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage

        chat = LlmChat(
            api_key=api_key,
            session_id=f"yomyom-pros-{uuid.uuid4().hex[:10]}",
            system_message=_LLM_SYSTEM,
        ).with_model("anthropic", "claude-sonnet-4-5-20250929")
        raw = await chat.send_message(UserMessage(text=f"OCR RAW:\n{ocr_text[:1800]}"))
    except Exception as e:
        log.warning("yomyom-pros LLM error: %s", e)
        return None
    if not raw:
        return None
    txt = raw.strip()
    txt = re.sub(r"^```(?:json)?\s*", "", txt)
    txt = re.sub(r"\s*```$", "", txt)
    try:
        data = json.loads(txt)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", txt, re.DOTALL)
        if not m:
            return None
        try:
            data = json.loads(m.group(0))
        except json.JSONDecodeError:
            return None
    if not isinstance(data, dict):
        return None
    return {
        "name": (data.get("name") or "").strip()[:120],
        "subtitle": (data.get("subtitle") or "").strip()[:150] or None,
        "description": (data.get("description") or "").strip()[:600],
        "category": (data.get("category") or "").strip().lower() or None,
        "phone": (data.get("phone") or "").strip() or None,
        "email": (data.get("email") or None),
    }


# ---------------------------------------------------------------------------
# DOM helpers
# ---------------------------------------------------------------------------
_PHONE_RX = re.compile(r"(?:\+972[\-\s]?|0)(?:5\d|[2-47-9])[\-\s]?\d{3}[\-\s]?\d{4}")


def _extract_phone_from_ocr(text: str) -> Optional[str]:
    """Pull the first plausible Israeli phone number out of an OCR dump."""
    if not text:
        return None
    for m in _PHONE_RX.finditer(text):
        raw = m.group(0)
        norm = _normalize_phone(raw)
        if norm:
            return norm
    return None


def _find_nearby_tel(img_tag) -> Optional[str]:
    """Look at the image's DOM neighborhood (next 20 siblings, then parent)
    for a tel: link. Used as an additional hint when OCR misses the number."""
    nxt = img_tag
    for _ in range(30):
        nxt = nxt.find_next()
        if nxt is None:
            break
        if getattr(nxt, "name", None) == "a" and (nxt.get("href") or "").lower().startswith("tel:"):
            phone = nxt["href"].split(":", 1)[1].strip()
            phone = re.sub(r"^[a-z]+://", "", phone, flags=re.I)
            return phone
        if getattr(nxt, "name", None) == "img" and "UploadImg" in (nxt.get("src") or ""):
            # next flyer reached without seeing a tel: link — give up
            break
    return None


async def _load_existing(client: httpx.AsyncClient) -> Dict[str, Dict[str, Any]]:
    try:
        r = await client.get(
            "http://localhost:8001/api/businesses"
            "?source=yomyom_pros&type=professional&limit=500",
            timeout=5,
        )
        if r.status_code != 200:
            return {}
        out: Dict[str, Dict[str, Any]] = {}
        for d in r.json():
            key = d.get("source_url")
            if key:
                out[key] = d
        return out
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Per-flyer extraction
# ---------------------------------------------------------------------------
async def _extract_flyer(
    client: httpx.AsyncClient,
    article_id: str,
    img_src: str,
    flyer_index: int,
    nearby_phone_hint: Optional[str],
    existing: Dict[str, Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    # Stable key per flyer image so upserts don't create duplicates.
    slug_key = re.sub(r"[^a-zA-Z0-9]+", "-", img_src.split("/")[-1])[:60]
    source_url = f"{_BASE}/article.asp?id={article_id}#flyer-{flyer_index}-{slug_key}"

    # Short-circuit: previously OCR'd record with a real name → reuse.
    cached = existing.get(source_url)
    if cached and cached.get("name") and not cached["name"].startswith("איש מקצוע #"):
        return _make_professional(
            name=cached.get("name") or "",
            subtitle=cached.get("subtitle"),
            description=cached.get("description") or "",
            source_url=source_url,
            source="yomyom_pros",
            source_name="יום-יום אילת",
            phone=cached.get("phone") or nearby_phone_hint,
            email=cached.get("email"),
            image=img_src,
            category_hint=cached.get("category_hint") or (cached.get("tags") or [None])[0],
            tags=[t for t in (cached.get("tags") or []) if t],
        )

    # Fetch + OCR.
    try:
        ir = await client.get(img_src, timeout=20)
    except Exception as e:
        log.warning("yomyom-pros img fetch error %s: %s", img_src, e)
        return None
    if ir.status_code != 200 or len(ir.content) < 500:
        return None
    ocr_text = await asyncio.to_thread(_ocr_image, ir.content)
    if not ocr_text.strip():
        return None

    llm = await _llm_extract(ocr_text)

    name = (llm or {}).get("name") or ""
    if not name:
        # useless flyer (sidebar ad, decoration, etc.) — skip
        return None

    subtitle = (llm or {}).get("subtitle")
    description = (llm or {}).get("description") or ""
    category = (llm or {}).get("category")
    email = (llm or {}).get("email")

    # Phone priority: LLM > nearby DOM tel: > OCR regex
    phone = _normalize_phone((llm or {}).get("phone")) \
        or _normalize_phone(nearby_phone_hint) \
        or _extract_phone_from_ocr(ocr_text)

    if not email:
        m = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", ocr_text)
        if m:
            email = m.group(0)

    if not description:
        description = "איש מקצוע באילת — הפרטים על העלון. התקשר/י ישירות למפרסם."

    return _make_professional(
        name=name,
        subtitle=subtitle,
        description=description,
        source_url=source_url,
        source="yomyom_pros",
        source_name="יום-יום אילת",
        phone=phone,
        email=email,
        image=img_src,
        category_hint=category,
        tags=[category] if category else [],
    )


# ---------------------------------------------------------------------------
# Main entry
# ---------------------------------------------------------------------------
async def scrape_yomyom_professionals(client: httpx.AsyncClient) -> List[Dict[str, Any]]:
    existing = await _load_existing(client)
    sem = asyncio.Semaphore(3)  # OCR + LLM is heavy

    async def run_article(art: Dict[str, str]) -> List[Dict[str, Any]]:
        url = f"{_BASE}/article.asp?id={art['id']}"
        html = await _fetch(client, url)
        if not html:
            return []
        soup = BeautifulSoup(html, "lxml")
        # Only keep flyer images that are inside the article body — filter out
        # site-header / sidebar thumbnails by requiring UploadImg + .jpg.
        flyers = []
        for im in soup.find_all("img", src=True):
            src = im.get("src") or ""
            if "UploadImg" in src and ".jpg" in src.lower():
                flyers.append(im)
        log.info("yomyom_pros article %s (%s): %d flyers", art["id"], art["label"], len(flyers))

        async def worker(idx: int, img_tag) -> Optional[Dict[str, Any]]:
            async with sem:
                nearby = _find_nearby_tel(img_tag)
                return await _extract_flyer(
                    client,
                    art["id"],
                    urljoin(_BASE, img_tag["src"]),
                    idx,
                    nearby,
                    existing,
                )

        results = await asyncio.gather(
            *[worker(i, f) for i, f in enumerate(flyers)]
        )
        return [r for r in results if r]

    all_pros: List[Dict[str, Any]] = []
    for art in _ARTICLES:
        try:
            pros = await run_article(art)
            all_pros.extend(pros)
        except Exception as e:
            log.exception("yomyom_pros article %s failed: %s", art["id"], e)

    log.info("yomyom_pros total → %d professionals", len(all_pros))
    return all_pros
