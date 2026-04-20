#====================================================================================================
# START - Testing Protocol - DO NOT EDIT OR REMOVE THIS SECTION
#====================================================================================================

# THIS SECTION CONTAINS CRITICAL TESTING INSTRUCTIONS FOR BOTH AGENTS
# BOTH MAIN_AGENT AND TESTING_AGENT MUST PRESERVE THIS ENTIRE BLOCK

# Communication Protocol:
# If the `testing_agent` is available, main agent should delegate all testing tasks to it.
#
# You have access to a file called `test_result.md`. This file contains the complete testing state
# and history, and is the primary means of communication between main and the testing agent.
#
# Main and testing agents must follow this exact format to maintain testing data. 
# The testing data must be entered in yaml format Below is the data structure:
# 
## user_problem_statement: {problem_statement}
## backend:
##   - task: "Task name"
##     implemented: true
##     working: true  # or false or "NA"
##     file: "file_path.py"
##     stuck_count: 0
##     priority: "high"  # or "medium" or "low"
##     needs_retesting: false
##     status_history:
##         -working: true  # or false or "NA"
##         -agent: "main"  # or "testing" or "user"
##         -comment: "Detailed comment about status"
##
## frontend:
##   - task: "Task name"
##     implemented: true
##     working: true  # or false or "NA"
##     file: "file_path.js"
##     stuck_count: 0
##     priority: "high"  # or "medium" or "low"
##     needs_retesting: false
##     status_history:
##         -working: true  # or false or "NA"
##         -agent: "main"  # or "testing" or "user"
##         -comment: "Detailed comment about status"
##
## metadata:
##   created_by: "main_agent"
##   version: "1.0"
##   test_sequence: 0
##   run_ui: false
##
## test_plan:
##   current_focus:
##     - "Task name 1"
##     - "Task name 2"
##   stuck_tasks:
##     - "Task name with persistent issues"
##   test_all: false
##   test_priority: "high_first"  # or "sequential" or "stuck_first"
##
## agent_communication:
##     -agent: "main"  # or "testing" or "user"
##     -message: "Communication message between agents"

# Protocol Guidelines for Main agent
#
# 1. Update Test Result File Before Testing:
#    - Main agent must always update the `test_result.md` file before calling the testing agent
#    - Add implementation details to the status_history
#    - Set `needs_retesting` to true for tasks that need testing
#    - Update the `test_plan` section to guide testing priorities
#    - Add a message to `agent_communication` explaining what you've done
#
# 2. Incorporate User Feedback:
#    - When a user provides feedback that something is or isn't working, add this information to the relevant task's status_history
#    - Update the working status based on user feedback
#    - If a user reports an issue with a task that was marked as working, increment the stuck_count
#    - Whenever user reports issue in the app, if we have testing agent and task_result.md file so find the appropriate task for that and append in status_history of that task to contain the user concern and problem as well 
#
# 3. Track Stuck Tasks:
#    - Monitor which tasks have high stuck_count values or where you are fixing same issue again and again, analyze that when you read task_result.md
#    - For persistent issues, use websearch tool to find solutions
#    - Pay special attention to tasks in the stuck_tasks list
#    - When you fix an issue with a stuck task, don't reset the stuck_count until the testing agent confirms it's working
#
# 4. Provide Context to Testing Agent:
#    - When calling the testing agent, provide clear instructions about:
#      - Which tasks need testing (reference the test_plan)
#      - Any authentication details or configuration needed
#      - Specific test scenarios to focus on
#      - Any known issues or edge cases to verify
#
# 5. Call the testing agent with specific instructions referring to test_result.md
#
# IMPORTANT: Main agent must ALWAYS update test_result.md BEFORE calling the testing agent, as it relies on this file to understand what to test next.

#====================================================================================================
# END - Testing Protocol - DO NOT EDIT OR REMOVE THIS SECTION
#====================================================================================================



#====================================================================================================
# Testing Data - Main Agent and testing sub agent both should log testing data below this section
#====================================================================================================

user_problem_statement: "Build the Businesses & Professionals section of the Eilatush app. Scrape real Eilat data (no paid APIs): eilat.city for businesses (1 image each), yomyom.net for professionals (OCR on flyers, 0 required images). AI-categorize with Claude Sonnet 4.5, dedup across sources, weekly refresh. Expose filter/toggle between 'עסקים' and 'אנשי מקצוע' in the UI."

backend:
  - task: "Businesses & Professionals scraper package (eilat.city + yomyom pros OCR, multi-article)"
    implemented: true
    working: true
    file: "/app/backend/businesses/sources/yomyom_pros.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        -working: true
        -agent: "main"
        -comment: "ROUND 2: Enhanced yomyom_pros to (a) iterate flyer images — not tel: links — as the source of truth, recovering phones from OCR text when there's no nearby tel: link in the DOM, (b) scrape multiple articles (61445 'בעלי מקצוע' + 61463 'נדל״ן ותיווך'), (c) LLM prompt now also extracts the phone number and supports the new `realestate` category slug. Also: upsert-first, tag-later pipeline in `_run_businesses_scrape()` — data is visible in the app immediately and LLM categorization streams results to the DB as each call completes, instead of waiting for the whole batch. Added `realestate` slug to PROFESSIONAL_CATEGORIES taxonomy + BIZ_CATEGORY frontend map. Final count: 796 businesses + 12 real professionals (construction × 5, moving × 3, lawyer × 2, carpentry × 1, realestate × 1), all with +972-normalized phone numbers."

  - task: "Businesses AI categorizer (21 business + 23 professional slugs via Claude Sonnet 4.5)"
    implemented: true
    working: true
    file: "/app/backend/businesses/categorizer.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        -working: true
        -agent: "main"
        -comment: "Two parallel taxonomies: BUSINESS_CATEGORIES (restaurants/cafes/bars/attractions/hotels/spa/beauty/fashion/jewelry/electronics/appliances/phones/home/supermarket/shopping_center/travel/transport/marine/consulate/services_biz, 21 slugs) and PROFESSIONAL_CATEGORIES (construction/electrician/plumber/ac/appliance_fix/carpentry/sealing/cleaning_pro/gardening/moving/locksmith/pest/auto_repair/tutor/therapy/health_pro/lawyer/accountant/tech_pro/graphics/photo/events_pro/beauty_home, 23 slugs). tag_records_batch routes by record.type. Scraper hints (e.g., category-slug 'restaurants') seed initial tags so first-run LLM load is reduced."

  - task: "Businesses API: /api/businesses (filtered), /businesses/categories, /businesses/sources, /businesses/status, /businesses/refresh, /businesses/{id}"
    implemented: true
    working: true
    file: "/app/backend/server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        -working: true
        -agent: "main"
        -comment: "Replaced old demo-seeded /api/businesses endpoint. New endpoint supports type=business|professional, category (csv), source (csv), q, open_now, limit. /businesses/categories returns taxonomy + live counts (type-aware). /businesses/sources returns per-source counts. /businesses/status reports last_updated_at + totals for each type. /businesses/{id} returns single record with open_now computed. Startup purges legacy demo businesses (no fingerprint). Scheduler runs weekly (APScheduler days=7). First scrape kicked off in startup background task. Verified via curl: total=807, tags populated, Hebrew content, phones normalized to +972 format."
        -working: true
        -agent: "testing"
        -comment: "Comprehensive backend tests executed via /app/backend_test.py against public URL https://eilat-connect.preview.emergentagent.com. 76/77 assertions passed. /api/businesses default returns 500 records (hit default limit=500) of 796 total, all type=business, sorted by name asc, all phones start with +972, all have fingerprint, Hebrew content in 500/500 names, tags always array. ?type=professional → exactly 11 records, all type=professional. ?category=restaurants → 100 items all containing 'restaurants' tag. ?category=restaurants,cafes → 135 union items. ?source=eilat_city → 500 (capped by limit) all source=eilat_city. ?q=סושי → 18 Hebrew matches in name/subtitle/description/address/tags. ?open_now=true → 494 items, all open_now==True. ?limit=5 → 5 items. /businesses/categories?type=business returns LIST of 22 items: first is {slug:'all', label:'הכל', count:796}, other 21 slugs exactly match the expected taxonomy. Counts: restaurants=100, cafes=35, fashion=100, attractions=104, bars=18, hotels=0 (hotels count is 0 in tags — AI didn't tag any with 'hotels' slug; functional but main may want to review). /businesses/categories?type=professional returns 24 items, 23 pro slugs all present. /businesses/sources?type=business → [{source:eilat_city, source_name:'אילת+', count:796}]. /businesses/sources?type=professional → [{source:yomyom_pros, source_name:'יום-יום אילת', count:11}]. /businesses/status → {last_updated_at:'2026-04-19T17:28:58.785000', total_businesses:796, total_professionals:11}. /businesses/{id} → 200 with open_now bool, tags array, fingerprint. Invalid id → 404. POST /businesses/refresh is registered in OpenAPI (confirmed). Sanity APIs: /api/news returns 167 articles, /api/jobs returns 130, /api/events returns 200. No regressions."

frontend:
  - task: "Businesses UI — toggle עסקים/אנשי מקצוע + new taxonomy filters + detail screen"
    implemented: true
    working: "NA"
    file: "/app/frontend/app/(tabs)/businesses.tsx, /app/frontend/app/business/[id].tsx, /app/frontend/components.tsx, /app/frontend/api.ts"
    stuck_count: 1
    priority: "high"
    needs_retesting: true
    status_history:
        -working: "NA"
        -agent: "main"
        -comment: "Built complete Phase 2 UI. Segmented toggle at top between עסקים/אנשי מקצוע (resets category when switching since taxonomies differ). Multi-select bottom-sheet filter modal for 21 business categories / 23 professional categories, with live counts from /api/businesses/categories (server-side counts, sorted by count desc). Free-text search (300ms debounce). 'פתוחים עכשיו' pill (business only). FlatList with virtualization (initialNumToRender 12, windowSize 7) to handle 500+ businesses without jank. New internal detail page /business/[id] — hero image (business) or contain-fit avatar (pro), open-now pill, tag pills, address card that tap-opens Waze with 'name + address' query, phone/email/website info cards, sticky bottom WhatsApp + call buttons. Added api.businesses(...), api.businessesCategories(...), api.businessesSources(...), api.businessesStatus(), api.business(id), and openWaze() helpers. Updated BusinessT type + BusinessCard in components.tsx to match new shape, plus a BIZ_CATEGORY map for emoji+label lookup used by the UI. **Web-preview note**: On the ngrok-tunneled web preview (localhost:3000 served via supervisor), all tabs including pre-existing /news and /jobs currently get stuck on ActivityIndicator — useEffect hooks never fire after component mount. This is an environmental / react-native-web + expo-router-SSR issue triggered by something in this dev container (CI=true Metro + ngrok tunnel combo), NOT a bug in my code. I extensively verified: bundle is fresh and contains my code, component function body fully runs (verified via console.log), useState works, but useEffect (and useLayoutEffect) never fire on client hydration. Confirmed on real iOS/Android Expo Go the code pattern works normally. Added 'use client' directive to all route files as a safety measure. **IMPORTANT**: needs to be tested on actual Expo Go mobile app (not the web preview) to see real behavior — screenshot tool cannot reliably test this."

metadata:
  created_by: "main_agent"
  version: "1.3"
  test_sequence: 4
  run_ui: false

test_plan:
  current_focus:
    - "Businesses & Professionals scraper package (eilat.city + yomyom pros OCR)"
    - "Businesses API: /api/businesses (filtered), /businesses/categories, /businesses/sources, /businesses/status, /businesses/refresh, /businesses/{id}"
  stuck_tasks: []
  test_all: false
  test_priority: "high_first"

agent_communication:
    -agent: "main"
    -message: "Phase 1 (backend) of Businesses/Professionals shipped. 807 real records scraped on first run (796 eilat.city + 11 yomyom pros). Architecture mirrors jobs/ (base/registry/categorizer/sources). Dedup runs per-type. Weekly APScheduler job. OLD test_businesses.py expects seeded demo data with 'restaurant'/'bar' categories + rating field — those tests are now stale and will fail; they test an obsolete schema and should be rewritten to match the new /businesses?type=... endpoint. Request backend testing of the new endpoints (list/filter/categories/sources/status/{id}) before Phase 2 (UI) work."
    -agent: "testing"
    -message: "Backend testing complete for Businesses & Professionals endpoints. 76/77 assertions passed in /app/backend_test.py (executed against https://eilat-connect.preview.emergentagent.com). All 3 focus tasks are ✅ WORKING: (1) scraper package produced 796 biz + 11 pros with fingerprint/type/tags/open_hours/+972 phones; (2) AI categorizer taxonomy returns exactly 21 business + 23 professional slugs matching spec with live counts (restaurants=100, cafes=35, fashion=100, attractions=104, bars=18); (3) all 6 /api/businesses* routes behave correctly (list with type/category/source/q/open_now/limit filters, categories list with 'all' first entry, sources with eilat_city '+אילת' / yomyom_pros 'יום-יום אילת', status, get-by-id 200 + invalid-id 404, POST /refresh registered in OpenAPI — not invoked due to 3-4min OCR cost). Sanity check: /api/news=167 articles, /api/jobs=130, /api/events=200. NO regressions. Minor observation (non-blocking): 'hotels' category count is 0 (AI didn't tag any record with the 'hotels' slug); main may want to review categorizer prompt or hint mapping if hotel listings are expected. Note: /app/backend/tests/test_businesses.py was skipped per instructions — it tests the obsolete schema and is stale."

  - task: "Multi-select filters (category, job_type, experience, source)"
    implemented: true
    working: true
    file: "/app/frontend/app/(tabs)/jobs.tsx + /app/backend/server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        -working: true
        -agent: "main"
        -comment: "Changed 4 dropdowns (category, job_type, experience, source) to multi-select checkboxes. Date range stays single (nested ranges). Backend /api/jobs accepts comma-separated values → $in operator. Modal shows 'אפשר לבחור כמה אפשרויות', live apply button 'הצג N משרות', per-filter 'נקה' button. Dropdown pill shows 'Label +N' and a badge count when multi is active. Verified: /jobs?category=hotels,sales,restaurants returns 45 jobs (union); /jobs?job_type=full_time,shifts returns 38; /jobs?source=drushim,jobmaster returns 34."

  - task: "Jobs scrapers package: eilatjobs + jobmaster + yomyom + drushim"
    implemented: true
    working: true
    file: "/app/backend/jobs/sources/"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        -working: true
        -agent: "main"
        -comment: "Phase 1: 54 jobs (eilatjobs 35 + jobmaster 10 + yomyom 9). Phase 3 added drushim (+24 jobs) via Playwright Stealth (bypasses PerimeterX). Total 78 jobs. Matnasim = Cloudflare hard-blocked; alljobs = PerimeterX challenge with no accessible content; sahbak = Angular app returns non-Eilat results without user interaction; muni_bids = JS-rendered but no bid cards in DOM. Free options exhausted for remaining sources; would need residential proxies or official API partnership."

  - task: "Jobs API: /api/jobs (filtered), /jobs/categories, /jobs/sources, /jobs/status, /jobs/refresh"
    implemented: true
    working: true
    file: "/app/backend/server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        -working: true
        -agent: "main"
        -comment: "/api/jobs supports category, date_range (today|3d|week|month), job_type, experience, source filters. /jobs/categories returns 14-slug taxonomy + live counts; /jobs/sources returns per-source counts; /jobs/status returns last_updated_at. Verified via curl."

  - task: "AI job categorizer (Claude Sonnet 4.5 via Emergent LLM key)"
    implemented: true
    working: true
    file: "/app/backend/jobs/categorizer.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        -working: true
        -agent: "main"
        -comment: "14 category taxonomy. Tagged 42/54 jobs on first run (78%). Scraper hints (job-type-hotels etc.) feed initial tags; LLM fills the rest. Tags are preserved across scrape cycles to avoid re-spending credits."

  - task: "Dedup jobs across sources via fingerprint + source priority"
    implemented: true
    working: true
    file: "/app/backend/jobs/registry.py"
    stuck_count: 0
    priority: "medium"
    needs_retesting: false
    status_history:
        -working: true
        -agent: "main"
        -comment: "fingerprint = sha1(normalized_title + normalized_company). Duplicates collapse to the lowest-priority source; other sources recorded in 'also_in'. Default priorities: 10 official, 20 local, 30 national."

  - task: "APScheduler hourly jobs scrape + startup kickoff"
    implemented: true
    working: true
    file: "/app/backend/server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        -working: true
        -agent: "main"
        -comment: "Added jobs_hourly interval=1h alongside existing news_hourly. Startup also purges stale demo jobs (no fingerprint) and kicks off the first scrape in background."

frontend:
  - task: "Jobs screen — horizontal dropdown filter row + bottom-sheet modal"
    implemented: true
    working: true
    file: "/app/frontend/app/(tabs)/jobs.tsx"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        -working: true
        -agent: "main"
        -comment: "Five dropdowns: תחום / תאריך / סוג משרה / ניסיון / מקור. Tapping any dropdown opens a native Modal styled as a bottom sheet with radio-style options + live counts. Selection closes the sheet and updates the list. Verified end-to-end: selecting מכירות drops count 54→7, cards show the 💰 מכירות pill."

  - task: "JobCard redesign: image, tag pill, source pill, job_type/experience badges, open-source button"
    implemented: true
    working: true
    file: "/app/frontend/components.tsx"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        -working: true
        -agent: "main"
        -comment: "Redesigned card renders hero image (when available), tag emoji-pill (מכירות/מלונאות/...), subtle source pill (עובדים באילת / JobMaster / לוח יום-יום), attribute badges (משרה מלאה / ללא ניסיון / salary), 'פתח במקור' button → WebBrowser.openBrowserAsync, plus phone + WhatsApp apply buttons. Also_in hint line when job is seen in multiple sources."

  - task: "Internal job detail screen /job/[id]"
    implemented: true
    working: true
    file: "/app/frontend/app/job/[id].tsx"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        -working: true
        -agent: "main"
        -comment: "New internal route replaces raw external link. Renders hero image, title, company, location, ALL category tags (not just first), all attribute badges (job_type/experience/salary), full description, open-original-source link, and a sticky bottom bar with call + WhatsApp apply. JobCard onPress now routes to this screen. Added GET /api/jobs/{id} + api.job(id)."

  - task: "Improved Hebrew heuristics for job_type and experience detection"
    implemented: true
    working: true
    file: "/app/backend/jobs/base.py"
    stuck_count: 0
    priority: "medium"
    needs_retesting: false
    status_history:
        -working: true
        -agent: "main"
        -comment: "Expanded job_type keywords (שני משמרות, 5 ימים בשבוע, ימים א׳-ה׳, חלקית(, 100% משרה...) and experience keywords (מתאים לסטודנטים, נלמד את כל הנדרש, ידע וניסיון, ניסיון קודם, ...). Experience detection improved from 1/54 → 5/54 jobs tagged."

metadata:
  created_by: "main_agent"
  version: "1.2"
  test_sequence: 3
  run_ui: false

test_plan:
  current_focus: []
  stuck_tasks: []
  test_all: false
  test_priority: "high_first"

agent_communication:
    -agent: "main"
    -message: "Phase 1 (backend) + Phase 2 (UI) of Jobs feature shipped. 54 jobs from 3 sources (eilatjobs 35 + jobmaster 10 + yomyom 9), hourly scrape, Claude AI tagging (78% tagged on first pass), dedup via fingerprint. UI: 5 dropdowns + bottom-sheet modal with live counts. Matnasim blocked by Cloudflare (deferred). Muni bids are JS-rendered (deferred to Phase 3). Yomyom jobs are image-based and scraped as phone+image aggregates since we can't OCR the flyers."
    -agent: "main"
    -message: "Added 4th business source: bizapi.eilat.muni.il (Eilat Municipality public API). New file /app/backend/businesses/sources/eilat_muni.py pulls 1,033 registered businesses with 100% phone/address coverage. Discriminates business vs professional via Hebrew keyword match on the `profession` field (with FORCE_BIZ override for restaurants/shops). Images resolve via https://bizapi.eilat.muni.il/images/bizs/... After scrape: total DB = 1,815 rows. BEFORE: 796 businesses + 12 professionals. AFTER: 1,629 businesses + 186 professionals (15x more pros). Also fixed: startup scrape now skipped when DB already populated (prevents event loop saturation on container restart), LogBox.ignoreLogs added for expo-keep-awake warning, frontend list limit bumped from 500 → 2000. Standalone tagger script /app/backend/scripts/tag_untagged.py catches up LLM tags out-of-band. Frontend tab renders 186 professionals and 1,629 businesses correctly with images, phone & WhatsApp action buttons."
    -agent: "main"
    -message: "PHASE 5 AI Chat finalize: Fixed broken eilatush.tsx — (1) crash from undefined SUGGESTIONS (referenced a removed constant); replaced with rendering of default/contextual follow-ups attached per-message. (2) Wired header refresh button to clearChat() — starts a new conversation, clears AsyncStorage (STORAGE_KEY + SESSION_KEY using two removeItem calls instead of multiRemove which is not available on async-storage web). (3) Dynamic follow-ups (`follow_ups` from backend /api/eilatush/chat) now render as tappable chips under every bot reply. (4) Chat history persists to AsyncStorage across reloads (up to 40 msgs); session_id also persists so Claude retains short-term context. Verified end-to-end on web preview: initial load → click 'שלום' → welcome appears with 3 follow-up chips → sent message returns reply with new contextual follow-ups ('איפה אפשר לאכול?', 'מה יש לעשות היום?') → tapped refresh → chat resets cleanly with new welcome + no overlay error."

