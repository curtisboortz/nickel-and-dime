# Nickel&Dime — Personal Finance Dashboard

A full-stack personal finance dashboard built with Python/Flask that tracks multi-asset portfolios with live market data, allocation drift analysis, budgeting, and economic indicators.

**[Live Demo](https://nickel-and-dime-production.up.railway.app)** (sample data — deploy your own for real use)

---

## Features

### Portfolio Tracking
- **Live prices** for stocks/ETFs (yfinance), crypto (CoinGecko), and precious metals (GoldAPI.io)
- **Multi-asset allocation** across 7 asset classes: Cash, Equities, Gold, Silver, Crypto, Real Assets, Art
- **Drift analysis** — current % vs target bands with visual indicators
- **Physical metals tracking** with purchase history and cost basis
- **Coinbase integration** for live crypto balance sync
- **Treasury yield monitoring** (10Y, 2Y, spread)

### Budgeting & Transactions
- Monthly budget with category-based spending limits
- Bank/credit card statement import (CSV & PDF)
- Recurring transaction detection and tracking
- Spending history by month with category breakdown
- Dividend and fee tracking

### Market Intelligence
- **Real-time pulse bar** — Gold, Silver, BTC, SPY, DXY, VIX, Oil, Copper, Yields
- **Interactive charts** — OHLC candlestick charts with multiple timeframes (1D to Max)
- **Economics tab** — FRED data: national debt, inflation (CPI/PCE), Fed funds rate, M2, yield curve, credit stress
- **Custom pulse cards** — add any ticker to the market monitor
- **Price alerts** — set target prices with directional triggers

### Financial Planning
- Bi-weekly contribution planning (tactical + catch-up phases)
- Financial goal tracking with progress bars
- Debt tracking with payoff estimates
- FX rate conversion
- Excel workbook export with 9 tabs

### Technical
- Progressive Web App (PWA) — installable on mobile/desktop
- Auto-refresh scheduler (configurable, runs 24/7)
- Optional PIN authentication
- Dark theme UI with responsive sidebar navigation
- Lazy-loaded tabs for instant page loads

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12, Flask |
| Data | JSON file storage, pandas, openpyxl |
| Market Data | yfinance, CoinGecko API, GoldAPI.io, FRED API |
| Charts | Chart.js (candlestick, line, bar) |
| Frontend | Vanilla HTML/CSS/JS, CSS Grid, CSS Variables |
| Deployment | Docker, Gunicorn, Render.com |

---

## Quick Start (Local)

```bash
# Clone and install
git clone https://github.com/curtisboortz/nickel-and-dime.git
cd nickel-and-dime
pip install -r requirements.txt

# Copy sample data to get started
copy sample_config.json config.json        # Windows
cp sample_config.json config.json          # macOS/Linux

# Run the dashboard
python server.py
# Open http://localhost:5000
```

### Optional: Add API Keys

Copy `.env.example` to `.env` and add keys for enhanced features:

```env
GOLDAPI_IO=your_key_here          # Live gold/silver prices (free: 100 req/month)
COINBASE_KEY_NAME=your_key        # Coinbase crypto balance sync (view-only)
COINBASE_PRIVATE_KEY=your_pem     # Coinbase PEM private key
FRED_API_KEY=your_key             # FRED economic data (free)
```

All features work without API keys — free APIs (yfinance, CoinGecko) are used as fallbacks.

---

## Deploy Your Own (Free)

### Render.com (Recommended)

1. Fork this repo on GitHub
2. Go to [render.com](https://render.com) and create a new **Web Service**
3. Connect your GitHub repo
4. Render auto-detects the `render.yaml` — just click **Deploy**
5. Set `DEMO_MODE=1` in environment variables for a public demo, or leave it off for personal use

### Docker

```bash
docker build -t nickel-and-dime .
docker run -p 10000:10000 -e DEMO_MODE=1 nickel-and-dime
```

---

## Architecture

```
server.py           Flask app entry point (dev server)
wsgi.py             WSGI entry point (production/gunicorn)
finance_manager.py  Core logic: price fetching, portfolio computation, Excel export
routes.py           Flask route handlers (Blueprint)
dashboard.py        HTML dashboard rendering (~5000 lines of responsive UI)
csv_import.py       CSV/PDF statement parsing and import
fred_manager.py     FRED economic data integration

config.json         User configuration (holdings, budget, targets) — gitignored
price_cache.json    Cached market prices — gitignored
price_history.json  Historical portfolio snapshots (OHLC) — gitignored

sample_*.json       Demo data for deployment and testing
```

---

## Configuration

Edit `config.json` to customize:

- **Holdings**: Add stocks/ETFs with ticker and quantity for live price tracking
- **Blended accounts**: Manual-entry accounts (401k, Fundrise, etc.)
- **Crypto holdings**: Synced from Coinbase or manually entered
- **Physical metals**: Gold/silver purchases with cost basis
- **Budget**: Monthly income and category spending limits
- **Targets**: Allocation target bands per asset class
- **Contribution plan**: Bi-weekly investment schedule

---

## Security

- `config.json` contains personal financial data and is **gitignored**
- API keys should go in `.env` (also gitignored), not in config
- Optional PIN authentication via `WEALTH_OS_PIN` env var
- HTTPS support with self-signed certificates
- Coinbase integration uses **view-only** API keys (no trading permissions)

---

## License

MIT
