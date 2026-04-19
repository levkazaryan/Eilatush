"""Scraper for https://yomyom.net/article.asp?id=61445 — "מדור בעלי מקצוע ונותני שירותים".

Same physical-flyer format as `yomyom_jobs`: each professional ad is an image
with a `tel:+972...` link underneath. We re-use the jobs OCR pipeline
(Tesseract → Claude Sonnet JSON) but prompt the LLM to extract a PROFESSIONAL
record (service provider) rather than a job.
"""
from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import re
import uuid
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin

import httpx
import pytesseract
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from PIL import Image

from ..base import _fetch, _make_professional, _strip, log

load_dotenv()

_URL = "https://yomyom.net/article.asp?id=61445"
_BASE = "https://yomyom.net"


# ---------------------------------------------------------------------------
# OCR helpers (same logic as jobs yomyom — duplicated here to keep package
# boundaries clean)
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
renovator, lawyer, tutor, cleaning service, etc.).

OCR output is often garbled. Read through it, figure out what the flyer says,
and return single-line JSON with these keys:

  {
    "name":        "<short name of the professional or business — e.g. 'דוד האינסטלטור' or 'שיפוצים מני'>",
    "subtitle":    "<short tagline or trade — e.g. 'אינסטלציה ופתיחת סתימות'>",
    "description": "<2-3 short clear Hebrew sentences about the services offered>",
    "category":    "<ONE English slug from: construction, electrician, plumber, ac, appliance_fix, carpentry, sealing, cleaning_pro, gardening, moving, locksmith, pest, auto_repair, tutor, therapy, health_pro, lawyer, accountant, tech_pro, graphics, photo, events_pro, beauty_home>",
    "email":       "<email if one appears on the flyer, else null>"
  }

RULES:
 - Return ONLY valid JSON (no markdown, no explanation).
 - Use clean Hebrew. Fix obvious OCR mistakes.
 - If you cannot find any coherent name, return name="" (empty string).
 - Keep name SHORT — 2-6 words.
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
        m = re.search(r"\{[^}]*\}", txt, re.DOTALL)
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
        "email": (data.get("email") or None),
    }


async def _extract_one(
    client: httpx.AsyncClient,
    phone: str,
    img_src: Optional[str],
    existing: Dict[str, Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    source_url = f"{_URL}#phone-{re.sub(r'[^0-9+]', '', phone)}"
    # Short-circuit: reuse cached record if already OCR'd with a real name.
    cached = existing.get(source_url)
    if cached and cached.get("name") and not cached["name"].startswith("איש מקצוע #"):
        return _make_professional(
            name=cached.get("name") or "",
            subtitle=cached.get("subtitle"),
            description=cached.get("description") or "",
            source_url=source_url,
            source="yomyom_pros",
            source_name="יום-יום אילת",
            phone=phone,
            email=cached.get("email"),
            image=img_src,
            category_hint=cached.get("category_hint"),
            tags=[cached["category_hint"]] if cached.get("category_hint") else [],
        )

    name = ""
    subtitle = None
    description = ""
    category_hint = None
    email = None

    if img_src:
        try:
            ir = await client.get(img_src, timeout=20)
            if ir.status_code == 200 and len(ir.content) > 500:
                ocr_text = await asyncio.to_thread(_ocr_image, ir.content)
                if ocr_text.strip():
                    llm = await _llm_extract(ocr_text)
                    if llm and llm.get("name"):
                        name = llm["name"]
                        subtitle = llm.get("subtitle")
                        description = llm.get("description") or ""
                        category_hint = llm.get("category")
                        email = llm.get("email")
                if not email:
                    m = re.search(
                        r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
                        ocr_text,
                    )
                    if m:
                        email = m.group(0)
        except Exception as e:
            log.warning("yomyom-pros OCR/LLM error for img %s: %s", img_src, e)

    if not name:
        # If no useful OCR, skip this flyer entirely to avoid placeholder spam.
        return None
    if not description:
        description = "איש מקצוע באילת — הפרטים על העלון. התקשר/י ישירות למפרסם."

    rec = _make_professional(
        name=name,
        subtitle=subtitle,
        description=description,
        source_url=source_url,
        source="yomyom_pros",
        source_name="יום-יום אילת",
        phone=phone,
        email=email,
        image=img_src,
        category_hint=category_hint,
        tags=[category_hint] if category_hint else [],
    )
    return rec


async def _load_existing(client: httpx.AsyncClient) -> Dict[str, Dict[str, Any]]:
    try:
        r = await client.get(
            "http://localhost:8001/api/businesses?source=yomyom_pros&type=professional&limit=500",
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


async def scrape_yomyom_professionals(client: httpx.AsyncClient) -> List[Dict[str, Any]]:
    html = await _fetch(client, _URL)
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")

    # Each ad is a flyer image followed by a tel: link saying "ליצירת קשר..."
    pairs: List[Tuple[str, Optional[str]]] = []
    seen_phones: set = set()
    for a in soup.find_all("a", href=True):
        h = a["href"].lower()
        if not h.startswith("tel:"):
            continue
        phone = a["href"].split(":", 1)[1].strip()
        phone = re.sub(r"^[a-z]+://", "", phone, flags=re.I)
        if not phone or phone in seen_phones:
            continue
        seen_phones.add(phone)
        # Find the previous flyer image (walk DOM backwards)
        img_src = None
        prev = a
        for _ in range(30):
            prev = prev.find_previous()
            if prev is None:
                break
            if getattr(prev, "name", None) == "img":
                src = prev.get("src") or ""
                if src and "UploadImg" in src and ".jpg" in src.lower():
                    img_src = urljoin(_BASE, src)
                    break
        pairs.append((phone, img_src))

    existing = await _load_existing(client)
    # OCR + LLM are expensive — limit concurrency to 3.
    sem = asyncio.Semaphore(3)

    async def worker(p: str, i: Optional[str]) -> Optional[Dict[str, Any]]:
        async with sem:
            return await _extract_one(client, p, i, existing)

    results = await asyncio.gather(*[worker(p, i) for p, i in pairs])
    pros = [r for r in results if r]
    log.info("yomyom_pros (OCR) → %d professionals", len(pros))
    return pros
