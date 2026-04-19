"""AI-based businesses & professionals categorizer.

Classifies Eilat businesses/professionals into a fixed Hebrew subject
taxonomy using Claude Sonnet 4.5 (Emergent universal LLM key).
Returns 1-2 category slugs per record.
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

log = logging.getLogger("biz_categorizer")

# ---------------------------------------------------------------------------
# Businesses taxonomy (location-based establishments).
# ---------------------------------------------------------------------------
BUSINESS_CATEGORIES: List[Dict[str, str]] = [
    {"slug": "restaurants",    "label": "מסעדות",              "emoji": "🍽️"},
    {"slug": "cafes",          "label": "בתי קפה",             "emoji": "☕"},
    {"slug": "bars",           "label": "פאבים וברים",          "emoji": "🍺"},
    {"slug": "fast_food",      "label": "מזון מהיר",            "emoji": "🍔"},
    {"slug": "attractions",    "label": "אטרקציות ובילויים",    "emoji": "🎢"},
    {"slug": "hotels",         "label": "מלונאות ולינה",         "emoji": "🏨"},
    {"slug": "spa",            "label": "ספא ועיסויים",          "emoji": "💆"},
    {"slug": "beauty",         "label": "יופי וטיפוח",          "emoji": "💅"},
    {"slug": "fashion",        "label": "אופנה",                "emoji": "👗"},
    {"slug": "jewelry",        "label": "תכשיטים",              "emoji": "💍"},
    {"slug": "electronics",    "label": "מחשבים ואלקטרוניקה",   "emoji": "💻"},
    {"slug": "appliances",     "label": "מוצרי חשמל ביתיים",    "emoji": "🔌"},
    {"slug": "phones",         "label": "טלפונים סלולרים",      "emoji": "📱"},
    {"slug": "home",           "label": "ריהוט ולבית",           "emoji": "🛋️"},
    {"slug": "supermarket",    "label": "סופרמרקטים",           "emoji": "🛒"},
    {"slug": "shopping_center","label": "מרכזי קניות",          "emoji": "🏬"},
    {"slug": "travel",         "label": "משרדי נסיעות",         "emoji": "✈️"},
    {"slug": "transport",      "label": "תחבורה והשכרה",        "emoji": "🚗"},
    {"slug": "marine",         "label": "ספורט ימי וצלילה",     "emoji": "🤿"},
    {"slug": "consulate",      "label": "קונסוליות",            "emoji": "🏛️"},
    {"slug": "services_biz",   "label": "שירותים",              "emoji": "🧾"},
]

BUSINESS_SLUGS = {c["slug"] for c in BUSINESS_CATEGORIES}

# ---------------------------------------------------------------------------
# Professionals taxonomy (service providers / tradesmen).
# ---------------------------------------------------------------------------
PROFESSIONAL_CATEGORIES: List[Dict[str, str]] = [
    {"slug": "construction",   "label": "שיפוצים ובנייה",        "emoji": "🏗️"},
    {"slug": "electrician",    "label": "חשמלאות",              "emoji": "⚡"},
    {"slug": "plumber",        "label": "אינסטלציה",            "emoji": "🔧"},
    {"slug": "ac",             "label": "מיזוג אוויר וקירור",    "emoji": "❄️"},
    {"slug": "appliance_fix",  "label": "תיקון מוצרי חשמל",      "emoji": "🔌"},
    {"slug": "carpentry",      "label": "נגרות",                "emoji": "🪚"},
    {"slug": "sealing",        "label": "איטום",                "emoji": "🧱"},
    {"slug": "cleaning_pro",   "label": "ניקיון",               "emoji": "🧹"},
    {"slug": "gardening",      "label": "גינון וטיפול בעצים",    "emoji": "🌳"},
    {"slug": "moving",         "label": "הובלות",               "emoji": "📦"},
    {"slug": "locksmith",      "label": "מנעולנות",             "emoji": "🔑"},
    {"slug": "pest",           "label": "הדברה",                "emoji": "🐛"},
    {"slug": "auto_repair",    "label": "מוסכים",               "emoji": "🚙"},
    {"slug": "tutor",          "label": "שיעורים פרטיים",       "emoji": "📚"},
    {"slug": "therapy",        "label": "טיפול רגשי ואישי",      "emoji": "💭"},
    {"slug": "health_pro",     "label": "בריאות אלטרנטיבית",    "emoji": "🏥"},
    {"slug": "lawyer",         "label": "עריכת דין",            "emoji": "⚖️"},
    {"slug": "accountant",     "label": "ראיית חשבון",          "emoji": "🧮"},
    {"slug": "tech_pro",       "label": "מחשבים וטכנולוגיה",    "emoji": "💻"},
    {"slug": "graphics",       "label": "עיצוב וגרפיקה",         "emoji": "🎨"},
    {"slug": "photo",          "label": "צילום",                "emoji": "📷"},
    {"slug": "events_pro",     "label": "אירועים והפקות",        "emoji": "🎉"},
    {"slug": "beauty_home",    "label": "יופי ופרטי",            "emoji": "💇"},
    {"slug": "realestate",     "label": "נדל״ן ותיווך",           "emoji": "🏠"},
]

PROFESSIONAL_SLUGS = {c["slug"] for c in PROFESSIONAL_CATEGORIES}


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------
_BIZ_SYSTEM_PROMPT = """You are a Hebrew business-tagging assistant for a local Eilat app.
Categorise each business into one or more of these 21 fixed categories:

  restaurants     — Sit-down restaurants of any cuisine
  cafes           — Cafes, coffee shops, bakeries
  bars            — Pubs, bars, nightclubs, wine bars
  fast_food       — Fast food, burgers, falafel, shawarma, pizza delivery
  attractions     — Tourist attractions, activity centers, water parks, museums, zoos
  hotels          — Hotels, guest houses, hostels, short rentals
  spa             — Spa centers, massages, wellness, dead-sea treatments
  beauty          — Hair salons, nail studios, makeup, barbershops
  fashion         — Clothing / shoe / accessory shops
  jewelry         — Jewelry stores, watches, goldsmiths
  electronics     — Computer stores, gadgets, tech retail
  appliances      — Household appliances (fridges, ovens, washing machines)
  phones          — Cellular stores and phone accessories
  home            — Furniture, home goods, gifts, gardens
  supermarket     — Supermarkets, grocery, 24/7 shops
  shopping_center — Malls, markets, commercial centers
  travel          — Travel agencies, tour operators, booking offices
  transport       — Car/bike rental, taxis, transport services
  marine          — Diving schools, boat tours, sea sports, beach activity
  consulate       — Consulates, embassies
  services_biz    — Generic services that don't fit above (laundry, key-cutting, etc.)

RULES:
 - Return ONLY a valid JSON array of category slugs. No prose, no markdown.
 - Return 1 or 2 slugs — the most relevant ones.
 - Use ONLY the slugs listed above.
 - If nothing fits, return [].
 - Do NOT invent new slugs.

EXAMPLES:
 Input:  "קאזה דו ברזיל | מסעדת בשרים וגריל"
 Output: ["restaurants"]

 Input:  "Skybar אילת | בר גג עם נוף לים"
 Output: ["bars"]

 Input:  "ספא הים האדום | טיפולי פנים בסגנון ים המלח"
 Output: ["spa"]

 Input:  "סופר קינג אילת | סופרמרקט 24/7"
 Output: ["supermarket"]
"""


_PRO_SYSTEM_PROMPT = """You are a Hebrew tradesman-tagging assistant for a local Eilat app.
Categorise each service-provider / professional into one or more of these 23 fixed categories:

  construction  — General contractors, builders, renovations
  electrician   — Electrical repairs, wiring, panels
  plumber       — Plumbing, drainage, water leaks
  ac            — AC installation/repair, refrigeration
  appliance_fix — Home appliance repair (washing machines, ovens…)
  carpentry     — Carpenters, custom wood, kitchens
  sealing       — Waterproofing, roof sealing
  cleaning_pro  — House cleaning, post-construction cleaning, office cleaning
  gardening     — Gardening, tree cutting, landscaping
  moving        — Movers, shipping, relocation
  locksmith     — Locks, door/lock changes
  pest          — Pest-control, exterminators
  auto_repair   — Garages, car mechanics, body-work
  tutor         — Private tutoring (school subjects, languages, music)
  therapy       — Psychologists, counsellors, NLP coaches, family therapy
  health_pro    — Alternative medicine, reflexology, nutrition, physio (private)
  lawyer        — Lawyers, notaries, legal consulting
  accountant    — Accountants, bookkeepers, tax advisors
  tech_pro      — Private computer technicians, IT for home/small business
  graphics      — Graphic designers, branding, logos
  photo         — Photographers, videographers, events photo
  events_pro    — Event planners, DJs, producers, party rentals
  beauty_home   — Mobile hairdressers, nail techs, private cosmeticians
  realestate    — Real estate brokers, apartment rentals, property sales

RULES:
 - Return ONLY a valid JSON array of category slugs. No prose, no markdown.
 - Return 1 or 2 slugs — the most relevant ones.
 - Use ONLY the slugs listed above.
 - If nothing fits, return [].
 - Do NOT invent new slugs.

EXAMPLES:
 Input:  "דוד האינסטלטור | פתיחת סתימות, תיקון דודים"
 Output: ["plumber"]

 Input:  "נגרות שלומי | מטבחים בהזמנה"
 Output: ["carpentry"]

 Input:  "עו״ד רחל כהן | דיני משפחה וגירושין"
 Output: ["lawyer"]
"""


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------
def _parse_tags(raw: str, valid: set) -> List[str]:
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
        if slug in valid and slug not in out:
            out.append(slug)
        if len(out) >= 2:
            break
    return out


async def _tag_one(
    name: str, desc: str, *, system_prompt: str, valid_slugs: set, session_prefix: str
) -> List[str]:
    api_key = os.environ.get("EMERGENT_LLM_KEY")
    if not api_key:
        log.warning("EMERGENT_LLM_KEY missing — skipping tagging")
        return []
    from emergentintegrations.llm.chat import LlmChat, UserMessage

    body_preview = (desc or "")[:400]
    prompt = f"NAME: {name}\nDESC: {body_preview}"
    try:
        chat = LlmChat(
            api_key=api_key,
            session_id=f"{session_prefix}-{uuid.uuid4().hex[:10]}",
            system_message=system_prompt,
        ).with_model("anthropic", "claude-sonnet-4-5-20250929")
        response = await chat.send_message(UserMessage(text=prompt))
    except Exception as e:
        log.warning("LLM tag call failed for %r: %s", name[:40], e)
        return []
    return _parse_tags(response or "", valid_slugs)


async def tag_business(name: str, desc: str = "") -> List[str]:
    return await _tag_one(
        name, desc,
        system_prompt=_BIZ_SYSTEM_PROMPT,
        valid_slugs=BUSINESS_SLUGS,
        session_prefix="biz-tag",
    )


async def tag_professional(name: str, desc: str = "") -> List[str]:
    return await _tag_one(
        name, desc,
        system_prompt=_PRO_SYSTEM_PROMPT,
        valid_slugs=PROFESSIONAL_SLUGS,
        session_prefix="pro-tag",
    )


async def tag_records_batch(
    records: List[Dict[str, Any]], concurrency: int = 4,
) -> List[List[str]]:
    """Classify a mixed batch of business/professional records in parallel.

    Each record must carry a `type` field ("business" or "professional") so
    we know which taxonomy to use.
    """
    sem = asyncio.Semaphore(concurrency)
    results: List[List[str]] = [[] for _ in records]

    async def worker(i: int, r: Dict[str, Any]) -> None:
        async with sem:
            name = r.get("name") or ""
            desc = " ".join(
                x for x in [r.get("subtitle"), r.get("description"), r.get("category_hint")] if x
            )
            try:
                if r.get("type") == "professional":
                    results[i] = await tag_professional(name, desc)
                else:
                    results[i] = await tag_business(name, desc)
            except Exception as e:
                log.warning("tag #%d failed: %s", i, e)
                results[i] = []

    await asyncio.gather(*[worker(i, r) for i, r in enumerate(records)])
    return results
