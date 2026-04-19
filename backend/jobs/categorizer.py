"""AI-based jobs categorizer.

Classifies Eilat job postings into a fixed Hebrew subject taxonomy using
Claude Sonnet 4.5 (Emergent universal LLM key). Returns 1-3 category slugs.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import uuid
from typing import Any, Dict, List

from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger("jobs_categorizer")

# Fixed job-category taxonomy displayed in the Jobs screen dropdown.
JOB_CATEGORIES: List[Dict[str, str]] = [
    {"slug": "hotels",       "label": "מלונאות",              "emoji": "🏨"},
    {"slug": "restaurants",  "label": "מסעדנות",             "emoji": "🍽️"},
    {"slug": "sales",        "label": "מכירות",               "emoji": "💰"},
    {"slug": "retail",       "label": "קמעונאות",             "emoji": "🛍️"},
    {"slug": "tourism",      "label": "תיירות ופנאי",          "emoji": "🏖️"},
    {"slug": "call_center",  "label": "מוקד ושירות לקוחות",    "emoji": "🎧"},
    {"slug": "security",     "label": "אבטחה",                "emoji": "🛡️"},
    {"slug": "cleaning",     "label": "ניקיון ואחזקה",        "emoji": "🧹"},
    {"slug": "logistics",    "label": "הובלות ולוגיסטיקה",   "emoji": "🚚"},
    {"slug": "office",       "label": "משרד ואדמיניסטרציה", "emoji": "💼"},
    {"slug": "health",       "label": "רפואה ובריאות",         "emoji": "🏥"},
    {"slug": "education",    "label": "חינוך והדרכה",          "emoji": "📚"},
    {"slug": "construction", "label": "בנייה ותעשיה",          "emoji": "🚧"},
    {"slug": "tech",         "label": "מחשבים והייטק",         "emoji": "💻"},
]

JOB_CATEGORY_SLUGS = {c["slug"] for c in JOB_CATEGORIES}

_SYSTEM_PROMPT = """You are a Hebrew job-tagging assistant for a local Eilat jobs app.
Your job is to categorise each job posting into one or more of these 14 fixed categories:

  hotels       — Jobs at hotels (front desk, housekeeping, reception, waitstaff in hotels)
  restaurants  — Restaurants, cafes, bars, kitchen staff, chefs, waitstaff (non-hotel)
  sales        — Sales reps, telesales, door-to-door, sales consultants, B2B sales
  retail       — Shop sales, cashiers, stockers, floor staff in shops/malls/kiosks
  tourism      — Tour guides, diving instructors, attractions staff, desert tours, sea activities
  call_center  — Call-center agents, customer service (non-shop), support, collections
  security     — Guards, patrol, cashiers' alarm, bouncers, CCTV operators
  cleaning     — Cleaners, housekeepers (non-hotel), maintenance, pool cleaners, street crews
  logistics    — Drivers, couriers, warehouse, shipping, port, movers
  office       — Administration, secretaries, clerical, HR, accounting, finance, payroll
  health       — Doctors, nurses, caregivers, lab, pharmacy, dental, mental health, elderly care
  education    — Teachers, tutors, counsellors, youth leaders, gan (kindergarten), instructors
  construction — Builders, electricians, plumbers, welders, carpenters, maintenance tech, factory
  tech         — Developers, IT, QA, data, cyber, ERP, network, hardware tech

RULES:
 - Return ONLY a valid JSON array of category slugs, nothing else (no markdown, no prose).
 - A job CAN have multiple tags (up to 2). Return the most relevant ones.
 - Use ONLY the slugs from the list above.
 - If nothing fits, return [].
 - Do NOT invent new categories.

EXAMPLES:
 Input:  "דרוש/ה מאבטח/ת למלון ישרוטל יהלום"
 Output: ["security","hotels"]

 Input:  "לרשת בגדים דרושים מוכריםױות לחנויות באילת"
 Output: ["retail","sales"]

 Input:  "מדריך צלילה PADI לעונת הקיץ"
 Output: ["tourism"]

 Input:  "נהג/ת משאית שינועי לחברת הובלות"
 Output: ["logistics"]

 Input:  "מלצרים למשמרת ערב מסעדת דגים"
 Output: ["restaurants"]
"""


def _parse_tags(raw: str) -> List[str]:
    if not raw:
        return []
    txt = raw.strip()
    txt = re.sub(r"^```(?:json)?\s*", "", txt)
    txt = re.sub(r"\s*```$", "", txt)
    try:
        arr = json.loads(txt)
    except json.JSONDecodeError:
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
        if slug in JOB_CATEGORY_SLUGS and slug not in out:
            out.append(slug)
        if len(out) >= 2:
            break
    return out


async def tag_job(title: str, description: str = "") -> List[str]:
    api_key = os.environ.get("EMERGENT_LLM_KEY")
    if not api_key:
        log.warning("EMERGENT_LLM_KEY missing — skipping job tagging")
        return []
    from emergentintegrations.llm.chat import LlmChat, UserMessage

    body_preview = (description or "")[:400]
    prompt = f"TITLE: {title}\nDESCRIPTION: {body_preview}"
    try:
        chat = LlmChat(
            api_key=api_key,
            session_id=f"job-tag-{uuid.uuid4().hex[:10]}",
            system_message=_SYSTEM_PROMPT,
        ).with_model("anthropic", "claude-sonnet-4-5-20250929")
        response = await chat.send_message(UserMessage(text=prompt))
    except Exception as e:
        log.warning("LLM job-tag call failed for %r: %s", title[:40], e)
        return []
    return _parse_tags(response or "")


async def tag_jobs_batch(jobs: List[Dict[str, Any]], concurrency: int = 4) -> List[List[str]]:
    sem = asyncio.Semaphore(concurrency)
    results: List[List[str]] = [[] for _ in jobs]

    async def worker(i: int, j: Dict[str, Any]) -> None:
        async with sem:
            try:
                results[i] = await tag_job(j.get("title") or "", j.get("description") or "")
            except Exception as e:
                log.warning("tag_job #%d failed: %s", i, e)
                results[i] = []

    await asyncio.gather(*[worker(i, j) for i, j in enumerate(jobs)])
    return results
