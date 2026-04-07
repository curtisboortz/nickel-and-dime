# Changelog

All notable changes to Nickel&Dime are documented here.

---

## [2.6.0] — 2026-04-07 — UX Polish, AI Advisor Upgrade & Amortization Calculator

### Added
- **Loan amortization calculator** — full-featured calculator in the Budget tab supporting three modes: fixed-rate, adjustable-rate (ARM), and refinance comparison; stacked bar chart showing principal vs interest breakdown over the life of the loan; paginated amortization schedule table; extra payment scenarios showing months and interest saved; ARM mode with configurable fixed period, adjustment interval, rate cap; refinance mode with cumulative cost comparison chart and break-even analysis
- **AI investment philosophy frameworks** — system prompt now incorporates analytical frameworks from Ray Dalio (risk parity / All Weather), Benjamin Graham & Warren Buffett (margin of safety / value investing), Jack Bogle (low-cost indexing), and Howard Marks (market cycles); AI attributes reasoning to specific frameworks when relevant
- **Three new AI tools** — `get_portfolio_history` (trend analysis with growth %, peak, drawdown), `get_sector_exposure` (bucket concentration with top holdings per sector), `get_tax_loss_harvest_candidates` (unrealized losses, wash sale flags, substitute ETF suggestions with estimated tax savings)
- **AI quick action buttons** — added "Tax-Loss Harvest" and "Portfolio Trend" quick prompts; existing prompts rewritten to reference investment frameworks (All Weather Check, Risk Analysis via Buffett lens, Market Outlook via Marks cycle framework)
- **View Transitions API** — tab switching now uses browser-native crossfade transitions for SPA-like navigation feel (graceful fallback for older browsers)
- **Animated number counters** — net worth and pulse card prices animate smoothly between values on live data updates with ease-out easing and directional color flash (green for up, red for down)
- **Staggered card entry animations** — cards cascade in with 50ms stagger when switching tabs, replacing the instant appear
- **Top loading bar** — thin gold progress bar at the top of the page during data fetches (refresh, initial load)
- **AI legal disclaimers** — "Not financial advice" disclaimer on AI welcome screen, persistent footer below chat input linking to /disclaimer page; AI system prompt enforces educational framing and hedge language

### Changed
- **Refresh button** — no longer triggers a full page reload; uses in-place data update via `applyLiveDataToDOM` with spinning animation on the refresh icon
- **All page reloads softened** — 25+ `location.reload()` calls across pulse, portfolio, and budget JS replaced with `ndSoftReload()` which wraps reloads in a 150ms fade transition
- **AI token limits increased** — streaming chat `max_tokens` raised from 800 to 1500; insights card from 600 to 800; temperature lowered from 0.7 to 0.6 for more consistent analysis
- **AI identity reframed** — changed from "senior portfolio analyst" to "portfolio research assistant" providing educational opinions, not professional financial advice
- **Quick action button labels** — "Build My Portfolio" renamed to "All Weather Check", "Analyze My Risk" to "Risk Analysis"

### Fixed
- Pre-existing lint issues: removed unused `finished_with_content` variable in `api_ai.py`, removed unused `compute_portfolio_value` import and call in `ai_context_service.py`

### UX Micro-Interactions
- Sidebar tooltip hover delay (200ms in, instant out)
- Button active press feedback (`scale(0.97)`)
- Focus-visible keyboard accessibility rings on all interactive elements
- Smooth scroll in AI chat instead of instant jump
- Currency switch uses soft reload transition
- Card hover transitions for background and border

---

## [2.5.0] — 2026-04-07 — Allocation Chart Redesign, Plaid Hardening & Data Fixes

### Added
- **Portfolio allocation donut redesign** — replaced messy dual-ring Chart.js donut with a clean single-ring design; center label shows total portfolio value; custom HTML legend with hierarchical parent/child categories showing dollar amounts and percentages sorted by size; professional high-contrast color palette
- **Editable class/bucket on Plaid holdings** — bucket dropdown is now editable on synced holdings (other fields remain locked); backend allows bucket-only updates for Plaid-sourced holdings while protecting all financial data
- **Auto-backfill institution branding** — `_backfill_branding_if_needed` runs during each Plaid sync to populate `institution_name`, `logo_base64`, and `primary_color` on PlaidItems created before branding support; `_fetch_institution_branding` now also returns institution name
- **400 error handler** — API routes now return JSON for CSRF/bad-request failures instead of raw HTML; Plaid Link flow shows actual error message with refresh suggestion

### Fixed
- **Plaid cost_basis was total, not per-share** — Plaid returns total cost basis for the position; now divided by quantity during sync so P&L percentages are accurate (was showing +258,000% on fractional shares)
- **Synthetic ticker too long** — `PRIV:INCOME_REAL_ESTATE_F` (25 chars) exceeded the `ticker` column's `String(20)` limit, causing Fundrise INSERT to fail; slug now truncated to 14 chars (19 total with prefix)
- **DB session poisoning on sync failure** — a failed INSERT would roll back the transaction but subsequent syncs in the same scheduler cycle would crash with "session already rolled back"; added `db.session.rollback()` in scheduler error handler
- **Migration chain broken** — d005 referenced `down_revision = "d004"` but actual revision ID was `"d004_plaid_support"`; fixed to match; also made d005 and d006 idempotent (check `information_schema` before ADD COLUMN / CREATE TABLE) so they survive partial-apply states
- **Investment/transaction sync isolation** — wrapped each phase in its own try/except so a transaction-sync failure doesn't prevent investment data from being saved
- **Script loading order** — `_skeletonRows` inlined into `<head>` so it exists before body inline scripts; `applyLiveDataToDOM` reference deferred with `typeof` check so it doesn't crash before `budget.js` loads
- **`/api/plaid/accounts` 500** — PlaidItem query wrapped in try/except with session rollback; endpoint now also returns branding data (`logo_base64`, `primary_color`)

---

## [2.4.1] — 2026-04-06 — Holdings Loading Fix & Read-Only Plaid

### Fixed
- **Holdings not loading after v2.4.0 redesign** — `GET /api/holdings` returned 500 when `PlaidItem` query referenced unmigrated `logo_base64`/`primary_color` columns; wrapped PlaidItem query in try/except so holdings still load (without branding) even if d006 migration is pending
- **Silent API errors wiping holdings data** — JS fetch did not check `r.ok`, so a 500 JSON error response was silently parsed as empty data; now throws on non-200 and triggers the red "Failed to load holdings" error state
- **Destructive bulk save** — `_save_holdings_bulk` would delete ALL existing holdings when zero matching rows were submitted (e.g. saving during a loading error); added backend safety check that preserves existing holdings when no IDs match, and frontend guard that blocks save while holdings are still loading

### Added
- **Read-only Plaid holdings** — linked brokerage holdings are now displayed as non-editable text with a lock icon instead of input fields; delete button hidden for synced rows
- **Backend Plaid protection** — `POST /api/holdings` (single and bulk) and `DELETE /api/holdings/<id>` now refuse to modify or delete Plaid-sourced holdings with a 400 error explaining they are managed by sync

### Changed
- `_save_holdings_bulk` now filters Plaid holdings out of the editable set entirely — only manual and imported holdings participate in the save/delete cycle

---

## [2.4.0] — 2026-04-06 — Holdings Page Redesign

### Added
- **Grouped account widgets** — holdings page reorganized from a flat table into collapsible per-account sections with institution branding (logos, primary colors), subtotals, and holding counts
- **Institution branding on PlaidItem** — new `logo_base64` (Text) and `primary_color` (String) columns; branding fetched from Plaid `/institutions/get_by_id` during token exchange
- **Tickerless holdings sync** — Plaid securities without a `ticker_symbol` (e.g. Fundrise private REITs) now sync with a synthetic `PRIV:` prefix ticker, `value_override` from `institution_value`, and bucket auto-set to "Alternatives"
- **Collapse state persistence** — per-account expand/collapse saved to localStorage
- **Plaid badge** — account headers show a "Plaid" badge for linked accounts
- **Grand total footer** — day P&L and total P&L with percentage across all account groups

### Changed
- `GET /api/holdings` response restructured: now returns `accounts[]` (grouped by account + institution) alongside the flat `holdings[]` for backward compatibility
- `_renderStockHoldings` replaced by `_renderAccountWidgets` + `_buildAccountTable` in `holdings.js`

### Database
- Migration `d006`: Adds `logo_base64` and `primary_color` columns to `plaid_items`

---

## [2.3.0] — 2026-04-06 — AI Insights, Allocation Templates, PDF Reports & Onboarding

### Added
- **AI Portfolio Insights** — `GET /api/insights` generates natural-language portfolio analysis using OpenAI (allocation health, concentration risk, diversification suggestions, rebalancing prompts); new insights card on portfolio tab
- **Allocation Templates** — 6 built-in templates (Bogleheads 3-Fund, All-Weather, 60/40, Growth, Income, Target-Date); `GET /api/templates`, `GET /api/templates/<id>/compare` endpoints; template picker UI with current-vs-target comparison bars
- **PDF Portfolio Reports** — `GET /api/report/pdf` generates branded multi-page PDF with allocation pie chart, holdings table, performance summary, and AI insights; download button on portfolio tab
- **Onboarding Wizard** — 3-step post-signup flow (connect brokerage, add manual holdings, set allocation targets); progress tracked via `onboarding_completed` flag on UserSettings
- **Referral System** — unique referral codes per user; `POST /api/referral/redeem` with 7-day Pro credit reward; referral link and stats in settings
- **Blog** — Markdown-powered blog engine at `/blog` with post listing and detail pages; `BlogPost` model with slug routing
- **CI pipeline** — GitHub Actions workflow for ruff linting

### Changed
- **FedWatch rewritten** — replaced manual CME futures parsing with `cme-fedwatch` library for more accurate and maintainable rate probability calculations
- **plaid-python v39 compatibility** — updated Plaid service imports for breaking changes in plaid-python v39

### Fixed
- Ruff lint errors blocking CI (E501, F401, F821, W292)
- Dashboard crash on missing DB columns — added resilient column checks
- Naive vs aware datetime comparison in TLH wash-sale window
- Railway staging deploy — pass `RAILWAY_TOKEN` as env var in GitHub Actions
- Onboarding wizard overlay and card backgrounds made opaque for readability

### Database
- Migration `d005`: Adds `onboarding_completed` to `user_settings`; creates `referral_codes`, `referral_redemptions`, and `blog_posts` tables

---

## [2.2.0] — 2026-04-05 — Plaid Integration

### Added
- **Plaid Link integration** — connect brokerage and bank accounts to auto-sync investment holdings and bank transactions via Plaid
- **PlaidItem model** — stores encrypted access tokens, institution metadata, sync cursors, and connection status per user
- **Investment holdings sync** — Plaid securities mapped to `Holding` (stocks/ETFs) and `CryptoHolding` (crypto) with `source="plaid"`; stale holdings auto-removed on each sync
- **Transaction sync** — Plaid transactions mapped to `Transaction` with cursor-based incremental sync and dedup via `import_hash`; Plaid categories mapped to existing budget categories
- **Settings UI** — "Brokerage Connections" section in settings modal with Connect Account (Plaid Link), per-institution Sync/Remove buttons, status badges, and last-sync timestamps
- **Webhook receiver** — `POST /api/plaid/webhook` handles `ITEM`, `HOLDINGS`, and `TRANSACTIONS` webhook events for real-time status and data updates
- **Scheduler job** — Plaid sync runs every 15 minutes via APScheduler alongside existing Coinbase and price refresh jobs
- **`source` column on Holding** — new column (default `"manual"`) distinguishes manual, CSV-imported, and Plaid-synced holdings; `plaid_item_id` FK links back to the connection for clean disconnect

### Database
- Migration `d004`: Creates `plaid_items` table; adds `source` and `plaid_item_id` columns to `holdings`

---

## [2.1.0] — 2026-04-04 — Feature Polish & Analytics

### Added
- **Crypto CRUD** — manual add/edit/delete for crypto holdings beyond Coinbase sync; inline "Add Crypto" form with symbol, quantity, and cost basis fields; edit button for manual entries
- **Skeleton loading states** — shimmer placeholders on allocation table, balances, holdings, and economics tab replacing blank "Loading..." text
- **Performance Attribution v2** — per-bucket returns computed from snapshot history; new `breakdown` JSON column on snapshots; Return column in attribution table
- **Monte Carlo v2** — `GET /api/mc-params` returns portfolio-weighted return and volatility from per-asset-class assumptions; frontend uses real parameters instead of hardcoded 7%/15%; model inputs displayed below chart
- **TLH wash-sale awareness** — 30-day purchase window detection with WASH badge; substitute ETF suggestions for 30+ ticker pairs; estimated tax savings summary row
- **PWA service worker** — `sw.js` with stale-while-revalidate caching for static assets; served from root scope via `/sw.js` route
- **Multi-currency at render time** — crypto and metals tables now use `fxFmt()` for values, converting at display time rather than post-render DOM sweep
- **Physical metals spot data** — API returns live spot prices with daily change %; spot info bar with gold/silver price and change rendered above metals table
- **Tax report CSV** — `GET /api/tax-report` generates downloadable CSV with cost basis, market value, unrealized P&L, TLH flags, and substitute ETFs across stocks, crypto, and metals; download button on portfolio tab

### Changed
- Performance Attribution chart sorted by value descending; tooltips show per-bucket return percentage
- TLH table shows "Potential Tax Savings (est. 25%)" footer row with total estimated savings
- Economics lazy-load placeholder upgraded from spinner to skeleton shimmer blocks

### Database
- Migration `d003`: Added `breakdown` JSON column to `portfolio_snapshots` table
- Snapshot service now persists per-bucket breakdown on every daily snapshot

---

## [2.0.0] — 2026-04-04 — Code Quality, Security & Refactoring

### Architecture
- **Split `dashboard.js`** (5,100+ lines) into 11 feature modules: `shared.js`, `summary.js`, `history.js`, `pulse.js`, `budget.js`, `economics.js`, `portfolio.js`, `sentiment.js`, `balances.js`, `holdings.js`, `settings.js`
- Updated `layout.html` to load modules in dependency order

### Performance
- **Fixed N+1 queries** in `get_holdings`, `tax_loss_harvesting`, `compute_portfolio_value` — batch `PriceCache` lookups instead of per-row queries
- **Batched DB commits** in `market_data.py` (yfinance + CoinGecko), `fred_service.py`, and sentiment service — single commit per refresh cycle instead of per-item

### Security
- **Fernet encryption for Coinbase API keys at rest** — new `app/utils/encryption.py` utility; keys encrypted on save, decrypted on read
- **CSRF protection tightened** — added global fetch interceptor in `shared.js` that auto-injects `X-CSRFToken` on all mutating requests; removed `@csrf.exempt` from all internal endpoints (kept only on Stripe webhook which uses signature verification)
- Added `<meta name="csrf-token">` to base template
- Added `cryptography>=42.0.0` to requirements

### Category System
- Centralized bucket definitions: Gold/Silver → Real Assets, Crypto → Alternatives
- User-configurable category rollups via `UserSettings.bucket_rollup` JSON field
- New API endpoints: `GET/POST /api/settings/bucket-rollup`
- Settings modal "Category Grouping" section with per-subcategory dropdowns
- Rollup overrides wired through `live_data`, `allocation_targets`, and `perf_attribution`
- Alembic migration `d002_add_bucket_rollup`

### Documentation
- **README.md** fully rewritten — updated architecture, tech stack, deployment (Railway), security section, quick start
- **`docs/API.md`** — comprehensive internal API reference (70+ endpoints across 9 blueprints)
- **`.env.example`** — added `FERNET_KEY` with generation instructions

### Legal & SEO
- New pages: Terms of Service (`/terms`), Privacy Policy (`/privacy`), Financial Disclaimer (`/disclaimer`)
- OG/Twitter Card meta tags in `base.html` with overridable blocks per page
- Social sharing card image (`og-card.png`)
- Landing page footer links updated to point to legal pages

---

## [1.4.0] — 2026-03-26 — Customizable Pulse Bar

### Added
- Add/remove pulse cards: hide any default card (X on hover), add custom tickers via "+" button
- Card size control: S (compact), M (default), L (large) toggle above pulse bar
- "Restore hidden" button to bring back all hidden default cards
- Custom cards get live prices and sparkline charts just like defaults
- Size preference saved per-user (server + localStorage)

---

## [1.3.0] — 2026-03-26 — Dashboard Polish & Data Integrity

### Added
- Allocation vs Target table with editable targets (explicit Save/Cancel flow)
- Monthly Investments tracker with add-category support
- Summary tab APIs (`/api/investments`, `/api/allocation-targets`)

### Fixed
- Edit Targets no longer wipes existing targets on open; requires explicit Save
- DXY historical chart now has data beyond 5-day (uses `DX-Y.NYB` for all periods)
- Crypto quantities capped to 6 decimal places max for readability
- Balances table restyled: cleaner font, delete button hidden until row hover

### Changed
- Pulse cards made more square (110x120 -> 90-120px range)
- Pulse price font reduced to fit narrower cards

---

## [1.2.0] — 2026-03-26 — Branding & Visual Fixes

### Added
- Official ND trademark logo across all contexts (sidebar, favicon, PWA icons)
- Generated `icon-192.png`, `icon-512.png`, `apple-touch-icon.png`, `favicon.ico` from logo
- Flask routes to serve icon files at root paths for PWA compatibility

### Fixed
- Logo not rendering in sidebar (was referencing missing file)
- Portfolio donut chart not appearing (script execution order issue)
- Sparklines not loading (API rewritten to support batch requests with internal name mapping)
- Summary tab data failing silently (`loadSummaryData` called before `dashboard.js` loaded)

---

## [1.1.0] — 2026-03-26 — Coinbase Integration & Dashboard Restoration

### Added
- Coinbase Advanced Trade API integration for automatic crypto balance sync
- Settings modal with Coinbase API key management (connect, sync, disconnect)
- Scheduled Coinbase sync every 10 minutes for all connected users
- Logout option in user settings (accessible to all users)
- Editable holdings table with live prices and computed totals
- Physical metals data migration to production DB
- Local JSON to PostgreSQL data migration script (`migrate_local_to_prod.py`)

### Fixed
- Crypto prices showing $0 (lookup key was `CG:{symbol}` instead of `CG:{coingecko_id}`)
- Physical metals valued at $0 (case-sensitive metal name comparison)
- Blended account allocations not mapping correctly to breakdown buckets
- Cache busting added to all static assets (`?v={timestamp}`) to prevent stale browser cache

### Changed
- Dashboard HTML restored to match original `dashboard.py` layout structure
- Holdings page rebuilt with full edit/save workflow (bulk save support)

---

## [1.0.2] — 2026-03-25 — Post-Launch Hotfixes

### Fixed
- Sentiment gauges (Fear & Greed) not loading on dashboard
- Balance account CRUD not working (add/edit/delete)
- JS null-safety errors (`invest-chat-input`, `TA_TICKERS` undefined)
- Added `manifest.json` for PWA support
- Built all tab HTML scaffolds with required DOM IDs
- Wired up Balances/Holdings tabs with API fetching
- Auto-trigger background price refresh when cache is empty
- `is_admin` DB column crash: switched to `ADMIN_EMAILS` env var approach
- Migration resilience: `op.add_column` with context processor safety net

### Changed
- Onboarding wizard updated to reference multi-brokerage support (not just Fidelity)
- Removed em dashes from landing page and program text

---

## [1.0.1] — 2026-03-25 — Launch Day Stabilization

### Added
- Live auto-polling: prices refresh every 30s-15m without page reload
- Visual "flash" animation on price updates
- localStorage persistence for refresh interval preference
- Admin role: founder account gets permanent Pro access via `ADMIN_EMAILS` env var
- Trial banners: notifications at 14 days, 3 days, and 1 day before expiry
- Auto-start 14-day Pro trial on new account registration

### Fixed
- Railway deployment: removed conflicting Dockerfile that hardcoded port 8080
- Gunicorn: isolated APScheduler from migrations, single worker with preload
- Timezone crash: switched from `US/Eastern` to `America/New_York`, added `tzdata`
- Python 3.9 compatibility: fixed type hints in `import_service.py`
- Railway healthcheck: added `/health` endpoint with increased timeout

### Changed
- Landing page redesigned: cool institutional palette (slate blues, teals, silver), bento grid layout, dashboard mockup in hero
- Pricing page: Pro bumped to $12/month, Pro card made visually dominant
- Auth pages redesigned: split-screen layout with branding and trial info

---

## [1.0.0] — 2026-03-25 — SaaS Launch

### Architecture
- Rebuilt as multi-tenant Flask SaaS with app factory pattern
- 8 blueprints: auth, pages, market, portfolio, budget, economics, billing, import
- 21 SQLAlchemy models replacing flat-file JSON storage
- Flask-Migrate with PostgreSQL (production) and SQLite (dev)
- Gunicorn + Railway deployment with auto-migrations

### Authentication
- Email/password registration and login (Flask-Login + bcrypt)
- Password reset flow with token-based email links
- Session management with remember-me support

### Billing (Stripe)
- Stripe Checkout with 14-day free trial
- Webhook handling for full subscription lifecycle
- Customer Portal for self-service management
- Automatic plan sync on payment success/failure

### Feature Gating (Free vs Pro)
- **Free**: Market pulse, economic calendar, sentiment gauges, manual balances, portfolio history, budget planner
- **Pro**: Real-time holdings tracker, brokerage CSV import, technical analysis (TradingView), full FRED data, data export

### Multi-Brokerage Import (Pro)
- Auto-detects CSV format from 11 brokerages: Fidelity, Charles Schwab, Vanguard, E-Trade, thinkorswim, Robinhood, WeBull, Interactive Brokers, Coinbase, M1 Finance, and generic CSV
- Preview with duplicate detection before committing
- Merge or replace mode for existing positions
- Handles preamble stripping, cash filtering, crypto routing, mutual fund detection

### Background Workers (APScheduler)
- Price refresh every 5 minutes (yfinance + CoinGecko)
- FRED economic data every 6 hours
- Economic calendar every 30 minutes (Investing.com + Faireconomy)
- Sentiment gauges every 15 minutes (CNN F&G + crypto F&G)
- Daily portfolio snapshots at 4:30 PM ET

### Frontend
- Jinja2 templates: base, landing page, auth flow, dashboard, billing, error pages
- 680-line extracted CSS with dark/light theme support
- 3,490-line extracted JS for charts, data display, and interactions
- Landing page with feature grid, pricing cards, and CTAs
- Drag-and-drop import UI with preview table
- Mobile-responsive with bottom navigation

### Budget Improvements
- Budget templates (50/30/20, Detailed Monthly, Investor Focus)
- CSV transaction import with dedup and auto-categorization
- Spending insights with month-over-month comparison and savings rate
- Full transaction CRUD (create, update, delete)

### Deployment
- Railway with PostgreSQL plugin and Cloudflare DNS
- Custom domain: nickelanddime.io
- Lightweight `/health` endpoint for Railway healthchecks
- `robots.txt` and `sitemap.xml` for SEO

---

## [0.9.0] — 2026-03-16 — Pre-Launch Refinements

### Fixed
- DXY pricing: hybrid `DX-Y.NYB` (spot) / `DX=F` (futures) approach
- External chart tooltip positioning

### Changed
- Updated FRED API endpoints for latest data
- Updated sentiment data sources

---

## [0.8.0] — 2026-03-04 to 2026-03-05 — Crypto & Performance

### Added
- Crypto Holdings section with Coinbase API integration
- Background thread for price refresh on save actions (instant UI redirect)
- Auto-reload page after save to prevent stale data display

### Changed
- Metals pricing switched to yfinance primary (`GC=F`, `SI=F`), GoldAPI as fallback

---

## [0.7.0] — 2026-03-03 — Market Sentiment

### Added
- Market Sentiment section on Charts tab
- 5 fear/greed gauges: CNN F&G (overall, stock, bond, options, safe haven) and crypto F&G

---

## [0.6.0] — 2026-02-27 — Charts & Budget Intelligence

### Added
- SPAXX money market auto-deduction when logging investments via chat

### Fixed
- Chart spacing: even-spaced intraday ticks, proportional daily+
- Time-based x-axis for portfolio history chart
- Price history wipe bug: added atomic writes, backup files, and safety checks

---

## [0.5.0] — 2026-02-26 — Initial Deployment

### Added
- Initial commit: full personal finance dashboard
- Railway deployment with Procfile
- Demo mode with isolated temp directory
- PWA manifest and service worker

### Fixed
- Logo rendering: inline SVG fallback, static asset serving from project root
- New-month budget function advancing correctly (added `python-dateutil`)
- Dockerfile PORT variable expansion
- Railway PORT binding (switched from Dockerfile to Procfile)
