"""Analytics module for Eilatush.

Tracks anonymous user events and provides aggregation queries used by the
admin chat mode. Data is stored in MongoDB collection `analytics_events`.

Each event document looks like:
{
  "user_id":   "anon_xxxx",          # anonymous client UUID (AsyncStorage)
  "event":     "business_view",       # event type
  "props":     { ... },               # arbitrary properties (id, source, etc.)
  "ts":        ISODate                # server-side timestamp
}
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

log = logging.getLogger("analytics")

# Allowed event types — keep this list explicit so we don't pollute the DB
EVENT_TYPES = {
    "app_open",
    "screen_view",            # props.screen = home/news/jobs/businesses/eilatush
    "business_view",          # props.id = business id
    "business_phone_click",
    "business_directions_click",
    "business_website_click",
    "job_view",
    "job_outbound_click",
    "event_view",
    "event_outbound_click",
    "news_view",
    "news_outbound_click",
    "ai_message",             # props.text = user's question (truncated 200 chars)
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _period_start(period: str) -> datetime:
    """Return start of the requested period (UTC). period in:
    today | week | month | 30d | 7d | all
    """
    now = datetime.now(timezone.utc)
    if period == "today":
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "yesterday":
        return now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
    if period in ("7d", "week"):
        return now - timedelta(days=7)
    if period in ("30d", "month"):
        return now - timedelta(days=30)
    if period == "90d":
        return now - timedelta(days=90)
    # default: all
    return datetime(2020, 1, 1, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------
async def track(db, user_id: str, event: str, props: Optional[Dict[str, Any]] = None) -> None:
    if event not in EVENT_TYPES:
        log.warning("track unknown event=%s", event)
        return
    if not user_id:
        return
    doc = {
        "user_id": str(user_id)[:64],
        "event": event,
        "props": props or {},
        "ts": datetime.now(timezone.utc),
    }
    try:
        await db.analytics_events.insert_one(doc)
    except Exception as e:
        log.warning("track insert failed: %s", e)


# ---------------------------------------------------------------------------
# Read — aggregations
# ---------------------------------------------------------------------------
async def user_metrics(db, period: str = "30d") -> Dict[str, Any]:
    """DAU, MAU, retention summary."""
    now = datetime.now(timezone.utc)
    start = _period_start(period)

    # Active users in period
    users = await db.analytics_events.distinct("user_id", {"ts": {"$gte": start}})
    period_users = len(users)

    # DAU (today)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    dau_users = await db.analytics_events.distinct("user_id", {"ts": {"$gte": today_start}})

    # MAU (last 30 days, regardless of period)
    mau_start = now - timedelta(days=30)
    mau_users = await db.analytics_events.distinct("user_id", {"ts": {"$gte": mau_start}})

    # New users in period (their FIRST event was inside period)
    new_users = 0
    sample_users = await db.analytics_events.distinct("user_id", {"ts": {"$gte": start}})
    for uid in sample_users:
        first = await db.analytics_events.find_one(
            {"user_id": uid}, sort=[("ts", 1)], projection={"ts": 1}
        )
        if first:
            ts = first["ts"]
            # Mongo round-trips datetimes as offset-naive UTC; force-aware
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if ts >= start:
                new_users += 1

    # Sessions ~ count of app_open events
    sessions = await db.analytics_events.count_documents(
        {"ts": {"$gte": start}, "event": "app_open"}
    )

    # Total events in period
    total_events = await db.analytics_events.count_documents({"ts": {"$gte": start}})

    return {
        "period": period,
        "active_users_in_period": period_users,
        "dau": len(dau_users),
        "mau": len(mau_users),
        "stickiness_dau_mau_pct": round(
            100 * len(dau_users) / max(1, len(mau_users)), 1
        ),
        "new_users_in_period": new_users,
        "sessions_in_period": sessions,
        "total_events_in_period": total_events,
        "events_per_user": round(total_events / max(1, period_users), 1),
    }


async def section_engagement(db, period: str = "30d") -> Dict[str, Any]:
    start = _period_start(period)
    pipeline = [
        {"$match": {"event": "screen_view", "ts": {"$gte": start}}},
        {"$group": {
            "_id": "$props.screen",
            "views": {"$sum": 1},
            "uniqueUsers": {"$addToSet": "$user_id"},
        }},
        {"$project": {
            "screen": "$_id",
            "views": 1,
            "unique_users": {"$size": "$uniqueUsers"},
            "_id": 0,
        }},
        {"$sort": {"views": -1}},
    ]
    rows = await db.analytics_events.aggregate(pipeline).to_list(50)
    total = sum(r["views"] for r in rows) or 1
    for r in rows:
        r["share_pct"] = round(100 * r["views"] / total, 1)
    return {"period": period, "screens": rows}


async def top_businesses(db, period: str = "30d", n: int = 10) -> Dict[str, Any]:
    start = _period_start(period)
    pipeline = [
        {"$match": {
            "event": {"$in": ["business_view", "business_phone_click",
                              "business_directions_click", "business_website_click"]},
            "ts": {"$gte": start},
        }},
        {"$group": {
            "_id": "$props.id",
            "views":           {"$sum": {"$cond": [{"$eq": ["$event", "business_view"]}, 1, 0]}},
            "phone_clicks":    {"$sum": {"$cond": [{"$eq": ["$event", "business_phone_click"]}, 1, 0]}},
            "directions":      {"$sum": {"$cond": [{"$eq": ["$event", "business_directions_click"]}, 1, 0]}},
            "website":         {"$sum": {"$cond": [{"$eq": ["$event", "business_website_click"]}, 1, 0]}},
        }},
        {"$sort": {"views": -1}},
        {"$limit": n},
    ]
    raw = await db.analytics_events.aggregate(pipeline).to_list(n)
    # enrich with name
    out: List[Dict[str, Any]] = []
    for r in raw:
        biz = await db.businesses.find_one({"id": r["_id"]}, {"_id": 0, "name": 1, "category": 1})
        out.append({
            "business_id": r["_id"],
            "name": (biz or {}).get("name", "?"),
            "category": (biz or {}).get("category"),
            "views": r["views"],
            "phone_clicks": r["phone_clicks"],
            "directions": r["directions"],
            "website": r["website"],
        })
    return {"period": period, "businesses": out}


async def top_ai_questions(db, period: str = "30d", n: int = 20) -> Dict[str, Any]:
    start = _period_start(period)
    pipeline = [
        {"$match": {"event": "ai_message", "ts": {"$gte": start}}},
        {"$group": {"_id": "$props.text", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": n},
    ]
    raw = await db.analytics_events.aggregate(pipeline).to_list(n)
    return {
        "period": period,
        "questions": [{"text": r["_id"], "count": r["count"]} for r in raw if r["_id"]],
    }


async def top_events(db, period: str = "30d", n: int = 10) -> Dict[str, Any]:
    start = _period_start(period)
    pipeline = [
        {"$match": {"event": {"$in": ["event_view", "event_outbound_click"]}, "ts": {"$gte": start}}},
        {"$group": {
            "_id": "$props.id",
            "views":    {"$sum": {"$cond": [{"$eq": ["$event", "event_view"]}, 1, 0]}},
            "outbound": {"$sum": {"$cond": [{"$eq": ["$event", "event_outbound_click"]}, 1, 0]}},
        }},
        {"$sort": {"views": -1}},
        {"$limit": n},
    ]
    raw = await db.analytics_events.aggregate(pipeline).to_list(n)
    out = []
    for r in raw:
        ev = await db.events.find_one({"id": r["_id"]}, {"_id": 0, "title": 1, "venue": 1})
        out.append({
            "event_id": r["_id"],
            "title": (ev or {}).get("title", "?"),
            "venue": (ev or {}).get("venue"),
            "views": r["views"],
            "outbound_clicks": r["outbound"],
        })
    return {"period": period, "events": out}


async def top_news(db, period: str = "30d", n: int = 10) -> Dict[str, Any]:
    start = _period_start(period)
    pipeline = [
        {"$match": {"event": {"$in": ["news_view", "news_outbound_click"]}, "ts": {"$gte": start}}},
        {"$group": {
            "_id": "$props.id",
            "views":    {"$sum": {"$cond": [{"$eq": ["$event", "news_view"]}, 1, 0]}},
            "outbound": {"$sum": {"$cond": [{"$eq": ["$event", "news_outbound_click"]}, 1, 0]}},
        }},
        {"$sort": {"views": -1}},
        {"$limit": n},
    ]
    raw = await db.analytics_events.aggregate(pipeline).to_list(n)
    out = []
    for r in raw:
        nw = await db.news.find_one({"id": r["_id"]}, {"_id": 0, "title": 1, "source": 1})
        out.append({
            "news_id": r["_id"],
            "title": (nw or {}).get("title", "?"),
            "source": (nw or {}).get("source"),
            "views": r["views"],
            "outbound_clicks": r["outbound"],
        })
    return {"period": period, "articles": out}


async def top_jobs(db, period: str = "30d", n: int = 10) -> Dict[str, Any]:
    start = _period_start(period)
    pipeline = [
        {"$match": {"event": {"$in": ["job_view", "job_outbound_click"]}, "ts": {"$gte": start}}},
        {"$group": {
            "_id": "$props.id",
            "views":    {"$sum": {"$cond": [{"$eq": ["$event", "job_view"]}, 1, 0]}},
            "outbound": {"$sum": {"$cond": [{"$eq": ["$event", "job_outbound_click"]}, 1, 0]}},
        }},
        {"$sort": {"views": -1}},
        {"$limit": n},
    ]
    raw = await db.analytics_events.aggregate(pipeline).to_list(n)
    out = []
    for r in raw:
        jb = await db.jobs.find_one({"id": r["_id"]}, {"_id": 0, "title": 1, "company": 1})
        out.append({
            "job_id": r["_id"],
            "title": (jb or {}).get("title", "?"),
            "company": (jb or {}).get("company"),
            "views": r["views"],
            "outbound_clicks": r["outbound"],
        })
    return {"period": period, "jobs": out}


async def full_report(db, period: str = "30d") -> Dict[str, Any]:
    """Single call that returns everything — used to inject into AI context."""
    return {
        "users": await user_metrics(db, period),
        "engagement": await section_engagement(db, period),
        "businesses": await top_businesses(db, period, n=10),
        "ai_questions": await top_ai_questions(db, period, n=15),
        "events": await top_events(db, period, n=10),
        "jobs": await top_jobs(db, period, n=10),
        "news": await top_news(db, period, n=10),
    }
