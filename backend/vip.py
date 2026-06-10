"""
תושב אילת VIP — Members + Discounts module.

Provides:
- /api/vip/register   (full_name, email, phone, dob, address)  → JWT
- /api/vip/login      (phone, dob)                              → JWT
- /api/vip/me         (Authorization: Bearer <jwt>)             → member info
- /api/vip/discounts  (Authorization)                           → list of active discounts

Auth model: phone + DOB. We hash a derived "auth secret" (phone|dob) with bcrypt.
No password. No OTP. JWT issued on register/login, stored client-side.
"""

import os
import re
import time
import bcrypt
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional, Dict, Any, Tuple

from fastapi import APIRouter, HTTPException, Header, status, Request
from jose import JWTError, jwt
from pydantic import BaseModel, EmailStr, Field, field_validator
import uuid


# ============================================================
# Config (lazy-read at use time; env loaded by server.py)
# ============================================================
def _get_jwt_secret() -> str:
    sec = os.environ.get("JWT_SECRET")
    if not sec:
        raise RuntimeError("JWT_SECRET is not set in environment")
    return sec


def _get_jwt_algorithm() -> str:
    return os.environ.get("JWT_ALGORITHM", "HS256")


def _get_access_token_exp_days() -> int:
    try:
        return int(os.environ.get("ACCESS_TOKEN_EXP_DAYS", "30"))
    except Exception:
        return 30


# Months of free membership for everyone
FREE_MEMBERSHIP_MONTHS = 6


# ============================================================
# Phone normalization (Israeli numbers)
# ============================================================
def normalize_il_phone(raw: str) -> str:
    """
    Convert any Israeli phone format to E.164 (+972XXXXXXXXX).
    Accepts: 0521234567, 052-123-4567, +972-52-123-4567, 972521234567, etc.
    """
    if not raw:
        raise ValueError("phone is required")
    # Strip everything except digits and leading +
    s = re.sub(r"[^\d+]", "", raw.strip())
    if s.startswith("+972"):
        rest = s[4:]
    elif s.startswith("972"):
        rest = s[3:]
    elif s.startswith("00972"):
        rest = s[5:]
    elif s.startswith("0"):
        rest = s[1:]
    else:
        rest = s
    rest = rest.lstrip("0")
    # Israeli mobile/landline numbers (without leading 0): 8 or 9 digits.
    if not rest.isdigit() or not (8 <= len(rest) <= 10):
        raise ValueError("invalid Israeli phone number")
    return "+972" + rest


# ============================================================
# Pydantic models
# ============================================================
class RegisterRequest(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=120)
    email: EmailStr
    phone: str
    dob: date  # YYYY-MM-DD
    address: str = Field(..., min_length=2, max_length=300)

    @field_validator("phone")
    @classmethod
    def _norm_phone(cls, v: str) -> str:
        try:
            return normalize_il_phone(v)
        except ValueError as e:
            raise ValueError(str(e))

    @field_validator("dob")
    @classmethod
    def _check_dob(cls, v: date) -> date:
        # Reject DOBs in the future or > 120 years ago
        today = date.today()
        if v >= today:
            raise ValueError("dob must be in the past")
        if (today.year - v.year) > 120:
            raise ValueError("dob is too old")
        return v


class LoginRequest(BaseModel):
    phone: str
    dob: date

    @field_validator("phone")
    @classmethod
    def _norm_phone(cls, v: str) -> str:
        try:
            return normalize_il_phone(v)
        except ValueError as e:
            raise ValueError(str(e))


class MemberOut(BaseModel):
    id: str
    full_name: str
    email: str
    phone: str
    dob: str  # ISO
    address: str
    member_number: str
    join_date: str  # ISO date
    expiry_date: str  # ISO date
    is_active: bool = True
    is_admin: bool = False
    last_login: Optional[str] = None  # ISO datetime
    created_at: Optional[str] = None  # ISO datetime


class AuthResponse(BaseModel):
    token: str
    member: MemberOut


class Discount(BaseModel):
    id: str
    place: str  # "אייסמול"
    business_name: str  # "bool" / "Joy Mobile"
    gift_text: str
    age_restriction: Optional[str] = "18+"
    category: Optional[str] = None
    image_url: Optional[str] = None
    order: int = 0
    active: bool = True


# ============================================================
# Auth helpers
# ============================================================
def _make_auth_secret(phone_e164: str, dob: date) -> bytes:
    raw = f"{phone_e164}|{dob.isoformat()}"
    return raw.encode("utf-8")


def _hash_secret(secret_bytes: bytes) -> str:
    salt = bcrypt.gensalt(rounds=10)
    return bcrypt.hashpw(secret_bytes, salt).decode("utf-8")


def _verify_secret(secret_bytes: bytes, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(secret_bytes, hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# Dummy hash used to equalize timing for non-existent users
_DUMMY_HASH = _hash_secret(b"dummy-not-a-user-please")


def _create_token(member_id: str) -> str:
    now = datetime.now(timezone.utc)
    exp = now + timedelta(days=_get_access_token_exp_days())
    payload = {
        "sub": member_id,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "type": "access",
    }
    return jwt.encode(payload, _get_jwt_secret(), algorithm=_get_jwt_algorithm())


def _decode_token(token: str) -> str:
    """Returns member_id on success; raises HTTPException on failure."""
    try:
        payload = jwt.decode(token, _get_jwt_secret(), algorithms=[_get_jwt_algorithm()])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    return sub


def _extract_bearer(authorization: Optional[str]) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    return authorization[len("Bearer "):].strip()


# ============================================================
# Helpers
# ============================================================
def _doc_to_member_out(doc: Dict[str, Any]) -> MemberOut:
    def _iso_datetime(v: Any) -> Optional[str]:
        if v is None:
            return None
        if isinstance(v, datetime):
            return v.replace(tzinfo=v.tzinfo or timezone.utc).isoformat()
        return str(v)

    return MemberOut(
        id=doc["id"],
        full_name=doc["full_name"],
        email=doc["email"],
        phone=doc["phone"],
        dob=doc["dob"].isoformat() if isinstance(doc["dob"], date) and not isinstance(doc["dob"], datetime) else (
            doc["dob"].date().isoformat() if isinstance(doc["dob"], datetime) else str(doc["dob"])
        ),
        address=doc["address"],
        member_number=doc["member_number"],
        join_date=doc["join_date"].date().isoformat() if isinstance(doc["join_date"], datetime) else str(doc["join_date"]),
        expiry_date=doc["expiry_date"].date().isoformat() if isinstance(doc["expiry_date"], datetime) else str(doc["expiry_date"]),
        is_active=bool(doc.get("is_active", True)),
        is_admin=bool(doc.get("is_admin", False)),
        last_login=_iso_datetime(doc.get("last_login")),
        created_at=_iso_datetime(doc.get("created_at")),
    )


def _format_member_number(seq: int) -> str:
    year = datetime.now(timezone.utc).year
    return f"VIP-{year}-{seq:04d}"


# ============================================================
# Simple per-IP rate limiter for login
# ============================================================
_LOGIN_ATTEMPTS: Dict[str, List[float]] = defaultdict(list)
_LOGIN_WINDOW_SEC = 60
_LOGIN_MAX_PER_WINDOW = 8


def _check_rate_limit(ip: str) -> None:
    now = time.time()
    attempts = [t for t in _LOGIN_ATTEMPTS[ip] if now - t < _LOGIN_WINDOW_SEC]
    if len(attempts) >= _LOGIN_MAX_PER_WINDOW:
        raise HTTPException(
            status_code=429,
            detail="יותר מדי ניסיונות התחברות. נסו שוב בעוד דקה.",
        )
    attempts.append(now)
    _LOGIN_ATTEMPTS[ip] = attempts


# ============================================================
# Discount seed (8 Ice Mall gifts)
# ============================================================
ICEMALL_DISCOUNTS_SEED = [
    {
        "id": "icemall-bool-spa",
        "place": "אייסמול",
        "business_name": "bool",
        "gift_text": "ספא דגים 10 דקות בחינם",
        "age_restriction": "18+",
        "category": "ספא ויופי",
        "image_url": "https://customer-assets.emergentagent.com/job_eilat-connect/artifacts/ys9kkal4_IMG_20260610_214048.jpg",
        "order": 1,
    },
    {
        "id": "icemall-bool-foot",
        "place": "אייסמול",
        "business_name": "bool",
        "gift_text": "עיסוי רגליים מפנק בחינם",
        "age_restriction": "18+",
        "category": "ספא ויופי",
        "image_url": "https://customer-assets.emergentagent.com/job_eilat-connect/artifacts/mfc5uc9q_IMG_20260610_214106.jpg",
        "order": 2,
    },
    {
        "id": "icemall-joy-mobile",
        "place": "אייסמול",
        "business_name": "Joy Mobile",
        "gift_text": "מגנט ממותג לרכב בחינם",
        "age_restriction": "18+",
        "category": "אקססוריז",
        "image_url": "https://customer-assets.emergentagent.com/job_eilat-connect/artifacts/oje9h6wn_IMG_20260610_214135.jpg",
        "order": 3,
    },
    {
        "id": "icemall-royalty",
        "place": "אייסמול",
        "business_name": "Royalty",
        "gift_text": "ניקוי וחידוש תכשיט יוקרה בחינם",
        "age_restriction": "18+",
        "category": "תכשיטים",
        "image_url": "https://customer-assets.emergentagent.com/job_eilat-connect/artifacts/5u5i00u6_IMG_20260610_214156.jpg",
        "order": 4,
    },
    {
        "id": "icemall-orea",
        "place": "אייסמול",
        "business_name": "Orea",
        "gift_text": "עץ ריח בחינם",
        "age_restriction": "18+",
        "category": "אקססוריז",
        "image_url": "https://customer-assets.emergentagent.com/job_eilat-connect/artifacts/puck3cry_pr_5.jpg",
        "order": 5,
    },
    {
        "id": "icemall-cafe-wifi",
        "place": "אייסמול",
        "business_name": "Cafe Wifi",
        "gift_text": "כוס לימונדה בגודל מיוחד בחינם",
        "age_restriction": "18+",
        "category": "בית קפה",
        "image_url": "https://customer-assets.emergentagent.com/job_eilat-connect/artifacts/g9h6tbqh_pr_6.jpg",
        "order": 6,
    },
    {
        "id": "icemall-us-crispy",
        "place": "אייסמול",
        "business_name": "US Crispy Chicken",
        "gift_text": "4 כנפי עוף בחינם",
        "age_restriction": "18+",
        "category": "מסעדה",
        "image_url": "https://customer-assets.emergentagent.com/job_eilat-connect/artifacts/fo00sw88_pr_7.jpg",
        "order": 7,
    },
    {
        "id": "icemall-opatra",
        "place": "אייסמול",
        "business_name": "OPATRA London",
        "gift_text": "טיפול עיניים ודוגמית קרם פנים בחינם",
        "age_restriction": "18+",
        "category": "קוסמטיקה",
        "image_url": "https://customer-assets.emergentagent.com/job_eilat-connect/artifacts/n3a2t2hn_pr_8.jpg",
        "order": 8,
    },
]


# ============================================================
# DB lifecycle (called from server.py startup)
# ============================================================
async def init_vip_collections(db) -> None:
    """Create indexes & seed initial discounts. Idempotent."""
    # Unique index on phone
    try:
        await db.vip_members.create_index("phone", unique=True, name="uniq_phone")
    except Exception:
        pass
    try:
        await db.vip_members.create_index("member_number", unique=True, name="uniq_member_number")
    except Exception:
        pass
    try:
        await db.vip_discounts.create_index("id", unique=True, name="uniq_disc_id")
    except Exception:
        pass

    # Seed discounts (upsert: keep manual edits to image_url etc., but ensure they exist)
    for d in ICEMALL_DISCOUNTS_SEED:
        doc = {**d, "active": True}
        await db.vip_discounts.update_one(
            {"id": d["id"]},
            {"$setOnInsert": doc},
            upsert=True,
        )

    # Seed the default admin (idempotent)
    await _seed_admin_member(db)


async def _seed_admin_member(db) -> None:
    """Create the initial admin member if missing; idempotent. Also re-flags as admin if exists."""
    ADMIN_FULL_NAME = "לב קזריאן"
    ADMIN_EMAIL = "email@levkazaryan.com"
    ADMIN_PHONE_RAW = "0535319943"
    ADMIN_DOB = date(1994, 5, 27)
    ADMIN_ADDRESS = "החשמונאים 9, דירה 18, אילת"

    try:
        phone_e164 = normalize_il_phone(ADMIN_PHONE_RAW)
    except Exception:
        return

    existing = await db.vip_members.find_one({"phone": phone_e164})
    if existing:
        # Make sure this account is flagged as admin
        if not existing.get("is_admin"):
            await db.vip_members.update_one(
                {"id": existing["id"]},
                {"$set": {"is_admin": True}},
            )
        return

    # Create from scratch
    member_number = await _next_member_number(db)
    now = datetime.now(timezone.utc)
    dob_dt = datetime(ADMIN_DOB.year, ADMIN_DOB.month, ADMIN_DOB.day, tzinfo=timezone.utc)
    expiry = now + timedelta(days=FREE_MEMBERSHIP_MONTHS * 30)
    secret = _make_auth_secret(phone_e164, ADMIN_DOB)
    auth_hash = _hash_secret(secret)

    doc = {
        "id": str(uuid.uuid4()),
        "full_name": ADMIN_FULL_NAME,
        "email": ADMIN_EMAIL.lower(),
        "phone": phone_e164,
        "dob": dob_dt,
        "address": ADMIN_ADDRESS,
        "member_number": member_number,
        "join_date": now,
        "expiry_date": expiry,
        "auth_secret_hash": auth_hash,
        "is_active": True,
        "is_admin": True,
        "created_at": now,
    }
    try:
        await db.vip_members.insert_one(doc)
    except Exception:
        # Race with another worker — ignore
        pass


async def _next_member_number(db) -> str:
    """Reserve & return the next member number atomically."""
    # Use a tiny counters collection
    counter = await db.counters.find_one_and_update(
        {"_id": "vip_members"},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=True,  # motor: ReturnDocument.AFTER
    )
    # Motor uses pymongo.ReturnDocument; passing True works as AFTER on most versions,
    # but safer to handle both — fall back to find.
    seq = None
    if counter and isinstance(counter, dict):
        seq = counter.get("seq")
    if seq is None:
        c2 = await db.counters.find_one({"_id": "vip_members"})
        seq = (c2 or {}).get("seq", 1)
    return _format_member_number(int(seq))


# ============================================================
# Router factory
# ============================================================
def build_vip_router(db) -> APIRouter:
    router = APIRouter(prefix="/vip", tags=["vip"])

    async def _get_current_member(authorization: Optional[str]) -> Dict[str, Any]:
        token = _extract_bearer(authorization)
        member_id = _decode_token(token)
        doc = await db.vip_members.find_one({"id": member_id})
        if not doc:
            raise HTTPException(status_code=401, detail="Member not found")
        # Drop Mongo's internal ObjectId before returning to callers
        doc.pop("_id", None)
        return doc

    # ---------- REGISTER ----------
    @router.post("/register", response_model=AuthResponse, status_code=201)
    async def register(req: RegisterRequest, request: Request):
        # Reject duplicate phone
        existing = await db.vip_members.find_one({"phone": req.phone})
        if existing:
            raise HTTPException(
                status_code=400,
                detail="מספר טלפון זה כבר רשום. אפשר להיכנס מהמסך הקודם.",
            )

        # Allocate member number
        member_number = await _next_member_number(db)

        now = datetime.now(timezone.utc)
        # DOB stored as datetime midnight UTC (Mongo doesn't have a pure date type)
        dob_dt = datetime(req.dob.year, req.dob.month, req.dob.day, tzinfo=timezone.utc)
        expiry = now + timedelta(days=FREE_MEMBERSHIP_MONTHS * 30)

        secret = _make_auth_secret(req.phone, req.dob)
        auth_hash = _hash_secret(secret)

        member_id = str(uuid.uuid4())
        doc = {
            "id": member_id,
            "full_name": req.full_name.strip(),
            "email": req.email.lower().strip(),
            "phone": req.phone,
            "dob": dob_dt,
            "address": req.address.strip(),
            "member_number": member_number,
            "join_date": now,
            "expiry_date": expiry,
            "auth_secret_hash": auth_hash,
            "is_active": True,
            "created_at": now,
        }

        try:
            await db.vip_members.insert_one(doc)
        except Exception as e:
            # likely DuplicateKeyError race
            existing = await db.vip_members.find_one({"phone": req.phone})
            if existing:
                raise HTTPException(status_code=400, detail="מספר טלפון זה כבר רשום.")
            raise HTTPException(status_code=500, detail=f"Failed to register: {e}")

        token = _create_token(member_id)
        return AuthResponse(token=token, member=_doc_to_member_out(doc))

    # ---------- LOGIN ----------
    @router.post("/login", response_model=AuthResponse)
    async def login(req: LoginRequest, request: Request):
        # Rate-limit per IP
        ip = (request.client.host if request.client else "unknown") or "unknown"
        _check_rate_limit(ip)

        secret = _make_auth_secret(req.phone, req.dob)
        doc = await db.vip_members.find_one({"phone": req.phone})

        if doc is None:
            # equalize timing
            _verify_secret(secret, _DUMMY_HASH)
            raise HTTPException(status_code=401, detail="טלפון או תאריך לידה שגויים")

        if not _verify_secret(secret, doc.get("auth_secret_hash", "")):
            raise HTTPException(status_code=401, detail="טלפון או תאריך לידה שגויים")

        if not doc.get("is_active", True):
            raise HTTPException(status_code=403, detail="חשבון לא פעיל")

        # update last_login (best-effort, non-blocking on error)
        try:
            await db.vip_members.update_one(
                {"id": doc["id"]},
                {"$set": {"last_login": datetime.now(timezone.utc)}},
            )
            doc["last_login"] = datetime.now(timezone.utc)
        except Exception:
            pass

        token = _create_token(doc["id"])
        return AuthResponse(token=token, member=_doc_to_member_out(doc))

    # ---------- ME ----------
    @router.get("/me", response_model=MemberOut)
    async def me(authorization: Optional[str] = Header(default=None)):
        doc = await _get_current_member(authorization)
        return _doc_to_member_out(doc)

    # ---------- DISCOUNTS ----------
    @router.get("/discounts", response_model=List[Discount])
    async def discounts(authorization: Optional[str] = Header(default=None)):
        # Require auth
        await _get_current_member(authorization)
        cursor = db.vip_discounts.find({"active": True}).sort("order", 1)
        out: List[Discount] = []
        async for d in cursor:
            out.append(
                Discount(
                    id=d["id"],
                    place=d.get("place", ""),
                    business_name=d.get("business_name", ""),
                    gift_text=d.get("gift_text", ""),
                    age_restriction=d.get("age_restriction"),
                    category=d.get("category"),
                    image_url=d.get("image_url"),
                    order=int(d.get("order", 0)),
                    active=bool(d.get("active", True)),
                )
            )
        return out

    # ---------- PUBLIC TEASER COUNT ----------
    @router.get("/teaser")
    async def teaser():
        """Public endpoint — number of available discounts for landing copy."""
        cnt = await db.vip_discounts.count_documents({"active": True})
        return {"discount_count": cnt}

    # ============================================================
    # ADMIN ENDPOINTS
    # ============================================================
    async def _require_admin(authorization: Optional[str]) -> Dict[str, Any]:
        doc = await _get_current_member(authorization)
        if not doc.get("is_admin"):
            raise HTTPException(status_code=403, detail="הרשאות מנהל נדרשות")
        return doc

    # ---------- ADMIN: LIST MEMBERS ----------
    @router.get("/admin/members")
    async def admin_list_members(
        authorization: Optional[str] = Header(default=None),
        q: Optional[str] = None,
        status: Optional[str] = "all",  # all | active | inactive
        limit: int = 200,
        skip: int = 0,
    ):
        await _require_admin(authorization)

        filt: Dict[str, Any] = {}
        if status == "active":
            filt["is_active"] = True
        elif status == "inactive":
            filt["is_active"] = False

        if q and q.strip():
            term = q.strip()
            # Try to normalize a phone search; fall back to raw
            phone_norm = None
            try:
                phone_norm = normalize_il_phone(term)
            except Exception:
                phone_norm = None

            or_conditions: List[Dict[str, Any]] = [
                {"full_name": {"$regex": re.escape(term), "$options": "i"}},
                {"email": {"$regex": re.escape(term), "$options": "i"}},
                {"member_number": {"$regex": re.escape(term), "$options": "i"}},
            ]
            if phone_norm:
                or_conditions.append({"phone": phone_norm})
            else:
                # Allow partial phone match (e.g. last 4 digits)
                digits_only = re.sub(r"\D", "", term)
                if digits_only:
                    or_conditions.append({"phone": {"$regex": re.escape(digits_only), "$options": "i"}})
            filt["$or"] = or_conditions

        total = await db.vip_members.count_documents(filt)
        cursor = (
            db.vip_members.find(filt)
            .sort("created_at", -1)
            .skip(max(0, skip))
            .limit(min(max(1, limit), 500))
        )
        items: List[MemberOut] = []
        async for d in cursor:
            d.pop("_id", None)
            items.append(_doc_to_member_out(d))
        return {"total": total, "items": [i.model_dump() for i in items]}

    # ---------- ADMIN: STATS ----------
    @router.get("/admin/stats")
    async def admin_stats(authorization: Optional[str] = Header(default=None)):
        await _require_admin(authorization)
        total = await db.vip_members.count_documents({})
        active = await db.vip_members.count_documents({"is_active": True})
        inactive = await db.vip_members.count_documents({"is_active": False})
        week_ago = datetime.now(timezone.utc) - timedelta(days=7)
        this_week = await db.vip_members.count_documents({"created_at": {"$gte": week_ago}})
        return {
            "total": total,
            "active": active,
            "inactive": inactive,
            "new_this_week": this_week,
        }

    # ---------- ADMIN: TOGGLE ACTIVE ----------
    @router.post("/admin/members/{member_id}/toggle-active")
    async def admin_toggle_active(
        member_id: str,
        authorization: Optional[str] = Header(default=None),
    ):
        admin_doc = await _require_admin(authorization)
        if member_id == admin_doc.get("id"):
            raise HTTPException(status_code=400, detail="אי אפשר להשבית את חשבון המנהל שלך")
        target = await db.vip_members.find_one({"id": member_id})
        if not target:
            raise HTTPException(status_code=404, detail="חבר לא נמצא")
        new_active = not bool(target.get("is_active", True))
        await db.vip_members.update_one(
            {"id": member_id},
            {"$set": {"is_active": new_active}},
        )
        updated = await db.vip_members.find_one({"id": member_id})
        updated.pop("_id", None)
        return {"member": _doc_to_member_out(updated).model_dump()}

    return router
