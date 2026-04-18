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

@api_router.get("/businesses")
async def get_businesses(category: Optional[str] = None, open_now: Optional[bool] = None, q: Optional[str] = None):
    query: Dict[str, Any] = {}
    if category:
        query["category"] = category
    if q:
        query["$or"] = [
            {"name": {"$regex": q, "$options": "i"}},
            {"description": {"$regex": q, "$options": "i"}},
            {"tags": {"$regex": q, "$options": "i"}},
        ]
    docs = await db.businesses.find(query, {"_id": 0}).to_list(500)
    for d in docs:
        d["open_now"] = _is_open_now(d.get("open_hours", ""))
    if open_now:
        docs = [d for d in docs if d["open_now"]]
    return docs

@api_router.get("/jobs")
async def get_jobs(urgency: Optional[str] = None, category: Optional[str] = None):
    query: Dict[str, Any] = {}
    if urgency:
        query["urgency"] = urgency
    if category:
        query["category"] = category
    docs = await db.jobs.find(query, {"_id": 0}).to_list(500)
    # sort: urgency (now > soon > this_week), newest first
    order = {"now": 0, "soon": 1, "this_week": 2}
    docs.sort(key=lambda d: (order.get(d.get("urgency", "soon"), 3), -d["posted_at"].timestamp() if isinstance(d["posted_at"], datetime) else 0))
    return docs

@api_router.get("/news")
async def get_news(source: Optional[str] = None):
    query: Dict[str, Any] = {}
    if source:
        # source filter now maps to source_type (news/alert/event)
        query["source_type"] = source
    docs = await db.news.find(query, {"_id": 0}).to_list(500)
    docs.sort(key=lambda d: d.get("published_at") or d.get("fetched_at") or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    # strip heavy content_html from list response
    for d in docs:
        d.pop("content_html", None)
    return docs


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
    if await db.businesses.count_documents({}) == 0:
        businesses = [
            {
                "id": str(uuid.uuid4()),
                "name": "סושי סאן - אילת",
                "category": "restaurant",
                "description": "סושי טרי בעבודת יד, משלוחים עד הבית",
                "image": "https://images.unsplash.com/photo-1549366970-6b64335a55cb?crop=entropy&cs=srgb&fm=jpg&w=800",
                "address": "רחוב התמרים 15, אילת",
                "phone": "+97286330011",
                "whatsapp": "+972501112233",
                "open_hours": "12:00-23:30",
                "deal": "20% הנחה על הזמנה ראשונה באפליקציה",
                "rating": 4.7,
                "tags": ["סושי", "יפני", "משלוחים", "זול"],
            },
            {
                "id": str(uuid.uuid4()),
                "name": "Skybar אילת",
                "category": "bar",
                "description": "בר גג עם נוף לים ולהרי אדום",
                "image": "https://images.unsplash.com/photo-1578626574897-2e9c35e1ea29?crop=entropy&cs=srgb&fm=jpg&w=800",
                "address": "טיילת הצפונית, אילת",
                "phone": "+97286550044",
                "whatsapp": "+972501112244",
                "open_hours": "18:00-03:00",
                "deal": "Happy Hour 18:00-20:00: 1+1",
                "rating": 4.6,
                "tags": ["בר", "קוקטיילים", "נוף", "גג"],
            },
            {
                "id": str(uuid.uuid4()),
                "name": "קפה דקל",
                "category": "cafe",
                "description": "בית קפה שכונתי, ארוחות בוקר, קפה ספיישלטי",
                "image": "https://images.unsplash.com/photo-1549366970-6b64335a55cb?crop=entropy&cs=srgb&fm=jpg&w=800",
                "address": "שדרות התמרים 42",
                "phone": "+97286112233",
                "whatsapp": "+972501112255",
                "open_hours": "07:00-20:00",
                "deal": "ארוחת בוקר זוגית 89 ₪",
                "rating": 4.5,
                "tags": ["קפה", "ארוחת בוקר", "משפחתי"],
            },
            {
                "id": str(uuid.uuid4()),
                "name": "פיצה טוסקנה",
                "category": "restaurant",
                "description": "פיצה איטלקית אותנטית בתנור אבן",
                "image": "https://images.unsplash.com/photo-1549366970-6b64335a55cb?crop=entropy&cs=srgb&fm=jpg&w=800",
                "address": "רחוב אילות 7",
                "phone": "+97286664455",
                "whatsapp": "+972501112266",
                "open_hours": "12:00-23:00",
                "deal": "פיצה משפחתית + שתייה 79 ₪",
                "rating": 4.4,
                "tags": ["פיצה", "איטלקי", "משפחות"],
            },
            {
                "id": str(uuid.uuid4()),
                "name": "חומוס אליהו",
                "category": "restaurant",
                "description": "חומוס מיתולוגי של אילת, פתוח מוקדם",
                "image": "https://images.unsplash.com/photo-1549366970-6b64335a55cb?crop=entropy&cs=srgb&fm=jpg&w=800",
                "address": "שוק המסחרי הישן",
                "phone": "+97286334455",
                "open_hours": "08:00-15:00",
                "deal": "מנת חומוס + פיתה + שתייה 35 ₪",
                "rating": 4.8,
                "tags": ["חומוס", "ישראלי", "זול", "בוקר"],
            },
            {
                "id": str(uuid.uuid4()),
                "name": "סופר קינג אילת",
                "category": "shop",
                "description": "סופרמרקט 24/7 עם משלוחים",
                "image": "https://images.unsplash.com/photo-1549366970-6b64335a55cb?crop=entropy&cs=srgb&fm=jpg&w=800",
                "address": "מרכז מסחרי הנמל",
                "phone": "+97286221100",
                "whatsapp": "+972501112277",
                "open_hours": "24h",
                "deal": "משלוח חינם מעל 150 ₪",
                "rating": 4.2,
                "tags": ["סופר", "24/7", "משלוחים"],
            },
            {
                "id": str(uuid.uuid4()),
                "name": "ספא הים האדום",
                "category": "beauty",
                "description": "ספא וטיפולי פנים בסגנון ים המלח",
                "image": "https://images.unsplash.com/photo-1578626574897-2e9c35e1ea29?crop=entropy&cs=srgb&fm=jpg&w=800",
                "address": "מלון רויאל ביץ'",
                "phone": "+97286776655",
                "whatsapp": "+972501112288",
                "open_hours": "09:00-21:00",
                "deal": "טיפול זוגי 40% הנחה",
                "rating": 4.9,
                "tags": ["ספא", "יופי", "זוגות"],
            },
            {
                "id": str(uuid.uuid4()),
                "name": "Dive Eilat",
                "category": "sport",
                "description": "מרכז צלילה מוסמך PADI",
                "image": "https://images.unsplash.com/photo-1549366970-6b64335a55cb?crop=entropy&cs=srgb&fm=jpg&w=800",
                "address": "חוף הצלילה הדרומי",
                "phone": "+97286445566",
                "whatsapp": "+972501112299",
                "open_hours": "08:00-18:00",
                "deal": "חבילת מבוא לצלילה 350 ₪",
                "rating": 4.7,
                "tags": ["צלילה", "ים", "ספורט ימי"],
            },
            {
                "id": str(uuid.uuid4()),
                "name": "המסבאה של אילת",
                "category": "bar",
                "description": "פאב אנגלי אמיתי, בירות מהחבית, משחקי ביליארד",
                "image": "https://images.unsplash.com/photo-1578626574897-2e9c35e1ea29?crop=entropy&cs=srgb&fm=jpg&w=800",
                "address": "מרינה, אילת",
                "phone": "+97286880099",
                "whatsapp": "+972501113300",
                "open_hours": "17:00-02:00",
                "deal": "כוס בירה שנייה 50% הנחה",
                "rating": 4.3,
                "tags": ["בר", "פאב", "בירה", "ביליארד"],
            },
            {
                "id": str(uuid.uuid4()),
                "name": "בורגר באר",
                "category": "restaurant",
                "description": "המבורגרים גורמה ובירה מקומית",
                "image": "https://images.unsplash.com/photo-1549366970-6b64335a55cb?crop=entropy&cs=srgb&fm=jpg&w=800",
                "address": "רחוב ברקת 9",
                "phone": "+97286990011",
                "whatsapp": "+972501113311",
                "open_hours": "12:00-00:00",
                "deal": "המבורגר + צ'יפס + בירה 69 ₪",
                "rating": 4.5,
                "tags": ["המבורגר", "בשר", "בירה"],
            },
            {
                "id": str(uuid.uuid4()),
                "name": "אופניים אילת",
                "category": "service",
                "description": "השכרת אופניים חשמליים וקורקינטים",
                "image": "https://images.unsplash.com/photo-1549366970-6b64335a55cb?crop=entropy&cs=srgb&fm=jpg&w=800",
                "address": "טיילת המרכזית",
                "phone": "+97286112244",
                "whatsapp": "+972501113322",
                "open_hours": "08:00-22:00",
                "deal": "יום שלם 79 ₪ במקום 120 ₪",
                "rating": 4.4,
                "tags": ["אופניים", "השכרה", "תיירות"],
            },
            {
                "id": str(uuid.uuid4()),
                "name": "מספרה ויבה",
                "category": "beauty",
                "description": "מספרת גברים ונשים, תסרוקות מקצועיות",
                "image": "https://images.unsplash.com/photo-1578626574897-2e9c35e1ea29?crop=entropy&cs=srgb&fm=jpg&w=800",
                "address": "מרכז מסחרי הים",
                "phone": "+97286223344",
                "whatsapp": "+972501113333",
                "open_hours": "09:00-20:00",
                "deal": "תספורת + עיצוב זקן 80 ₪",
                "rating": 4.6,
                "tags": ["מספרה", "גברים", "נשים"],
            },
        ]
        await db.businesses.insert_many(businesses)

    # --- Jobs ---
    if await db.jobs.count_documents({}) == 0:
        jobs = [
            {
                "id": str(uuid.uuid4()),
                "title": "מלצר/ית משמרת ערב",
                "company": "מלון רויאל ביץ'",
                "category": "hotel",
                "description": "דרוש/ה מלצר/ית למשמרת ערב החל מהיום. 45 ₪ לשעה + טיפים.",
                "salary": "45 ₪ לשעה + טיפים",
                "urgency": "now",
                "location": "אילת – מלון רויאל ביץ'",
                "phone": "+97286776655",
                "whatsapp": "+972501112288",
                "posted_at": now - timedelta(hours=2),
            },
            {
                "id": str(uuid.uuid4()),
                "title": "דיילת קבלה",
                "company": "מלון הרודס",
                "category": "hotel",
                "description": "משרה מלאה, משמרות בוקר/ערב. אנגלית חובה.",
                "salary": "8,500-10,000 ₪",
                "urgency": "soon",
                "location": "אילת – מלון הרודס",
                "whatsapp": "+972501114400",
                "posted_at": now - timedelta(hours=8),
            },
            {
                "id": str(uuid.uuid4()),
                "title": "בריסטה לבית קפה",
                "company": "קפה דקל",
                "category": "restaurant",
                "description": "משמרות בוקר, יחס משפחתי, טיפים יפים.",
                "salary": "42 ₪ לשעה + טיפים",
                "urgency": "now",
                "location": "אילת – שדרות התמרים 42",
                "phone": "+97286112233",
                "whatsapp": "+972501112255",
                "posted_at": now - timedelta(hours=1),
            },
            {
                "id": str(uuid.uuid4()),
                "title": "מדריך/ת צלילה PADI",
                "company": "Dive Eilat",
                "category": "tourism",
                "description": "עבור עונת הקיץ, תעודת PADI חובה.",
                "salary": "לפי הסכם",
                "urgency": "this_week",
                "location": "חוף הצלילה הדרומי",
                "whatsapp": "+972501112299",
                "posted_at": now - timedelta(days=1),
            },
            {
                "id": str(uuid.uuid4()),
                "title": "קופאי/ת סופרמרקט",
                "company": "סופר קינג",
                "category": "retail",
                "description": "עבודה במשמרות 24/7, שכר שעתי + תוספות.",
                "salary": "38 ₪ לשעה",
                "urgency": "soon",
                "location": "אילת – מרכז הנמל",
                "phone": "+97286221100",
                "whatsapp": "+972501112277",
                "posted_at": now - timedelta(hours=20),
            },
            {
                "id": str(uuid.uuid4()),
                "title": "מאבטח/ת אירועים",
                "company": "Sunset Beach Club",
                "category": "service",
                "description": "משמרת לילה היום! תעודת מאבטח חובה.",
                "salary": "55 ₪ לשעה",
                "urgency": "now",
                "location": "חוף הדקל, אילת",
                "whatsapp": "+972501234567",
                "posted_at": now - timedelta(minutes=45),
            },
        ]
        await db.jobs.insert_many(jobs)

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
    # start scheduler + kick off first scrape in background
    _start_scheduler()
    import asyncio
    asyncio.create_task(_run_scrape_job())


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
    scheduler.start()
    app.state.scheduler = scheduler
    logger.info("scheduler started (news every 1h)")


@app.on_event("shutdown")
async def shutdown_db_client():
    sch = getattr(app.state, "scheduler", None)
    if sch:
        try:
            sch.shutdown(wait=False)
        except Exception:
            pass
    client.close()
