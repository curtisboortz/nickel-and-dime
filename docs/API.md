# Nickel&Dime Internal API Reference

All API endpoints are prefixed with `/api` unless noted otherwise.
Authenticated endpoints require a valid session cookie (`@login_required`).
Pro-only endpoints additionally require an active Pro subscription (`@requires_pro`).

CSRF protection is enforced on all mutating endpoints. The frontend auto-injects `X-CSRFToken` via a global fetch interceptor.

---

## Authentication (`auth.py` — no prefix)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET, POST | `/register` | — | Create account |
| GET | `/verify-email/<token>` | — | Email verification |
| GET | `/resend-verification` | Login | Resend verification email |
| GET, POST | `/login` | — | Log in |
| GET | `/logout` | Login | Log out |
| GET, POST | `/forgot-password` | — | Request password reset |
| GET, POST | `/reset-password/<token>` | — | Complete password reset |

---

## Market Data (`api_market.py`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/live-data` | Login | Portfolio summary, allocation breakdown, pulse cards |
| POST | `/api/refresh` | Login | Trigger manual price refresh |
| POST | `/api/bg-refresh` | Login | Background price refresh |
| GET | `/api/sparklines` | Login | Sparkline data for pulse cards |
| GET | `/api/historical` | Login | OHLC candle data for a ticker |
| GET | `/api/fx-rate` | Login | Current FX rate for currency conversion |
| POST | `/api/pulse-order` | Login | Save pulse card layout order |
| POST | `/api/pulse-cards` | Login | Add a new pulse card |
| DELETE | `/api/pulse-cards/<id>` | Login | Remove a pulse card |
| POST | `/api/pulse-cards/restore-all` | Login | Restore default pulse cards |
| POST | `/api/pulse-size` | Login | Save pulse card size preference |

---

## Portfolio (`api_portfolio.py`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/holdings` | Pro | All holdings, crypto, metals with live prices |
| POST | `/api/holdings` | Pro | Create or update a holding |
| DELETE | `/api/holdings/<id>` | Pro | Delete a holding |
| DELETE | `/api/crypto/<id>` | Pro | Delete a crypto holding |
| GET, POST, DELETE | `/api/physical-metals` | Pro | CRUD physical metals |
| POST | `/api/quick-update` | Pro | Quick-update holding fields |
| GET | `/api/export` | Pro | Export portfolio as Excel workbook |
| GET | `/api/balances` | Login | Blended account balances |
| POST | `/api/balances` | Login | Save blended account |
| POST | `/api/balances/rename` | Login | Rename blended account |
| POST | `/api/balances/reorder` | Login | Reorder blended accounts |
| DELETE | `/api/balances/<id>` | Login | Delete blended account |
| GET | `/api/portfolio-history` | Login | Historical portfolio snapshots |
| GET | `/api/ta-tickers` | Login | Technical analysis ticker list |
| POST | `/api/ta-tickers` | Login | Save TA ticker list |
| GET | `/api/tax-loss-harvesting` | Login | Tax-loss harvesting opportunities |
| GET | `/api/perf-attribution` | Login | Performance attribution by category |
| GET | `/api/buckets` | Login | Available asset categories |
| POST | `/api/normalize-buckets` | Login | Re-normalize bucket labels |

---

## Budget & Transactions (`api_budget.py`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/budget-data` | Login | Current budget and transactions |
| POST | `/api/budget-data` | Login | Save budget configuration |
| GET | `/api/budget-templates` | Login | Pre-built budget templates |
| POST | `/api/budget-templates/<id>` | Login | Apply a budget template |
| POST | `/api/transactions` | Login | Add transaction |
| PUT | `/api/transactions/<id>` | Login | Update transaction |
| DELETE | `/api/transactions/<id>` | Login | Delete transaction |
| POST | `/api/transactions/import-csv` | Login | Import transactions from CSV |
| GET | `/api/category-rules` | Login | Auto-categorization rules |
| POST | `/api/category-rules` | Login | Create category rule |
| DELETE | `/api/category-rules/<id>` | Login | Delete category rule |
| GET | `/api/spending-insights` | Login | Monthly spending breakdown |
| GET | `/api/investments` | Login | Monthly investment log |
| POST | `/api/investments` | Login | Save investment entries |
| POST | `/api/investments/new-month` | Login | Start a new investment month |
| GET | `/api/allocation-targets` | Login | Allocation target bands |
| POST | `/api/allocation-targets` | Login | Save allocation targets |
| POST | `/api/allocation-targets/delete` | Login | Delete an allocation target |

---

## Economics (`api_economics.py`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/fred-data` | Login | FRED economic data (CPI, rates, M2, etc.) |
| GET | `/api/economic-calendar` | Login | Upcoming economic events |
| GET | `/api/fedwatch` | Login | Fed funds rate probabilities |
| GET | `/api/sentiment` | Login | Current Fear & Greed indexes |
| GET | `/api/sentiment-history` | Login | Historical sentiment data |
| GET | `/api/cape` | Login | Shiller CAPE ratio |
| GET | `/api/buffett` | Login | Buffett Indicator (market cap / GDP) |

---

## Brokerage Import (`api_import.py`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/import/brokerages` | Pro | List supported brokerages |
| POST | `/api/import/preview` | Pro | Parse CSV and return preview |
| POST | `/api/import/commit` | Pro | Commit previewed import to database |

---

## Settings & Integrations (`api_settings.py`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/settings/integrations` | Pro | Integration connection status |
| POST | `/api/settings/coinbase-keys` | Pro | Save encrypted Coinbase API keys |
| DELETE | `/api/settings/coinbase-keys` | Pro | Remove Coinbase API keys |
| POST | `/api/coinbase-sync` | Pro | Trigger manual Coinbase sync |
| GET | `/api/settings/bucket-rollup` | Login | Category rollup preferences |
| POST | `/api/settings/bucket-rollup` | Login | Save category rollup overrides |

---

## Billing (`api_billing.py`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/create-checkout` | Login | Create Stripe Checkout session |
| POST | `/api/billing-portal` | Login | Create Stripe billing portal session |
| GET | `/api/subscription-status` | Login | Current subscription status |
| POST | `/api/stripe-webhook` | — | Stripe webhook (signature-verified, CSRF exempt) |

---

## Pages (`pages.py` — no prefix)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/` | — | Landing page |
| GET | `/dashboard`, `/dashboard/<tab>` | Login | Dashboard shell |
| GET | `/api/tab-content/<tab>` | Login | Lazy-loaded tab HTML |
| GET | `/economics` | Login | Economics page |
| GET | `/technical` | Login | Technical analysis page |
| GET | `/billing/pricing` | Login | Pricing page |
| GET | `/billing/account` | Login | Account / billing page |
| GET | `/health` | — | Health check |
| GET | `/api/diag` | Admin | Server diagnostics |
| POST | `/api/client-errors` | Login | Client-side error reports |
