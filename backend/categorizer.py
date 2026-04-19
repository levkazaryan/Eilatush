"""AI-based article categorizer.

Classifies Eilat news articles into a fixed set of Hebrew subject categories
using Claude Sonnet 4.5 via the Emergent universal LLM key. Supports multiple
tags per article and returns a list of slugs.

Usage:
    from categorizer import CATEGORIES, tag_article, tag_articles_batch
    tags = await tag_article(title, summary, content_text)
    # tags -> ["crime", "security"]
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import uuid
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger("categorizer")

# Fixed category taxonomy for Eilatush news — displayed left-to-right in the
# app's chip row. `slug` is the stable ID stored in Mongo; `label` + `emoji`
# are what the UI renders.
CATEGORIES: List[Dict[str, str]] = [
    {"slug": "crime",        "label": "פלילים ומשטרה",  "emoji": "🚔"},
    {"slug": "security",     "label": "ביטחון ומלחמה",   "emoji": "🛡️"},
    {"slug": "health",       "label": "בריאות ורפואה",   "emoji": "🏥"},
    {"slug": "tourism",      "label": "תיירות ונופש",    "emoji": "🏖️"},
    {"slug": "economy",      "label": "כלכלה ועסקים",    "emoji": "💼"},
    {"slug": "sports",       "label": "ספורט",           "emoji": "⚽"},
    {"slug": "community",    "label": "עירייה וקהילה",   "emoji": "🏛️"},
    {"slug": "nature",       "label": "סביבה וטבע",      "emoji": "🐟"},
    {"slug": "leisure",      "label": "בילוי ופנאי",     "emoji": "🎉"},
]

CATEGORY_SLUGS = {c["slug"] for c in CATEGORIES}

_SYSTEM_PROMPT = """You are a Hebrew news-tagging assistant for a local Eilat news app.
Your job is to categorise each article into one or more of these 9 fixed categories:

  crime      — Crime, police, arrests, drugs, violence, theft, fraud, court cases
  security   — War, military, IDF, rockets/missiles/UAV, air-raid sirens, security briefings
  health     — Hospitals (especially Yoseftal), doctors, medicine, patient deaths, healthcare system
  tourism    — Hotels, vacation packages, flights to Eilat, beach activities, Pesach/חופשה
  economy    — Real estate prices, businesses opening/closing, port of Eilat, municipal budget,
               transport infrastructure, airline route economics
  sports     — Local sports teams (Hapoel Eilat, Maccabi Bnei Eilat), competitions, tournaments
  community  — Municipality announcements, local events, community initiatives, memorial days,
               donations, citizen recognition, civic life
  nature     — Environment, marine life (sharks, corals), pollution, desalination/water, wildlife
  leisure    — Entertainment, dining, free activities, spa/massage, diving, attractions, culture

RULES:
 - Return ONLY a valid JSON array of category slugs, nothing else (no markdown, no prose).
 - An article CAN have multiple tags (up to 3). Return the most relevant ones.
 - Use ONLY the slugs from the list above.
 - If nothing fits, return [].
 - Do NOT invent new categories.

EXAMPLES:
 Input:  "הקשיש שרצח את אשתו נמצא ללא רוח חיים"
 Output: ["crime"]

 Input:  "אל על חוזרת להפעיל קו סדיר בין ת"א לאילת"
 Output: ["economy","tourism"]

 Input:  "זמן ההתגוננות באילת הוארך מ-30 שניות לדקה וחצי"
 Output: ["security"]

 Input:  "כריש טיגריסי תועד סמוך לחופי ישראל"
 Output: ["nature"]

 Input:  "הפועל אילת עלתה לליגת העל"
 Output: ["sports"]
"""


def _parse_tags(raw: str) -> List[str]:
    """Extract a clean list of valid category slugs from the LLM's raw text."""
    if not raw:
        return []
    # Attempt direct JSON parse
    txt = raw.strip()
    # Strip ```json ... ``` fences if present
    txt = re.sub(r"^```(?:json)?\s*", "", txt)
    txt = re.sub(r"\s*```$", "", txt)
    try:
        arr = json.loads(txt)
    except json.JSONDecodeError:
        # Fallback: find first [...] block
        m = re.search(r"\[[^\]]*\]", txt)
        if not m:
            return []
        try:
            arr = json.loads(m.group(0))
        except json.JSONDecodeError:
            return []
    if not isinstance(arr, list):
        return []
    out: List[str] = []
    for item in arr:
        if not isinstance(item, str):
            continue
        slug = item.strip().lower()
        if slug in CATEGORY_SLUGS and slug not in out:
            out.append(slug)
        if len(out) >= 3:
            break
    return out


async def tag_article(
    title: str, summary: str = "", content_text: str = ""
) -> List[str]:
    """Classify a single article. Returns a list of category slugs (may be empty)."""
    api_key = os.environ.get("EMERGENT_LLM_KEY")
    if not api_key:
        log.warning("EMERGENT_LLM_KEY missing — skipping tagging")
        return []

    # Lazy import so the module still loads if emergentintegrations is absent
    from emergentintegrations.llm.chat import LlmChat, UserMessage

    # Compose a compact prompt: title + ~300 chars of summary/body is enough
    body_preview = (summary or content_text or "")[:400]
    prompt = f"TITLE: {title}\nSUMMARY: {body_preview}"

    try:
        chat = LlmChat(
            api_key=api_key,
            session_id=f"tag-{uuid.uuid4().hex[:10]}",
            system_message=_SYSTEM_PROMPT,
        ).with_model("anthropic", "claude-sonnet-4-5-20250929")
        response = await chat.send_message(UserMessage(text=prompt))
    except Exception as e:
        log.warning("LLM tag call failed for %r: %s", title[:40], e)
        return []

    return _parse_tags(response or "")


async def tag_articles_batch(
    articles: List[Dict[str, Any]], concurrency: int = 4
) -> List[List[str]]:
    """Tag a list of articles with bounded concurrency. Returns aligned list of
    tag-lists (same length + order as the input)."""
    sem = asyncio.Semaphore(concurrency)
    results: List[List[str]] = [[] for _ in articles]

    async def worker(i: int, a: Dict[str, Any]) -> None:
        async with sem:
            title = a.get("title") or ""
            summary = a.get("summary") or ""
            content = ""
            ch = a.get("content_html") or ""
            if ch:
                content = re.sub(r"<[^>]+>", " ", ch)
                content = re.sub(r"\s+", " ", content).strip()
            try:
                results[i] = await tag_article(title, summary, content)
            except Exception as e:
                log.warning("tag failure #%d: %s", i, e)
                results[i] = []

    await asyncio.gather(*[worker(i, a) for i, a in enumerate(articles)])
    return results
