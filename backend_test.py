"""
Backend tests for the Businesses & Professionals endpoints in the Eilatush app.

Tests these endpoints:
  GET /api/businesses (with filters)
  GET /api/businesses/categories
  GET /api/businesses/sources
  GET /api/businesses/status
  GET /api/businesses/{id}
  Sanity check: /api/news, /api/jobs, /api/events

Base URL is read from frontend/.env EXPO_PUBLIC_BACKEND_URL. All routes are
prefixed with /api (Kubernetes ingress rule). We do NOT hit /businesses/refresh
because it runs OCR and takes 3-4 minutes.
"""

from __future__ import annotations
import os
import re
import sys
import json
from typing import Any, Dict, List

import requests

# --- Resolve base URL from frontend/.env ------------------------------------
def _resolve_base_url() -> str:
    env_path = "/app/frontend/.env"
    url = None
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("EXPO_PUBLIC_BACKEND_URL="):
                    url = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    except FileNotFoundError:
        pass
    if not url:
        url = os.environ.get("EXPO_PUBLIC_BACKEND_URL") or os.environ.get("REACT_APP_BACKEND_URL")
    if not url:
        url = "http://localhost:8001"
    return url.rstrip("/")

BASE = _resolve_base_url()
API = f"{BASE}/api"

print(f"\n[backend_test] BASE URL = {BASE}\n")

HEBREW_RE = re.compile(r"[\u0590-\u05FF]")

results: List[Dict[str, Any]] = []
failures: List[str] = []

def record(name: str, ok: bool, detail: str = ""):
    results.append({"name": name, "ok": ok, "detail": detail})
    status = "PASS" if ok else "FAIL"
    print(f"  [{status}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        failures.append(f"{name}: {detail}")

def get(path: str, **params):
    url = f"{API}{path}"
    r = requests.get(url, params=params or None, timeout=60)
    return r

# ------------------------------------------------------------------
# 1. GET /api/businesses (filters)
# ------------------------------------------------------------------

def test_businesses_default():
    print("\n>> /api/businesses (default, type=business)")
    r = get("/businesses")
    if r.status_code != 200:
        record("businesses default 200", False, f"status={r.status_code} body={r.text[:200]}")
        return None
    data = r.json()
    record("businesses default 200", True)
    if not isinstance(data, list):
        record("businesses returns list", False, f"got {type(data).__name__}")
        return None
    record("businesses returns list", True, f"count={len(data)}")
    record("businesses count ~796 (>=500)", len(data) >= 500, f"count={len(data)}")

    if not data:
        return data
    sample = data[0]
    required = ["id", "type", "name", "tags", "open_now", "fingerprint"]
    missing = [k for k in required if k not in sample]
    record("business record has required fields", not missing, f"missing={missing} sample_keys={list(sample.keys())[:20]}")
    record("record.type=='business'", sample.get("type") == "business", f"type={sample.get('type')}")
    record("record.tags is array", isinstance(sample.get("tags"), list))
    record("record.open_now is bool", isinstance(sample.get("open_now"), bool))
    record("record.fingerprint is str", isinstance(sample.get("fingerprint"), str) and bool(sample.get("fingerprint")))

    # Hebrew content presence
    hebrew_count = sum(1 for d in data if HEBREW_RE.search((d.get("name") or "") + (d.get("subtitle") or "")))
    record("Hebrew content present in names/subtitles", hebrew_count >= len(data) * 0.5, f"{hebrew_count}/{len(data)}")

    # Validation rules across ALL records
    bad_phone = []
    missing_fp = []
    bad_type = []
    non_array_tags = []
    for d in data:
        ph = d.get("phone")
        if ph and not str(ph).startswith("+972"):
            bad_phone.append(ph)
        if not d.get("fingerprint"):
            missing_fp.append(d.get("id"))
        if d.get("type") not in ("business", "professional"):
            bad_type.append(d.get("type"))
        if d.get("tags") is not None and not isinstance(d.get("tags"), list):
            non_array_tags.append(d.get("id"))
    record("all phones +972 (or empty)", not bad_phone, f"bad={bad_phone[:5]} ({len(bad_phone)} total)")
    record("all records have fingerprint", not missing_fp, f"missing_fp_ids={missing_fp[:5]}")
    record("all type in {business,professional}", not bad_type, f"bad_types={set(bad_type)}")
    record("tags always array (never scalar)", not non_array_tags, f"bad={non_array_tags[:5]}")

    # Sorted by name
    names = [d.get("name", "") for d in data]
    record("sorted by name asc", names == sorted(names), f"not sorted around idx {next((i for i,(a,b) in enumerate(zip(names, sorted(names))) if a!=b), -1)}")

    return data

def test_businesses_type_professional():
    print("\n>> /api/businesses?type=professional")
    r = get("/businesses", type="professional")
    if r.status_code != 200:
        record("professional 200", False, f"status={r.status_code}")
        return
    data = r.json()
    record("professional 200", True, f"count={len(data)}")
    record("professional count ~11 (>=5)", len(data) >= 5, f"count={len(data)}")
    bad = [d for d in data if d.get("type") != "professional"]
    record("every record type=='professional'", not bad, f"bad={len(bad)}")
    bad_phone = [d.get("phone") for d in data if d.get("phone") and not str(d["phone"]).startswith("+972")]
    record("professional phones +972", not bad_phone, f"bad={bad_phone[:5]}")

def test_businesses_type_business_explicit():
    print("\n>> /api/businesses?type=business")
    r = get("/businesses", type="business")
    if r.status_code != 200:
        record("business explicit 200", False, f"status={r.status_code}")
        return
    data = r.json()
    record("business explicit 200", True, f"count={len(data)}")
    record("business count ~796 (>=500)", len(data) >= 500, f"count={len(data)}")
    bad = [d for d in data if d.get("type") != "business"]
    record("every record type=='business'", not bad, f"bad={len(bad)}")

def test_businesses_category_restaurants():
    print("\n>> /api/businesses?category=restaurants")
    r = get("/businesses", category="restaurants")
    if r.status_code != 200:
        record("category restaurants 200", False, f"status={r.status_code}")
        return
    data = r.json()
    record("category restaurants 200", True, f"count={len(data)}")
    # Each item must have 'restaurants' in its tags
    bad = [d.get("id") for d in data if "restaurants" not in (d.get("tags") or [])]
    record("all items contain 'restaurants' tag", not bad, f"bad={bad[:5]}")
    record("restaurants count roughly >=80 (docs say ~100)", len(data) >= 60, f"count={len(data)}")

def test_businesses_category_multi():
    print("\n>> /api/businesses?category=restaurants,cafes")
    r_multi = get("/businesses", category="restaurants,cafes")
    r_rest = get("/businesses", category="restaurants")
    if r_multi.status_code != 200 or r_rest.status_code != 200:
        record("multi category 200", False, f"multi={r_multi.status_code} rest={r_rest.status_code}")
        return
    multi = r_multi.json()
    rest = r_rest.json()
    record("multi category 200", True, f"multi={len(multi)} rest_only={len(rest)}")
    record("multi count >= restaurants-only", len(multi) >= len(rest), f"multi={len(multi)} rest={len(rest)}")
    bad = [d.get("id") for d in multi if not ({"restaurants", "cafes"} & set(d.get("tags") or []))]
    record("every multi item has restaurants OR cafes", not bad, f"bad={bad[:5]}")

def test_businesses_source_filter():
    print("\n>> /api/businesses?source=eilat_city")
    r = get("/businesses", source="eilat_city")
    if r.status_code != 200:
        record("source filter 200", False, f"status={r.status_code}")
        return
    data = r.json()
    record("source filter 200", True, f"count={len(data)}")
    bad = [d for d in data if d.get("source") != "eilat_city"]
    record("every item source=='eilat_city'", not bad, f"bad={len(bad)}")

def test_businesses_hebrew_query():
    print("\n>> /api/businesses?q=סושי")
    r = get("/businesses", q="סושי")
    if r.status_code != 200:
        record("hebrew query 200", False, f"status={r.status_code}")
        return
    data = r.json()
    record("hebrew query 200", True, f"count={len(data)}")
    # We cannot force the presence of matches, but if any, verify match logic
    if data:
        for d in data[:3]:
            hay = " ".join([
                str(d.get("name") or ""),
                str(d.get("subtitle") or ""),
                str(d.get("description") or ""),
                str(d.get("address") or ""),
                " ".join(d.get("tags") or []),
            ])
            if "סושי" not in hay:
                record("hebrew q matches name/subtitle/description/address/tags", False, f"no 'סושי' in {d.get('id')}")
                return
        record("hebrew q matches name/subtitle/description/address/tags", True)
    else:
        record("hebrew q search returns list (possibly 0)", True, "0 matches — acceptable")

def test_businesses_open_now():
    print("\n>> /api/businesses?open_now=true")
    r = get("/businesses", open_now="true")
    if r.status_code != 200:
        record("open_now 200", False, f"status={r.status_code}")
        return
    data = r.json()
    record("open_now 200", True, f"count={len(data)}")
    bad = [d.get("id") for d in data if d.get("open_now") is not True]
    record("every item open_now==True", not bad, f"bad={bad[:5]}")

def test_businesses_limit():
    print("\n>> /api/businesses?limit=5")
    r = get("/businesses", limit=5)
    if r.status_code != 200:
        record("limit 200", False, f"status={r.status_code}")
        return
    data = r.json()
    record("limit 200", True, f"count={len(data)}")
    record("limit<=5", len(data) <= 5, f"count={len(data)}")

# ------------------------------------------------------------------
# 2. GET /api/businesses/categories
# ------------------------------------------------------------------

EXPECTED_BIZ_SLUGS = {
    "restaurants", "cafes", "bars", "fast_food", "attractions", "hotels",
    "spa", "beauty", "fashion", "jewelry", "electronics", "appliances",
    "phones", "home", "supermarket", "shopping_center", "travel", "transport",
    "marine", "consulate", "services_biz",
}
EXPECTED_PRO_SLUGS = {
    "construction", "electrician", "plumber", "ac", "appliance_fix",
    "carpentry", "sealing", "cleaning_pro", "gardening", "moving",
    "locksmith", "pest", "auto_repair", "tutor", "therapy", "health_pro",
    "lawyer", "accountant", "tech_pro", "graphics", "photo", "events_pro",
    "beauty_home",
}

def test_categories_business():
    print("\n>> /api/businesses/categories?type=business")
    r = get("/businesses/categories", type="business")
    if r.status_code != 200:
        record("categories business 200", False, f"status={r.status_code}")
        return
    data = r.json()
    record("categories business 200", True, f"count={len(data)}")
    record("categories is LIST", isinstance(data, list), f"type={type(data).__name__}")
    if not isinstance(data, list) or not data:
        return
    first = data[0]
    record("first entry slug='all'", first.get("slug") == "all", f"got {first.get('slug')}")
    record("first entry label='הכל'", first.get("label") == "הכל", f"got {first.get('label')}")
    record("first entry has count", isinstance(first.get("count"), int) and first["count"] >= 500, f"count={first.get('count')}")

    slugs_in = {item["slug"] for item in data if item["slug"] != "all"}
    record("21 business slugs present", slugs_in == EXPECTED_BIZ_SLUGS, f"missing={EXPECTED_BIZ_SLUGS-slugs_in} extra={slugs_in-EXPECTED_BIZ_SLUGS}")

    # Each entry has slug/label/emoji/count
    bad = [it.get("slug") for it in data if not all(k in it for k in ("slug", "label", "emoji", "count"))]
    record("each entry has slug/label/emoji/count", not bad, f"bad={bad[:5]}")

    counts = {it["slug"]: it["count"] for it in data}
    print(f"    counts: restaurants={counts.get('restaurants')} cafes={counts.get('cafes')} "
          f"fashion={counts.get('fashion')} attractions={counts.get('attractions')} "
          f"hotels={counts.get('hotels')} bars={counts.get('bars')}")
    record("restaurants count >= 60", counts.get("restaurants", 0) >= 60, f"{counts.get('restaurants')}")
    record("cafes count >= 20", counts.get("cafes", 0) >= 20, f"{counts.get('cafes')}")
    record("fashion count >= 40", counts.get("fashion", 0) >= 40, f"{counts.get('fashion')}")
    record("attractions count >= 60", counts.get("attractions", 0) >= 60, f"{counts.get('attractions')}")

def test_categories_professional():
    print("\n>> /api/businesses/categories?type=professional")
    r = get("/businesses/categories", type="professional")
    if r.status_code != 200:
        record("categories pro 200", False, f"status={r.status_code}")
        return
    data = r.json()
    record("categories pro 200", True, f"count={len(data)}")
    record("pro categories is LIST", isinstance(data, list))
    if not isinstance(data, list) or not data:
        return
    first = data[0]
    record("pro first slug='all'", first.get("slug") == "all")
    record("pro first label='הכל'", first.get("label") == "הכל")
    slugs = {it["slug"] for it in data if it["slug"] != "all"}
    record("23 professional slugs present", slugs == EXPECTED_PRO_SLUGS, f"missing={EXPECTED_PRO_SLUGS-slugs} extra={slugs-EXPECTED_PRO_SLUGS}")

# ------------------------------------------------------------------
# 3. GET /api/businesses/sources
# ------------------------------------------------------------------

def test_sources_business():
    print("\n>> /api/businesses/sources?type=business")
    r = get("/businesses/sources", type="business")
    if r.status_code != 200:
        record("sources business 200", False, f"status={r.status_code}")
        return
    data = r.json()
    record("sources business 200", True, f"{data}")
    record("sources is list", isinstance(data, list))
    if not data:
        record("sources business non-empty", False)
        return
    # Find eilat_city
    ec = next((s for s in data if s["source"] == "eilat_city"), None)
    record("eilat_city present", ec is not None, f"got sources: {[s['source'] for s in data]}")
    if ec:
        record("eilat_city source_name='אילת+'", ec.get("source_name") == "אילת+", f"got {ec.get('source_name')}")
        record("eilat_city count >=500 (~796)", ec.get("count", 0) >= 500, f"{ec.get('count')}")

def test_sources_professional():
    print("\n>> /api/businesses/sources?type=professional")
    r = get("/businesses/sources", type="professional")
    if r.status_code != 200:
        record("sources pro 200", False, f"status={r.status_code}")
        return
    data = r.json()
    record("sources pro 200", True, f"{data}")
    yy = next((s for s in data if s["source"] == "yomyom_pros"), None)
    record("yomyom_pros present", yy is not None, f"got: {[s['source'] for s in data]}")
    if yy:
        record("yomyom_pros source_name='יום-יום אילת'", yy.get("source_name") == "יום-יום אילת", f"got {yy.get('source_name')}")
        record("yomyom_pros count >=5 (~11)", yy.get("count", 0) >= 5, f"{yy.get('count')}")

# ------------------------------------------------------------------
# 4. GET /api/businesses/status
# ------------------------------------------------------------------

def test_status():
    print("\n>> /api/businesses/status")
    r = get("/businesses/status")
    if r.status_code != 200:
        record("status 200", False, f"status={r.status_code}")
        return
    data = r.json()
    record("status 200", True, f"{data}")
    required = ["last_updated_at", "total_businesses", "total_professionals"]
    missing = [k for k in required if k not in data]
    record("status has required fields", not missing, f"missing={missing}")
    record("status.total_businesses >=500 (~796)", data.get("total_businesses", 0) >= 500, f"{data.get('total_businesses')}")
    record("status.total_professionals >=5 (~11)", data.get("total_professionals", 0) >= 5, f"{data.get('total_professionals')}")
    # last_updated_at may be None or iso string
    lu = data.get("last_updated_at")
    record("status.last_updated_at is null or iso string", lu is None or isinstance(lu, str), f"got {type(lu).__name__} value={lu}")

# ------------------------------------------------------------------
# 5. GET /api/businesses/{id}
# ------------------------------------------------------------------

def test_get_by_id(sample_id: str):
    print(f"\n>> /api/businesses/{{id}} (id={sample_id})")
    r = get(f"/businesses/{sample_id}")
    if r.status_code != 200:
        record("get-by-id 200", False, f"status={r.status_code} body={r.text[:200]}")
        return
    data = r.json()
    record("get-by-id 200", True)
    record("get-by-id returns id", data.get("id") == sample_id)
    record("get-by-id has open_now bool", isinstance(data.get("open_now"), bool))
    record("get-by-id has fingerprint", bool(data.get("fingerprint")))
    record("get-by-id has tags array", isinstance(data.get("tags"), list))

def test_get_invalid_id():
    print("\n>> /api/businesses/does-not-exist-xyz (expect 404)")
    r = get("/businesses/does-not-exist-xyz-987654")
    record("invalid id -> 404", r.status_code == 404, f"status={r.status_code} body={r.text[:120]}")

# ------------------------------------------------------------------
# 6. refresh endpoint existence (no POST invocation)
# ------------------------------------------------------------------

def test_refresh_endpoint_exists():
    print("\n>> HEAD /api/businesses/refresh (endpoint existence)")
    # A POST would trigger 3-4 min scrape. Do a GET and expect 405 (method not allowed)
    # which proves the route exists as POST. Alternatively OPTIONS.
    r = requests.request("GET", f"{API}/businesses/refresh", timeout=10)
    ok = r.status_code in (404, 405, 200)
    # We specifically want it NOT to be 404 (route registered as POST returns 405 on GET)
    record("refresh endpoint registered (GET returns 405)", r.status_code == 405, f"status={r.status_code}")

# ------------------------------------------------------------------
# Sanity: other APIs did not regress
# ------------------------------------------------------------------

def test_news():
    print("\n>> /api/news")
    r = get("/news")
    if r.status_code != 200:
        record("news 200", False, f"status={r.status_code}")
        return
    data = r.json()
    # Could be list or dict with results; handle both
    items = data if isinstance(data, list) else data.get("items") or data.get("news") or []
    record("news 200", True, f"count={len(items)}")
    record("news count >= 50", len(items) >= 50, f"count={len(items)}")

def test_jobs():
    print("\n>> /api/jobs")
    r = get("/jobs")
    if r.status_code != 200:
        record("jobs 200", False, f"status={r.status_code}")
        return
    data = r.json()
    items = data if isinstance(data, list) else data.get("items") or []
    record("jobs 200", True, f"count={len(items)}")
    record("jobs count >= 30", len(items) >= 30, f"count={len(items)}")

def test_events():
    print("\n>> /api/events")
    r = get("/events")
    record("events 200", r.status_code == 200, f"status={r.status_code}")

# ------------------------------------------------------------------
# Driver
# ------------------------------------------------------------------

def main():
    # 1. main list + validations
    data = test_businesses_default()
    test_businesses_type_professional()
    test_businesses_type_business_explicit()
    test_businesses_category_restaurants()
    test_businesses_category_multi()
    test_businesses_source_filter()
    test_businesses_hebrew_query()
    test_businesses_open_now()
    test_businesses_limit()

    # 2. categories
    test_categories_business()
    test_categories_professional()

    # 3. sources
    test_sources_business()
    test_sources_professional()

    # 4. status
    test_status()

    # 5. by id + invalid
    if data:
        test_get_by_id(data[0]["id"])
    test_get_invalid_id()

    # 6. refresh exists
    test_refresh_endpoint_exists()

    # sanity other APIs
    test_news()
    test_jobs()
    test_events()

    # Summary
    print("\n" + "=" * 72)
    passed = sum(1 for r in results if r["ok"])
    total = len(results)
    print(f"RESULTS: {passed}/{total} passed")
    if failures:
        print("\nFAILURES:")
        for f in failures:
            print(f"  - {f}")
    print("=" * 72)
    sys.exit(0 if not failures else 1)


if __name__ == "__main__":
    main()
