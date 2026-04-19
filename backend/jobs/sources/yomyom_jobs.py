"""Scraper for https://www.yomyom.net/article.asp?id=61444 (לוח דרושים יום-יום).

The page is image-based: each job is an uploaded JPG flyer paired with a
`tel:+972...` link for contact. We run Hebrew OCR (Tesseract) on each flyer
and feed the raw text to Claude to recover a clean `title`, `company`, and
`description`. This turns generic "משרה בלוח יום-יום אילת #N" entries into
real titles like "עובד/ת סופר" / "חשמלאי מוסמך - מלון קומפורט אילת".

Fallback: if LLM is down, the scraper picks the longest-looking Hebrew line
from the OCR output as a best-effort title.
"""
from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin

import httpx
import pytesseract
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from PIL import Image

from ..base import HEADERS, _fetch, _make_job, _strip, log

load_dotenv()

_URL = "https://www.yomyom.net/article.asp?id=61444"
_BASE = "https://www.yomyom.net"

# ---------------------------------------------------------------------------
# OCR helpers
# ---------------------------------------------------------------------------
def _ocr_image(raw: bytes) -> str:
    try:
        img = Image.open(io.BytesIO(raw))
        # Upscale small images to improve OCR accuracy
        if min(img.size) < 600:
            ratio = 1000 / max(img.size)
            img = img.resize((int(img.size[0] * ratio), int(img.size[1] * ratio)))
        text = pytesseract.image_to_string(img, lang="heb+eng", config="--psm 6")
        return text
    except Exception as e:
        log.warning("yomyom OCR failed: %s", e)
        return ""


# Characters commonly produced as OCR noise
_OCR_NOISE_RE = re.compile(r"[^\u0590-\u05ff\w\s\-/.,'\"?!()#&+–:]", re.UNICODE)
_WHITES_RE = re.compile(r"\s+")


def _clean_ocr_line(line: str) -> str:
    s = _OCR_NOISE_RE.sub(" ", line)
    return _WHITES_RE.sub(" ", s).strip()


def _hebrew_ratio(s: str) -> float:
    if not s:
        return 0.0
    hebrew = len(re.findall(r"[\u0590-\u05ff]", s))
    total = len(re.findall(r"\w", s, re.UNICODE))
    return hebrew / total if total else 0.0


def _best_title_fallback(ocr_text: str) -> Tuple[str, str]:
    """Picks a best title + description WITHOUT LLM help.
    Title = the longest line that is mostly Hebrew (ratio > 0.6) and > 10 chars.
    Description = the first 3 other meaningful lines joined.
    """
    lines = [_clean_ocr_line(ln) for ln in ocr_text.split("\n")]
    # Keep only reasonably-Hebrew lines, length 6-90
    scored: List[Tuple[int, str]] = []
    for ln in lines:
        if 6 <= len(ln) <= 90 and _hebrew_ratio(ln) >= 0.55:
            # score = length + bonus if contains job-words
            score = len(ln)
            if re.search(r"\bדרוש[/א-ת]{0,3}\b|\bעובד[/א-ת]{0,3}\b|\bמנהל[/א-ת]{0,3}\b|\bמלון\b", ln):
                score += 30
            scored.append((score, ln))
    scored.sort(key=lambda x: -x[0])
    title = scored[0][1] if scored else ""
    other_lines = [ln for s, ln in scored[1:5]]
    desc = " · ".join(other_lines)
    return title, desc


# ---------------------------------------------------------------------------
# LLM cleanup — ask Claude to turn OCR text into structured title/company/desc
# ---------------------------------------------------------------------------
_LLM_SYSTEM = """You are a Hebrew OCR cleanup assistant for an Eilat jobs app.

You receive raw OCR output from a physical job-flyer image. OCR tends to
produce garbled text, repeated characters, and broken lines.

Your job: read through the garbled text, figure out what the flyer says, and
return a single-line JSON with these keys:

  {
    "title":       "<role / position, e.g. 'עובד/ת סופר' or 'חשמלאי מוסמך'>",
    "company":     "<hiring business if mentioned, else null>",
    "description": "<2-3 short clear sentences describing what the job is>",
    "email":       "<contact email address if one appears on the flyer, else null>"
  }

RULES:
 - Return ONLY valid JSON (no markdown, no explanation).
 - Use clean Hebrew. Fix obvious OCR mistakes (missing nikud, wrong letters).
 - Email addresses may appear as "mail@domain.co.il" or with spaces/OCR noise;
   if you can confidently reconstruct one, return it in the email field.
   Otherwise set email=null.
 - If the flyer clearly advertises a BUSINESS (e.g. construction, movers,
   shipping services) rather than a JOB, still try to extract a plausible job
   title from it (e.g. "עובדי בניין" for a construction company ad).
 - If you cannot find any coherent title, return title="" (empty string).
 - Keep title SHORT — 3-8 words.
 - company MAY BE NULL — only include if a real business name is visible.
 - Always return valid JSON, even if fields are empty.
"""


async def _llm_extract(ocr_text: str) -> Optional[Dict[str, Any]]:
    api_key = os.environ.get("EMERGENT_LLM_KEY")
    if not api_key or not ocr_text.strip():
        return None
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage

        chat = LlmChat(
            api_key=api_key,
            session_id=f"yomyom-ocr-{uuid.uuid4().hex[:10]}",
            system_message=_LLM_SYSTEM,
        ).with_model("anthropic", "claude-sonnet-4-5-20250929")
        raw = await chat.send_message(UserMessage(text=f"OCR RAW:\n{ocr_text[:1800]}"))
    except Exception as e:
        log.warning("yomyom LLM extract error: %s", e)
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
        "title": (data.get("title") or "").strip()[:160],
        "company": ((data.get("company") or "") or "").strip()[:120] or None,
        "description": (data.get("description") or "").strip()[:600],
        "email": (data.get("email") or None),
    }


# ---------------------------------------------------------------------------
# Main scraper
# ---------------------------------------------------------------------------
async def _extract_one(
    client: httpx.AsyncClient,
    idx: int,
    phone: str,
    img_src: Optional[str],
    existing_titles: Dict[str, Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    # Build job id early — stable based on phone
    source_url = f"{_URL}#phone-{re.sub(r'[^0-9+]', '', phone)}"
    # Short-circuit: skip OCR if we already have this job with a real title cached
    existing = existing_titles.get(source_url)
    # Skip OCR + LLM if we already have a good cached record (clean title and,
    # if the flyer has an email, we've already extracted it). We still refresh
    # jobs that were saved BEFORE email extraction was added so their emails
    # can be picked up on the next scrape cycle.
    has_clean_title = existing and not existing.get("title", "").startswith("משרה בלוח יום-יום")
    # A sentinel in the DB record: if `email_checked` is True, we already asked
    # the LLM about email for this flyer.
    email_already_checked = bool(existing and existing.get("email_checked"))
    if has_clean_title and email_already_checked:
        cached = _make_job(
            title=existing["title"],
            company=existing.get("company"),
            description=existing.get("description") or "משרה מלוח יום-יום באילת.",
            source_url=source_url,
            source="yomyom",
            source_name="לוח יום-יום",
            phone=phone,
            email=existing.get("email"),
            image=img_src,
            posted_at=datetime.now(timezone.utc),
        )
        cached["email_checked"] = True
        return cached

    title = ""
    company = None
    description = ""
    email = None

    if img_src:
        try:
            ir = await client.get(img_src, timeout=15)
            if ir.status_code == 200 and len(ir.content) > 500:
                ocr_text = await asyncio.to_thread(_ocr_image, ir.content)
                if ocr_text.strip():
                    llm = await _llm_extract(ocr_text)
                    if llm and llm.get("title"):
                        title = llm["title"]
                        company = llm.get("company")
                        description = llm.get("description") or ""
                        email = llm.get("email")
                    else:
                        # Fallback: pick best Hebrew line
                        t, d = _best_title_fallback(ocr_text)
                        title = t
                        description = d
                    # Regex fallback for email if LLM missed it
                    if not email:
                        m = re.search(
                            r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
                            ocr_text,
                        )
                        if m:
                            email = m.group(0)
        except Exception as e:
            log.warning("yomyom OCR/LLM pipeline error for img %s: %s", img_src, e)

    if not title:
        title = f"משרה בלוח יום-יום אילת #{idx + 1}"
    if not description:
        description = (
            "משרה לחוז אילת שפורסמה בלוח הדרושים של יום-יום אילת. "
            "לפרטי המשרה ופרטי הקשר התקשרו ישירות למפרסם."
        )

    result = _make_job(
        title=title,
        company=company,
        description=description,
        source_url=source_url,
        source="yomyom",
        source_name="לוח יום-יום",
        phone=phone,
        email=email,
        image=img_src,
        posted_at=datetime.now(timezone.utc),
    )
    result["email_checked"] = True
    return result


async def _load_existing_by_source_url(client: httpx.AsyncClient) -> Dict[str, Dict[str, Any]]:
    """Read previously-scraped yomyom jobs so we can skip OCR on unchanged rows.

    We hit our own backend for this (running on the same pod). If that fails,
    we fall back to an empty cache (OCR every row).
    """
    try:
        r = await client.get("http://localhost:8001/api/jobs?source=yomyom", timeout=5)
        if r.status_code != 200:
            return {}
        out: Dict[str, Dict[str, Any]] = {}
        for j in r.json():
            key = j.get("source_url") or ""
            if key:
                out[key] = j
        return out
    except Exception:
        return {}


async def scrape_yomyom_jobs(client: httpx.AsyncClient) -> List[Dict[str, Any]]:
    html = await _fetch(client, _URL)
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    tel_links = [a for a in soup.find_all("a", href=True) if a["href"].lower().startswith("tel:")]
    # Build (phone, img_src) pairs by walking the DOM
    pairs: List[Tuple[str, Optional[str]]] = []
    seen_phones: set = set()
    for a in tel_links:
        phone = a["href"].split(":", 1)[1].strip()
        phone = re.sub(r"^[a-z]+://", "", phone, flags=re.I)
        if not phone or phone in seen_phones:
            continue
        seen_phones.add(phone)
        img_src = None
        prev = a
        for _ in range(25):
            prev = prev.find_previous()
            if prev is None:
                break
            if getattr(prev, "name", None) == "img":
                src = prev.get("src") or ""
                if src and "UploadImg" in src and ".jpg" in src.lower():
                    img_src = urljoin(_BASE, src)
                    break
        pairs.append((phone, img_src))

    # Load cache of existing yomyom jobs to avoid re-OCRing unchanged ones
    existing = await _load_existing_by_source_url(client)

    # OCR in parallel (but conservatively — these are local CPU + an LLM call)
    sem = asyncio.Semaphore(3)

    async def worker(idx: int, phone: str, img: Optional[str]) -> Optional[Dict[str, Any]]:
        async with sem:
            return await _extract_one(client, idx, phone, img, existing)

    results = await asyncio.gather(*[worker(i, ph, im) for i, (ph, im) in enumerate(pairs)])
    jobs = [r for r in results if r]
    log.info("yomyom_jobs (OCR) → %d jobs", len(jobs))
    return jobs
