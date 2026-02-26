"""Flask route handlers for the Nickel&Dime dashboard (Blueprint)."""

import json
import os
from datetime import datetime
from pathlib import Path
from urllib.parse import quote
from flask import Blueprint, request, redirect

bp = Blueprint("main", __name__)

# Module-level references, set by init_routes()
CONFIG_PATH = None
BASE = None
AUTH_PIN = ""
_deps = {}  # all other dependencies


DEMO_MODE = False

def init_routes(config):
    """Inject dependencies from main(). Call before registering blueprint."""
    global CONFIG_PATH, BASE, AUTH_PIN, DEMO_MODE, _deps, scheduler
    CONFIG_PATH = config["CONFIG_PATH"]
    BASE = config["BASE"]
    AUTH_PIN = config["AUTH_PIN"]
    DEMO_MODE = config.get("DEMO_MODE", False)
    scheduler = config.get("scheduler")
    _deps.update(config)


# ── Accessor helpers for closure dependencies ──
def load_config(path=None):
    return _deps["load_config"](path or CONFIG_PATH)

def save_config(path, cfg):
    return _deps["save_config"](path, cfg)

def render_dashboard(data, saved="", active_tab="summary"):
    return _deps["render_dashboard"](data, saved=saved, active_tab=active_tab, demo_mode=DEMO_MODE)

def append_history_log(action, details=""):
    return _deps["append_history_log"](action, details)

def get_dashboard_data_cached(base, config):
    return _deps["get_dashboard_data_cached"](base, config)


def run_update(*args, **kwargs):
    return _deps["run_update"](*args, **kwargs)

def get_effective_api_keys(config):
    return _deps["get_effective_api_keys"](config)

def get_dashboard_data(base, config, **kwargs):
    return _deps["get_dashboard_data"](base, config, **kwargs)

def load_price_cache(base):
    """Load cached prices from price_cache.json."""
    path = Path(base) / "price_cache.json"
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def import_csv(config_path, csv_path, source):
    return _deps["import_csv"](config_path, csv_path, source)

def import_statement(config_path, stmt_path, overrides):
    return _deps["import_statement"](config_path, stmt_path, overrides)

def detect_recurring_transactions(transactions, existing):
    return _deps["detect_recurring_transactions"](transactions, existing)


scheduler = None  # Set by init_routes


# Demo mode: block all write operations
@bp.before_request
def check_demo_mode():
    from flask import jsonify
    if not DEMO_MODE:
        return
    # Allow all GET/HEAD requests and read-only API endpoints
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return
    # Allow bg-refresh (so live prices still work in demo)
    if request.path in ("/api/bg-refresh",):
        return
    # Block all other POST/PUT/DELETE in demo mode
    if request.is_json or request.path.startswith("/api/"):
        return jsonify({"success": False, "error": "Demo mode — changes are disabled. Deploy your own instance to use all features."}), 403
    # For form submissions, redirect with message
    return redirect("/?saved=Demo+mode+%E2%80%94+changes+are+disabled")


# Phase 1: Authentication middleware
@bp.before_request
def check_auth():
    from flask import session
    if not AUTH_PIN:
        return  # No PIN set, skip auth
    if request.path in ("/login", "/static") or request.path.startswith("/api/"):
        return
    if not session.get("authenticated"):
        if request.method == "POST" and request.path == "/login":
            return
        return render_login_page()


@bp.route("/login", methods=["GET", "POST"])
def login():
    from flask import session
    if request.method == "POST":
        pin = request.form.get("pin", "")
        if pin == AUTH_PIN:
            session["authenticated"] = True
            return redirect("/")
        return render_login_page(error="Incorrect PIN")
    return render_login_page()


def render_login_page(error=""):
    error_html = f'<p class="auth-error">{error}</p>' if error else ""
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>Nickel&amp;Dime</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
<style>:root{{--bg-primary:#09090b;--bg-card:#161619;--border-subtle:rgba(255,255,255,0.06);--accent-primary:#d4a017;--accent-glow:rgba(212,160,23,0.15);--text-primary:#f1f5f9;--text-muted:#64748b;--danger:#f87171;}}
*{{box-sizing:border-box;margin:0;padding:0;}} body{{font-family:'Inter',sans-serif;background:var(--bg-primary);color:var(--text-primary);}}
.auth-screen{{display:flex;align-items:center;justify-content:center;min-height:100vh;flex-direction:column;gap:24px;}}
.auth-box{{background:var(--bg-card);border:1px solid var(--border-subtle);border-radius:16px;padding:40px;text-align:center;max-width:360px;width:90%;}}
.auth-box h1{{font-size:1.4rem;margin-bottom:8px;color:var(--accent-primary);}}
.auth-box p{{color:var(--text-muted);font-size:0.85rem;margin-bottom:16px;}}
.auth-box input{{margin:8px 0 16px;text-align:center;font-size:1.2rem;letter-spacing:0.3em;padding:12px;background:#1a1a1f;border:1px solid var(--border-subtle);color:var(--text-primary);border-radius:8px;width:100%;}}
.auth-box input:focus{{outline:none;border-color:var(--accent-primary);box-shadow:0 0 0 3px var(--accent-glow);}}
.auth-box button{{width:100%;padding:12px;background:var(--accent-primary);color:#09090b;border:none;border-radius:8px;font-weight:600;font-size:1rem;cursor:pointer;}}
.auth-box .auth-error{{color:var(--danger);font-size:0.85rem;margin-top:8px;}}
</style></head><body><div class="auth-screen"><div class="auth-box">
<h1>Nickel&amp;Dime</h1><p>Enter your PIN to continue</p>
<form method="post" action="/login"><input type="password" name="pin" placeholder="****" autofocus maxlength="20"><button type="submit">Unlock</button></form>{error_html}
</div></div></body></html>"""

def run_price_update(config, fetch_metals=True):
    tickers = list(
        {h["ticker"] for h in config.get("holdings", []) if h.get("ticker") and h["ticker"] != "SPAXX"}
    )
    crypto_symbols = list({c["symbol"] for c in config.get("crypto_holdings", [])})
    # Include custom pulse card tickers by type (stock -> tickers, crypto -> crypto_symbols)
    for cp in config.get("custom_pulse_cards", []):
        t = cp.get("ticker", "").upper()
        if not t:
            continue
        ptype = cp.get("type", "stock")
        if ptype == "crypto":
            if t not in crypto_symbols:
                crypto_symbols.append(t)
        else:
            if t not in tickers:
                tickers.append(t)
    gold_key = get_effective_api_keys(config).get("goldapi_io", "")
    run_update(BASE, config, tickers, crypto_symbols, gold_key, fetch_metals=fetch_metals, verbose=False)

# Phase 1: URL routing - each tab gets its own URL
@bp.route("/")
@bp.route("/balances")
@bp.route("/budget")
@bp.route("/holdings")
@bp.route("/import")
@bp.route("/history")
@bp.route("/charts")
@bp.route("/economics")
def index():
    config = load_config(CONFIG_PATH)
    # Use cached data for instant page load (no network calls)
    # Fresh prices are fetched in background via /api/bg-refresh
    data = get_dashboard_data_cached(BASE, config)
    saved = request.args.get("saved", "")
    # Determine active tab from URL path or query param
    path_tab = request.path.strip("/")
    tab_map = {"balances": "balances", "budget": "budget", "holdings": "holdings", "import": "import", "history": "history", "charts": "history", "economics": "economics"}
    active = tab_map.get(path_tab, request.args.get("tab", "summary"))
    return render_dashboard(data, saved=saved, active_tab=active)

@bp.route("/refresh", methods=["POST"])
def refresh():
    config = load_config(CONFIG_PATH)
    run_price_update(config, fetch_metals=True)
    return redirect("/?saved=Prices refreshed")

@bp.route("/api/bg-refresh", methods=["POST"])
def bg_refresh():
    """Background price refresh - called by page on load for live data."""
    from flask import jsonify
    import threading
    def _do_refresh():
        try:
            config = load_config(CONFIG_PATH)
            run_price_update(config, fetch_metals=True)
        except Exception as e:
            print(f"[bg-refresh] Error: {e}")
    t = threading.Thread(target=_do_refresh, daemon=True)
    t.start()
    return jsonify({"status": "started"})

@bp.route("/api/live-data")
def api_live_data():
    """Return current portfolio totals and key prices from cache (fast)."""
    from flask import jsonify
    from datetime import datetime, timedelta
    config = load_config(CONFIG_PATH)
    data = get_dashboard_data_cached(BASE, config)
    stock_prices_raw = data.get("stock_prices", {}) or {}
    total = data.get("total", 0)
    price_history = data.get("price_history", [])
    yesterday_str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    prev_total = None
    for entry in reversed(price_history):
        entry_date = (entry.get("date") or "")[:10]
        if entry_date <= yesterday_str:
            prev_total = entry.get("total")
            break
    if prev_total is None and price_history:
        prev_total = price_history[0].get("total")
    if prev_total is None:
        prev_total = total
    daily_change = total - prev_total if prev_total else 0
    daily_change_pct = (daily_change / prev_total * 100) if prev_total and prev_total > 0 else 0
    result = {
        "total": total,
        "daily_change": daily_change,
        "daily_change_pct": daily_change_pct,
        "gold": data.get("metals_prices", {}).get("GOLD", 0),
        "silver": data.get("metals_prices", {}).get("SILVER", 0),
        "gold_silver_ratio": data.get("gold_silver_ratio"),
        "tnx_10y": data.get("treasury_yields", {}).get("tnx_10y"),
        "tnx_2y": data.get("treasury_yields", {}).get("tnx_2y"),
        "btc": data.get("crypto_prices", {}).get("BTC", 0),
        "spy": stock_prices_raw.get("SPY", 0),
        "dxy": stock_prices_raw.get("DX-Y.NYB", 0),
        "vix": stock_prices_raw.get("^VIX", 0),
        "oil": stock_prices_raw.get("CL=F", 0),
        "copper": stock_prices_raw.get("HG=F", 0),
    }
    # Include custom pulse card prices (use type: crypto -> crypto_prices, stock -> stock_prices)
    stock_prices = data.get("stock_prices", {}) or {}
    crypto_prices = data.get("crypto_prices", {}) or {}
    for cp in config.get("custom_pulse_cards", []):
        t = cp.get("ticker", "").upper()
        ptype = cp.get("type", "stock")
        src = crypto_prices if ptype == "crypto" else stock_prices
        result[f"custom_{t}"] = src.get(t) or 0
    return jsonify(result)

@bp.route("/api/pulse-order", methods=["POST"])
def api_pulse_order():
    """Save pulse card order."""
    from flask import jsonify
    data = request.get_json(force=True)
    order = data.get("order", [])
    config = load_config(CONFIG_PATH)
    config["pulse_card_order"] = order
    save_config(CONFIG_PATH, config)
    return jsonify({"success": True})

@bp.route("/api/widget-order", methods=["POST"])
def api_widget_order():
    """Save dashboard widget order to config."""
    from flask import jsonify
    data = request.get_json(force=True)
    config = load_config(CONFIG_PATH)
    config["widget_order"] = data
    save_config(CONFIG_PATH, config)
    return jsonify({"success": True})

@bp.route("/api/pulse-cards", methods=["POST"])
def api_add_pulse_card():
    """Add a custom pulse card."""
    from flask import jsonify
    data = request.get_json(force=True)
    ticker = data.get("ticker", "").strip().upper()
    label = data.get("label", "").strip() or ticker
    ptype = data.get("type", "stock").lower()
    if ptype not in ("stock", "crypto"):
        ptype = "stock"
    if not ticker:
        return jsonify({"success": False, "error": "Ticker is required"}), 400
    config = load_config(CONFIG_PATH)
    custom = config.get("custom_pulse_cards", [])
    # Check for duplicates (same ticker+type)
    if any(c.get("ticker") == ticker for c in custom):
        return jsonify({"success": False, "error": f"{ticker} already added"}), 400
    custom.append({"ticker": ticker, "label": label, "type": ptype})
    config["custom_pulse_cards"] = custom
    # Also add to order
    order = config.get("pulse_card_order", [])
    card_id = f"custom-{ticker}"
    if card_id not in order:
        order.append(card_id)
        config["pulse_card_order"] = order
    save_config(CONFIG_PATH, config)
    return jsonify({"success": True})

@bp.route("/api/pulse-cards/<card_id>", methods=["DELETE"])
def api_remove_pulse_card(card_id):
    """Remove a pulse card (custom cards are deleted, default cards are hidden)."""
    from flask import jsonify
    config = load_config(CONFIG_PATH)
    if card_id.startswith("custom-"):
        # Custom card: remove entirely
        ticker = card_id.replace("custom-", "").upper()
        custom = config.get("custom_pulse_cards", [])
        config["custom_pulse_cards"] = [c for c in custom if c.get("ticker") != ticker]
    else:
        # Default card: add to hidden list
        hidden = config.get("hidden_pulse_cards", [])
        if card_id not in hidden:
            hidden.append(card_id)
        config["hidden_pulse_cards"] = hidden
    # Also remove from order
    order = config.get("pulse_card_order", [])
    config["pulse_card_order"] = [o for o in order if o != card_id]
    save_config(CONFIG_PATH, config)
    return jsonify({"success": True})

@bp.route("/api/pulse-cards/restore-all", methods=["POST"])
def api_restore_pulse_cards():
    """Restore all hidden default pulse cards."""
    from flask import jsonify
    config = load_config(CONFIG_PATH)
    config["hidden_pulse_cards"] = []
    save_config(CONFIG_PATH, config)
    return jsonify({"success": True})

# Yahoo Finance uses ETH-USD, BTC-USD etc. for crypto; "ETH" alone returns Grayscale ETF
_CRYPTO_YF_MAP = {"ETH": "ETH-USD", "BTC": "BTC-USD", "SOL": "SOL-USD", "XRP": "XRP-USD",
                  "ADA": "ADA-USD", "DOGE": "DOGE-USD", "XLM": "XLM-USD", "USDC": "USDC-USD"}


@bp.route("/api/sparklines")
def api_sparklines():
    """Return intraday price data for multiple symbols in one request.
    Uses 1-day period with 5-minute intervals for detailed daily view.
    Falls back to 5-day daily data if intraday is unavailable.
    Pass crypto=ETH,BTC to map those symbols to ETH-USD, BTC-USD for yfinance."""
    import yfinance as yf
    from flask import jsonify
    symbols = request.args.get("symbols", "GC=F,SI=F,BTC-USD,SPY").split(",")
    crypto_param = request.args.get("crypto", "")
    crypto_set = {s.strip().upper() for s in crypto_param.split(",") if s.strip()}
    result = {}
    TARGET_POINTS = 78  # normalize all sparklines to ~78 points (like regular market hours)
    for sym in symbols[:20]:  # limit to 20 symbols
        sym = sym.strip()
        yf_sym = (_CRYPTO_YF_MAP.get(sym.upper()) or sym + "-USD") if sym.upper() in crypto_set else sym
        try:
            t = yf.Ticker(yf_sym)
            # Try intraday first (5-min intervals over 1 day)
            h = t.history(period="1d", interval="5m")
            if h is not None and len(h) > 5:
                points = [round(float(row["Close"]), 2) for _, row in h.iterrows()]
                # Downsample to TARGET_POINTS if too many (futures/crypto have extended hours)
                if len(points) > TARGET_POINTS * 1.5:
                    step = len(points) / TARGET_POINTS
                    points = [points[int(i * step)] for i in range(TARGET_POINTS)]
                result[sym] = points
            else:
                # Fallback to 5-day daily
                h = t.history(period="5d")
                if h is not None and len(h) > 0:
                    result[sym] = [round(float(row["Close"]), 2) for _, row in h.iterrows()]
                else:
                    result[sym] = []
        except Exception:
            result[sym] = []
    return jsonify(result)

@bp.route("/api/historical")
def api_historical():
    """Return historical OHLC(V) price data for charting.
    Params: symbol, period, interval (optional, for intraday), type (stock|crypto)."""
    import yfinance as yf
    from flask import jsonify
    symbol = request.args.get("symbol", "GC=F")
    period = request.args.get("period", "1mo")
    interval = request.args.get("interval", "")
    asset_type = request.args.get("type", "stock")

    ALLOWED_PERIODS = {"1d", "5d", "1mo", "3mo", "6mo", "1y", "5y", "max"}
    ALLOWED_INTERVALS = {"1m", "2m", "5m", "15m", "30m", "60m", "1h", "1d", "5d", "1wk", "1mo"}
    if period not in ALLOWED_PERIODS:
        period = "1mo"
    if interval and interval not in ALLOWED_INTERVALS:
        interval = ""

    yf_symbol = symbol
    if asset_type == "crypto":
        yf_symbol = _CRYPTO_YF_MAP.get(symbol.upper()) or (symbol.upper() + "-USD")

    is_intraday = interval in ("1m", "2m", "5m", "15m", "30m", "60m", "1h")
    date_fmt = "%Y-%m-%dT%H:%M" if is_intraday else "%Y-%m-%d"

    try:
        if symbol == "10Y2Y-SPREAD":
            t10 = yf.Ticker("^TNX")
            t2 = yf.Ticker("2YY=F")
            kw = {"period": period}
            if interval:
                kw["interval"] = interval
            h10 = t10.history(**kw)
            h2 = t2.history(**kw)
            if h10 is None or h2 is None or len(h10) == 0 or len(h2) == 0:
                return jsonify({"error": "No data for spread", "symbol": symbol, "period": period}), 404
            h10 = h10.copy()
            h2 = h2.copy()
            h10["date_str"] = h10.index.strftime(date_fmt)
            h2["date_str"] = h2.index.strftime(date_fmt)
            h10_dict = h10.set_index("date_str").to_dict("index")
            h2_dict = h2.set_index("date_str").to_dict("index")
            data = []
            prev_c = None
            for date_str in sorted(h10_dict.keys()):
                if date_str in h2_dict:
                    r10, r2 = h10_dict[date_str], h2_dict[date_str]
                    c = round(float(r10["Close"]) - float(r2["Close"]), 3)
                    o = round(float(r10["Open"]) - float(r2["Open"]), 3)
                    h = round(float(r10["High"]) - float(r2["Low"]), 3)
                    l = round(float(r10["Low"]) - float(r2["High"]), 3)
                    if is_intraday and prev_c is not None and o == c == h == l == prev_c:
                        continue
                    prev_c = c
                    data.append({"date": date_str, "o": o, "h": h, "l": l, "c": c})
            return jsonify({"symbol": symbol, "period": period, "interval": interval, "data": data})

        if symbol == "AUAG-RATIO":
            tg = yf.Ticker("GC=F")
            ts = yf.Ticker("SI=F")
            kw = {"period": period}
            if interval:
                kw["interval"] = interval
            hg = tg.history(**kw)
            hs = ts.history(**kw)
            if hg is None or hs is None or len(hg) == 0 or len(hs) == 0:
                return jsonify({"error": "No data for ratio", "symbol": symbol, "period": period}), 404
            hg = hg.copy()
            hs = hs.copy()
            hg["date_str"] = hg.index.strftime(date_fmt)
            hs["date_str"] = hs.index.strftime(date_fmt)
            hg_dict = hg.set_index("date_str").to_dict("index")
            hs_dict = hs.set_index("date_str").to_dict("index")
            data = []
            prev_c = None
            for date_str in sorted(hg_dict.keys()):
                if date_str in hs_dict:
                    gc, sc = float(hg_dict[date_str]["Close"]), float(hs_dict[date_str]["Close"])
                    go, so = float(hg_dict[date_str]["Open"]), float(hs_dict[date_str]["Open"])
                    if sc > 0 and so > 0:
                        c = round(gc / sc, 2)
                        o = round(go / so, 2)
                        h = round(gc / sc * 1.01, 2)
                        l = round(gc / sc * 0.99, 2)
                        if is_intraday and prev_c is not None and o == c == h == l == prev_c:
                            continue
                        prev_c = c
                        data.append({"date": date_str, "o": o, "h": h, "l": l, "c": c})
            return jsonify({"symbol": symbol, "period": period, "interval": interval, "data": data})

        ticker = yf.Ticker(yf_symbol)
        kw = {"period": period}
        if interval:
            kw["interval"] = interval
        hist = ticker.history(**kw)
        if hist is None or len(hist) == 0:
            return jsonify({"error": "No data", "symbol": symbol, "period": period}), 404
        data = []
        prev_c = None
        for idx, row in hist.iterrows():
            o = round(float(row["Open"]), 2) if row["Open"] else None
            h = round(float(row["High"]), 2) if row["High"] else None
            l = round(float(row["Low"]), 2) if row["Low"] else None
            c = round(float(row["Close"]), 2) if row["Close"] else None
            # Skip flat bars during market-closed hours (OHLC all equal to previous close)
            if is_intraday and prev_c is not None and o == c == h == l == prev_c:
                continue
            prev_c = c
            entry = {"date": idx.strftime(date_fmt), "o": o, "h": h, "l": l, "c": c}
            if "Volume" in row and row["Volume"]:
                entry["v"] = int(row["Volume"])
            data.append(entry)
        return jsonify({"symbol": symbol, "period": period, "interval": interval, "data": data})
    except Exception as e:
        return jsonify({"error": str(e), "symbol": symbol, "period": period}), 500


@bp.route("/api/fred-data")
def api_fred_data():
    """Return FRED series data (cached). Query params: series_ids=ID1,ID2 optional; refresh=1 to force fetch."""
    from flask import jsonify
    import fred_manager
    config = load_config(CONFIG_PATH)
    api_keys = get_effective_api_keys(config)
    fred_key = os.environ.get("FRED_API_KEY") or api_keys.get("fred_api_key") or ""
    series_ids = request.args.get("series_ids", "")
    if series_ids:
        ids = [s.strip() for s in series_ids.split(",") if s.strip()]
    else:
        ids = fred_manager.ALL_FRED_SERIES
    refresh = request.args.get("refresh", "").lower() in ("1", "true", "yes")
    max_age = 1 if refresh else 24  # 1 hour effective refresh when refresh=1
    horizon = request.args.get("horizon", "1y").lower()
    if horizon == "max":
        max_points_daily, max_points_other = 3780, 600  # ~15y daily (captures 2008, 2020 stress), ~50y monthly
    elif horizon == "5y":
        max_points_daily, max_points_other = 1260, 60  # ~5y daily, ~5y monthly
    else:
        max_points_daily, max_points_other = 252, 120  # ~1y daily, ~10y monthly
    daily_series = set(fred_manager.YIELD_CURVE_SERIES + fred_manager.CREDIT_SERIES + fred_manager.REAL_YIELDS_SERIES)
    result = {}
    for sid in ids[:50]:
        if refresh:
            data = fred_manager.fetch_series(sid, fred_key)
            if data:
                fred_manager.set_fred_series(BASE, sid, data)
        else:
            data = fred_manager.get_series_cached(sid, fred_key, BASE, max_age_hours=max_age)
        # Trim to keep response fast
        max_pts = max_points_daily if sid in daily_series else max_points_other
        if data and len(data) > max_pts:
            data = data[-max_pts:]
        # Sanitize NaN/Inf values (invalid JSON) from cached or freshly fetched data
        import math
        if data:
            data = [{"date": p["date"], "value": p["value"] if p.get("value") is not None and not (isinstance(p["value"], float) and (math.isnan(p["value"]) or math.isinf(p["value"]))) else None} for p in data]
        entry = fred_manager.get_fred_cache(BASE).get(sid, {})
        result[sid] = {"data": data, "updated": entry.get("updated")}
    return jsonify(result)


@bp.route("/api/save-contributions", methods=["POST"])
def api_save_contributions():
    """Save monthly investment contributions."""
    from flask import jsonify
    config = load_config(CONFIG_PATH)
    monthly = config.get("monthly_investments", {})
    contributions = monthly.get("contributions", {})
    
    data = request.get_json() or {}
    for key, value in data.items():
        if key in contributions:
            contributions[key] = float(value) if value else 0
    
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
    
    return jsonify({"success": True})

# Phase 2: Transaction tracking
@bp.route("/api/add-transaction", methods=["POST"])
def api_add_transaction():
    """Add a spending transaction."""
    from flask import jsonify
    config = load_config(CONFIG_PATH)
    txns = config.get("transactions", [])
    data = request.get_json() or {}
    txn = {
        "date": data.get("date", datetime.now().strftime("%Y-%m-%d")),
        "category": data.get("category", "Other"),
        "amount": float(data.get("amount", 0)),
        "note": data.get("note", "")
    }
    txns.append(txn)
    config["transactions"] = txns

    # Update spending history
    month_key = txn["date"][:7]
    history = config.get("spending_history", {})
    if month_key not in history:
        history[month_key] = {}
    cat = txn["category"]
    history[month_key][cat] = history[month_key].get(cat, 0) + txn["amount"]
    config["spending_history"] = history

    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
    return jsonify({"success": True})

# Phase 3: Price alerts
@bp.route("/api/price-alerts", methods=["GET", "POST", "DELETE"])
def api_price_alerts():
    """Manage price alerts."""
    from flask import jsonify
    config = load_config(CONFIG_PATH)
    alerts = config.get("price_alerts", [])
    if request.method == "POST":
        data = request.get_json() or {}
        alerts.append({
            "symbol": data.get("symbol", ""),
            "target": float(data.get("target", 0)),
            "direction": data.get("direction", "above"),
            "triggered": False
        })
        config["price_alerts"] = alerts
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
        return jsonify({"success": True})
    elif request.method == "DELETE":
        idx = request.args.get("idx")
        if idx is not None and int(idx) < len(alerts):
            alerts.pop(int(idx))
            config["price_alerts"] = alerts
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)
        return jsonify({"success": True})
    return jsonify(alerts)

# Phase 4: PWA manifest
@bp.route("/manifest.json")
def manifest():
    from flask import jsonify
    return jsonify({
        "name": "Nickel&Dime",
        "short_name": "Nickel&Dime",
        "description": "Your unified financial command center",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#09090b",
        "theme_color": "#09090b",
        "icons": [
            {"src": "/icon-192.png", "sizes": "192x192", "type": "image/png"},
            {"src": "/icon-512.png", "sizes": "512x512", "type": "image/png"}
        ]
    })

@bp.route("/favicon.ico")
@bp.route("/apple-touch-icon.png")
@bp.route("/icon-192.png")
@bp.route("/icon-512.png")
@bp.route("/logo-sidebar.png")
def serve_icon():
    """Serve icon/image files from the project root."""
    from flask import send_from_directory
    filename = request.path.lstrip("/")
    return send_from_directory(BASE, filename)

@bp.route("/sw.js")
def service_worker():
    """Basic service worker for PWA."""
    from flask import Response
    sw = """
self.addEventListener('install', function(e) { self.skipWaiting(); });
self.addEventListener('activate', function(e) { clients.claim(); });
self.addEventListener('fetch', function(e) {
  e.respondWith(fetch(e.request).catch(function() {
return new Response('Offline - please reconnect', { headers: { 'Content-Type': 'text/html' }});
  }));
});
"""
    return Response(sw, mimetype="application/javascript")

@bp.route("/api/tab-content/<tab>")
def api_tab_content(tab):
    """Return rendered HTML for a single tab (lazy loading)."""
    from flask import Response
    valid_tabs = {"summary", "balances", "budget", "holdings", "import", "history", "economics"}
    if tab not in valid_tabs:
        return Response("Not found", status=404)
    if tab == "economics":
        from dashboard import render_economics_fragment_html
        return Response(render_economics_fragment_html(), mimetype="text/html",
                        headers={"Cache-Control": "public, max-age=3600"})
    config = load_config(CONFIG_PATH)
    data = get_dashboard_data_cached(BASE, config)
    full_html = render_dashboard(data, active_tab=tab)
    start_m = f"<!-- TAB:{tab} -->"
    end_m = f"<!-- /TAB:{tab} -->"
    si = full_html.find(start_m)
    ei = full_html.find(end_m)
    if si != -1 and ei != -1:
        return Response(full_html[si + len(start_m):ei], mimetype="text/html")
    return Response("Tab content not found", status=404)


@bp.route("/api/budget-data")
def api_budget_data():
    """Return transaction/budget data for lazy initialization of the budget tab."""
    from flask import jsonify
    config = load_config(CONFIG_PATH)
    budget = config.get("budget", {})
    categories = budget.get("categories", [])
    return jsonify({
        "transactions": config.get("transactions", []),
        "budget_limits": {c.get("name", ""): float(c.get("limit", 0) or 0) for c in categories},
        "budget_cats": [c.get("name", "") for c in categories],
        "recurring": config.get("recurring_transactions", []),
        "spending_history": config.get("spending_history", {}),
        "dividends": config.get("dividends", []),
    })


# Phase 4: Export API
@bp.route("/api/export")
def api_export():
    """Export full portfolio data as JSON."""
    from flask import jsonify
    config = load_config(CONFIG_PATH)
    data = get_dashboard_data(BASE, config, verbose=False)
    export = {
        "exported_at": datetime.now().isoformat(),
        "total": data.get("total", 0),
        "buckets": data.get("buckets", {}),
        "holdings": [{
            "ticker": h.get("ticker"),
            "account": h.get("account"),
            "asset_class": h.get("asset_class"),
            "qty": h.get("qty"),
            "value": h.get("value", 0)
        } for h in data.get("holdings", [])],
        "blended_accounts": config.get("blended_accounts", []),
        "crypto_holdings": config.get("crypto_holdings", []),
        "budget": config.get("budget", {}),
        "monthly_investments": config.get("monthly_investments", {}),
        "price_history": data.get("price_history", [])[-30:],
    }
    return jsonify(export)

@bp.route("/api/new-month", methods=["POST"])
def api_new_month():
    """Start a new month - reset all investment contributions to 0."""
    from flask import jsonify
    from datetime import datetime
    config = load_config(CONFIG_PATH)
    monthly = config.get("monthly_investments", {})
    budget = config.get("budget", {})
    
    new_month = datetime.now().strftime("%Y-%m")
    
    # Update months
    monthly["month"] = new_month
    budget["month"] = new_month
    
    # Reset all contributions to 0
    contributions = monthly.get("contributions", {})
    for key in contributions:
        contributions[key] = 0
    
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
    
    return jsonify({"success": True, "month": new_month})

@bp.route("/api/new-budget-month", methods=["POST"])
def api_new_budget_month():
    """Start a new budget month - updates both budget and investment months, resets contributions."""
    from flask import jsonify
    from datetime import datetime
    config = load_config(CONFIG_PATH)
    monthly = config.get("monthly_investments", {})
    budget = config.get("budget", {})
    
    new_month = datetime.now().strftime("%Y-%m")
    
    # Update both months
    monthly["month"] = new_month
    budget["month"] = new_month
    
    # Reset investment contributions to 0
    contributions = monthly.get("contributions", {})
    for key in contributions:
        contributions[key] = 0
    
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
    
    return jsonify({"success": True, "month": new_month})

@bp.route("/save/balances", methods=["POST"])
def save_balances():
    config = load_config(CONFIG_PATH)
    blended = config.get("blended_accounts", [])
    for b in blended:
        name = b.get("name", "")
        key = "bal_" + name.replace(" ", "_")
        if key in request.form:
            try:
                val = request.form[key].replace(",", "").strip() or "0"
                b["value"] = round(float(val), 2)
            except ValueError:
                pass
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
    append_history_log("Balances updated", "Blended account values saved from dashboard")
    run_price_update(config, fetch_metals=False)
    return redirect("/?saved=Balances&tab=balances")

@bp.route("/save/budget", methods=["POST"])
def save_budget():
    config = load_config(CONFIG_PATH)
    budget = config.get("budget", {})
    try:
        budget["monthly_income"] = float(request.form.get("monthly_income", "0").replace(",", "") or "0")
    except ValueError:
        budget["monthly_income"] = 0
    categories = budget.get("categories", [])
    for i, cat in enumerate(categories):
        key = f"cat_{i}"
        if key in request.form:
            try:
                cat["limit"] = float(request.form[key].replace(",", "").strip() or "0")
            except ValueError:
                cat["limit"] = 0
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
    append_history_log("Budget updated", "Monthly income and category limits saved from dashboard")
    run_price_update(config, fetch_metals=False)
    return redirect("/?saved=Budget&tab=budget")

@bp.route("/save/debts", methods=["POST"])
def save_debts():
    config = load_config(CONFIG_PATH)
    debts = []
    i = 0
    while True:
        name_key = f"debt_name_{i}"
        bal_key = f"debt_bal_{i}"
        pmt_key = f"debt_pmt_{i}"
        if name_key not in request.form:
            break
        name = request.form.get(name_key, "").strip()
        if not name:
            i += 1
            continue
        try:
            balance = float(request.form.get(bal_key, "0").replace(",", "") or "0")
        except ValueError:
            balance = 0
        try:
            payment = float(request.form.get(pmt_key, "0").replace(",", "") or "0")
        except ValueError:
            payment = 0
        debts.append({"name": name, "balance": balance, "monthly_payment": payment})
        i += 1
    config["debts"] = debts
    save_config(CONFIG_PATH, config)
    append_history_log("Debts updated", f"Saved {len(debts)} debts, total: ${sum(d['balance'] for d in debts):,.0f}")
    return redirect("/?saved=Debts&tab=budget")

@bp.route("/import/csv", methods=["POST"])
def import_csv_route():
    source = request.form.get("source", "fidelity").strip()
    file = request.files.get("csv_file")
    if not file or not file.filename or not file.filename.lower().endswith(".csv"):
        return redirect("/?saved=Please select a CSV file&tab=import")
    tmp = BASE / "tmp_upload.csv"
    try:
        file.save(str(tmp))
        updated, msg = import_csv(CONFIG_PATH, tmp, source)
    finally:
        if tmp.exists():
            tmp.unlink()
    if updated:
        config = load_config(CONFIG_PATH)
        append_history_log("CSV import", f"{msg} (source: {source})")
        run_price_update(config, fetch_metals=False)
    return redirect("/?saved=" + quote(msg) + "&tab=import")

@bp.route("/api/statement-preview", methods=["POST"])
def api_statement_preview():
    """Parse a bank/CC statement (CSV or PDF) and return preview of transactions for review."""
    from flask import jsonify
    from csv_import import parse_statement
    file = request.files.get("statement_file")
    if not file or not file.filename:
        return jsonify({"error": "No file uploaded"}), 400
    ext = Path(file.filename).suffix.lower()
    if ext not in (".csv", ".pdf"):
        return jsonify({"error": "Unsupported file type. Please upload a CSV or PDF."}), 400
    tmp = BASE / f"tmp_statement{ext}"
    try:
        file.save(str(tmp))
        transactions = parse_statement(tmp)
    finally:
        if tmp.exists():
            tmp.unlink()
    if not transactions:
        return jsonify({"error": f"No transactions found. Make sure the {'CSV has Date and Description columns' if ext == '.csv' else 'PDF contains a transaction table'}."}), 400
    # Summarize by category
    cat_totals = {}
    for t in transactions:
        cat_totals[t["category"]] = cat_totals.get(t["category"], 0) + t["amount"]
    return jsonify({
        "transactions": transactions[:200],
        "total_count": len(transactions),
        "total_amount": round(sum(t["amount"] for t in transactions), 2),
        "by_category": cat_totals
    })

@bp.route("/import/statement", methods=["POST"])
def import_statement_route():
    """Import bank/CC statement transactions (CSV or PDF) into the budget tracker."""
    from flask import jsonify
    file = request.files.get("statement_file")
    if not file or not file.filename:
        return redirect("/?saved=No file selected&tab=import")

    # Get category overrides from form
    overrides_json = request.form.get("category_overrides", "{}")
    try:
        category_overrides = json.loads(overrides_json)
    except (json.JSONDecodeError, TypeError):
        category_overrides = {}

    ext = Path(file.filename).suffix.lower()
    tmp = BASE / f"tmp_statement{ext}"
    try:
        file.save(str(tmp))
        added, transactions, msg = import_statement(CONFIG_PATH, tmp, category_overrides)
    finally:
        if tmp.exists():
            tmp.unlink()

    if added > 0:
        append_history_log("Statement import", msg)
    return redirect("/?saved=" + quote(msg) + "&tab=budget&detect_recurring=1")

@bp.route("/import/statement-batch", methods=["POST"])
def import_statement_batch():
    """Import pre-parsed transactions (from multi-file preview) into the budget tracker."""
    from flask import jsonify
    data = request.get_json(force=True)
    transactions = data.get("transactions", [])
    category_overrides = data.get("category_overrides", {})

    if not transactions:
        return jsonify({"success": False, "error": "No transactions to import"}), 400

    # Apply category overrides
    for txn in transactions:
        desc = txn.get("description", "")
        if desc in category_overrides:
            txn["category"] = category_overrides[desc]

    # Load config and add transactions
    config = load_config(CONFIG_PATH)
    existing_txns = config.get("transactions", [])
    spending_history = config.get("spending_history", {})
    # Save pre-import snapshot for undo
    pre_import_txn_count = len(existing_txns)

    added = 0
    for txn in transactions:
        # Dedup
        is_dup = any(
            t.get("date") == txn.get("date") and
            t.get("note", "").lower() == txn.get("description", "").lower() and
            abs(t.get("amount", 0) - txn.get("amount", 0)) < 0.01
            for t in existing_txns
        )
        if is_dup:
            continue

        entry = {
            "date": txn.get("date", ""),
            "category": txn.get("category", "Other"),
            "amount": txn.get("amount", 0),
            "note": txn.get("description", "")
        }
        existing_txns.append(entry)
        added += 1

        # Update spending history
        month_key = txn.get("date", "")[:7]
        if month_key:
            if month_key not in spending_history:
                spending_history[month_key] = {}
            cat = txn.get("category", "Other")
            spending_history[month_key][cat] = spending_history[month_key].get(cat, 0) + txn.get("amount", 0)

    config["transactions"] = existing_txns
    config["spending_history"] = spending_history
    # Save undo snapshot: store what was added so it can be reversed
    config["_last_import"] = {
        "count": added,
        "timestamp": datetime.now().isoformat(),
        "transaction_count_before": pre_import_txn_count,
    }
    save_config(CONFIG_PATH, config)

    msg = f"Imported {added} new transactions ({len(transactions)} total parsed, {len(transactions) - added} duplicates skipped)."
    if added > 0:
        append_history_log("Statement batch import", msg)

    return jsonify({
        "success": True,
        "message": msg,
        "added": added,
        "detect_recurring": added > 0
    })

@bp.route("/api/undo-import", methods=["POST"])
def api_undo_import():
    """Undo the last statement import by removing the added transactions."""
    from flask import jsonify
    config = load_config(CONFIG_PATH)
    last_import = config.get("_last_import")
    if not last_import or last_import.get("count", 0) == 0:
        return jsonify({"success": False, "error": "No import to undo."})

    count_before = last_import.get("transaction_count_before", 0)
    txns = config.get("transactions", [])
    removed = len(txns) - count_before

    # Trim transactions back to pre-import state
    config["transactions"] = txns[:count_before]

    # Rebuild spending history from remaining transactions
    spending_history = {}
    for t in config["transactions"]:
        mk = t.get("date", "")[:7]
        if mk:
            if mk not in spending_history:
                spending_history[mk] = {}
            cat = t.get("category", "Other")
            spending_history[mk][cat] = spending_history[mk].get(cat, 0) + t.get("amount", 0)
    config["spending_history"] = spending_history

    # Clear undo state
    config.pop("_last_import", None)
    config.pop("_spending_history_backup", None)
    save_config(CONFIG_PATH, config)

    return jsonify({"success": True, "removed": removed, "message": f"Undid last import: removed {removed} transactions."})

@bp.route("/api/clear-transactions", methods=["POST"])
def api_clear_transactions():
    """Clear ALL transactions and spending history. Nuclear option."""
    from flask import jsonify
    config = load_config(CONFIG_PATH)
    count = len(config.get("transactions", []))
    config["transactions"] = []
    config["spending_history"] = {}
    config.pop("_last_import", None)
    config.pop("_spending_history_backup", None)
    save_config(CONFIG_PATH, config)
    return jsonify({"success": True, "message": f"Cleared all {count} transactions and reset spending history."})

# ── Recurring Transactions API ──
@bp.route("/api/recurring", methods=["GET", "POST", "DELETE"])
def api_recurring():
    from flask import jsonify
    config = load_config(CONFIG_PATH)
    recurring = config.get("recurring_transactions", [])
    if request.method == "POST":
        data = request.get_json(force=True)
        recurring.append({
            "name": data.get("name", ""),
            "amount": float(data.get("amount", 0)),
            "category": data.get("category", "Other"),
            "frequency": data.get("frequency", "monthly"),
        })
        config["recurring_transactions"] = recurring
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
        return jsonify({"ok": True})
    elif request.method == "DELETE":
        idx = int(request.args.get("idx", -1))
        if 0 <= idx < len(recurring):
            recurring.pop(idx)
            config["recurring_transactions"] = recurring
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)
        return jsonify({"ok": True})
    return jsonify(recurring)

@bp.route("/api/recurring/apply", methods=["POST"])
def api_recurring_apply():
    """Apply all recurring transactions as manual transactions for the current month."""
    from flask import jsonify
    config = load_config(CONFIG_PATH)
    recurring = config.get("recurring_transactions", [])
    if not recurring:
        return jsonify({"ok": False, "error": "No recurring transactions configured."})
    transactions = config.get("transactions", [])
    spending_history = config.get("spending_history", {})
    now = datetime.now()
    current_month = now.strftime("%Y-%m")
    count = 0
    for rt in recurring:
        freq = rt.get("frequency", "monthly")
        # For monthly, apply once; weekly x4, biweekly x2, quarterly check if applicable, yearly check
        if freq == "monthly":
            multiplier = 1
        elif freq == "weekly":
            multiplier = 4
        elif freq == "biweekly":
            multiplier = 2
        elif freq == "quarterly":
            if now.month % 3 != 1:
                continue
            multiplier = 1
        elif freq == "yearly":
            if now.month != 1:
                continue
            multiplier = 1
        else:
            multiplier = 1
        for _ in range(multiplier):
            txn = {
                "date": now.strftime("%Y-%m-%d"),
                "category": rt.get("category", "Other"),
                "amount": rt.get("amount", 0),
                "note": f"[Recurring] {rt.get('name', '')}",
            }
            transactions.append(txn)
            count += 1
            # Update spending history
            if current_month not in spending_history:
                spending_history[current_month] = {}
            cat = txn["category"]
            spending_history[current_month][cat] = spending_history[current_month].get(cat, 0) + txn["amount"]
    config["transactions"] = transactions
    config["spending_history"] = spending_history
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
    return jsonify({"ok": True, "count": count})

# ── Goal Tracking API ──
@bp.route("/api/goals", methods=["GET", "POST", "DELETE"])
def api_goals():
    from flask import jsonify
    config = load_config(CONFIG_PATH)
    goals = config.get("financial_goals", [])
    if request.method == "POST":
        data = request.get_json(force=True)
        goals.append({
            "name": data.get("name", ""),
            "target": float(data.get("target", 0)),
            "current": float(data.get("current", 0)),
            "target_date": data.get("target_date", ""),
        })
        config["financial_goals"] = goals
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
        return jsonify({"ok": True})
    elif request.method == "DELETE":
        idx = int(request.args.get("idx", -1))
        if 0 <= idx < len(goals):
            goals.pop(idx)
            config["financial_goals"] = goals
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)
        return jsonify({"ok": True})
    return jsonify(goals)

@bp.route("/api/goals/update", methods=["POST"])
def api_goals_update():
    from flask import jsonify
    config = load_config(CONFIG_PATH)
    goals = config.get("financial_goals", [])
    data = request.get_json(force=True)
    idx = int(data.get("idx", -1))
    if 0 <= idx < len(goals):
        goals[idx]["current"] = float(data.get("current", goals[idx].get("current", 0)))
        config["financial_goals"] = goals
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
        return jsonify({"ok": True})
    return jsonify({"ok": False}), 400

# ── FX Rate API ──
@bp.route("/api/fx-rate")
def api_fx_rate():
    from flask import jsonify
    to_currency = request.args.get("to", "EUR").upper()
    if to_currency == "USD":
        return jsonify({"rate": 1.0, "from": "USD", "to": "USD"})
    try:
        import yfinance as yf
        pair = f"USD{to_currency}=X"
        ticker = yf.Ticker(pair)
        hist = ticker.history(period="5d")
        if hist is not None and len(hist) > 0:
            rate = float(hist["Close"].iloc[-1])
            return jsonify({"rate": round(rate, 6), "from": "USD", "to": to_currency})
    except Exception:
        pass
    # Fallback rates (approximate)
    fallback = {"EUR": 0.92, "GBP": 0.79, "JPY": 149.5, "CAD": 1.36, "AUD": 1.53, "CHF": 0.88}
    rate = fallback.get(to_currency, 1.0)
    return jsonify({"rate": rate, "from": "USD", "to": to_currency, "fallback": True})

@bp.route("/api/recurring/detect", methods=["GET"])
def api_recurring_detect():
    """Scan transaction history for recurring patterns and suggest new recurring items."""
    from flask import jsonify
    config = load_config(CONFIG_PATH)
    transactions = config.get("transactions", [])
    existing_recurring = config.get("recurring_transactions", [])
    suggestions = detect_recurring_transactions(transactions, existing_recurring)
    return jsonify({"suggestions": suggestions})

# ── Dividends & Fees API ──
@bp.route("/api/dividends", methods=["GET", "POST"])
def api_dividends():
    from flask import jsonify
    config = load_config(CONFIG_PATH)
    dividends = config.get("dividends", [])
    if request.method == "POST":
        data = request.get_json(force=True)
        dividends.append({
            "date": data.get("date", datetime.now().strftime("%Y-%m-%d")),
            "ticker": data.get("ticker", "").upper(),
            "amount": float(data.get("amount", 0)),
            "type": data.get("type", "dividend"),
            "note": data.get("note", ""),
        })
        config["dividends"] = dividends
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
        return jsonify({"ok": True})
    return jsonify(dividends)

@bp.route("/save/holdings", methods=["POST"])
def save_holdings():
    config = load_config(CONFIG_PATH)
    accounts = request.form.getlist("h_account")
    tickers = request.form.getlist("h_ticker")
    asset_classes = request.form.getlist("h_asset_class")
    qtys = request.form.getlist("h_qty")
    value_overrides = request.form.getlist("h_value_override")
    notes = request.form.getlist("h_notes")
    new_holdings = []
    for i in range(len(accounts)):
        acc = (accounts[i] or "").strip()
        tick = (tickers[i] or "").strip()
        if not acc and not tick:
            continue
        ac = (asset_classes[i] or "Equities").strip()
        try:
            qty = float(qtys[i].replace(",", "").strip()) if qtys[i] and qtys[i].strip() else None
        except (ValueError, TypeError):
            qty = None
        try:
            vo = float(value_overrides[i].replace(",", "").strip()) if value_overrides[i] and value_overrides[i].strip() else None
        except (ValueError, TypeError):
            vo = None
        new_holdings.append({
            "account": acc or "Fidelity",
            "ticker": tick or "",
            "asset_class": ac or "Equities",
            "qty": qty,
            "value_override": vo,
            "notes": (notes[i] or "").strip(),
        })
    config["holdings"] = new_holdings
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
    append_history_log("Holdings updated", f"{len(new_holdings)} positions saved from dashboard")
    run_price_update(config, fetch_metals=False)
    return redirect("/?saved=Holdings&tab=holdings")

@bp.route("/api/quick-update", methods=["POST"])
def api_quick_update():
    """Update a holding value or balance from the investment chat.
    Accepts {amount, target, account (optional)}.
    For holdings with qty: adds shares (amount / current_price).
    For holdings without qty (value-only like SPAXX): adds to value_override.
    For blended accounts: adds to value.
    Returns what was updated so the frontend can display confirmation."""
    from flask import jsonify
    data = request.get_json(force=True)
    amount = float(data.get("amount", 0))
    target = (data.get("target", "") or "").strip()
    account = (data.get("account", "") or "").strip()
    if not target or amount == 0:
        return jsonify({"ok": False, "error": "Missing target or amount"})

    config = load_config(CONFIG_PATH)
    target_upper = target.upper()
    target_lower = target.lower()

    # 1) Try to match a holding by ticker
    holdings = config.get("holdings", [])
    matched_holding = None
    for h in holdings:
        ticker = (h.get("ticker") or "").upper()
        if ticker == target_upper:
            # If account specified, also match account
            if account and account.lower() not in (h.get("account") or "").lower():
                continue
            matched_holding = h
            break

    if matched_holding:
        ticker = matched_holding.get("ticker", "")
        qty = matched_holding.get("qty")
        has_qty = qty is not None and float(qty) > 0

        if has_qty:
            # Has shares — add more shares: new_shares = amount / current_price
            price_cache = load_price_cache(BASE)
            stock_prices = price_cache.get("stocks", {})
            crypto_prices = price_cache.get("crypto", {})
            metals_prices = price_cache.get("metals", {})
            # Check stocks first, then crypto, then metals
            current_price = stock_prices.get(ticker) or stock_prices.get(ticker.upper())
            if not current_price or current_price <= 0:
                current_price = crypto_prices.get(ticker.upper()) or crypto_prices.get(ticker.lower())
            if not current_price or current_price <= 0:
                current_price = metals_prices.get(ticker.upper())
            if not current_price or current_price <= 0:
                return jsonify({"ok": False, "error": f"No live price for {ticker} — can't calculate shares"})
            new_shares = round(amount / current_price, 3)
            old_qty = float(qty)
            new_qty = round(old_qty + new_shares, 3)
            old_value = round(old_qty * current_price, 2)
            new_value = round(new_qty * current_price, 2)
            matched_holding["qty"] = new_qty
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)
            return jsonify({
                "ok": True,
                "type": "holding",
                "ticker": ticker,
                "account": matched_holding.get("account"),
                "old_value": old_value,
                "new_value": new_value,
                "shares_added": new_shares,
                "new_qty": new_qty,
                "price": current_price,
            })
        else:
            # Value-only position (no qty, e.g. SPAXX cash) — add to value_override
            old_val = float(matched_holding.get("value_override") or 0)
            matched_holding["value_override"] = round(old_val + amount, 2)
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)
            return jsonify({
                "ok": True,
                "type": "holding",
                "ticker": ticker,
                "account": matched_holding.get("account"),
                "old_value": old_val,
                "new_value": matched_holding["value_override"],
            })

    # 2) Try to match a blended account by name
    blended = config.get("blended_accounts", [])
    matched_account = None
    for b in blended:
        name = (b.get("name") or "").lower()
        if target_lower in name or name in target_lower:
            matched_account = b
            break

    if matched_account:
        old_val = float(matched_account.get("value") or 0)
        matched_account["value"] = round(old_val + amount, 2)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
        return jsonify({
            "ok": True,
            "type": "balance",
            "name": matched_account.get("name"),
            "old_value": old_val,
            "new_value": matched_account["value"],
        })

    return jsonify({"ok": False, "error": f"No holding or account found for '{target}'"})


@bp.route("/api/physical-metals", methods=["GET", "POST", "DELETE"])
def api_physical_metals():
    """CRUD for physical metals purchases."""
    from flask import jsonify
    config = load_config(CONFIG_PATH)

    # One-time migration: move legacy inputs fields into physical_metals array
    if "physical_metals" not in config:
        config["physical_metals"] = []
        inp = config.get("inputs", {})
        gold_oz = float(inp.get("physical_gold_oz", 0))
        silver_oz = float(inp.get("physical_silver_oz", 0))
        if gold_oz > 0:
            config["physical_metals"].append({
                "metal": "Gold",
                "form": "Migrated",
                "qty_oz": gold_oz,
                "cost_per_oz": 0,
                "date": "",
                "note": "Migrated from legacy settings",
            })
        if silver_oz > 0:
            config["physical_metals"].append({
                "metal": "Silver",
                "form": "Migrated",
                "qty_oz": silver_oz,
                "cost_per_oz": 0,
                "date": "",
                "note": "Migrated from legacy settings",
            })
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)

    metals = config.get("physical_metals", [])

    if request.method == "GET":
        return jsonify(metals)

    if request.method == "DELETE":
        data = request.get_json(force=True)
        idx = int(data.get("index", -1))
        if 0 <= idx < len(metals):
            removed = metals.pop(idx)
            config["physical_metals"] = metals
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)
            return jsonify({"ok": True, "removed": removed})
        return jsonify({"ok": False, "error": "Invalid index"}), 400

    # POST — add a new purchase
    data = request.get_json(force=True)
    entry = {
        "metal": data.get("metal", "Gold").capitalize(),
        "form": data.get("form", ""),
        "qty_oz": round(float(data.get("qty_oz", 0)), 4),
        "cost_per_oz": round(float(data.get("cost_per_oz", 0)), 2),
        "date": data.get("date", datetime.now().strftime("%Y-%m-%d")),
        "note": data.get("note", ""),
    }
    metals.append(entry)
    config["physical_metals"] = metals
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
    return jsonify({"ok": True, "entry": entry, "total": len(metals)})


@bp.route("/api/auto-refresh", methods=["GET", "POST"])
def api_auto_refresh():
    """Get or update auto-refresh settings."""
    from flask import jsonify
    config = load_config(CONFIG_PATH)
    if request.method == "GET":
        auto_cfg = config.get("auto_refresh", {"enabled": True, "interval_minutes": 15})
        return jsonify(auto_cfg)
    else:
        data = request.get_json(force=True)
        auto_cfg = config.get("auto_refresh", {})
        if "enabled" in data:
            auto_cfg["enabled"] = bool(data["enabled"])
        if "interval_minutes" in data:
            mins = int(data["interval_minutes"])
            auto_cfg["interval_minutes"] = max(5, min(mins, 1440))  # 5 min to 24 hours
        config["auto_refresh"] = auto_cfg
        save_config(CONFIG_PATH, config)
        # Reschedule if scheduler is available
        if scheduler:
            try:
                scheduler.reschedule_job("auto_refresh", trigger="interval", minutes=auto_cfg.get("interval_minutes", 15))
                print(f"[Auto-refresh] Rescheduled to every {auto_cfg.get('interval_minutes', 15)} min")
            except Exception:
                pass
        return jsonify({"success": True, **auto_cfg})

