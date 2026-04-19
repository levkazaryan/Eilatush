"""Scraper for the Eilat municipality business API (bizapi.eilat.muni.il).

Official registry of all businesses licensed by the Eilat municipality.
Returns ~1,033 businesses with 100% coverage of phone/email/address.

API endpoint (public, no auth):
    GET https://bizapi.eilat.muni.il/api/v1/biz/all
Response shape:
    {data: [{id, name, desc, addr, tel, cel, email, url, imgUrl, profession, ...}]}

Image URLs are served from https://bizapi.eilat.muni.il/<imgUrl>.

The `profession` field is populated (253 unique values) for items that are
service-providers. We use it plus a simple keyword match to decide whether
each record is a `business` (location-based, e.g. restaurant/shop) or a
`professional` (service-provider, e.g. lawyer/coach/electrician).
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

import httpx

from ..base import _fetch, _make_business, _make_professional, _strip, log

_BASE = "https://bizapi.eilat.muni.il"
_ENDPOINT = f"{_BASE}/api/v1/biz/all"


# Keyword → Hebrew patterns that strongly indicate a SERVICE PROVIDER
# rather than a location-based business. Matched case-insensitively against
# the `profession` string.
_PRO_KEYWORDS = [
    r"עו['\"״]ד", r"עורך[י]? דין", r"עורכ[תי]? דין", r"משרד עורכי דין",
    r"רו['\"״]ח", r"ראיית חשבון", r"רואה חשבון",
    r"ייעוץ", r"יעוץ", r"יועצ", r"מיצוי זכויות",
    r"אימון", r"מאמנ", r"הדרכ", r"הוראה", r"מורה", r"שיעור",
    r"טיפול", r"מטפל", r"מטפלת", r"ליווי", r"אימון עסקי", r"אימון אישי",
    r"שיפוץ", r"שיפוצי", r"קבלן",
    r"חשמלאי", r"חשמל ותשתיות",
    r"אינסטלצ",
    r"נגר", r"נגרי",
    r"הדברה",
    r"צילום", r"צלמ", r"צלמת", r"וידאו",
    r"תיווך", r"נדל[\"״״]?ן", r"נכסים", r"השכר[תה]",
    r"שיווק", r"בניית אתרי", r"דיגיטלי", r"פרסום",
    r"מעצב", r"עיצוב גרפי", r"גרפי",
    r"מנעולנ",
    r"הובל",
    r"קוסמטיק", r"ביוטי", r"מספרה", r"סטייליסט",
    r"מזגנ", r"מיזוג",
    r"עיסוי",
    r"גינון",
    r"ניקיון",
    r"נומרולוג", r"רפלקסולוג", r"נטורופת",
    r"רפואה משלימה", r"רפואה אלטרנטיב",
    r"יוגה", r"מדיטצ",
    r"תזונה", r"דיאט",
    r"הרצאה", r"הרצאות", r"סדנאות",
    r"צורפ", r"תכשיט",
    r"מורה דרך", r"הוראת נהיגה", r"בית ספר לנהיגה",
    r"הפקת אירוע", r"הפקות אירוע",
    r"אילוף",
    r"אדריכל", r"תכנון", r"עיצוב פנים", r"עיצוב ותכנון",
]
_PRO_RX = re.compile("|".join(f"(?:{k})" for k in _PRO_KEYWORDS), re.IGNORECASE)


# Override: some professions look like services but the business is actually
# a shop/restaurant. If `profession` matches these, keep it as business.
_FORCE_BIZ_KEYWORDS = [
    r"מסעדה", r"מסעד", r"חנות", r"קפה", r"פאב", r"בר ", r"מלון", r"סופר",
    r"מאפ", r"קליניקה", r"אולם", r"קונדיטוריה", r"אטליז", r"גלידה",
    r"מזון", r"סופרמרקט", r"דירות נופש",
]
_FORCE_BIZ_RX = re.compile("|".join(f"(?:{k})" for k in _FORCE_BIZ_KEYWORDS))


def _guess_type(profession: Optional[str], desc: str) -> str:
    """Return 'business' or 'professional'."""
    p = (profession or "").strip()
    if not p:
        return "business"
    if _FORCE_BIZ_RX.search(p):
        return "business"
    if _PRO_RX.search(p):
        return "professional"
    # Also peek into description for pro keywords if profession is ambiguous
    if _PRO_RX.search(desc or ""):
        return "professional"
    return "business"


def _clean_tel(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    raw = str(raw).strip()
    # Some entries have "1-700-..." which we keep as-is; normalize later
    return raw or None


def _abs_img(img_url: Optional[str]) -> Optional[str]:
    if not img_url:
        return None
    # stored paths use backslashes on server - normalize
    p = img_url.replace("\\", "/").lstrip("/")
    return f"{_BASE}/{p}"


async def scrape_eilat_muni(client: httpx.AsyncClient) -> List[Dict[str, Any]]:
    raw = await _fetch(client, _ENDPOINT)
    if not raw:
        log.warning("eilat_muni: empty response")
        return []
    import json
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        log.warning("eilat_muni: JSON parse failed: %s", e)
        return []

    items = data.get("data") or []
    log.info("eilat_muni: API returned %d items", len(items))

    records: List[Dict[str, Any]] = []
    for it in items:
        name = _strip(it.get("name") or "")
        if not name or len(name) < 2:
            continue
        desc = _strip(it.get("desc") or "")
        addr = _strip(it.get("addr") or "") or None
        phone = _clean_tel(it.get("tel") or it.get("cel"))
        cel = _clean_tel(it.get("cel"))
        whatsapp = cel or phone
        email = (it.get("email") or "").strip() or None
        website = (it.get("url") or "").strip() or None
        if website and not website.lower().startswith(("http://", "https://")):
            website = "https://" + website
        profession = (it.get("profession") or "").strip() or None
        biz_id = it.get("id")
        source_url = f"https://biz.eilat.muni.il/biz/{biz_id}"
        image = _abs_img(it.get("imgUrl"))

        record_type = _guess_type(profession, desc)

        if record_type == "professional":
            rec = _make_professional(
                name=name,
                subtitle=profession,
                description=desc,
                source_url=source_url,
                source="eilat_muni",
                source_name="עיריית אילת",
                phone=phone,
                whatsapp=whatsapp,
                email=email,
                image=image,
                category_hint=profession,
            )
        else:
            rec = _make_business(
                name=name,
                subtitle=profession,
                description=desc,
                source_url=source_url,
                source="eilat_muni",
                source_name="עיריית אילת",
                address=addr,
                phone=phone,
                whatsapp=whatsapp,
                email=email,
                website=website,
                image=image,
                category_hint=profession,
            )
        records.append(rec)

    n_pros = sum(1 for r in records if r["type"] == "professional")
    log.info(
        "eilat_muni → %d records (%d businesses + %d professionals)",
        len(records),
        len(records) - n_pros,
        n_pros,
    )
    return records
