from fastapi import FastAPI, APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import json
import uuid
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional, Literal, Any, Dict
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from scrapers import run_all_scrapers
from jobs import run_all_job_scrapers
from businesses import run_all_business_scrapers

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

EMERGENT_LLM_KEY = os.environ.get('EMERGENT_LLM_KEY')

app = FastAPI(title="Eilatush API")
api_router = APIRouter(prefix="/api")

# ------------------- MODELS -------------------

class Event(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    description: str
    category: str  # party, concert, show, activity, food, sport
    venue: str
    image: str
    starts_at: datetime
    ends_at: Optional[datetime] = None
    price: Optional[str] = None
    whatsapp: Optional[str] = None
    phone: Optional[str] = None
    link: Optional[str] = None

class Business(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    category: str  # restaurant, bar, cafe, shop, service, beauty, sport
    description: str
    image: str
    address: str
    phone: Optional[str] = None
    whatsapp: Optional[str] = None
    open_hours: str  # "09:00-23:00"
    deal: Optional[str] = None
    rating: float = 4.5
    tags: List[str] = []

class Job(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    company: str
    category: str  # hotel, restaurant, tourism, retail, service
    description: str
    salary: Optional[str] = None
    urgency: Literal["now", "soon", "this_week"] = "soon"
    location: str
    phone: Optional[str] = None
    whatsapp: Optional[str] = None
    posted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class News(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    summary: str
    source: str  # municipality, event, alert
    image: Optional[str] = None
    published_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    link: Optional[str] = None

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None

# ------------------- HELPERS -------------------

def _clean(doc: dict) -> dict:
    if not doc:
        return doc
    doc.pop("_id", None)
    return doc

def _time_band(starts_at: datetime) -> str:
    now = datetime.now(timezone.utc)
    if starts_at.tzinfo is None:
        starts_at = starts_at.replace(tzinfo=timezone.utc)
    delta = (starts_at - now).total_seconds()
    if delta <= 3600 and delta >= -7200:  # within last 2h or next 1h
        return "now"
    # Tonight means later today / up to 6 AM next morning
    end_of_tonight = now.replace(hour=23, minute=59, second=59) + timedelta(hours=7)
    if starts_at <= end_of_tonight:
        return "tonight"
    return "later"

def _is_open_now(open_hours: str) -> bool:
    try:
        # format "09:00-23:00" or "24h"
        if open_hours.strip().lower() in ("24h", "24/7"):
            return True
        start, end = open_hours.split("-")
        now = datetime.now(timezone.utc) + timedelta(hours=2)  # Israel UTC+2 (approx, ignoring DST)
        sh, sm = [int(x) for x in start.split(":")]
        eh, em = [int(x) for x in end.split(":")]
        cur_min = now.hour * 60 + now.minute
        s_min = sh * 60 + sm
        e_min = eh * 60 + em
        if e_min < s_min:  # overnight
            return cur_min >= s_min or cur_min <= e_min
        return s_min <= cur_min <= e_min
    except Exception:
        return True

# ------------------- ROUTES -------------------

@api_router.get("/")
async def root():
    return {"message": "Eilatush API – אילתוש"}

@api_router.get("/events")
async def get_events(band: Optional[str] = None, category: Optional[str] = None):
    q: Dict[str, Any] = {}
    if category:
        q["category"] = category
    docs = await db.events.find(q, {"_id": 0}).to_list(500)
    # sort by start time
    docs.sort(key=lambda d: d["starts_at"])
    if band:
        docs = [d for d in docs if _time_band(d["starts_at"]) == band]
    # add computed band field
    for d in docs:
        d["band"] = _time_band(d["starts_at"])
    return docs

def _split_csv(val: Optional[str]) -> List[str]:
    if not val:
        return []
    return [v for v in (s.strip() for s in val.split(",")) if v]


@api_router.get("/businesses")
async def get_businesses(
    type: Optional[str] = None,       # "business" | "professional" (default = business)
    category: Optional[str] = None,   # comma-separated slugs
    source: Optional[str] = None,     # comma-separated source slugs
    q: Optional[str] = None,
    open_now: Optional[bool] = None,
    limit: int = 500,
):
    query: Dict[str, Any] = {}
    t = (type or "business").lower()
    if t in ("business", "professional"):
        query["type"] = t
    cats = _split_csv(category)
    if cats:
        query["tags"] = {"$in": cats}
    srcs = _split_csv(source)
    if srcs:
        query["source"] = {"$in": srcs}
    if q:
        query["$or"] = [
            {"name": {"$regex": q, "$options": "i"}},
            {"subtitle": {"$regex": q, "$options": "i"}},
            {"description": {"$regex": q, "$options": "i"}},
            {"address": {"$regex": q, "$options": "i"}},
            {"tags": {"$regex": q, "$options": "i"}},
        ]
    docs = await db.businesses.find(query, {"_id": 0}).sort("name", 1).to_list(int(limit))
    for d in docs:
        d.setdefault("tags", [])
        d.setdefault("also_in", [])
        d["open_now"] = _is_open_now(d.get("open_hours", "") or "")
    if open_now:
        docs = [d for d in docs if d["open_now"]]
    return docs


@api_router.get("/businesses/categories")
async def get_biz_categories(type: Optional[str] = None):
    """Return the fixed taxonomy + counts per slug for businesses or professionals."""
    try:
        from businesses.categorizer import BUSINESS_CATEGORIES, PROFESSIONAL_CATEGORIES
    except Exception:
        BUSINESS_CATEGORIES, PROFESSIONAL_CATEGORIES = [], []

    t = (type or "business").lower()
    taxonomy = PROFESSIONAL_CATEGORIES if t == "professional" else BUSINESS_CATEGORIES

    pipeline = [
        {"$match": {"type": t, "tags": {"$ne": None}}},
        {"$unwind": "$tags"},
        {"$group": {"_id": "$tags", "count": {"$sum": 1}}},
    ]
    counts: Dict[str, int] = {}
    try:
        docs = await db.businesses.aggregate(pipeline).to_list(100)
        for d in docs:
            counts[d["_id"]] = d["count"]
    except Exception:
        pass
    total = await db.businesses.count_documents({"type": t})
    out = [{"slug": "all", "label": "הכל", "emoji": "🧾", "count": total}]
    for c in taxonomy:
        out.append({
            "slug": c["slug"],
            "label": c["label"],
            "emoji": c["emoji"],
            "count": counts.get(c["slug"], 0),
        })
    return out


@api_router.get("/businesses/sources")
async def get_biz_sources(type: Optional[str] = None):
    match: Dict[str, Any] = {}
    if type:
        match["type"] = type
    pipeline = [
        {"$match": match},
        {"$group": {"_id": {"src": "$source", "name": "$source_name"}, "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    docs = await db.businesses.aggregate(pipeline).to_list(100)
    return [
        {"source": d["_id"]["src"], "source_name": d["_id"].get("name") or d["_id"]["src"], "count": d["count"]}
        for d in docs
    ]


@api_router.get("/businesses/status")
async def get_biz_status():
    last = await db.businesses.find_one(
        {"fetched_at": {"$ne": None}},
        sort=[("fetched_at", -1)],
        projection={"_id": 0, "fetched_at": 1},
    )
    total_biz = await db.businesses.count_documents({"type": "business"})
    total_pro = await db.businesses.count_documents({"type": "professional"})
    return {
        "last_updated_at": (last or {}).get("fetched_at"),
        "total_businesses": total_biz,
        "total_professionals": total_pro,
    }


@api_router.post("/businesses/refresh")
async def refresh_businesses_now():
    count = await _run_businesses_scrape()
    return {"fetched": count}


@api_router.get("/businesses/{biz_id}")
async def get_business(biz_id: str):
    doc = await db.businesses.find_one({"id": biz_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Business not found")
    doc.setdefault("tags", [])
    doc.setdefault("also_in", [])
    doc["open_now"] = _is_open_now(doc.get("open_hours", "") or "")
    return doc

@api_router.get("/jobs")
async def get_jobs(
    urgency: Optional[str] = None,
    category: Optional[str] = None,     # comma-separated list: "hotels,sales"
    date_range: Optional[str] = None,   # "today" | "3d" | "week" | "month"
    job_type: Optional[str] = None,     # comma-separated list: "full_time,shifts"
    experience: Optional[str] = None,   # comma-separated list: "none,required"
    source: Optional[str] = None,       # comma-separated list: "drushim,jobmaster"
):
    query: Dict[str, Any] = {}
    if urgency:
        query["urgency"] = urgency

    def _split(val: Optional[str]) -> List[str]:
        if not val:
            return []
        return [v for v in (s.strip() for s in val.split(",")) if v]

    cats = _split(category)
    if cats:
        # tags is an array per doc → $in matches any
        query["tags"] = {"$in": cats}
    jts = _split(job_type)
    if jts:
        query["job_type"] = {"$in": jts}
    exps = _split(experience)
    if exps:
        query["experience"] = {"$in": exps}
    srcs = _split(source)
    if srcs:
        query["source"] = {"$in": srcs}
    # date_range stays single (ranges are nested)
    if date_range in ("today", "3d", "week", "month"):
        now = datetime.now(timezone.utc)
        deltas = {"today": timedelta(days=1), "3d": timedelta(days=3),
                  "week": timedelta(days=7), "month": timedelta(days=30)}
        query["posted_at"] = {"$gte": now - deltas[date_range]}
    docs = await db.jobs.find(query, {"_id": 0}).to_list(500)
    def _key(d: Dict[str, Any]):
        p = d.get("posted_at")
        ts = -p.timestamp() if isinstance(p, datetime) else 0
        return ts
    docs.sort(key=_key)
    for d in docs:
        d.setdefault("tags", [])
        d.setdefault("also_in", [])
    return docs


@api_router.get("/jobs/categories")
async def get_jobs_categories():
    """Return the fixed jobs category taxonomy + counts per slug."""
    try:
        from jobs.categorizer import JOB_CATEGORIES
    except Exception:
        JOB_CATEGORIES = []

    pipeline = [
        {"$match": {"tags": {"$ne": None}}},
        {"$unwind": "$tags"},
        {"$group": {"_id": "$tags", "count": {"$sum": 1}}},
    ]
    counts: Dict[str, int] = {}
    try:
        docs = await db.jobs.aggregate(pipeline).to_list(100)
        for d in docs:
            counts[d["_id"]] = d["count"]
    except Exception:
        pass
    total = await db.jobs.count_documents({})
    out = [{"slug": "all", "label": "הכל", "emoji": "🧾", "count": total}]
    for c in JOB_CATEGORIES:
        out.append({
            "slug": c["slug"],
            "label": c["label"],
            "emoji": c["emoji"],
            "count": counts.get(c["slug"], 0),
        })
    return out


@api_router.get("/jobs/sources")
async def get_jobs_sources():
    """Distinct job sources + counts."""
    pipeline = [
        {"$match": {"source": {"$exists": True, "$ne": None}}},
        {"$group": {"_id": {"src": "$source", "name": "$source_name"}, "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    docs = await db.jobs.aggregate(pipeline).to_list(100)
    return [
        {"source": d["_id"]["src"], "source_name": d["_id"].get("name") or d["_id"]["src"], "count": d["count"]}
        for d in docs
    ]


@api_router.get("/jobs/status")
async def get_jobs_status():
    last = await db.jobs.find_one(
        {"fetched_at": {"$ne": None}},
        sort=[("fetched_at", -1)],
        projection={"_id": 0, "fetched_at": 1},
    )
    total = await db.jobs.count_documents({})
    return {
        "last_updated_at": (last or {}).get("fetched_at"),
        "total_jobs": total,
    }


@api_router.post("/jobs/refresh")
async def refresh_jobs_now():
    """Manual trigger to run the jobs scrapers immediately."""
    count = await _run_jobs_scrape()
    return {"fetched": count}


@api_router.get("/jobs/{job_id}")
async def get_job(job_id: str):
    doc = await db.jobs.find_one({"id": job_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Job not found")
    doc.setdefault("tags", [])
    doc.setdefault("also_in", [])
    return doc

@api_router.get("/news")
async def get_news(
    source: Optional[str] = None,
    source_name: Optional[str] = None,
    category: Optional[str] = None,
):
    query: Dict[str, Any] = {
        # only return real articles that have a publication date
        "published_at": {"$ne": None},
    }
    if source:
        query["source_type"] = source
    if source_name:
        query["source_name"] = source_name
    if category:
        # Articles can carry multiple tags; match any article whose `tags`
        # array contains the requested slug.
        query["tags"] = category
    docs = await db.news.find(query, {"_id": 0}).to_list(500)
    # Sort by real published_at (newest → oldest)
    def _key(d):
        p = d.get("published_at")
        return -p.timestamp() if isinstance(p, datetime) else 0
    docs.sort(key=_key)
    # Generate a preview from content_html when summary is empty (happens
    # after our title/date cleanup for sources like Maariv/Globes where the
    # summary was just the title repeated). Then strip heavy content_html.
    import re as _re
    for d in docs:
        s = (d.get("summary") or "").strip()
        if not s:
            ch = d.get("content_html") or ""
            if ch:
                # strip tags → plain text, collapse whitespace
                plain = _re.sub(r"<[^>]+>", " ", ch)
                plain = _re.sub(r"\s+", " ", plain).strip()
                if plain:
                    d["summary"] = plain[:280]
        d.pop("content_html", None)
        # make sure `tags` is always present (empty list for legacy docs)
        d.setdefault("tags", [])
    return docs


@api_router.get("/news/categories")
async def get_news_categories():
    """Return the fixed category taxonomy (slug + Hebrew label + emoji) along
    with the live count of articles per category. Frontend uses this to render
    the chip row."""
    try:
        from categorizer import CATEGORIES
    except Exception:
        CATEGORIES = []

    pipeline = [
        {"$match": {"published_at": {"$ne": None}, "tags": {"$ne": None}}},
        {"$unwind": "$tags"},
        {"$group": {"_id": "$tags", "count": {"$sum": 1}}},
    ]
    counts: Dict[str, int] = {}
    try:
        docs = await db.news.aggregate(pipeline).to_list(100)
        for d in docs:
            counts[d["_id"]] = d["count"]
    except Exception:
        pass

    total = await db.news.count_documents({"published_at": {"$ne": None}})
    out = [
        {"slug": "all", "label": "הכל", "emoji": "📰", "count": total},
    ]
    for c in CATEGORIES:
        out.append({
            "slug": c["slug"],
            "label": c["label"],
            "emoji": c["emoji"],
            "count": counts.get(c["slug"], 0),
        })
    return out


@api_router.get("/news/sources")
async def get_news_sources():
    """Return list of distinct source_name values (articles w/ a real publication date)."""
    pipeline = [
        {"$match": {
            "source_name": {"$exists": True, "$ne": None},
            "published_at": {"$ne": None},
        }},
        {"$group": {"_id": "$source_name", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    docs = await db.news.aggregate(pipeline).to_list(100)
    return [{"source_name": d["_id"], "count": d["count"]} for d in docs]


@api_router.get("/news/status")
async def get_news_status():
    """Return aggregate news feed status — including the last scrape time (max fetched_at)."""
    last = await db.news.find_one(
        {"fetched_at": {"$ne": None}},
        sort=[("fetched_at", -1)],
        projection={"_id": 0, "fetched_at": 1},
    )
    total = await db.news.count_documents({"published_at": {"$ne": None}})
    return {
        "last_updated_at": (last or {}).get("fetched_at"),
        "total_articles": total,
    }


@api_router.get("/news/{article_id}")
async def get_news_article(article_id: str):
    doc = await db.news.find_one({"id": article_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Article not found")
    return doc


@api_router.post("/news/refresh")
async def refresh_news_now():
    """Manual trigger to run scrapers immediately."""
    count = await _run_scrape_job()
    return {"fetched": count}

# --------- Eilatush AI ---------

EILATUSH_SYSTEM_PROMPT = """אתה "אילתוש", עוזר חכם ומקומי של אפליקציית Eilatush - אפליקציה לתושבי אילת.
המטרה שלך: לעזור למשתמשים למצוא מהר מה שהם מחפשים באפליקציה: אירועים, עסקים, משרות ומבזקים.

אתה חייב להחזיר תשובה בפורמט JSON תקין וללא טקסט נוסף:
{
  "reply": "תשובה קצרה וחמה בעברית, 1-2 משפטים. אל תכתוב מידע ארוך - רק הפניה למה שמצאת.",
  "intent": "events" | "businesses" | "jobs" | "news" | "general",
  "filters": {
    "category": null | "party" | "concert" | "food" | "bar" | "restaurant" | "cafe" | "shop" | "hotel" | "tourism" | "beauty" | "sport",
    "time": null | "now" | "tonight" | "later",
    "urgency": null | "now" | "soon" | "this_week",
    "keywords": ["מילות חיפוש בעברית"]
  }
}

דוגמאות:
- "ברים פתוחים עכשיו" → intent: businesses, category: bar, keywords: []
- "מה קורה הלילה" → intent: events, time: tonight
- "עבודה דחופה במלון" → intent: jobs, category: hotel, urgency: now
- "סושי זול" → intent: businesses, category: restaurant, keywords: ["סושי"]
- "מסיבה עכשיו" → intent: events, category: party, time: now

חשוב: תמיד JSON חוקי בלבד. בלי markdown, בלי הסברים חיצוניים."""

async def _llm_classify(message: str, session_id: str) -> Dict[str, Any]:
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=session_id,
            system_message=EILATUSH_SYSTEM_PROMPT,
        ).with_model("anthropic", "claude-sonnet-4-5-20250929")
        resp = await chat.send_message(UserMessage(text=message))
        text = resp.strip()
        # strip code fences if present
        if text.startswith("```"):
            text = text.strip("`")
            if text.startswith("json"):
                text = text[4:].strip()
        return json.loads(text)
    except Exception as e:
        logger.exception("LLM classify failed: %s", e)
        # heuristic fallback
        lower = message.lower()
        intent = "general"
        filters: Dict[str, Any] = {"category": None, "time": None, "urgency": None, "keywords": []}
        if any(k in message for k in ["אירוע", "מסיב", "הופע", "הלילה", "הערב", "עכשיו"]):
            intent = "events"
            if "עכשיו" in message:
                filters["time"] = "now"
            elif "הלילה" in message or "הערב" in message:
                filters["time"] = "tonight"
        elif any(k in message for k in ["עבודה", "משרה", "ג׳וב", "שיפט"]):
            intent = "jobs"
            if "דחוף" in message or "עכשיו" in message:
                filters["urgency"] = "now"
        elif any(k in message for k in ["מסעדה", "בר", "אוכל", "סושי", "חומוס", "פיצה", "בית קפה", "מבצע"]):
            intent = "businesses"
        elif any(k in message for k in ["חדש", "עדכון", "מבזק", "עירייה"]):
            intent = "news"
        return {
            "reply": "הנה מה שמצאתי בשבילך 🐠",
            "intent": intent,
            "filters": filters,
        }

@api_router.post("/eilatush/chat")
async def eilatush_chat(body: ChatRequest):
    session_id = body.session_id or str(uuid.uuid4())
    parsed = await _llm_classify(body.message, session_id)
    intent = parsed.get("intent", "general")
    filters = parsed.get("filters") or {}
    results: List[Dict[str, Any]] = []

    if intent == "events":
        q: Dict[str, Any] = {}
        if filters.get("category"):
            q["category"] = filters["category"]
        docs = await db.events.find(q, {"_id": 0}).to_list(500)
        for d in docs:
            d["band"] = _time_band(d["starts_at"])
        if filters.get("time"):
            docs = [d for d in docs if d["band"] == filters["time"]]
        kws = filters.get("keywords") or []
        if kws:
            docs = [d for d in docs if any(kw in (d["title"] + d["description"]) for kw in kws)]
        docs.sort(key=lambda d: d["starts_at"])
        results = [{"type": "event", "item": d} for d in docs[:10]]

    elif intent == "businesses":
        q = {}
        if filters.get("category"):
            q["category"] = filters["category"]
        docs = await db.businesses.find(q, {"_id": 0}).to_list(500)
        for d in docs:
            d["open_now"] = _is_open_now(d.get("open_hours", ""))
        if filters.get("time") == "now":
            docs = [d for d in docs if d["open_now"]]
        kws = filters.get("keywords") or []
        if kws:
            docs = [d for d in docs if any(kw in (d["name"] + d["description"] + " ".join(d.get("tags", []))) for kw in kws)]
        results = [{"type": "business", "item": d} for d in docs[:10]]

    elif intent == "jobs":
        q = {}
        if filters.get("category"):
            q["category"] = filters["category"]
        if filters.get("urgency"):
            q["urgency"] = filters["urgency"]
        docs = await db.jobs.find(q, {"_id": 0}).to_list(500)
        results = [{"type": "job", "item": d} for d in docs[:10]]

    elif intent == "news":
        docs = await db.news.find({}, {"_id": 0}).to_list(500)
        docs.sort(key=lambda d: d["published_at"], reverse=True)
        results = [{"type": "news", "item": d} for d in docs[:10]]

    return {
        "session_id": session_id,
        "reply": parsed.get("reply") or "הנה מה שמצאתי 🐠",
        "intent": intent,
        "results": results,
    }

# ------------------- SEED -------------------

def _iso(dt: datetime) -> datetime:
    return dt

async def seed_data():
    now = datetime.now(timezone.utc)

    # --- Events ---
    if await db.events.count_documents({}) == 0:
        events = [
            {
                "id": str(uuid.uuid4()),
                "title": "מסיבת חוף ב־Sunset Beach",
                "description": "DJ סט חי, קוקטיילים ומסיבת ריקודים עד הבוקר על שפת הים האדום",
                "category": "party",
                "venue": "Sunset Beach Club, חוף הדקל",
                "image": "https://images.unsplash.com/photo-1740432276173-7a0e546e26cf?crop=entropy&cs=srgb&fm=jpg&w=800",
                "starts_at": now + timedelta(minutes=30),
                "ends_at": now + timedelta(hours=6),
                "price": "כניסה חופשית לנשים עד 23:00",
                "whatsapp": "+972501234567",
                "phone": "+97286332211",
            },
            {
                "id": str(uuid.uuid4()),
                "title": "הופעה חיה: עידן רייכל",
                "description": "ערב מוזיקה אקוסטית בפארק העירוני של אילת",
                "category": "concert",
                "venue": "פארק העיר אילת",
                "image": "https://images.unsplash.com/photo-1740432276173-7a0e546e26cf?crop=entropy&cs=srgb&fm=jpg&w=800",
                "starts_at": now + timedelta(hours=3),
                "price": "120 ₪",
                "whatsapp": "+972521234567",
            },
            {
                "id": str(uuid.uuid4()),
                "title": "סטנד־אפ לילה באילת",
                "description": "שלושה קומיקאים מובילים על במה אחת. בואו עם מצב רוח.",
                "category": "show",
                "venue": "מועדון הקומדיה, מרינה",
                "image": "https://images.unsplash.com/photo-1578626574897-2e9c35e1ea29?crop=entropy&cs=srgb&fm=jpg&w=800",
                "starts_at": now + timedelta(hours=5),
                "price": "80 ₪",
                "phone": "+97286543210",
            },
            {
                "id": str(uuid.uuid4()),
                "title": "צלילת ליל ירח במפרץ האלמוגים",
                "description": "חוויית צלילה מודרכת עם מדריכים מוסמכים. ציוד כלול.",
                "category": "activity",
                "venue": "מפרץ האלמוגים",
                "image": "https://images.unsplash.com/photo-1549366970-6b64335a55cb?crop=entropy&cs=srgb&fm=jpg&w=800",
                "starts_at": now + timedelta(hours=8),
                "price": "250 ₪",
                "whatsapp": "+972541234567",
            },
            {
                "id": str(uuid.uuid4()),
                "title": "פסטיבל אוכל רחוב – סיטי סנטר",
                "description": "עשרות דוכנים, שפים מקומיים, מוזיקה חיה ואווירה מטריפה",
                "category": "food",
                "venue": "רחוב התמרים, אילת",
                "image": "https://images.unsplash.com/photo-1549366970-6b64335a55cb?crop=entropy&cs=srgb&fm=jpg&w=800",
                "starts_at": now + timedelta(days=1, hours=5),
                "price": "חינם",
            },
            {
                "id": str(uuid.uuid4()),
                "title": "מרתון אילת השנתי",
                "description": "מרתון עירוני – 5K / 10K / חצי מרתון לכל רמות הכושר",
                "category": "sport",
                "venue": "טיילת אילת",
                "image": "https://images.unsplash.com/photo-1578626574897-2e9c35e1ea29?crop=entropy&cs=srgb&fm=jpg&w=800",
                "starts_at": now + timedelta(days=3),
                "price": "רישום: 90 ₪",
            },
            {
                "id": str(uuid.uuid4()),
                "title": "Ladies Night @ Skybar",
                "description": "קוקטיילים 1+1, DJ סטים ונוף משגע לים",
                "category": "party",
                "venue": "Skybar, מלון רויאל",
                "image": "https://images.unsplash.com/photo-1578626574897-2e9c35e1ea29?crop=entropy&cs=srgb&fm=jpg&w=800",
                "starts_at": now + timedelta(hours=4),
                "price": "כניסה חופשית לנשים",
                "whatsapp": "+972501112233",
            },
            {
                "id": str(uuid.uuid4()),
                "title": "יוגה בזריחה על הטיילת",
                "description": "שיעור פתוח לכולם עם מדריכה מוסמכת. הביאו מזרן.",
                "category": "sport",
                "venue": "טיילת הצפונית",
                "image": "https://images.unsplash.com/photo-1549366970-6b64335a55cb?crop=entropy&cs=srgb&fm=jpg&w=800",
                "starts_at": now + timedelta(days=1, hours=14),
                "price": "30 ₪",
            },
        ]
        await db.events.insert_many(events)

    # --- Businesses ---
    # Demo businesses are NOT seeded. Businesses & professionals come only
    # from real scrapers (run_all_business_scrapers). This keeps the
    # `businesses` collection strictly sourced from user-approved websites.

    # --- Jobs ---
    # Demo jobs are NOT seeded. Jobs come only from real scrapers (run_all_job_scrapers).
    # This keeps the `jobs` collection strictly sourced from user-approved websites.

    # --- News ---
    # Demo news is NOT seeded. News comes only from real scrapers (run_all_scrapers).
    # This keeps the `news` collection strictly sourced from user-approved websites.

    logger.info("Seed complete")

# ------------------- APP WIRING -------------------

app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

@app.on_event("startup")
async def on_startup():
    await seed_data()
    # Clear legacy demo news once (ids are UUID format). Real scraped articles
    # have deterministic sha1-based ids of 20 hex chars.
    try:
        await db.news.delete_many({"id": {"$not": {"$regex": "^[a-f0-9]{20}$"}}})
    except Exception:
        pass
    # Clear legacy demo jobs — real scraped jobs always have a `fingerprint`.
    try:
        await db.jobs.delete_many({"fingerprint": {"$exists": False}})
    except Exception:
        pass
    # Clear legacy demo businesses — real scraped records always have a
    # `fingerprint` field (seeded demo docs lack it).
    try:
        await db.businesses.delete_many({"fingerprint": {"$exists": False}})
    except Exception:
        pass
    # start scheduler + kick off first scrape in background
    _start_scheduler()
    import asyncio
    asyncio.create_task(_run_scrape_job())
    asyncio.create_task(_run_jobs_scrape())
    asyncio.create_task(_run_businesses_scrape())


async def _run_scrape_job() -> int:
    logger.info("news scrape job starting…")
    try:
        articles = await run_all_scrapers()
    except Exception as e:
        logger.exception("scrape job failed: %s", e)
        return 0
    if not articles:
        logger.warning("scrape job produced 0 articles")
        return 0
    # ---- Auto-tag newly-fetched articles that aren't in DB yet (or lack tags).
    # This uses Claude Sonnet via the Emergent universal LLM key. Articles that
    # already have tags stay untouched so we don't re-spend LLM credits.
    try:
        from categorizer import tag_articles_batch
        # Build a lookup of existing tags so we can preserve them on re-upsert.
        existing_tags_by_id: Dict[str, List[str]] = {}
        async for d in db.news.find(
            {"tags": {"$exists": True}},
            {"id": 1, "tags": 1, "_id": 0},
        ):
            existing_tags_by_id[d["id"]] = d.get("tags") or []
        # Articles that still need tagging: NOT in DB OR have empty tags.
        to_tag = [
            a for a in articles
            if not existing_tags_by_id.get(a["id"])  # missing or []
        ]
        if to_tag:
            logger.info("tagging %d new articles…", len(to_tag))
            tag_lists = await tag_articles_batch(to_tag, concurrency=4)
            for a, tags in zip(to_tag, tag_lists):
                a["tags"] = tags
        # For every article NOT in to_tag, preserve the existing tags by
        # overlaying them from DB. This prevents the upsert from wiping out
        # tags we already paid the LLM to compute.
        for a in articles:
            if a["id"] in existing_tags_by_id and not a.get("tags"):
                a["tags"] = existing_tags_by_id[a["id"]]
            a.setdefault("tags", [])
    except Exception as e:
        logger.exception("auto-tagging failed (non-fatal): %s", e)
        for a in articles:
            a.setdefault("tags", [])
    # upsert by id (sha1 of source_url)
    count = 0
    for a in articles:
        await db.news.update_one({"id": a["id"]}, {"$set": a}, upsert=True)
        count += 1
    # After a successful scrape, purge any remaining non-scraped demo items
    try:
        await db.news.delete_many({"source_url": {"$exists": False}})
    except Exception:
        pass
    logger.info("news scrape job done: %d articles upserted", count)
    return count


def _start_scheduler():
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(_run_scrape_job, "interval", hours=1, id="news_hourly", replace_existing=True)
    scheduler.add_job(_run_jobs_scrape, "interval", hours=1, id="jobs_hourly", replace_existing=True)
    # Businesses/professionals change slowly — weekly is plenty.
    scheduler.add_job(_run_businesses_scrape, "interval", days=7, id="biz_weekly", replace_existing=True)
    scheduler.start()
    app.state.scheduler = scheduler
    logger.info("scheduler started (news + jobs every 1h)")


async def _run_jobs_scrape() -> int:
    """Scrape all job sources, dedupe, auto-tag with Claude, upsert in Mongo."""
    logger.info("jobs scrape job starting…")
    try:
        jobs = await run_all_job_scrapers()
    except Exception as e:
        logger.exception("jobs scrape failed: %s", e)
        return 0
    if not jobs:
        logger.warning("jobs scrape produced 0 jobs")
        return 0
    # Auto-tag with Claude. Preserve tags for jobs already in DB with tags set,
    # so we don't re-spend LLM credits on every run.
    try:
        from jobs.categorizer import tag_jobs_batch
        existing_tags_by_id: Dict[str, List[str]] = {}
        async for d in db.jobs.find(
            {"tags": {"$exists": True}},
            {"id": 1, "tags": 1, "_id": 0},
        ):
            existing_tags_by_id[d["id"]] = d.get("tags") or []
        # We tag jobs where the DB has no tags, or the scraper returned empty tags.
        to_tag: List[Dict[str, Any]] = []
        for j in jobs:
            existing = existing_tags_by_id.get(j["id"]) or []
            scraper_tags = j.get("tags") or []
            # Only add to llm queue if there are NO tags at all (neither DB nor scraper)
            if not existing and not scraper_tags:
                to_tag.append(j)
        if to_tag:
            logger.info("tagging %d new jobs with LLM…", len(to_tag))
            tag_lists = await tag_jobs_batch(to_tag, concurrency=4)
            for j, tags in zip(to_tag, tag_lists):
                j["tags"] = list(set((j.get("tags") or []) + (tags or [])))
        # Preserve existing tags for jobs already in DB (the scraper may have
        # returned [] while a previous LLM call had real tags).
        for j in jobs:
            if j["id"] in existing_tags_by_id and not j.get("tags"):
                j["tags"] = existing_tags_by_id[j["id"]]
            j.setdefault("tags", [])
    except Exception as e:
        logger.exception("jobs auto-tag failed (non-fatal): %s", e)
        for j in jobs:
            j.setdefault("tags", [])
    # Upsert by id (sha1 of source_url).
    count = 0
    scraped_ids: List[str] = []
    for j in jobs:
        await db.jobs.update_one({"id": j["id"]}, {"$set": j}, upsert=True)
        scraped_ids.append(j["id"])
        count += 1
    # Purge jobs from our scrapers that weren't seen in this run (expired).
    # Only delete docs that HAVE a fingerprint (= were scraped) AND weren't
    # returned this cycle. Demo/seed jobs stay untouched.
    try:
        await db.jobs.delete_many({
            "fingerprint": {"$exists": True},
            "id": {"$nin": scraped_ids},
        })
    except Exception:
        pass
    logger.info("jobs scrape job done: %d jobs upserted", count)
    return count


async def _run_businesses_scrape() -> int:
    """Scrape all business/professional sources, dedupe, auto-tag, upsert."""
    logger.info("businesses scrape job starting…")
    try:
        items = await run_all_business_scrapers()
    except Exception as e:
        logger.exception("businesses scrape failed: %s", e)
        return 0
    if not items:
        logger.warning("businesses scrape produced 0 items")
        return 0
    # Auto-tag with Claude. Preserve existing tags to save LLM credits.
    try:
        from businesses.categorizer import tag_records_batch
        existing_tags_by_id: Dict[str, List[str]] = {}
        async for d in db.businesses.find(
            {"tags": {"$exists": True}},
            {"id": 1, "tags": 1, "_id": 0},
        ):
            existing_tags_by_id[d["id"]] = d.get("tags") or []
        to_tag: List[Dict[str, Any]] = []
        for it in items:
            existing = existing_tags_by_id.get(it["id"]) or []
            scraper_tags = it.get("tags") or []
            if not existing and not scraper_tags:
                to_tag.append(it)
        if to_tag:
            logger.info("tagging %d new businesses/pros with LLM…", len(to_tag))
            tag_lists = await tag_records_batch(to_tag, concurrency=4)
            for it, tags in zip(to_tag, tag_lists):
                it["tags"] = list(set((it.get("tags") or []) + (tags or [])))
        for it in items:
            if it["id"] in existing_tags_by_id and not it.get("tags"):
                it["tags"] = existing_tags_by_id[it["id"]]
            it.setdefault("tags", [])
    except Exception as e:
        logger.exception("businesses auto-tag failed (non-fatal): %s", e)
        for it in items:
            it.setdefault("tags", [])
    # Upsert by id.
    count = 0
    scraped_ids: List[str] = []
    for it in items:
        await db.businesses.update_one({"id": it["id"]}, {"$set": it}, upsert=True)
        scraped_ids.append(it["id"])
        count += 1
    # Purge stale scraped records (fingerprint exists = was scraped previously
    # but missing from this run).
    try:
        await db.businesses.delete_many({
            "fingerprint": {"$exists": True},
            "id": {"$nin": scraped_ids},
        })
    except Exception:
        pass
    logger.info("businesses scrape job done: %d items upserted", count)
    return count


@app.on_event("shutdown")
async def shutdown_db_client():
    sch = getattr(app.state, "scheduler", None)
    if sch:
        try:
            sch.shutdown(wait=False)
        except Exception:
            pass
    client.close()
