"""Admin mode for the Eilatush AI chat.

Conversational flow:
  USER:  "תני לי סטטיסטיקה" / "סטטיסטיקה" / "דוח" / "admin"
  EILATUSH: "🔒 שלום מקסים. הזן את קוד הגישה כדי לראות נתונים."
  USER:  "evolvex"  ← password
  EILATUSH: "✅ מצב מנהל פעיל. מה תרצה לבדוק?"
  USER:  asks any free-form question about the data
  EILATUSH: answers using the latest analytics + reasons over them
  USER:  "PDF" / "תוריד דוח"
  EILATUSH: returns a PDF download link

Everything is in Hebrew. The admin session is in-memory (session_id keyed)
and expires when the chat session is reset.
"""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict, Optional

import analytics
log = logging.getLogger("admin_chat")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
ADMIN_PASSWORD = os.getenv("EILATUSH_ADMIN_PASSWORD", "evolvex").strip().lower()
SESSION_TTL_SEC = 60 * 60   # 1 hour

# Trigger phrases (case-insensitive). Any of these activates the password
# challenge (when the session is NOT yet authenticated).
TRIGGER_PHRASES = [
    "תני לי סטטיסטיקה",
    "תני סטטיסטיקה",
    "תן לי סטטיסטיקה",
    "סטטיסטיקה",
    "סטטיסטיקות",
    "נתונים",
    "דוח",
    "דו\"ח",
    "מצב מנהל",
    "admin",
    "stats",
    "report",
]

# In-memory session store (good enough for a single backend pod / MVP).
# Each entry: {state, authed_until, last_period}
_SESSIONS: Dict[str, Dict[str, Any]] = {}


# ---------------------------------------------------------------------------
# State helpers
# ---------------------------------------------------------------------------
def _now() -> float:
    return time.time()


def _is_authed(session_id: str) -> bool:
    s = _SESSIONS.get(session_id)
    if not s:
        return False
    return s.get("authed_until", 0) > _now()


def _touch_auth(session_id: str) -> None:
    s = _SESSIONS.setdefault(session_id, {})
    s["authed_until"] = _now() + SESSION_TTL_SEC


def _is_trigger(text: str) -> bool:
    t = (text or "").strip().lower()
    if not t:
        return False
    return any(p.lower() in t for p in TRIGGER_PHRASES)


def _is_password(text: str) -> bool:
    return (text or "").strip().lower() == ADMIN_PASSWORD


def _is_pdf_request(text: str) -> bool:
    t = (text or "").strip().lower()
    return any(
        kw in t
        for kw in ["pdf", "קובץ", "תוריד דוח", "תוריד דו\"ח", "הורד", "להוריד"]
    )


def _detect_period(text: str) -> str:
    t = (text or "").lower()
    if "היום" in t or "today" in t:
        return "today"
    if "שבוע" in t or "week" in t or "7" in t:
        return "7d"
    if "חודש" in t or "month" in t or "30" in t:
        return "30d"
    if "אתמול" in t:
        return "yesterday"
    if "הכל" in t or "all" in t or "תמיד" in t:
        return "all"
    if "90" in t:
        return "90d"
    return "30d"  # default


# ---------------------------------------------------------------------------
# AI reasoning over stats
# ---------------------------------------------------------------------------
ADMIN_AI_PROMPT_TPL = """אתה אילתוש - העוזרת המקומית של אילת. עכשיו אתה בתפקיד אנליסט נתונים פנימי של בעל האפליקציה.

📊 הנתונים האחרונים (תקופה: {period_label}) — JSON גולמי:
```json
{stats_json}
```

📜 הוראות:
1. ענה בעברית, חם וענייני, באמצעות המספרים המדויקים מתוך ה-JSON למעלה.
2. אם המשתמש שואל משהו שאין בנתונים - הגד "אין לי על זה מידע כרגע" — אל תמציא.
3. השתמש באימוג'ים לתצוגה ברורה (📊 👥 🏪 📰 🤖 🎉 💼).
4. אם השאלה דורשת חישוב או השוואה - חשב על בסיס הנתונים והסבר את התוצאה.
5. אם המשתמש מבקש דוח PDF - תגיד שאתה מכין ושיהיה מוכן בעוד מספר שניות.
6. תשובה ב-2-6 משפטים. אל תוסיף "אתה רוצה" או הצעות יזומות אלא אם נשאלת.
7. אם השאלה לא ברורה - בקש הבהרה.
8. אל תפלוט JSON או markdown - רק טקסט עברי נקי.

❓ שאלת המשתמש:
{user_question}
"""

PERIOD_LABELS = {
    "today":      "היום",
    "yesterday":  "אתמול",
    "7d":         "7 ימים אחרונים",
    "30d":        "30 ימים אחרונים",
    "90d":        "90 ימים אחרונים",
    "all":        "מאז הקמת האפליקציה",
}


async def _ai_answer(stats: Dict[str, Any], period: str, question: str, session_id: str) -> str:
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    api_key = os.getenv("EMERGENT_LLM_KEY", "")
    prompt = ADMIN_AI_PROMPT_TPL.format(
        period_label=PERIOD_LABELS.get(period, period),
        stats_json=json.dumps(stats, ensure_ascii=False, default=str)[:14000],
        user_question=question,
    )
    chat = LlmChat(
        api_key=api_key,
        session_id=f"admin-{session_id}",
        system_message=prompt,
    ).with_model("anthropic", "claude-sonnet-4-5-20250929")
    resp = await chat.send_message(UserMessage(text=question))
    return resp.strip()


# ---------------------------------------------------------------------------
# Public entry point — called from /api/eilatush/chat
# ---------------------------------------------------------------------------
async def handle_admin_turn(db, session_id: str, user_msg: str) -> Optional[Dict[str, Any]]:
    """Return a chat response dict if this turn is part of admin flow, else None."""
    sess = _SESSIONS.setdefault(session_id, {})
    state = sess.get("state", "idle")
    text = (user_msg or "").strip()

    # 1) Triggered: not authed AND user typed a trigger
    if not _is_authed(session_id) and state == "idle" and _is_trigger(text):
        sess["state"] = "awaiting_password"
        return {
            "reply": "🔒 שלום! לפני שאמסור נתונים — מה קוד הגישה?",
            "follow_ups": [],
            "admin_payload": {"step": "password"},
        }

    # 2) User just sent the password
    if state == "awaiting_password":
        if _is_password(text):
            _touch_auth(session_id)
            sess["state"] = "authed"
            return {
                "reply": (
                    "✅ מצב מנהל פעיל. אתה יכול לשאול אותי כל דבר על הנתונים:\n"
                    "👥 משתמשים פעילים, 📊 שימוש לפי לשונית, 🏪 עסקים פופולריים, "
                    "🎉 אירועים, 💼 משרות, 📰 חדשות, 🤖 שאלות שקיבלתי מהמשתמשים.\n\n"
                    "אפשר גם לבקש: \"תן לי סיכום של 7 ימים אחרונים\" או \"תוריד דוח PDF\""
                ),
                "follow_ups": [
                    "סיכום 30 ימים אחרונים",
                    "10 העסקים הפופולריים ביותר",
                    "מה השאלות הכי נפוצות?",
                    "תוריד דוח PDF",
                ],
                "admin_payload": {"step": "authed"},
            }
        # Wrong password — silently exit admin flow (security)
        sess["state"] = "idle"
        return None  # let regular chat handle this

    # 3) Already authed → handle admin queries
    if _is_authed(session_id):
        # PDF request short-circuit
        if _is_pdf_request(text):
            period = _detect_period(text) or sess.get("last_period") or "30d"
            return {
                "reply": (
                    f"📄 מכין דו״ח PDF לתקופה: {PERIOD_LABELS.get(period, period)}.\n"
                    f"🔗 קישור הורדה: /api/admin/report.pdf?period={period}&token={ADMIN_PASSWORD}\n"
                    "(לחץ על הקישור או העתק לדפדפן)"
                ),
                "follow_ups": [
                    "סיכום 7 ימים",
                    "עסקים פופולריים",
                    "מה השאלות הכי נפוצות?",
                ],
                "admin_payload": {
                    "step": "pdf",
                    "pdf_url": f"/api/admin/report.pdf?period={period}&token={ADMIN_PASSWORD}",
                    "period": period,
                },
            }

        # Otherwise: fetch latest stats + ask AI to reason
        period = _detect_period(text)
        sess["last_period"] = period
        stats = await analytics.full_report(db, period=period)
        reply = await _ai_answer(stats, period, text, session_id)
        return {
            "reply": reply,
            "follow_ups": [
                "תוריד דוח PDF",
                "סיכום 7 ימים אחרונים",
                "10 העסקים הפופולריים",
                "מה השאלות הכי נפוצות?",
            ],
            "admin_payload": {"step": "stats", "period": period},
        }

    return None
