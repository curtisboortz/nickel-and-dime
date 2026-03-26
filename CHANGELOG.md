# Changelog

All notable changes to Nickel&Dime are documented here.

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
