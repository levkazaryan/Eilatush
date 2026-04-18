# Eilatush (אילתוש) — PRD

## Vision
A local utility mobile app for Eilat (Israel) residents. Answers the daily questions — "What's happening tonight?", "Where should I go?", "Where can I work?", "What's going on in the city?" — faster than Instagram, WhatsApp groups, or Google.

**Not** a social network. **Not** a marketplace. **Not** a tourist app. A local utility that opens and gives instant value.

## Users
- Eilat residents (primary, Hebrew-speaking)
- No login required (open access MVP)

## Core Features (MVP shipped)
1. **בית — What's Happening Now** (`/`): Events sorted into time bands עכשיו / הערב / בהמשך. Filter chips by time and category (מסיבות, הופעות, מופעים, פעילות, אוכל, ספורט). Event cards with image, time, venue, price, call & WhatsApp CTAs.
2. **עסקים — Businesses** (`/businesses`): Local business directory with search, category filter (מסעדות, ברים, בתי קפה, חנויות, שירותים, יופי, ספורט), "open now" badge (פתוח/סגור), deal badges, WhatsApp & call CTAs.
3. **עבודה — Jobs** (`/jobs`): Local job listings. Urgency filters (🔥 עכשיו, בקרוב, השבוע) and industry filters (מלונאות, מסעדות, תיירות…). "Quick apply" via WhatsApp.
4. **חדשות — News** (`/news`): Curated local updates — source filters (עירייה, התראות, אירועים). Timestamped cards with source badges.
5. **אילתוש — AI Assistant** (`/eilatush`): Chat interface powered by Claude Sonnet 4.5 (via Emergent Universal LLM Key). Understands Hebrew queries ("ברים פתוחים עכשיו", "עבודה דחופה", "סושי זול"), returns rich **cards** (events / businesses / jobs / news) — not plain text. Suggestion chips on welcome. Center-floating orange mascot button on the tab bar.

## Tech Stack
- **Frontend**: Expo Router (React Native), SDK 54, RTL-forced, dark theme, Heebo-friendly typography
- **Backend**: FastAPI + Motor (MongoDB), seeded with realistic Hebrew content for Eilat
- **AI**: Emergent Universal Key → `anthropic/claude-sonnet-4-5-20250929` via `emergentintegrations`
- **Design Theme**: "Deep Sea & Desert Neon" — bg `#0C0C12`, primary Sunset Orange `#FF512F`, secondary Red Sea Cyan `#00F2FE`

## Endpoints
- `GET /api/events?band=now|tonight|later&category=…`
- `GET /api/businesses?category=…&open_now=true&q=…`
- `GET /api/jobs?urgency=now|soon|this_week&category=…`
- `GET /api/news?source=municipality|alert|event`
- `POST /api/eilatush/chat` → `{session_id, reply, intent, results: [{type, item}]}`

## Seeded Demo Data (Hebrew)
- 8 events (party, concert, show, activity, food, sport) across time bands
- 12 businesses (restaurants, bars, cafes, shops, services, beauty, sport)
- 6 jobs (hotel, restaurant, tourism, retail, service) with urgency
- 6 news items (municipality, alerts, events)

## Monetization Path (future)
- Featured placements for businesses
- Promoted deals
- Push notifications for premium partners
- Users never pay

## Roadmap (not in MVP)
- Admin panel to manage content (events/businesses/jobs/news)
- **Facebook integration for Eilat.Muni page** — requires Meta Graph API Page Access Token (pending approval from municipality + Meta). Scraper scaffold exists; will activate once token is provided.
- Push notifications
- Smart Matching ("start now" jobs notified to nearby users)
- Tourist mode (English)

## News Auto-Ingestion (added)
- 15 approved source URLs (eilat.muni.il, eilat.city, eilatport.co.il, icemalleilat.co.il, biz.eilat.muni.il, smarticket events, ynet Eilat topic, mako Eilat tag, sba.org.il course, tiuli, gov.il, parks.org.il, yomyom.net, kan.org.il, facebook.com/Eilat.Muni). Sources that block scraping (403) are skipped silently — logged in backend.
- APScheduler runs `run_all_scrapers` every hour in the background; also once on startup.
- Each article saved with sha1(source_url) as stable id → idempotent upserts.
- Demo news removed on first successful scrape.
- Listing endpoint `/api/news` strips `content_html` for fast listing; detail endpoint `/api/news/{id}` returns full content.
- Manual trigger: `POST /api/news/refresh`.
- Article detail screen parses HTML → extracts images + paragraphs for clean in-app reading.
- Source badge above every article (clickable) + bottom CTA "קרא את הכתבה המלאה במקור" → opens the original link (legally required attribution).

## Business Enhancement (Smart Default)
Added automatic "open now" computation to business cards and Claude-powered intent routing so the home screen always shows actionable content — a key driver of daily active usage (the "trigger loop" described in the vision). Deal badges and urgency pills make revenue-ready surfaces for featured/promoted listings on day one.
