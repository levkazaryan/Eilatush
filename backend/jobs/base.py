"""Shared primitives for jobs scrapers: HTTP fetch, text helpers,
fingerprint for dedup, heuristics for job_type / experience.
"""
from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

log = logging.getLogger("jobs")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "he-IL,he;q=0.9,en;q=0.8",
}

TIMEOUT = httpx.Timeout(20.0, connect=10.0)


# ---------------------------------------------------------------------------
# Fetch helpers
# ---------------------------------------------------------------------------
async def _fetch(client: httpx.AsyncClient, url: str) -> Optional[str]:
    try:
        r = await client.get(url, timeout=TIMEOUT, follow_redirects=True)
        r.raise_for_status()
        return r.text
    except Exception as e:
        log.warning("jobs fetch failed %s: %s", url, e)
        return None


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------
def _strip(s: Optional[str]) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


def _hash_url(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:20]


# Remove noise words / punctuation before comparing titles across sources.
_STOP_WORDS_RE = re.compile(
    r"\b(?:דרוש|דרושה|דרושים|דרושות|ל|לאילת|באילת|לעבודה|למלון|דחוף|מיידי|לאלתר)\b",
    re.IGNORECASE,
)
_NON_HEBREW_ALPHANUM = re.compile(r"[^\u0590-\u05ff\w\s]+", re.UNICODE)


# ---------------------------------------------------------------------------
# Eilat-only city filter
# ---------------------------------------------------------------------------
# Israeli cities that often produce false positives in jobs searches. If a job
# title/description mentions one of these AND does not mention "אילת",
# we treat it as out-of-area and drop it.
_NON_EILAT_CITIES = [
    # South & Negev
    "אופקים", "ערד", "באר שבע", "באר-שבע", "ב\"ש",
    "דימונה", "ירוחם", "נתיבות", "רהט", "אופקים",
    "אשקלון", "אשדוד", "מצפה רמון", "מצפה-רמון",
    "קרית גת", "קרית-גת", "ק\"ג", "כרמי גת", "כרמי-גת",
    "שדרות", "אופקים", "להבים", "מיתר", "עומר",
    # Center
    "ירושלים", "מעלה אדומים", "בית שמש", "בית-שמש", "מודיעין",
    "תל אביב", "תל-אביב", "ת\"א", "תל אביב-יפו", "יפו",
    "רמת גן", "רמת-גן", "פתח תקווה", "פתח-תקווה", "פ\"ת",
    "ראשון לציון", "ראשון-לציון", "חולון", "בת ים", "בת-ים",
    "רחובות", "רעננה", "כפר סבא", "כפר-סבא", "הרצליה",
    "נתניה", "חדרה", "לוד", "רמלה", "אריאל",
    "בני ברק", "בני-ברק", "גבעתיים", "כפר יונה",
    "ראש העין", "ראש-העין", "הוד השרון", "הוד-השרון",
    # North
    "חיפה", "כרמיאל", "נצרת", "נצרת עילית", "עפולה",
    "טבריה", "צפת", "קרית שמונה", "קרית-שמונה",
    "עכו", "מעלות", "כרמיאל", "מגדל העמק", "מגדל-העמק",
    "טירת כרמל", "טירת-כרמל", "קרית מוצקין", "קרית-מוצקין",
    "קרית ים", "קרית-ים", "קרית ביאליק", "קרית-ביאליק",
    "קרית אתא", "קרית-אתא", "נשר", "יקנעם",
    "נהריה", "כרמיאל", "מעלות תרשיחא", "מעלות-תרשיחא",
    "סחנין", "טמרה", "באקה", "אום אל פחם", "אום-אל-פחם",
    # West Bank settlements
    "אריאל", "אפרת", "מעלה אדומים", "ביתר עילית",
    # "Country-wide" job postings that aren't local to Eilat
    "ברחבי הארץ", "ארצי", "כל הארץ", "מספר אזורים", "אזור עובדה",
    "כלל ארצי", "כלל-ארצי", "ברחבי ישראל",
]
_EILAT_RE = re.compile(r"אילת", re.UNICODE)


def is_in_eilat(*texts: Optional[str]) -> bool:
    """Return True if a job is plausibly in Eilat.

    Logic:
      • If any text mentions "אילת" → KEEP (True)
      • Else if any text mentions a known non-Eilat city → DROP (False)
      • Else (no city mentioned) → KEEP (True) — assume Eilat-scoped
        because the source was already filtered by city in the URL.
    """
    blob = " ".join((t or "") for t in texts)
    if not blob.strip():
        return True
    if _EILAT_RE.search(blob):
        return True
    for city in _NON_EILAT_CITIES:
        if city in blob:
            return False
    return True


def _normalize_for_fingerprint(s: str) -> str:
    """Normalize text for fuzzy matching across sources.
    - lowercase (for english parts)
    - strip punctuation
    - remove stop words (`דרוש`, `לאילת`, etc.)
    - collapse whitespace
    - collapse gender suffix patterns like "מלצר/ית" -> "מלצר".
    """
    if not s:
        return ""
    t = s.strip().lower()
    # Unify gender-duality: "מלצר/ית" or "דרוש/ה"
    t = re.sub(r"/[\u0590-\u05ff]+", "", t)
    t = _NON_HEBREW_ALPHANUM.sub(" ", t)
    t = _STOP_WORDS_RE.sub(" ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _fingerprint(title: str, company: Optional[str] = None) -> str:
    """Stable hash fingerprint used to dedupe jobs that appear on multiple
    sources. Based on normalized (title + company)."""
    key = _normalize_for_fingerprint(title) + "|" + _normalize_for_fingerprint(company or "")
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Heuristics for structured attrs (job_type, experience)
# ---------------------------------------------------------------------------
def _detect_job_type(text: str) -> Optional[str]:
    """Return one of: full_time | part_time | shifts | temporary | remote | None.
    Uses Hebrew keyword matching with multi-pattern support.
    Priority order matters: shifts > remote > part_time > temporary > full_time.
    """
    if not text:
        return None
    t = text.lower()
    # --- shifts (strong indicator for Eilat hotels/restaurants/retail)
    if any(k in text for k in [
        "משמרות", "משמרת בוקר", "משמרת ערב", "משמרת לילה",
        "משמרת", "בוקר/ערב", "ערב/לילה", "במשמרות",
    ]) or "shifts" in t:
        return "shifts"
    # --- remote
    if any(k in text for k in [
        "מהבית", "עבודה מרחוק", "work from home", "wfh",
    ]) or "remote" in t:
        return "remote"
    # --- part_time
    if any(k in text for k in [
        "משרה חלקית", "חצי משרה", "75% משרה", "60% משרה", "50% משרה",
        "פרילאנסר", "פרילנס", "עצמאי", "מספר שעות ביום",
        "חלקית (", "גם כחלקית",
    ]):
        return "part_time"
    # --- temporary / seasonal
    if any(k in text for k in [
        "נוער/ת", "נוער", "זמני", "עונתי", "פרויקט",
        "החלפה", "החלפות", "לחופשת קיץ", "לקיץ", "לחופש",
        "לתקופה מוגבלת", "לתקופה קצרה",
    ]):
        return "temporary"
    # --- full_time
    if any(k in text for k in [
        "משרה מלאה", "100% משרה", "משרה מלאה!", "משרה מלאה בלבד",
        "5/6 ימים בשבוע", "6 ימים בשבוע", "5 ימים בשבוע",
        "שעות מלאות", "ימים א׳-ה׳", "א'-ה'",
    ]) or "100%" in text:
        return "full_time"
    return None


_EXP_YEARS_RE = re.compile(r"(\d+)\s*[-–]?\s*(\d*)\s*שנ[יותא]{0,5}.{0,15}ניסיון")
_EXP_PLUS_RE = re.compile(r"ניסיון\s+של\s+(\d+)")


def _detect_experience(text: str) -> Optional[str]:
    """Return one of: none | required | None."""
    if not text:
        return None
    # No-experience flags — return early (strongest signal)
    if any(k in text for k in [
        "ללא ניסיון", "לא נדרש ניסיון", "לא דרוש ניסיון",
        "לא חובה ניסיון", "לא חייב ניסיון", "לא חובה",
        "גם ללא ניסיון", "גם לבלי ניסיון",
        "מתאים גם לחסרי ניסיון", "מתאים לסטודנטים",
        "הכשרה", "נלמד את כל הנדרש", "מלמדים מאפס",
        "קורס הכשרה",
    ]):
        return "none"
    # Required experience
    if any(k in text for k in [
        "ניסיון חובה", "ניסיון נדרש", "דרוש/ה ניסיון",
        "ניסיון קודם", "חובה ניסיון", "חובה – ניסיון",
        "עם ניסיון", "ניסיון מוכח", "ידע וניסיון",
    ]):
        return "required"
    if _EXP_YEARS_RE.search(text) or _EXP_PLUS_RE.search(text):
        return "required"
    return None


# ---------------------------------------------------------------------------
# Phone / Whatsapp helpers
# ---------------------------------------------------------------------------
def _normalize_phone(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    s = re.sub(r"[^0-9+]", "", raw)
    if not s:
        return None
    # convert 0X... to +972X...
    if s.startswith("0"):
        s = "+972" + s[1:]
    elif s.startswith("972"):
        s = "+" + s
    elif not s.startswith("+"):
        return None
    # must be reasonable length
    digits = re.sub(r"[^0-9]", "", s)
    if len(digits) < 9 or len(digits) > 15:
        return None
    return s


# ---------------------------------------------------------------------------
# Record builder
# ---------------------------------------------------------------------------
def _make_job(
    title: str,
    company: Optional[str],
    description: str,
    source_url: str,
    source: str,
    source_name: str,
    posted_at: Optional[datetime] = None,
    salary: Optional[str] = None,
    location: str = "אילת",
    phone: Optional[str] = None,
    whatsapp: Optional[str] = None,
    email: Optional[str] = None,
    job_type: Optional[str] = None,
    experience: Optional[str] = None,
    image: Optional[str] = None,
    tags: Optional[List[str]] = None,
) -> Dict[str, Any]:
    title_clean = _strip(title)[:300]
    desc_clean = _strip(description)[:3000]
    company_clean = _strip(company or "")[:200] or None
    # heuristics fill in if caller didn't provide
    if job_type is None:
        job_type = _detect_job_type(title_clean + " " + desc_clean)
    if experience is None:
        experience = _detect_experience(title_clean + " " + desc_clean)
    return {
        "id": _hash_url(source_url),
        "title": title_clean,
        "company": company_clean,
        "description": desc_clean,
        "salary": _strip(salary or "")[:120] or None,
        "location": _strip(location)[:200] or "אילת",
        "phone": _normalize_phone(phone),
        "whatsapp": _normalize_phone(whatsapp),
        "email": (email or None),
        "source": source,
        "source_name": source_name,
        "source_url": source_url,
        "posted_at": posted_at or datetime.now(timezone.utc),
        "fetched_at": datetime.now(timezone.utc),
        "job_type": job_type,
        "experience": experience,
        "image": image,
        "tags": tags or [],
        "fingerprint": _fingerprint(title_clean, company_clean),
    }
