"""AI-powered event deduplication.

Many Eilat events are published to multiple platforms (Smarticket, Tickchak,
the municipality's site, cinema chains, etc.).  The same show — "מופע אילתוש"
at "היכל התרבות" at 17:30 — can therefore appear 3-5 times in our DB with
slightly different titles, venues, prices, and images.

This module collapses those duplicates into ONE canonical event with a
``sources: [...]`` array containing every place the event was found.  It uses
Claude Sonnet 4.5 to judge whether two candidates are the same event —
this catches matches that simple string comparison misses (e.g. Hebrew vs.
English title, abbreviated venue, typos, "מופע" vs "הופעה" as synonyms).

Pipeline (called after every event scrape):

    1. Pull all FUTURE events from Mongo.
    2. Group by date.
    3. Inside each date, find candidate pairs (time within ±60 minutes).
    4. Ask Claude for each pair: "same event? which fields are best?"
    5. Build clusters from confirmed-same pairs (union-find).
    6. For each cluster, write the merged event back, set sources array,
       delete the duplicates.

Cost: pairs are <30 / day in practice → ~$0.01–$0.05 per scrape.  All calls
go through the existing Emergent LLM Key (``EMERGENT_LLM_KEY``).
"""
from __future__ import annotations

import json
import logging
import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger("events.dedup")

# ---------------------------------------------------------------------------
# Tunables
# ---------------------------------------------------------------------------
TIME_WINDOW_MIN = 60          # candidate pair: |Δstart| ≤ 60 min
MIN_CONFIDENCE = 0.70          # require Claude confidence ≥ this for merge
MAX_PAIRS_PER_RUN = 100        # safety cap to keep cost predictable
MIN_TOKEN_OVERLAP = 1          # title+venue must share ≥ this many tokens
                               # otherwise we skip the LLM call entirely
                               # (huge cost saver for "placeholder 18:00" pairs)

# Image source preference (left-to-right = most preferred).
# eilat_muni and cinema_eilat are curated; tickchak/smarticket are auto-generated.
IMAGE_PREF = ["eilat_muni", "cinema_eilat", "eilat_city", "tickchak", "smarticket", "easy"]


# Words that appear in many titles but tell us nothing about the event identity.
# Filtered out before computing token overlap.
_STOP_TOKENS = {
    # Hebrew determiners / conjunctions / common words
    "של", "את", "עם", "על", "אל", "מן", "כל", "אם", "אבל", "או", "גם", "כי",
    "זה", "זו", "זאת", "אלה", "אלו", "היא", "הוא", "הם", "הן",
    # Generic event words (real differentiator comes from name, not category)
    "מופע", "הופעה", "הצגה", "כנס", "אירוע", "פסטיבל", "מסיבה",
    "אילת", "ילדים", "משפחה", "לילדים", "למשפחה",
    # Cinema noise prefix
    "🎬", "סרט", "סרטים", "קולנוע",
    # Date/time tokens that sources add
    "2025", "2026", "2027",
    # Common English noise
    "the", "a", "an", "of", "and", "or", "to", "for",
}


def _tokenize(text: Optional[str]) -> set:
    """Return a set of meaningful tokens from a Hebrew/English string."""
    if not text:
        return set()
    import re as _re
    # split on whitespace and punctuation
    parts = _re.split(r"[\s,.\-—–:;!?'\"\(\)\[\]\/\\&\|\u05BE\u05F3\u05F4]+", text)
    tokens = set()
    for p in parts:
        p = p.strip().lower()
        # strip surrounding punctuation
        p = p.strip("״׳'\"`")
        if not p or p in _STOP_TOKENS:
            continue
        if len(p) < 2:
            continue
        if p.isdigit() and int(p) < 100:  # short numbers like "20" "30" rarely useful
            continue
        tokens.add(p)
    return tokens


def _has_shared_tokens(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    """Quick pre-filter — share at least N meaningful tokens in title OR venue.

    This skips ~80% of LLM calls on busy days where dozens of unrelated events
    happen to share a placeholder start time like 18:00.
    """
    a_tok = _tokenize(a.get("title")) | _tokenize(a.get("venue"))
    b_tok = _tokenize(b.get("title")) | _tokenize(b.get("venue"))
    return len(a_tok & b_tok) >= MIN_TOKEN_OVERLAP


# ---------------------------------------------------------------------------
# Public entry-point
# ---------------------------------------------------------------------------
async def dedup_future_events(db) -> Dict[str, Any]:
    """Run the full dedup pass.  Returns a stats dict for logging / admin.

    Safe to call multiple times — already-merged events have a ``sources``
    array that we respect: a merged event participates in further pairings
    only as ITSELF (we don't re-explode the cluster).
    """
    now = datetime.now(timezone.utc)
    cursor = db.events.find(
        {"starts_at": {"$gte": now}, "_dedup_skip": {"$ne": True}},
        {"_id": 0},
    ).sort("starts_at", 1)
    events: List[Dict[str, Any]] = await cursor.to_list(length=2000)
    if not events:
        return {"examined": 0, "candidate_pairs": 0, "merged_pairs": 0, "clusters": 0, "deleted": 0}

    log.info("dedup: examining %d future events", len(events))

    # Group by date string
    by_date: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for ev in events:
        start = ev.get("starts_at")
        if not isinstance(start, datetime):
            continue
        by_date[start.date().isoformat()].append(ev)

    # Build candidate pairs by time window inside each date bucket
    pairs: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []
    skipped_no_overlap = 0
    for date_key, group in by_date.items():
        if len(group) < 2:
            continue
        group.sort(key=lambda e: e["starts_at"])
        for i, a in enumerate(group):
            for b in group[i + 1:]:
                # quick prune: time gap
                diff = abs((b["starts_at"] - a["starts_at"]).total_seconds()) / 60.0
                if diff > TIME_WINDOW_MIN:
                    # group is sorted, so all later items are even farther
                    break
                # Already merged together?  (Same id is impossible because Mongo,
                # but a shared canonical ref is possible after multiple runs.)
                if a["id"] == b["id"]:
                    continue
                # Cheap pre-filter: skip pairs with no meaningful word overlap
                # in title or venue.  Saves ~80% of LLM calls on busy days.
                if not _has_shared_tokens(a, b):
                    skipped_no_overlap += 1
                    continue
                pairs.append((a, b))
                if len(pairs) >= MAX_PAIRS_PER_RUN:
                    break
            if len(pairs) >= MAX_PAIRS_PER_RUN:
                break
        if len(pairs) >= MAX_PAIRS_PER_RUN:
            break

    log.info("dedup: %d candidate pairs (after pre-filter; %d skipped no-overlap)",
             len(pairs), skipped_no_overlap)
    if not pairs:
        return {"examined": len(events), "candidate_pairs": 0, "merged_pairs": 0, "clusters": 0, "deleted": 0}

    # Ask Claude for each pair (in parallel batches to keep latency OK)
    verdicts: List[Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]] = []
    import asyncio
    sem = asyncio.Semaphore(4)  # 4 concurrent LLM calls

    async def _judge(pair):
        a, b = pair
        async with sem:
            verdict = await _claude_pair_verdict(a, b)
            return (a, b, verdict)

    tasks = [_judge(p) for p in pairs]
    for coro in asyncio.as_completed(tasks):
        verdicts.append(await coro)

    same_pairs = [
        (a, b, v) for (a, b, v) in verdicts
        if v.get("is_same_event") is True and float(v.get("confidence", 0)) >= MIN_CONFIDENCE
    ]
    log.info("dedup: %d / %d pairs confirmed as same event", len(same_pairs), len(verdicts))

    # Union-find to build clusters
    parent: Dict[str, str] = {}
    def find(x: str) -> str:
        while parent.get(x, x) != x:
            parent[x] = parent.get(parent.get(x, x), x)
            x = parent[x]
        parent.setdefault(x, x)
        return x
    def union(x: str, y: str) -> None:
        rx, ry = find(x), find(y)
        if rx != ry:
            parent[rx] = ry

    by_id: Dict[str, Dict[str, Any]] = {e["id"]: e for e in events}
    pair_verdicts: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for a, b, v in same_pairs:
        union(a["id"], b["id"])
        # Store under a frozenset-style canonical key so cluster lookups can
        # find verdicts regardless of (a, b) ordering.
        key = tuple(sorted((a["id"], b["id"])))
        pair_verdicts[key] = v

    clusters: Dict[str, List[str]] = defaultdict(list)
    for eid in by_id.keys():
        root = find(eid)
        clusters[root].append(eid)

    multi = {k: v for k, v in clusters.items() if len(v) > 1}
    log.info("dedup: %d clusters with ≥2 members", len(multi))

    deleted = 0
    merged_clusters = 0
    for root, member_ids in multi.items():
        members = [by_id[m] for m in member_ids]
        # Pick ONLY the verdicts whose both endpoints belong to this cluster
        member_set = set(member_ids)
        cluster_verdicts = {
            k: v for k, v in pair_verdicts.items()
            if k[0] in member_set and k[1] in member_set
        }
        merged_ev = _merge_cluster(members, cluster_verdicts)
        # Save merged record under primary id; delete the others.
        await db.events.replace_one({"id": merged_ev["id"]}, merged_ev, upsert=True)
        for m in members:
            if m["id"] != merged_ev["id"]:
                await db.events.delete_one({"id": m["id"]})
                deleted += 1
        merged_clusters += 1

    stats = {
        "examined": len(events),
        "candidate_pairs": len(pairs),
        "merged_pairs": len(same_pairs),
        "clusters": merged_clusters,
        "deleted": deleted,
    }
    log.info("dedup done: %s", stats)
    return stats


# ---------------------------------------------------------------------------
# LLM judgment
# ---------------------------------------------------------------------------
PROMPT_TEMPLATE = """אתה עוזר שמשווה אירועים שנגרדו ממקורות שונים באילת.
החלט אם שני האירועים הבאים הם **אותו האירוע** שפורסם פעמיים, או שני אירועים שונים שמתקיימים באותו יום.

קח בחשבון:
- כותרות יכולות להיות שונות אבל לתאר את אותו אירוע (לדוגמה: "מופע הקיץ" ו"מופע הקיץ 2025")
- שמות אולמות יכולים להיות מקוצרים ("היכל התרבות" = "אולם וילסון, היכל התרבות אילת")
- אם המופע מסומן כ"בוטל" באחד מהמקורות — זה עדיין אותו האירוע (תסמן same=true)
- אם המקורות הם של אותה הפקה אבל באולמות שונים → אירועים שונים
- אם הזמנים שונים ביותר מ-20 דקות וגם המקום שונה → סביר שהם שונים

אירוע A (מקור: {a_source})
  כותרת: {a_title}
  שעה:   {a_time}
  אולם:  {a_venue}
  תיאור: {a_desc}
  מחיר:  {a_price}
  קישור: {a_link}

אירוע B (מקור: {b_source})
  כותרת: {b_title}
  שעה:   {b_time}
  אולם:  {b_venue}
  תיאור: {b_desc}
  מחיר:  {b_price}
  קישור: {b_link}

החזר JSON תקין בלבד, ללא טקסט נוסף:
{{
  "is_same_event": true/false,
  "confidence": 0.0-1.0,
  "reasoning": "הסבר קצר בעברית",
  "best_title": "...",       // הכותרת הברורה והשלמה יותר
  "best_venue": "...",       // האולם הספציפי ביותר (או null)
  "best_description": "...", // התיאור הארוך והמשמעותי יותר (או null)
  "best_price": "...",       // המחיר אם קיים באחד (או null)
  "best_category": "..."     // קטגוריה אם קיימת (או null)
}}
"""


def _fmt_dt(dt: Optional[datetime]) -> str:
    if not isinstance(dt, datetime):
        return "—"
    return dt.strftime("%Y-%m-%d %H:%M")


async def _claude_pair_verdict(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    """Ask Claude whether two events are duplicates.  Returns the parsed JSON.

    On any error (network, malformed JSON, missing API key) we return
    ``{"is_same_event": False}`` so the pair is kept separate — safe default.
    """
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
    except Exception as e:  # noqa: BLE001
        log.warning("emergentintegrations not installed: %s", e)
        return {"is_same_event": False, "confidence": 0.0, "reasoning": "llm-unavailable"}

    api_key = os.getenv("EMERGENT_LLM_KEY", "").strip()
    if not api_key:
        log.warning("EMERGENT_LLM_KEY missing — skipping dedup")
        return {"is_same_event": False, "confidence": 0.0, "reasoning": "no-api-key"}

    prompt = PROMPT_TEMPLATE.format(
        a_source=a.get("source", "?"),
        a_title=(a.get("title") or "—")[:200],
        a_time=_fmt_dt(a.get("starts_at")),
        a_venue=(a.get("venue") or "—")[:120],
        a_desc=(a.get("description") or "—")[:400],
        a_price=(a.get("price") or "—"),
        a_link=(a.get("link") or "—")[:150],
        b_source=b.get("source", "?"),
        b_title=(b.get("title") or "—")[:200],
        b_time=_fmt_dt(b.get("starts_at")),
        b_venue=(b.get("venue") or "—")[:120],
        b_desc=(b.get("description") or "—")[:400],
        b_price=(b.get("price") or "—"),
        b_link=(b.get("link") or "—")[:150],
    )

    try:
        chat = LlmChat(
            api_key=api_key,
            session_id=f"event-dedup-{a['id']}-{b['id']}",
            system_message="אתה עוזר שמחזיר תמיד JSON תקין בלבד, ללא טקסט סביב.",
        ).with_model("anthropic", "claude-sonnet-4-5-20250929")
        msg = UserMessage(text=prompt)
        resp = await chat.send_message(msg)
        text = (resp or "").strip()
        # Strip markdown fences if Claude wrapped its output
        if text.startswith("```"):
            text = text.split("```", 2)[1]
            if text.startswith("json"):
                text = text[4:].lstrip("\n")
        data = json.loads(text)
        if not isinstance(data, dict):
            raise ValueError("not a dict")
        return data
    except Exception as e:  # noqa: BLE001
        log.warning("dedup: claude failed for %s vs %s: %s", a["id"], b["id"], e)
        return {"is_same_event": False, "confidence": 0.0, "reasoning": "llm-error"}


# ---------------------------------------------------------------------------
# Cluster merging
# ---------------------------------------------------------------------------
def _pick_image(members: List[Dict[str, Any]]) -> Optional[str]:
    """Pick the best image across cluster members using IMAGE_PREF order."""
    by_source: Dict[str, str] = {}
    for m in members:
        img = m.get("image")
        src = m.get("source", "")
        if img and not by_source.get(src):
            by_source[src] = img
    for pref in IMAGE_PREF:
        if pref in by_source:
            return by_source[pref]
    # Fallback: any non-empty image
    for m in members:
        if m.get("image"):
            return m["image"]
    return None


def _existing_sources(member: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Pull a `sources` array from an event — accept either the new schema
    (already-merged record) or the legacy single-source schema."""
    src_arr = member.get("sources")
    if isinstance(src_arr, list) and src_arr:
        return src_arr
    # Synthesize from the single-source fields
    return [{
        "source": member.get("source") or "",
        "source_name": member.get("source_name") or None,
        "link": member.get("link") or None,
        "image": member.get("image") or None,
    }]


def _merge_cluster(
    members: List[Dict[str, Any]],
    verdicts: Dict[Tuple[str, str], Dict[str, Any]],
) -> Dict[str, Any]:
    """Merge a list of duplicate events into one canonical record.

    Strategy:
      * Pick the member with the most-complete data as the base (the one with
        the most non-null fields wins; tie-broken by earliest fetched_at).
      * Fields are then overridden by `best_*` hints from Claude where useful.
      * `sources` array unions all per-member source dicts (deduped by source slug).
    """
    def completeness(e: Dict[str, Any]) -> int:
        score = 0
        for f in ("title", "description", "venue", "image", "price", "category", "link"):
            if e.get(f):
                score += 1
        return score

    members_sorted = sorted(
        members,
        key=lambda e: (-completeness(e), e.get("fetched_at") or datetime.min.replace(tzinfo=timezone.utc)),
    )
    base = dict(members_sorted[0])  # mutable copy

    # Aggregate Claude best_* hints from all pair-verdicts involving this cluster
    titles, venues, descs, prices, cats = [], [], [], [], []
    for v in verdicts.values():
        if not isinstance(v, dict):
            continue
        for k, bucket in (("best_title", titles), ("best_venue", venues),
                          ("best_description", descs), ("best_price", prices),
                          ("best_category", cats)):
            val = v.get(k)
            if val and isinstance(val, str) and val not in ("—", "null", "None"):
                bucket.append(val)

    def pick_longest(values: List[str], current: Optional[str]) -> Optional[str]:
        candidates = [c for c in values if c] + ([current] if current else [])
        candidates = [c.strip() for c in candidates if c and c.strip()]
        if not candidates:
            return current
        return max(candidates, key=len)

    base["title"] = pick_longest(titles, base.get("title"))
    base["venue"] = pick_longest(venues, base.get("venue"))
    base["description"] = pick_longest(descs, base.get("description"))
    base["price"] = base.get("price") or (prices[0] if prices else None)
    base["category"] = base.get("category") or (cats[0] if cats else None)

    # Picture: explicit preference order, regardless of base
    img = _pick_image(members)
    if img:
        base["image"] = img

    # Build the union of sources
    seen_src: Dict[str, Dict[str, Any]] = {}
    for m in members:
        for s in _existing_sources(m):
            slug = (s.get("source") or "").lower()
            if not slug:
                continue
            if slug not in seen_src:
                seen_src[slug] = s
            else:
                # Prefer entry with a link over one without
                if not seen_src[slug].get("link") and s.get("link"):
                    seen_src[slug] = s
    base["sources"] = list(seen_src.values())

    # Bookkeeping
    base["merged_at"] = datetime.now(timezone.utc)
    base["merged_count"] = len(members)
    return base
