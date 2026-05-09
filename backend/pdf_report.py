"""Branded Hebrew RTL PDF generator for Eilatush admin reports.

Uses ReportLab + arabic-reshaper + python-bidi for proper Hebrew shaping.
"""
from __future__ import annotations

import io
import logging
import os
from datetime import datetime
from typing import Any, Dict, List

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
)
from reportlab.lib.enums import TA_RIGHT, TA_CENTER
from arabic_reshaper import reshape
from bidi.algorithm import get_display

log = logging.getLogger("pdf_report")

# ---------------------------------------------------------------------------
# Hebrew font registration
# ---------------------------------------------------------------------------
# DejaVuSans ships with most Linux distros AND has full Hebrew glyphs.
# Fallback to Helvetica if not found (Hebrew chars then render as boxes).
_FONT_NAME = "DejaVuSans"
_FONT_REGISTERED = False


def _ensure_fonts() -> str:
    global _FONT_REGISTERED
    if _FONT_REGISTERED:
        return _FONT_NAME
    # Local bundled font (highest priority — works in any deploy env)
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(here, "fonts", "DejaVuSans.ttf"),
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/TTF/DejaVuSans.ttf",
    ]
    bold_candidates = [
        os.path.join(here, "fonts", "DejaVuSans-Bold.ttf"),
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
    ]
    try:
        from reportlab.pdfbase.pdfmetrics import registerFontFamily
        for path in candidates:
            try:
                pdfmetrics.registerFont(TTFont(_FONT_NAME, path))
                break
            except Exception:
                continue
        for path in bold_candidates:
            try:
                pdfmetrics.registerFont(TTFont(_FONT_NAME + "-Bold", path))
                break
            except Exception:
                continue
        # Map family so reportlab can resolve <b> tags & bold styles
        registerFontFamily(
            _FONT_NAME,
            normal=_FONT_NAME,
            bold=_FONT_NAME + "-Bold",
            italic=_FONT_NAME,
            boldItalic=_FONT_NAME + "-Bold",
        )
        _FONT_REGISTERED = True
    except Exception as e:
        log.warning("font registration failed: %s — using Helvetica", e)
    return _FONT_NAME


def _heb(text: str) -> str:
    """Reshape + bidi-reorder Hebrew/Arabic text for proper RTL display."""
    if not text:
        return ""
    try:
        return get_display(reshape(str(text)))
    except Exception:
        return str(text)


# ---------------------------------------------------------------------------
# PDF building
# ---------------------------------------------------------------------------
EILATUSH_TEAL = colors.HexColor("#0D9488")
EILATUSH_DARK = colors.HexColor("#0F172A")
EILATUSH_LIGHT = colors.HexColor("#F1F5F9")


def _make_styles(font: str):
    base = getSampleStyleSheet()
    title = ParagraphStyle(
        "Title", parent=base["Title"], fontName=font + "-Bold",
        fontSize=22, alignment=TA_CENTER, textColor=EILATUSH_TEAL,
        spaceAfter=12,
    )
    h2 = ParagraphStyle(
        "H2", parent=base["Heading2"], fontName=font + "-Bold",
        fontSize=15, alignment=TA_RIGHT, textColor=EILATUSH_DARK,
        spaceBefore=14, spaceAfter=8,
    )
    body = ParagraphStyle(
        "Body", parent=base["BodyText"], fontName=font,
        fontSize=11, alignment=TA_RIGHT, leading=16,
    )
    small = ParagraphStyle(
        "Small", parent=base["BodyText"], fontName=font,
        fontSize=9, alignment=TA_CENTER, textColor=colors.grey,
    )
    return title, h2, body, small


def _table_from_rows(rows: List[List[str]], font: str, header: bool = True):
    """Make a styled table. Rows are pre-bidi-reshaped Hebrew strings."""
    t = Table(rows, hAlign="RIGHT", repeatRows=1 if header else 0)
    style = TableStyle([
        ("FONT", (0, 0), (-1, -1), font, 10),
        ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW", (0, 0), (-1, 0), 1.5, EILATUSH_TEAL),
        ("BACKGROUND", (0, 0), (-1, 0), EILATUSH_LIGHT),
        ("TEXTCOLOR", (0, 0), (-1, 0), EILATUSH_DARK),
        ("FONTNAME", (0, 0), (-1, 0), font + "-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#FAFAFA")]),
    ])
    t.setStyle(style)
    return t


def generate_report_pdf(report: Dict[str, Any], period_label: str = "30 ימים אחרונים") -> bytes:
    """Return PDF bytes for a full analytics report."""
    font = _ensure_fonts()
    title_st, h2_st, body_st, small_st = _make_styles(font)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        topMargin=1.5 * cm, bottomMargin=1.5 * cm,
        leftMargin=1.5 * cm, rightMargin=1.5 * cm,
        title="Eilatush Analytics Report",
    )

    story: List[Any] = []

    # --- Cover header -----------------------------------------------------
    story.append(Paragraph(_heb("🐠 דוח אילתוש"), title_st))
    story.append(Paragraph(_heb(f"תקופה: {period_label}"), small_st))
    story.append(Paragraph(
        _heb(f"הופק ב: {datetime.now().strftime('%d/%m/%Y %H:%M')}"), small_st
    ))
    story.append(Spacer(1, 12))

    # --- Section: Users ---------------------------------------------------
    u = report.get("users") or {}
    story.append(Paragraph(_heb("👥 נתוני משתמשים"), h2_st))
    rows = [
        [_heb("ערך"), _heb("מדד")],
        [str(u.get("dau", 0)), _heb("משתמשים פעילים היום (DAU)")],
        [str(u.get("mau", 0)), _heb("משתמשים פעילים בחודש (MAU)")],
        [f"{u.get('stickiness_dau_mau_pct', 0)}%", _heb("דביקות (DAU/MAU)")],
        [str(u.get("active_users_in_period", 0)), _heb("משתמשים פעילים בתקופה")],
        [str(u.get("new_users_in_period", 0)), _heb("משתמשים חדשים בתקופה")],
        [str(u.get("sessions_in_period", 0)), _heb("מספר סשנים")],
        [str(u.get("events_per_user", 0)), _heb("אירועים ממוצעים למשתמש")],
    ]
    story.append(_table_from_rows(rows, font))

    # --- Section: Engagement ---------------------------------------------
    eng = (report.get("engagement") or {}).get("screens") or []
    story.append(Paragraph(_heb("📊 שימוש לפי לשונית"), h2_st))
    if eng:
        rows = [[_heb("אחוז"), _heb("משתמשים יחודיים"), _heb("צפיות"), _heb("לשונית")]]
        for s in eng:
            rows.append([
                f"{s.get('share_pct', 0)}%",
                str(s.get("unique_users", 0)),
                str(s.get("views", 0)),
                _heb(s.get("screen") or "?"),
            ])
        story.append(_table_from_rows(rows, font))
    else:
        story.append(Paragraph(_heb("אין נתונים בתקופה זו."), body_st))

    # --- Section: Top Businesses -----------------------------------------
    biz = (report.get("businesses") or {}).get("businesses") or []
    story.append(PageBreak())
    story.append(Paragraph(_heb("🏪 עסקים פופולריים"), h2_st))
    if biz:
        rows = [[
            _heb("הוראות"), _heb("שיחות"), _heb("צפיות"), _heb("שם העסק"),
        ]]
        for b in biz[:15]:
            rows.append([
                str(b.get("directions", 0)),
                str(b.get("phone_clicks", 0)),
                str(b.get("views", 0)),
                _heb((b.get("name") or "?")[:40]),
            ])
        story.append(_table_from_rows(rows, font))
    else:
        story.append(Paragraph(_heb("אין נתונים."), body_st))

    # --- Section: Top Events ---------------------------------------------
    evs = (report.get("events") or {}).get("events") or []
    story.append(Paragraph(_heb("🎉 אירועים פופולריים"), h2_st))
    if evs:
        rows = [[_heb("יציאה למקור"), _heb("צפיות"), _heb("מקום"), _heb("אירוע")]]
        for e in evs[:10]:
            rows.append([
                str(e.get("outbound_clicks", 0)),
                str(e.get("views", 0)),
                _heb((e.get("venue") or "")[:25]),
                _heb((e.get("title") or "?")[:35]),
            ])
        story.append(_table_from_rows(rows, font))
    else:
        story.append(Paragraph(_heb("אין נתונים."), body_st))

    # --- Section: Top Jobs -----------------------------------------------
    jbs = (report.get("jobs") or {}).get("jobs") or []
    story.append(Paragraph(_heb("💼 משרות פופולריות"), h2_st))
    if jbs:
        rows = [[_heb("יציאה למקור"), _heb("צפיות"), _heb("חברה"), _heb("משרה")]]
        for j in jbs[:10]:
            rows.append([
                str(j.get("outbound_clicks", 0)),
                str(j.get("views", 0)),
                _heb((j.get("company") or "")[:25]),
                _heb((j.get("title") or "?")[:35]),
            ])
        story.append(_table_from_rows(rows, font))
    else:
        story.append(Paragraph(_heb("אין נתונים."), body_st))

    # --- Section: News ---------------------------------------------------
    news = (report.get("news") or {}).get("articles") or []
    story.append(PageBreak())
    story.append(Paragraph(_heb("📰 כתבות פופולריות"), h2_st))
    if news:
        rows = [[_heb("פתיחת מקור"), _heb("צפיות"), _heb("מקור"), _heb("כותרת")]]
        for a in news[:10]:
            rows.append([
                str(a.get("outbound_clicks", 0)),
                str(a.get("views", 0)),
                _heb((a.get("source") or "")[:20]),
                _heb((a.get("title") or "?")[:40]),
            ])
        story.append(_table_from_rows(rows, font))
    else:
        story.append(Paragraph(_heb("אין נתונים."), body_st))

    # --- Section: AI Questions -------------------------------------------
    qs = (report.get("ai_questions") or {}).get("questions") or []
    story.append(Paragraph(_heb("🤖 שאלות נפוצות לאילתוש"), h2_st))
    if qs:
        rows = [[_heb("פעמים"), _heb("שאלה")]]
        for q in qs[:20]:
            rows.append([str(q.get("count", 0)), _heb((q.get("text") or "")[:80])])
        story.append(_table_from_rows(rows, font))
    else:
        story.append(Paragraph(_heb("אין נתונים."), body_st))

    # --- Footer ----------------------------------------------------------
    story.append(Spacer(1, 18))
    story.append(Paragraph(
        _heb("🐠 Eilatush · דוח פנימי · אין להעביר"), small_st,
    ))

    doc.build(story)
    return buf.getvalue()
