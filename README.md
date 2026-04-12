# Nickel&Dime — Personal Finance SaaS

A full-stack personal finance platform built with Python/Flask and PostgreSQL. Track multi-asset portfolios with live market data, allocation drift analysis, economic indicators, budgeting, and technical analysis — all behind a subscription-gated SaaS model.

**[nickelanddime.io](https://nickelanddime.io)**

---

## Features

### Dashboard & Summary
- Real-time portfolio value with currency conversion (USD/CAD/EUR/GBP)
- Allocation vs. target donut chart with expandable sub-categories
- Configurable category grouping (e.g. roll Gold/Silver into Real Assets)
- Monthly investment tracker

### Portfolio & Holdings
- **Live prices** for stocks/ETFs (yfinance), crypto (CoinGecko), and precious metals
- **Multi-brokerage CSV import** with auto-detection (Fidelity, Schwab, Vanguard, TD, and more)
- **Coinbase API integration** for automatic crypto balance sync (encrypted at rest)
- Per-holding cost basis, daily P&L, and total P&L
- Sortable, editable holdings tables with inline notes
- Physical metals tracking with purchase history

### Pulse Cards
- Customizable market monitor tiles — add any ticker, index, or ratio
- Sparkline mini-charts with selectable duration (1D–1Y)
- Drag-and-drop reordering with persistent layout

### Market Intelligence
- **Economics tab** — FRED data: national debt, CPI/PCE inflation, Fed funds rate, M2, yield curve, credit spreads, Buffett Indicator, CAPE ratio
- **FedWatch** — CME-style rate probability chart with FOMC calendar
- **Fear & Greed** — CNN index for stocks, CoinMarketCap index for crypto
- **Economic calendar** with smart green/red coding for beats vs. misses

### Technical Analysis (Pro)
- OHLC candlestick charts with multiple timeframes (1D to Max)
- Quick access to all portfolio holdings
- Projected growth with Monte Carlo simulation
- Drawdown analysis and tax-loss harvesting opportunities
- Performance attribution by asset class

### Budgeting
- Monthly budget with category-based spending limits
- Bank/credit card CSV import
- Spending history by month with category breakdown

### Financial Planning
- Contribution planning (tactical + catch-up phases)
- Financial goal tracking with progress bars
- FX rate conversion

### Account & Billing
- Free tier with core dashboard features
- Pro tier ($15/month) with GPT-5.4 AI, full FRED data, portfolio digests, and more
- Stripe-powered subscriptions with automatic 2-week trial
- Password reset via email (Resend/SMTP)

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12, Flask, SQLAlchemy, Flask-Migrate |
| Database | PostgreSQL (prod), SQLite (dev) |
| Auth | Flask-Login, Flask-Bcrypt, Flask-WTF (CSRF) |
| Billing | Stripe Subscriptions |
| Market Data | yfinance, CoinGecko, FRED API, CoinMarketCap |
| Crypto Sync | Coinbase Advanced Trade API |
| Encryption | Fernet (secrets at rest) |
| Background | APScheduler (price refresh, snapshots) |
| Charts | Chart.js (candlestick, line, bar, doughnut) |
| Frontend | Vanilla HTML/CSS/JS, modular script architecture |
| Email | Flask-Mail / Resend |
| Deployment | Railway, Gunicorn |
| CI/CD | GitHub Actions, Ruff, Pytest |

---

## Quick Start (Local)

```bash
git clone https://github.com/curtisboortz/nickel-and-dime.git
cd nickel-and-dime
python -m venv venv && venv\Scripts\activate   # Windows
# python -m venv venv && source venv/bin/activate  # macOS/Linux
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and fill in at minimum:

```env
FLASK_ENV=dev
FLASK_SECRET=some-random-string
```

Initialize the database and run:

```bash
flask db upgrade
python wsgi.py
# Open http://localhost:5000
```

### Optional API Keys

| Key | Purpose | Free? |
|-----|---------|-------|
| `FRED_API_KEY` | FRED economic data | Yes |
| `CMC_API_KEY` | Crypto Fear & Greed index | Yes (basic tier) |
| `STRIPE_SECRET_KEY` | Subscription billing | Test keys free |
| `FERNET_KEY` | Encrypt Coinbase keys at rest | N/A (generate locally) |
| `COINBASE_KEY_NAME` | Coinbase crypto sync | Yes (view-only) |
| `COINBASE_PRIVATE_KEY` | Coinbase PEM key | Yes |

Generate a Fernet key:
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

---

## Deployment (Railway)

1. Push to GitHub
2. Create a new project on [railway.app](https://railway.app)
3. Add a PostgreSQL service and link it (sets `DATABASE_URL` automatically)
4. Set environment variables from `.env.example`
5. Railway auto-detects the `Procfile` and deploys

---

## Architecture

```
app/
  __init__.py           Flask app factory (create_app)
  config.py             Dev / Prod / Test configuration
  extensions.py         SQLAlchemy, Migrate, Login, CSRF, Mail, Limiter

  blueprints/
    auth.py             Login, register, password reset
    pages.py            Landing page, dashboard shell
    api_portfolio.py    Holdings, crypto, metals, allocation, P&L
    api_budget.py       Transactions, spending, budgets
    api_market.py       Prices, pulse cards, candles, refresh
    api_settings.py     Coinbase keys, category grouping
    api_billing.py      Stripe checkout, webhooks, subscription
    api_import.py       Multi-brokerage CSV import

  models/
    user.py             User, subscription tier, trial
    portfolio.py        Holding, CryptoHolding, Metal, BlendedAccount, etc.
    market.py           PriceCache, PulseCard, FredCache, EconEvent
    settings.py         UserSettings (Coinbase keys, rollup prefs)
    budget.py           Transaction, Budget, Category

  services/
    market_data.py      yfinance + CoinGecko batch price fetching
    coinbase_service.py Coinbase Advanced Trade sync
    fred_service.py     FRED economic data refresh
    portfolio_service.py Portfolio value computation, snapshots
    sentiment_service.py Fear & Greed index caching

  utils/
    auth.py             @requires_pro decorator, admin check
    buckets.py          Asset category definitions, normalization, rollup
    encryption.py       Fernet encrypt/decrypt for secrets at rest
    import_parsers.py   CSV auto-detection for multiple brokerages

  static/js/
    shared.js           Diagnostics, CSRF interceptor, currency, globals
    summary.js          Allocation table, donut chart, monthly investments
    history.js          Portfolio history chart
    pulse.js            Pulse cards, sparklines, drag-and-drop
    budget.js           Transactions, spending, command palette
    economics.js        FRED charts, FedWatch, CAPE, Buffett, calendar
    portfolio.js        Projections, TA, Monte Carlo, drawdown, TLH
    sentiment.js        Sentiment gauges and history
    balances.js         Blended accounts, bucket helpers
    holdings.js         Holdings, crypto, metals tables
    settings.js         Settings modal, integrations, category grouping

  templates/
    base.html           Base template with CSRF meta tag
    landing.html        Public landing page
    dashboard/layout.html  Authenticated dashboard shell

wsgi.py               WSGI entry point (production)
Procfile              Gunicorn command for Railway
migrations/           Alembic migration versions
tests/                Pytest suite
```

---

## Security

- CSRF protection on all mutating endpoints (Flask-WTF) with auto-injected tokens
- Coinbase API keys encrypted at rest with Fernet symmetric encryption
- Passwords hashed with bcrypt
- Session cookies: `Secure`, `HttpOnly`, `SameSite=Lax` in production
- Rate limiting on auth endpoints
- XSS protection via server-side escaping and client-side `_esc()` helper
- Stripe webhook verified by signature (only endpoint exempt from CSRF)

---

## Testing

```bash
pytest                    # Run full suite
pytest --tb=short -q      # Quick summary
ruff check app/           # Lint
```

---

## License

MIT
