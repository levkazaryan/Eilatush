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

user_problem_statement: "Build the Jobs page of the Eilatush app with (1) AI-categorized subject filter via dropdown, (2) date-uploaded filter, (3) more useful filter dimensions (job_type, experience, source), (4) dedup across sources, (5) hourly auto-scrape from 3+ approved Eilat job boards (eilatjobs.com, jobmaster.co.il, yomyom.net)."

backend:
  - task: "Jobs scrapers package: eilatjobs + jobmaster + yomyom"
    implemented: true
    working: true
    file: "/app/backend/jobs/sources/"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        -working: true
        -agent: "main"
        -comment: "Smoke-tested run_all_job_scrapers directly: returned 54 unique jobs (35 eilatjobs + 10 jobmaster + 9 yomyom) with title, description, phone, image, fingerprint, job_type hints."

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

