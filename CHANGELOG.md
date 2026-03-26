# Changelog

All notable changes to Nickel&Dime are documented here.

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

## [0.x] — 2025 to 2026-03 — Personal Dashboard Era

### Initial Build
- Single-user personal finance dashboard
- All data in `config.json` and `price_history.json` flat files
- Monolithic `dashboard.py` generating full HTML as Python f-string

### Market Data
- Real-time prices via yfinance (stocks, ETFs, futures, treasuries)
- CoinGecko for crypto prices
- DXY fix: hybrid `DX-Y.NYB` (spot) / `DX=F` (futures) approach
- Gold and silver via yfinance (`GC=F`, `SI=F`)

### Portfolio Tracking
- Stock, ETF, and mutual fund holdings with live valuation
- Crypto holdings with Coinbase API sync
- Physical metals tracking (gold, silver by ounce)
- Blended account balances with allocation percentages
- Daily OHLC portfolio snapshots with history chart

### Economics
- Economic calendar from Investing.com and Faireconomy with actual vs forecast
- FRED data (debt/fiscal, CPI/PCE, monetary policy, labor, housing, trade)
- CNN Fear & Greed and crypto Fear & Greed gauges
- CAPE ratio and Buffett Indicator

### Technical Analysis
- Embedded TradingView charts with full indicator support

### Budgeting
- Monthly income and expense categories
- Transaction tracking with category assignment
- Spending breakdown with visual charts

### UI
- Dark/light theme toggle with localStorage persistence
- Sidebar navigation with 8 tabs
- Command palette (Ctrl+K) for quick navigation
- Pulse chart modals with multi-timeframe OHLC/candlestick views
- PWA support with manifest.json and service worker
