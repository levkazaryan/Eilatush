from fastapi import FastAPI, APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse, HTMLResponse
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
from events import run_all_event_scrapers

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

EMERGENT_LLM_KEY = os.environ.get('EMERGENT_LLM_KEY')

app = FastAPI(title="Eilatush API")
api_router = APIRouter(prefix="/api")


# ------------------- ROOT-LEVEL HEALTH PROBES -------------------
# These endpoints live on the root `app` (NOT the /api router) so that
# Kubernetes / Nginx liveness & readiness probes hitting "/health" and "/"
# return 200 OK even before the DB connection is established. Critical for
# Emergent's native deployment where K8s kills pods that fail health checks.
@app.get("/health")
async def _health_probe():
    return {"status": "ok"}


@app.get("/")
async def _root_probe():
    return {"status": "ok", "service": "eilatush-api"}

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

class ChatHistoryItem(BaseModel):
    role: str  # "user" | "assistant"
    text: str


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    history: Optional[List[ChatHistoryItem]] = None
    user_gender: Optional[str] = None  # "m" | "f" | None

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


@api_router.get("/privacy", response_class=HTMLResponse)
async def privacy_policy():
    """
    Public privacy policy page for Google Play Store listing.
    Required URL: https://eilat-connect.emergent.host/api/privacy
    """
    try:
        policy_path = ROOT_DIR.parent / "frontend" / "assets" / "store" / "privacy-policy.html"
        if policy_path.exists():
            return HTMLResponse(content=policy_path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.error(f"Failed to load privacy policy file: {e}")

    # Fallback inline minimal policy (used if file is missing)
    return HTMLResponse(content="""<!DOCTYPE html><html lang="he" dir="rtl"><head>
<meta charset="UTF-8"><title>מדיניות פרטיות – אילתוש</title></head>
<body style="font-family:sans-serif;max-width:720px;margin:2rem auto;padding:1rem;line-height:1.6">
<h1>מדיניות פרטיות – אילתוש</h1>
<p>אילתוש לא אוספת מידע אישי. אין הרשמה, אין מעקב אחר משתמשים, אין גישה למצלמה/מיקום/אנשי קשר.
הנתונים היחידים הנשמרים הם היסטוריית שיחה מקומית בלבד על המכשיר (AsyncStorage).
האפליקציה מתחברת לשרתים שלנו בלבד כדי להציג חדשות, עסקים, עבודה ואירועים מקומיים,
ולשירות Claude של Anthropic לצורך תשובות העוזרת החכמה.</p>
<p>לשאלות: פנייה דרך כפתור WhatsApp באפליקציה.</p>
<p>© אילתוש 2026</p></body></html>""")

@api_router.get("/events")
async def get_events(
    band: Optional[str] = None,
    category: Optional[str] = None,
    date: Optional[str] = None,        # YYYY-MM-DD for a specific day
    limit: int = 500,
):
    q: Dict[str, Any] = {}
    if category:
        q["category"] = category
    # date filter: events whose start falls in the requested Israeli-local day
    if date:
        try:
            y, m, d = (int(x) for x in date.split("-"))
            # Israel local day → UTC window (IST = UTC+2)
            from datetime import datetime as _dt, timezone as _tz, timedelta as _td
            day_start_local = _dt(y, m, d, 0, 0, tzinfo=_tz(_td(hours=2)))
            day_end_local = day_start_local + _td(days=1)
            q["starts_at"] = {
                "$gte": day_start_local.astimezone(_tz.utc),
                "$lt": day_end_local.astimezone(_tz.utc),
            }
        except Exception:
            pass
    else:
        # Default ("All" tab) — hide events that already ended.
        # An event is considered "ended" if:
        #   • end_at exists AND end_at < now, OR
        #   • starts_at is before TODAY (Israeli local day start)
        # Events starting today (or in the future) stay visible all day even
        # without an explicit end_at, so users can still browse "today's"
        # things until midnight Asia/Jerusalem.
        from datetime import datetime as _dt, timezone as _tz, timedelta as _td
        ist = _tz(_td(hours=2))
        now_utc = _dt.now(_tz.utc)
        today_start_utc = _dt.now(ist).replace(hour=0, minute=0, second=0, microsecond=0).astimezone(_tz.utc)
        q["$or"] = [
            # Events with explicit end_at: still upcoming if end_at >= now
            {"end_at": {"$gte": now_utc}},
            # Events without end_at: still upcoming if starts_at >= today start
            {"end_at": None, "starts_at": {"$gte": today_start_utc}},
            {"end_at": {"$exists": False}, "starts_at": {"$gte": today_start_utc}},
        ]
    docs = await db.events.find(q, {"_id": 0}).to_list(limit)
    # sort by start time (earliest first)
    docs.sort(key=lambda d: d.get("starts_at") or datetime.now(timezone.utc))
    if band:
        docs = [d for d in docs if _time_band(d["starts_at"]) == band]
    # add computed band field
    for d in docs:
        d["band"] = _time_band(d["starts_at"])
    return docs


@api_router.post("/events/refresh")
async def refresh_events() -> Dict[str, Any]:
    """Manual trigger for the event scrape + categorization pipeline."""
    count = await _run_events_scrape()
    return {"ok": True, "fetched": count}


@api_router.get("/events/days")
async def events_days() -> List[Dict[str, Any]]:
    """Return {date, count, label} for each upcoming day that has events (next 30)."""
    from datetime import datetime as _dt, timezone as _tz, timedelta as _td
    ist = _tz(_td(hours=2))
    now = _dt.now(ist)
    horizon = now + _td(days=30)
    docs = await db.events.find(
        {"starts_at": {"$gte": now.astimezone(_tz.utc), "$lt": horizon.astimezone(_tz.utc)}},
        {"_id": 0, "starts_at": 1},
    ).to_list(5000)
    by_day: Dict[str, int] = {}
    for d in docs:
        sa = d.get("starts_at")
        if not sa:
            continue
        if sa.tzinfo is None:
            sa = sa.replace(tzinfo=_tz.utc)
        key = sa.astimezone(ist).strftime("%Y-%m-%d")
        by_day[key] = by_day.get(key, 0) + 1
    out = [{"date": k, "count": v} for k, v in sorted(by_day.items())]
    return out


@api_router.get("/events/status")
async def events_status() -> Dict[str, Any]:
    total = await db.events.count_documents({})
    by_source: Dict[str, int] = {}
    async for d in db.events.aggregate([
        {"$group": {"_id": "$source", "c": {"$sum": 1}}}
    ]):
        by_source[d["_id"] or "seed"] = d["c"]
    latest = await db.events.find({"fetched_at": {"$exists": True}}, {"_id": 0, "fetched_at": 1}) \
        .sort("fetched_at", -1).limit(1).to_list(1)
    return {
        "total": total,
        "by_source": by_source,
        "last_updated_at": (latest[0]["fetched_at"].isoformat() if latest else None),
    }

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


# ------------------- ANALYTICS -------------------
class TrackEventRequest(BaseModel):
    user_id: str
    event: str
    props: Optional[Dict[str, Any]] = None


@api_router.post("/track")
async def track_event(body: TrackEventRequest):
    """Anonymous user analytics ingest. Called by the mobile app on every
    significant interaction (tab views, business clicks, phone clicks, etc.).
    """
    import analytics
    await analytics.track(db, body.user_id, body.event, body.props or {})
    return {"ok": True}


@api_router.get("/admin/report.pdf")
async def admin_report_pdf(period: str = "30d", token: str = ""):
    """Returns a branded Hebrew PDF analytics report.

    Auth: requires the admin token (same as chat password). Returns 403 if
    the token doesn't match. Used as a download link from the admin chat flow.
    """
    from admin_chat import ADMIN_PASSWORD, PERIOD_LABELS
    import analytics
    from pdf_report import generate_report_pdf
    from fastapi.responses import Response

    if (token or "").strip().lower() != ADMIN_PASSWORD:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Invalid admin token.")

    data = await analytics.full_report(db, period=period)
    pdf_bytes = generate_report_pdf(
        data, period_label=PERIOD_LABELS.get(period, period)
    )
    filename = f"eilatush-report-{period}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@api_router.post("/jobs/purge-non-eilat")
async def purge_non_eilat_jobs():
    """Admin: walk through all jobs in DB and DELETE any whose title /
    company / description clearly belong to a non-Eilat city. Lightweight
    (no scrape, runs in ~1 sec) — used to clean up stale records when the
    scrape filter is too slow to run via Cloudflare."""
    from jobs.base import is_in_eilat
    deleted = 0
    examined = 0
    examples: list[str] = []
    async for j in db.jobs.find({}, {"_id": 0}):
        examined += 1
        # NOTE: do NOT pass `location` here — scrapers default it to "אילת"
        # for every record, which would make the filter a no-op.  We rely on
        # the title / company / description to detect the real city.
        if not is_in_eilat(
            j.get("title"), j.get("company"), j.get("description")
        ):
            await db.jobs.delete_one({"id": j["id"]})
            deleted += 1
            if len(examples) < 10:
                examples.append({
                    "title": (j.get("title") or "")[:80],
                    "location": (j.get("location") or "")[:60],
                })
    return {"examined": examined, "deleted": deleted, "examples": examples}


# ---------------------------------------------------------------------------
# App version / Update prompt
# ---------------------------------------------------------------------------
# A single MongoDB doc tracks the latest published Android version so that
# the mobile app can prompt users to update on launch.
#
#   collection: app_config
#   doc:        { _id: "android_version", latest_version, min_required_version,
#                 message, play_store_url, force, updated_at }
#
# The admin endpoint POST /api/admin/version is called automatically by the
# GitHub Actions CI pipeline after a successful EAS submit, so the version
# stays in sync with what's actually live on Google Play.
PLAY_STORE_URL_DEFAULT = "https://play.google.com/store/apps/details?id=app.eilatush"
DEFAULT_UPDATE_MESSAGE = "יש גרסה חדשה של אילתוש! עדכן/י עכשיו כדי ליהנות מתכונות חדשות 🐬"


def _parse_version(v: Optional[str]) -> tuple[int, ...]:
    """Parse "1.2.3" into (1, 2, 3). Missing parts default to 0."""
    if not v:
        return (0, 0, 0)
    parts = []
    for p in str(v).strip().split("."):
        try:
            parts.append(int(p))
        except ValueError:
            parts.append(0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])


@api_router.get("/app-version")
async def get_app_version():
    """Public — read by the mobile app on every launch."""
    doc = await db.app_config.find_one({"_id": "android_version"}, {"_id": 0})
    if not doc:
        # Sensible defaults if nothing has been set yet
        doc = {
            "latest_version": "1.0.0",
            "min_required_version": "1.0.0",
            "message": DEFAULT_UPDATE_MESSAGE,
            "play_store_url": PLAY_STORE_URL_DEFAULT,
            "force": False,
        }
    return doc


class _VersionUpdateBody(BaseModel):
    password: str
    latest_version: str
    min_required_version: Optional[str] = None
    message: Optional[str] = None
    play_store_url: Optional[str] = None
    force: Optional[bool] = None


@api_router.post("/admin/version")
async def admin_set_version(body: _VersionUpdateBody):
    """Admin — called by CI after a successful Play Store submit, or manually
    via curl. Protected by the same admin password used for the AI chatbot."""
    from admin_chat import ADMIN_PASSWORD
    if body.password.strip().lower() != ADMIN_PASSWORD:
        raise HTTPException(status_code=403, detail="Forbidden")

    update: Dict[str, Any] = {
        "latest_version": body.latest_version.strip(),
        "updated_at": datetime.now(timezone.utc),
    }
    if body.min_required_version is not None:
        update["min_required_version"] = body.min_required_version.strip()
    if body.message is not None:
        update["message"] = body.message
    if body.play_store_url is not None:
        update["play_store_url"] = body.play_store_url
    if body.force is not None:
        update["force"] = bool(body.force)

    # First write — set sensible defaults for any field the caller didn't pass
    existing = await db.app_config.find_one({"_id": "android_version"}, {"_id": 0})
    if not existing:
        update.setdefault("min_required_version", body.latest_version.strip())
        update.setdefault("message", DEFAULT_UPDATE_MESSAGE)
        update.setdefault("play_store_url", PLAY_STORE_URL_DEFAULT)
        update.setdefault("force", False)

    await db.app_config.update_one(
        {"_id": "android_version"},
        {"$set": update},
        upsert=True,
    )
    saved = await db.app_config.find_one({"_id": "android_version"}, {"_id": 0})
    return {"status": "ok", "config": saved}


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
            "reply": "הנה מה שמצאתי בשבילך",
            "intent": intent,
            "filters": filters,
        }

# Personality: warm, local Eilati female friend. Short, friendly, uses emoji sparingly.
EILATUSH_REPLY_PROMPT = """\
את אילתוש - חברה אישית מקומית ותושבת אילת. את *אישה* ומדברת תמיד על עצמך בלשון נקבה ("אני יודעת", "מצאתי", "חשבתי", "אני כאן"). מעולם לא בלשון זכר.
מדברת בעברית טבעית, קצרה, חמה, ועם הומור מקומי ("יא אילתושי", "חחח", "סבבה").
תפקידך: לענות בצורה ישירה, לא למכור, לא להיות רובוטית. יש לך גישה לתוצאות אמיתיות ממסד הנתונים שלנו (אירועים, עסקים, חדשות, עבודות).

חוקים:
1. תשובה של 1-3 משפטים בלבד. אל תפרטי רשימות - המשתמש יראה את הכרטיסיות בעצמו.
2. אם אין תוצאות - תגידי ישירות בלי תירוצים, והציעי כיוון חלופי.
3. התייחסי לפרט אחד מהתוצאות אם זה עוזר ("זה ב-Sunset נשמע שווה" / "הכי רלוונטי זה..."). לא יותר.
4. אל תגידי "מצאתי X תוצאות" - המשתמש רואה את זה.
5. אם המשתמש שאל משהו כללי (לא חיפוש) - תעני כמו חברה שיודעת את אילת. קצר.
6. מזג אוויר - אם המשתמש שאל - השתמשי במידע שצורף ({weather_ctx}). אם לא - התעלמי.
7. תמיד הציעי 3 שאלות המשך קצרות ורלוונטיות - פועל + מקום/סוג.
8. *חובה* - כל דיבור על עצמך בלשון נקבה בלבד ("אני אראה לך", "חשבתי עלייך", "מצאתי לך"). לעולם אל תכתבי בלשון זכר.
9. אל תשתמשי באימוג'י דג בשום מקרה.

מזג אוויר עכשיו באילת: {weather_ctx}
שאלת המשתמש: "{user_msg}"
כוונה שזוהתה: {intent}
סיכום תוצאות שנמצאו (אל תצטטי הכל, רק התייחסי):
{results_summary}

החזירי JSON תקין ובלבד, ללא markdown:
{{
  "reply": "תשובה טבעית של 1-3 משפטים בלשון נקבה",
  "follow_ups": ["שאלה 1", "שאלה 2", "שאלה 3"]
}}"""


async def _fetch_weather_brief() -> str:
    try:
        import httpx as _h
        async with _h.AsyncClient(timeout=6) as c:
            r = await c.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": 29.5577,
                    "longitude": 34.9519,
                    "current": "temperature_2m,weather_code,is_day",
                    "timezone": "auto",
                },
            )
            j = r.json()
            cur = j.get("current", {})
            t = cur.get("temperature_2m")
            code = cur.get("weather_code", 0)
            is_day = cur.get("is_day", 1)
            label = (
                "בהיר" if code == 0 else
                "מעונן חלקית" if code <= 2 else
                "מעונן" if code == 3 else
                "גשום" if code >= 51 and code <= 67 else
                "סופה" if code >= 95 else
                "לא ידוע"
            )
            tod = "יום" if is_day else "לילה"
            return f"{round(t) if t is not None else '?'}° · {label} · {tod}"
    except Exception:
        return "לא זמין"


def _summarize_results(intent: str, results: List[Dict[str, Any]]) -> str:
    if not results:
        return "אין תוצאות."
    lines = []
    for r in results[:5]:
        it = r.get("item", {}) or {}
        if intent == "events":
            lines.append(f"- {it.get('title','?')} · {it.get('venue','')}"[:120])
        elif intent == "businesses":
            lines.append(f"- {it.get('name','?')} · {it.get('category','')} · {it.get('address','')}"[:120])
        elif intent == "jobs":
            lines.append(f"- {it.get('title','?')} · {it.get('company','')}"[:120])
        elif intent == "news":
            lines.append(f"- {it.get('title','?')} · {it.get('source','')}"[:120])
    return "\n".join(lines) if lines else "אין תוצאות."


async def _generate_reply(
    user_msg: str,
    intent: str,
    results: List[Dict[str, Any]],
    session_id: str,
    weather: str,
    user_gender: Optional[str] = None,
) -> Dict[str, Any]:
    """Run a second LLM pass to craft a conversational reply + follow-ups."""
    # Build gender-aware directive to inject into system message
    if user_gender == "m":
        gender_rule = (
            "המשתמש הוא *גבר*. פני אליו תמיד בלשון זכר: "
            "'אתה', 'תגיד', 'בא לך', 'אתה יכול', 'מצאתי לך'. "
            "לעולם אל תפני אליו בלשון נקבה."
        )
    elif user_gender == "f":
        gender_rule = (
            "המשתמשת היא *אישה*. פני אליה תמיד בלשון נקבה: "
            "'את', 'תגידי', 'בא לך', 'את יכולה', 'מצאתי לך'. "
            "לעולם אל תפני אליה בלשון זכר."
        )
    else:
        gender_rule = (
            "אם לא ברור המגדר של המשתמש - השתמשי בצורה ניטרלית או כפולה 'שאל/י'."
        )

    prompt = EILATUSH_REPLY_PROMPT.format(
        user_msg=user_msg,
        intent=intent,
        weather_ctx=weather,
        results_summary=_summarize_results(intent, results),
    )
    # Append gender rule to prompt so Claude adapts each turn
    prompt = f"{prompt}\n\nכללי פנייה למשתמש: {gender_rule}"

    system_msg = (
        "את אילתוש - חברה מקומית לתושבי אילת. "
        "מדברת תמיד בלשון נקבה על עצמך. קצרה, חמה, עברית. "
        "אל תשתמשי באימוג'י דג. "
        f"{gender_rule}"
    )
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"{session_id}_reply",
            system_message=system_msg,
        ).with_model("anthropic", "claude-sonnet-4-5-20250929")
        resp = await chat.send_message(UserMessage(text=prompt))
        text = resp.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.startswith("json"):
                text = text[4:].strip()
        parsed = json.loads(text)
        reply = parsed.get("reply") or "הנה מה שמצאתי"
        follow_ups = [
            s.strip() for s in (parsed.get("follow_ups") or []) if isinstance(s, str)
        ][:3]
        return {"reply": reply, "follow_ups": follow_ups}
    except Exception as e:
        logger.warning("reply gen failed, using fallback: %s", e)
        return {
            "reply": (
                "מצאתי כמה דברים רלוונטיים למטה 👇" if results
                else "לא מצאתי כרגע. רוצה לנסות אחרת?"
            ),
            "follow_ups": _default_followups(intent),
        }


def _default_followups(intent: str) -> List[str]:
    mapping = {
        "events": ["מה קורה מחר?", "יש הופעה בשבת?", "מסיבת חוף הלילה?"],
        "businesses": ["פאב פתוח עכשיו?", "סושי זול?", "ספא טוב?"],
        "jobs": ["עבודה דחופה בערב?", "משרות במלון?", "עבודה לסטודנט?"],
        "news": ["מה חדש בעירייה?", "פתיחות חדשות?", "מבצעים השבוע?"],
        "general": ["מה קורה הערב?", "איפה טוב לאכול?", "עבודה דחופה?"],
    }
    return mapping.get(intent, mapping["general"])


@api_router.post("/eilatush/chat")
async def eilatush_chat(body: ChatRequest):
    session_id = body.session_id or str(uuid.uuid4())
    user_msg = body.message

    # ---------- ANALYTICS: log user question (truncated) ----------
    try:
        import analytics
        # Use session_id as a soft user id for now (real user_id comes from
        # the /api/track endpoint when frontend sends it).
        await analytics.track(
            db, session_id, "ai_message",
            {"text": (user_msg or "")[:200]}
        )
    except Exception:
        pass

    # ---------- ADMIN MODE INTERCEPT ----------
    # If the message is part of an admin flow (trigger / password / question
    # while authenticated), handle it here BEFORE the normal classifier.
    # See `admin_chat.py` for the flow logic.
    try:
        from admin_chat import handle_admin_turn
        admin_resp = await handle_admin_turn(db, session_id, user_msg)
        if admin_resp is not None:
            return {
                "session_id": session_id,
                "reply": admin_resp["reply"],
                "intent": "admin",
                "results": [],
                "follow_ups": admin_resp.get("follow_ups") or [],
                "weather": None,
                "admin": admin_resp.get("admin_payload"),
            }
    except Exception as _e:
        log.warning("admin chat failed: %s", _e)

    parsed = await _llm_classify(user_msg, session_id)
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
            docs = [d for d in docs if any(kw in (d.get("title","") + (d.get("description") or "")) for kw in kws)]
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
            docs = [d for d in docs if any(
                kw in (d.get("name","") + (d.get("description") or "") + " ".join(d.get("tags") or []))
                for kw in kws
            )]
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

    # -- 2nd LLM pass for conversational reply + follow-ups --
    weather = await _fetch_weather_brief()
    gen = await _generate_reply(user_msg, intent, results, session_id, weather, body.user_gender)

    return {
        "session_id": session_id,
        "reply": gen["reply"],
        "intent": intent,
        "results": results,
        "follow_ups": gen["follow_ups"] or _default_followups(intent),
        "weather": weather,
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
    # Clear legacy seeded demo events — real scraped events always have a
    # `source` field (seed records from early development do not).
    try:
        await db.events.delete_many({"source": {"$exists": False}})
    except Exception:
        pass
    # start scheduler + kick off first scrape in background.
    # Skip startup-scrape for a collection if it already has fresh data — but
    # ALWAYS scrape on startup when the existing data is stale (older than the
    # configured TTL).  This is critical on Kubernetes: pods get restarted
    # frequently, and APScheduler's cron triggers can be missed if the pod
    # isn't alive at the exact trigger minute.  The staleness check guarantees
    # we always have fresh data at most `stale_after_hours` old, no matter how
    # often the pod is restarted.
    _start_scheduler()
    import asyncio

    async def _maybe_run(
        count_fn,
        runner,
        min_count: int,
        label: str,
        last_updated_field: Optional[str] = None,
        collection_name: Optional[str] = None,
        stale_after_hours: int = 24,
    ) -> None:
        try:
            c = await count_fn()
        except Exception:
            c = 0
        # Check staleness even when count is high.
        if c >= min_count and last_updated_field and collection_name:
            try:
                latest = await db[collection_name].find_one(
                    {last_updated_field: {"$exists": True}},
                    sort=[(last_updated_field, -1)],
                    projection={last_updated_field: 1, "_id": 0},
                )
                last = latest.get(last_updated_field) if latest else None
                if last:
                    # Mongo stores naive UTC datetimes — coerce to aware for safe compare
                    if last.tzinfo is None:
                        last = last.replace(tzinfo=timezone.utc)
                    age_hours = (datetime.now(timezone.utc) - last).total_seconds() / 3600
                    if age_hours < stale_after_hours:
                        logger.info(
                            "startup skip %s scrape (have %d rows, last update %.1fh ago)",
                            label, c, age_hours,
                        )
                        return
                    logger.info(
                        "startup %s scrape: data is %.1fh old (>%dh threshold) — refreshing",
                        label, age_hours, stale_after_hours,
                    )
                else:
                    logger.info(
                        "startup %s scrape: no last-update timestamp found — refreshing",
                        label,
                    )
            except Exception as e:
                logger.warning("staleness check failed for %s: %s", label, e)
                # Fall through to original count-only behaviour
                logger.info("startup skip %s scrape (have %d rows)", label, c)
                return
        elif c >= min_count:
            logger.info("startup skip %s scrape (have %d rows)", label, c)
            return
        await runner()

    asyncio.create_task(
        _maybe_run(
            lambda: db.news.count_documents({}),
            _run_scrape_job, 30, "news",
            last_updated_field="fetched_at",
            collection_name="news",
            stale_after_hours=6,
        )
    )
    asyncio.create_task(
        _maybe_run(
            lambda: db.jobs.count_documents({}),
            _run_jobs_scrape, 20, "jobs",
            last_updated_field="fetched_at",
            collection_name="jobs",
            stale_after_hours=24,
        )
    )
    asyncio.create_task(
        _maybe_run(
            lambda: db.businesses.count_documents({}),
            _run_businesses_scrape, 500, "businesses",
            last_updated_field="fetched_at",
            collection_name="businesses",
            stale_after_hours=24 * 7,
        )
    )
    asyncio.create_task(
        _maybe_run(
            lambda: db.events.count_documents({"source": {"$exists": True}}),
            _run_events_scrape, 20, "events",
            last_updated_field="fetched_at",
            collection_name="events",
            stale_after_hours=24,
        )
    )


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
    # Jobs refresh every morning at 08:00 Israel local time.
    scheduler.add_job(
        _run_jobs_scrape,
        "cron",
        hour=8,
        minute=0,
        timezone="Asia/Jerusalem",
        id="jobs_daily_0800",
        replace_existing=True,
    )
    # Businesses/professionals change slowly — weekly is plenty.
    scheduler.add_job(_run_businesses_scrape, "interval", days=7, id="biz_weekly", replace_existing=True)
    # Events refresh every morning at 08:00 Israel local time.
    scheduler.add_job(
        _run_events_scrape,
        "cron",
        hour=8,
        minute=0,
        timezone="Asia/Jerusalem",
        id="events_daily_0800",
        replace_existing=True,
    )
    scheduler.start()
    app.state.scheduler = scheduler
    logger.info("scheduler started (news hourly, biz weekly, jobs+events daily 08:00 Asia/Jerusalem)")


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
    """Scrape all business/professional sources, dedupe, upsert, then tag."""
    logger.info("businesses scrape job starting…")
    try:
        items = await run_all_business_scrapers()
    except Exception as e:
        logger.exception("businesses scrape failed: %s", e)
        return 0
    if not items:
        logger.warning("businesses scrape produced 0 items")
        return 0

    # Preserve any existing LLM tags so re-scrape doesn't lose them.
    existing_tags_by_id: Dict[str, List[str]] = {}
    try:
        async for d in db.businesses.find(
            {"tags": {"$exists": True}},
            {"id": 1, "tags": 1, "_id": 0},
        ):
            if d.get("tags"):
                existing_tags_by_id[d["id"]] = d.get("tags") or []
    except Exception:
        pass
    for it in items:
        if it["id"] in existing_tags_by_id:
            it["tags"] = existing_tags_by_id[it["id"]]
        else:
            it.setdefault("tags", [])

    # --- Upsert FIRST so data is visible on the app immediately. ---
    count = 0
    scraped_ids: List[str] = []
    for it in items:
        await db.businesses.update_one({"id": it["id"]}, {"$set": it}, upsert=True)
        scraped_ids.append(it["id"])
        count += 1
    try:
        await db.businesses.delete_many({
            "fingerprint": {"$exists": True},
            "id": {"$nin": scraped_ids},
        })
    except Exception:
        pass
    logger.info("businesses upsert done: %d items in DB", count)

    # --- Then LLM-tag only items that still have fewer than 2 tags. ---
    try:
        from businesses.categorizer import tag_records_batch
        to_tag = [it for it in items if len(it.get("tags") or []) < 2]
        if to_tag:
            logger.info("tagging %d businesses/pros with LLM…", len(to_tag))
            tag_lists = await tag_records_batch(to_tag, concurrency=6)
            for it, tags in zip(to_tag, tag_lists):
                merged = list(dict.fromkeys((tags or []) + (it.get("tags") or [])))
                it["tags"] = merged[:3]
                # Stream results to DB as they arrive (item-by-item update).
                try:
                    await db.businesses.update_one(
                        {"id": it["id"]}, {"$set": {"tags": it["tags"]}}
                    )
                except Exception:
                    pass
    except Exception as e:
        logger.exception("businesses auto-tag failed (non-fatal): %s", e)

    logger.info("businesses scrape job done: %d items upserted+tagged", count)
    return count


async def _run_events_scrape() -> int:
    """Scrape all event sources, dedupe, upsert and tag (Claude 4.5)."""
    logger.info("events scrape job starting…")
    try:
        items = await run_all_event_scrapers()
    except Exception as e:
        logger.exception("events scrape failed: %s", e)
        return 0
    if not items:
        logger.warning("events scrape produced 0 items")
        return 0

    # Preserve existing tags so we don't re-pay LLM credits each run.
    existing_tags: Dict[str, List[str]] = {}
    try:
        async for d in db.events.find(
            {"tags": {"$exists": True}},
            {"id": 1, "tags": 1, "_id": 0},
        ):
            if d.get("tags"):
                existing_tags[d["id"]] = d["tags"]
    except Exception:
        pass
    for it in items:
        if it["id"] in existing_tags:
            it["tags"] = existing_tags[it["id"]]

    count = 0
    scraped_ids: List[str] = []
    for it in items:
        try:
            await db.events.update_one({"id": it["id"]}, {"$set": it}, upsert=True)
            scraped_ids.append(it["id"])
            count += 1
        except Exception as e:
            logger.warning("events upsert failed for %s: %s", it.get("id"), e)

    # Purge expired scraped events (older than 2 days ago) that weren't seen
    # this run. Keeps the collection tidy.
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=2)
        await db.events.delete_many({
            "source": {"$exists": True},
            "starts_at": {"$lt": cutoff},
        })
    except Exception:
        pass

    # Purge stale "snapshot" sources (cinema_eilat) — these list TODAY's
    # screenings only, so we delete any rows from this source whose ID is
    # NOT in this scrape's results. Guarded by len(src_ids)>0 so a failed
    # scrape never wipes the whole collection.
    SNAPSHOT_SOURCES = ("cinema_eilat",)
    try:
        for src in SNAPSHOT_SOURCES:
            src_ids = [it["id"] for it in items if it.get("source") == src]
            if src_ids:
                await db.events.delete_many({
                    "source": src,
                    "id": {"$nin": src_ids},
                })
    except Exception:
        pass

    # LLM categorization via the Businesses categorizer (reuses same taxonomy).
    # We keep it simple: one tag per event representing category (party /
    # concert / show / activity / food / sport / cinema).
    try:
        to_tag = [it for it in items if not it.get("tags")]
        if to_tag:
            logger.info("tagging %d new events with LLM…", len(to_tag))
            # Adapter: pass a simplified record shape to the businesses tagger.
            adapted = [
                {
                    "id": it["id"],
                    "name": it["title"],
                    "subtitle": it.get("venue") or "",
                    "description": it.get("description") or "",
                    "type": "event",
                }
                for it in to_tag
            ]
            from businesses.categorizer import tag_records_batch
            tag_lists = await tag_records_batch(adapted, concurrency=4)
            for it, tags in zip(to_tag, tag_lists):
                if not tags:
                    continue
                it["tags"] = tags[:3]
                try:
                    await db.events.update_one(
                        {"id": it["id"]}, {"$set": {"tags": it["tags"]}}
                    )
                except Exception:
                    pass
    except Exception as e:
        logger.exception("events auto-tag failed (non-fatal): %s", e)

    logger.info("events scrape job done: %d upserted", count)
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
