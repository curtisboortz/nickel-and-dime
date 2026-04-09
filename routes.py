"""Flask route handlers for the Nickel&Dime dashboard (Blueprint)."""

import json
import os
from datetime import datetime
from pathlib import Path
from urllib.parse import quote
import pandas as pd
from flask import Blueprint, request, redirect

bp = Blueprint("main", __name__)

# Module-level references, set by init_routes()
CONFIG_PATH = None
BASE = None
PROJECT_ROOT = None
AUTH_PIN = ""
_deps = {}  # all other dependencies


DEMO_MODE = False

def init_routes(config):
    """Inject dependencies from main(). Call before registering blueprint."""
    global CONFIG_PATH, BASE, PROJECT_ROOT, AUTH_PIN, DEMO_MODE, _deps, scheduler
    CONFIG_PATH = config["CONFIG_PATH"]
    BASE = config["BASE"]
    PROJECT_ROOT = config.get("PROJECT_ROOT", config["BASE"])
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
    """Load cached prices from price_cache.json (tolerant of partial writes)."""
    path = Path(base) / "price_cache.json"
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = f.read()
        return json.loads(raw)
    except json.JSONDecodeError:
        # File may have been partially written — try to salvage first JSON object
        try:
            decoder = json.JSONDecoder()
            obj, _ = decoder.raw_decode(raw)
            return obj
        except Exception:
            return {}
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
        return jsonify({"success": False, "error": "Demo mode: changes are disabled. Deploy your own instance to use all features."}), 403
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
@bp.route("/technical")
def index():
    config = load_config(CONFIG_PATH)
    # Use cached data for instant page load (no network calls)
    # Fresh prices are fetched in background via /api/bg-refresh
    data = get_dashboard_data_cached(BASE, config)
    saved = request.args.get("saved", "")
    # Determine active tab from URL path or query param
    path_tab = request.path.strip("/")
    tab_map = {"balances": "balances", "budget": "budget", "holdings": "holdings", "import": "import", "history": "history", "charts": "history", "economics": "economics", "technical": "technical"}
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
        "gold_oil_ratio": round(data.get("metals_prices", {}).get("GOLD", 0) / stock_prices_raw.get("CL=F", 1), 1) if data.get("metals_prices", {}).get("GOLD") and stock_prices_raw.get("CL=F") else None,
        "tnx_10y": data.get("treasury_yields", {}).get("tnx_10y"),
        "tnx_2y": data.get("treasury_yields", {}).get("tnx_2y"),
        "btc": data.get("crypto_prices", {}).get("BTC", 0),
        "spy": stock_prices_raw.get("SPY", 0),
        "dxy": stock_prices_raw.get("DX=F", 0),
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
    # Full crypto + stock price maps for holdings page live updates
    result["crypto_prices"] = crypto_prices
    result["stock_prices"] = stock_prices
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
            h = None
            # DXY: prefer spot index over futures for accurate intraday sparkline
            if yf_sym == "DX=F":
                try:
                    dl = yf.download("DX-Y.NYB", period="1d", interval="5m", progress=False)
                    if dl is not None and not dl.empty:
                        if isinstance(dl.columns, pd.MultiIndex):
                            dl.columns = dl.columns.droplevel("Ticker")
                        h = dl
                except Exception:
                    pass
            if h is None:
                t = yf.Ticker(yf_sym)
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
                t = yf.Ticker(yf_sym)
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

        if symbol in ("AUAG-RATIO", "GOLDOIL-RATIO"):
            num_ticker = "GC=F"
            den_ticker = "SI=F" if symbol == "AUAG-RATIO" else "CL=F"
            tn = yf.Ticker(num_ticker)
            td = yf.Ticker(den_ticker)
            kw = {"period": period}
            if interval:
                kw["interval"] = interval
            hn = tn.history(**kw)
            hd = td.history(**kw)
            if hn is None or hd is None or len(hn) == 0 or len(hd) == 0:
                return jsonify({"error": "No data for ratio", "symbol": symbol, "period": period}), 404
            hn = hn.copy()
            hd = hd.copy()
            hn["date_str"] = hn.index.strftime(date_fmt)
            hd["date_str"] = hd.index.strftime(date_fmt)
            hn_dict = hn.set_index("date_str").to_dict("index")
            hd_dict = hd.set_index("date_str").to_dict("index")
            data = []
            prev_c = None
            for date_str in sorted(hn_dict.keys()):
                if date_str in hd_dict:
                    nc, dc = float(hn_dict[date_str]["Close"]), float(hd_dict[date_str]["Close"])
                    no, do_ = float(hn_dict[date_str]["Open"]), float(hd_dict[date_str]["Open"])
                    if dc > 0 and do_ > 0:
                        c = round(nc / dc, 2)
                        o = round(no / do_, 2)
                        h = max(c, o)
                        l = min(c, o)
                        if is_intraday and prev_c is not None and o == c == h == l == prev_c:
                            continue
                        prev_c = c
                        data.append({"date": date_str, "o": o, "h": h, "l": l, "c": c})
            return jsonify({"symbol": symbol, "period": period, "interval": interval, "data": data})

        # DXY: prefer spot index (DX-Y.NYB) over futures (DX=F) for intraday;
        # DX=F fast_info returns stale settlement values, DX-Y.NYB via download is accurate.
        hist = None
        if yf_symbol == "DX=F" and period in ("1d", "5d"):
            try:
                dl = yf.download("DX-Y.NYB", period=period, interval=interval or "5m", progress=False)
                if dl is not None and not dl.empty:
                    if isinstance(dl.columns, pd.MultiIndex):
                        dl.columns = dl.columns.droplevel("Ticker")
                    hist = dl
            except Exception:
                pass

        if hist is None:
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
    """Serve icon/image files from the real project root (not temp demo dir)."""
    from flask import send_from_directory
    filename = request.path.lstrip("/")
    return send_from_directory(PROJECT_ROOT, filename)

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
    """Start a new month - advance to next month and reset contributions."""
    from flask import jsonify
    from datetime import datetime
    from dateutil.relativedelta import relativedelta
    config = load_config(CONFIG_PATH)
    monthly = config.get("monthly_investments", {})
    budget = config.get("budget", {})
    
    current_stored = monthly.get("month", datetime.now().strftime("%Y-%m"))
    stored_date = datetime.strptime(current_stored, "%Y-%m")
    next_date = stored_date + relativedelta(months=1)
    new_month = next_date.strftime("%Y-%m")
    
    monthly["month"] = new_month
    budget["month"] = new_month
    
    contributions = monthly.get("contributions", {})
    for key in contributions:
        contributions[key] = 0
    
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
    
    return jsonify({"success": True, "month": new_month})

@bp.route("/api/new-budget-month", methods=["POST"])
def api_new_budget_month():
    """Start a new budget month - advance both months and reset contributions."""
    from flask import jsonify
    from datetime import datetime
    from dateutil.relativedelta import relativedelta
    config = load_config(CONFIG_PATH)
    monthly = config.get("monthly_investments", {})
    budget = config.get("budget", {})
    
    current_stored = budget.get("month", monthly.get("month", datetime.now().strftime("%Y-%m")))
    stored_date = datetime.strptime(current_stored, "%Y-%m")
    next_date = stored_date + relativedelta(months=1)
    new_month = next_date.strftime("%Y-%m")
    
    monthly["month"] = new_month
    budget["month"] = new_month
    
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
    import threading
    threading.Thread(target=run_price_update, args=(config,), kwargs={"fetch_metals": False}, daemon=True).start()
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
    import threading
    threading.Thread(target=run_price_update, args=(config,), kwargs={"fetch_metals": False}, daemon=True).start()
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
        import threading
        threading.Thread(target=run_price_update, args=(config,), kwargs={"fetch_metals": False}, daemon=True).start()
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
    import threading
    threading.Thread(target=run_price_update, args=(config,), kwargs={"fetch_metals": False}, daemon=True).start()
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
                return jsonify({"ok": False, "error": f"No live price for {ticker}; can't calculate shares"})
            new_shares = round(amount / current_price, 3)
            old_qty = float(qty)
            new_qty = round(old_qty + new_shares, 3)
            old_value = round(old_qty * current_price, 2)
            new_value = round(new_qty * current_price, 2)
            matched_holding["qty"] = new_qty

            # Deduct from SPAXX money market in the same account
            cash_deducted = 0
            old_cash = 0
            new_cash = 0
            holding_acct = (matched_holding.get("account") or "").lower()
            for h in holdings:
                if (h.get("ticker") or "").upper() == "SPAXX" and \
                   (h.get("account") or "").lower() == holding_acct:
                    old_cash = float(h.get("value_override") or 0)
                    h["value_override"] = round(old_cash - amount, 2)
                    new_cash = h["value_override"]
                    cash_deducted = amount
                    break

            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)
            resp = {
                "ok": True,
                "type": "holding",
                "ticker": ticker,
                "account": matched_holding.get("account"),
                "old_value": old_value,
                "new_value": new_value,
                "shares_added": new_shares,
                "new_qty": new_qty,
                "price": current_price,
            }
            if cash_deducted > 0:
                resp["cash_deducted"] = cash_deducted
                resp["old_cash"] = old_cash
                resp["new_cash"] = new_cash
            return jsonify(resp)
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


# ── Sentiment / Fear & Greed ────────────────────────────────────

_sentiment_cache = {"data": None, "ts": 0}
_SENTIMENT_TTL = 1800  # 30 minutes

@bp.route("/api/sentiment")
def api_sentiment():
    """Return fear & greed / sentiment data for stocks, crypto, gold, VIX, yield curve."""
    from flask import jsonify
    import time, math

    if DEMO_MODE:
        return jsonify({
            "stock":  {"value": 42, "label": "Fear"},
            "crypto": {"value": 25, "label": "Extreme Fear"},
            "gold":   {"value": 68, "label": "Greed"},
            "vix":    {"value": 22.5, "score": 55, "label": "Moderate"},
            "yield_curve": {"value": 62, "spread": 0.45, "label": "Greed"},
        })

    now = time.time()
    refresh = request.args.get("refresh", "").lower() in ("1", "true")
    if not refresh and _sentiment_cache["data"] and (now - _sentiment_cache["ts"]) < _SENTIMENT_TTL:
        return jsonify(_sentiment_cache["data"])

    result = {}

    # Fetch CNN and Crypto F&G in parallel
    import urllib.request
    from concurrent.futures import ThreadPoolExecutor, as_completed

    def _fetch_cnn():
        req = urllib.request.Request(
            "https://production.dataviz.cnn.io/index/fearandgreed/graphdata",
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "application/json, text/plain, */*",
                "Referer": "https://edition.cnn.com/markets/fear-and-greed",
                "Origin": "https://edition.cnn.com",
            }
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            cnn = json.loads(resp.read().decode())
        fg = cnn.get("fear_and_greed", {})
        score = fg.get("score", 50)
        return {"value": round(score), "label": _fg_label(score)}

    def _fetch_crypto():
        config = load_config(CONFIG_PATH)
        cmc_key = get_effective_api_keys(config).get("cmc_api_key", "")
        if cmc_key:
            try:
                req = urllib.request.Request(
                    "https://pro-api.coinmarketcap.com/v3/fear-and-greed/latest",
                    headers={
                        "X-CMC_PRO_API_KEY": cmc_key,
                        "Accept": "application/json",
                    }
                )
                with urllib.request.urlopen(req, timeout=8) as resp:
                    body = json.loads(resp.read().decode())
                val = int(body["data"]["value"])
                cls = body["data"].get("value_classification", _fg_label(val))
                return {"value": val, "label": cls, "source": "cmc"}
            except Exception as e:
                print(f"[Sentiment] CMC F&G failed, falling back to alternative.me: {e}")
        req = urllib.request.Request(
            "https://api.alternative.me/fng/?limit=1",
            headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            alt = json.loads(resp.read().decode())
        entry = alt.get("data", [{}])[0]
        val = int(entry.get("value", 50))
        return {"value": val, "label": entry.get("value_classification", _fg_label(val)), "source": "alt"}

    with ThreadPoolExecutor(max_workers=2) as pool:
        cnn_fut = pool.submit(_fetch_cnn)
        crypto_fut = pool.submit(_fetch_crypto)

    try:
        result["stock"] = cnn_fut.result(timeout=10)
    except Exception as e:
        print(f"[Sentiment] CNN F&G fetch failed: {e}")
        result["stock"] = None

    try:
        result["crypto"] = crypto_fut.result(timeout=10)
    except Exception as e:
        print(f"[Sentiment] Crypto F&G fetch failed: {e}")
        result["crypto"] = None

    # --- 3) VIX fear level ---
    cache = load_price_cache(BASE)
    stocks = cache.get("stocks", {})
    vix_val = stocks.get("^VIX") or stocks.get("VIX") or 0
    if vix_val:
        vix_score = _vix_to_score(vix_val)
        result["vix"] = {"value": round(vix_val, 1), "score": vix_score, "label": _fg_label(vix_score)}
    else:
        result["vix"] = None

    # --- 4) Gold sentiment (computed) ---
    try:
        gold_price = (cache.get("metals", {}).get("GOLD") or 0)
        dxy = stocks.get("DX=F") or 0
        gvz = stocks.get("^GVZ") or 0
        gold_score = _compute_gold_sentiment(gold_price, vix_val, dxy, gvz)
        result["gold"] = {"value": gold_score, "label": _fg_label(gold_score)}
    except Exception as e:
        print(f"[Sentiment] Gold sentiment calc failed: {e}")
        result["gold"] = None

    # --- 5) Yield curve sentiment ---
    try:
        treasury = cache.get("treasury", {})
        y10 = treasury.get("tnx_10y")
        y2 = treasury.get("tnx_2y")
        if y10 is not None and y2 is not None:
            spread = y10 - y2
            yc_score = _yield_curve_to_score(spread)
            result["yield_curve"] = {"value": yc_score, "spread": round(spread, 2), "label": _fg_label(yc_score)}
        else:
            result["yield_curve"] = None
    except Exception:
        result["yield_curve"] = None

    _sentiment_cache["data"] = result
    _sentiment_cache["ts"] = now
    return jsonify(result)


def _fg_label(score):
    if score <= 25:
        return "Extreme Fear"
    elif score <= 45:
        return "Fear"
    elif score <= 55:
        return "Neutral"
    elif score <= 75:
        return "Greed"
    else:
        return "Extreme Greed"


def _vix_to_score(vix):
    """Map VIX to 0-100 (inverted: high VIX = low score / more fear)."""
    if vix >= 40:
        return 5
    elif vix >= 30:
        return int(5 + (40 - vix) * 2)
    elif vix >= 20:
        return int(25 + (30 - vix) * 3.5)
    elif vix >= 12:
        return int(60 + (20 - vix) * 5)
    else:
        return 100


def _compute_gold_sentiment(gold_price, vix, dxy, gvz):
    """Compute a 0-100 gold sentiment score from available signals.
    Higher = more bullish/greed for gold.
    Signals: high gold price momentum (implied), low DXY, high VIX (safe-haven),
    low gold volatility (calm accumulation)."""
    score = 50  # baseline

    if dxy:
        if dxy < 100:
            score += min(15, (100 - dxy) * 1.5)
        else:
            score -= min(15, (dxy - 100) * 1.5)

    if vix:
        if vix > 25:
            score += min(10, (vix - 25) * 1.0)
        elif vix < 15:
            score -= min(10, (15 - vix) * 1.5)

    if gvz:
        if gvz < 15:
            score += 8
        elif gvz > 25:
            score -= min(10, (gvz - 25) * 1.0)

    if gold_price:
        if gold_price > 2500:
            score += min(10, (gold_price - 2500) / 100)
        elif gold_price < 1800:
            score -= min(10, (1800 - gold_price) / 100)

    return max(0, min(100, round(score)))


def _yield_curve_to_score(spread):
    """Map 10Y-2Y spread to 0-100 sentiment. Inverted curve = fear, steep = greed."""
    if spread < -1.0:
        return 0
    elif spread < 0:
        return int(25 + spread * 25)
    elif spread < 0.5:
        return int(25 + spread * 60)
    elif spread < 1.5:
        return int(55 + (spread - 0.5) * 35)
    else:
        return min(100, int(90 + (spread - 1.5) * 10))


# ── Sentiment History ────────────────────────────────────────────────
_sent_hist_cache = {}          # keyed by range string, e.g. {"1y": {"data":…, "ts":…}}
_SENT_HIST_TTL = 3600 * 6     # 6 hours

_SENT_RANGE_MAP = {
    "1y":  {"yf_period": "1y",  "crypto_limit": 365,  "yc_days": 252},
    "3y":  {"yf_period": "3y",  "crypto_limit": 1095, "yc_days": 756},
    "5y":  {"yf_period": "5y",  "crypto_limit": 1825, "yc_days": 1260},
    "max": {"yf_period": "max", "crypto_limit": 0,    "yc_days": 0},
}


@bp.route("/api/sentiment-history")
def api_sentiment_history():
    """Return daily history for each sentiment gauge. ?range=1y|3y|5y|max"""
    from flask import jsonify, request as flask_request
    import time
    now = time.time()

    rng = flask_request.args.get("range", "1y")
    if rng not in _SENT_RANGE_MAP:
        rng = "1y"
    params = _SENT_RANGE_MAP[rng]

    cached = _sent_hist_cache.get(rng)
    if cached and cached.get("data") and (now - cached.get("ts", 0)) < _SENT_HIST_TTL:
        return jsonify(cached["data"])

    from concurrent.futures import ThreadPoolExecutor
    import urllib.request
    from datetime import datetime

    result = {}

    def _hist_cnn():
        """CNN Fear & Greed historical data, extended with VIX-derived scores for ranges > 1Y.
        CNN only provides ~1 year of history, so for 3Y/5Y/Max we backfill with
        a multi-factor stock sentiment proxy (VIX + S&P 500 momentum)."""
        cnn_data = {}
        try:
            req = urllib.request.Request(
                "https://production.dataviz.cnn.io/index/fearandgreed/graphdata",
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept": "application/json, text/plain, */*",
                    "Referer": "https://edition.cnn.com/markets/fear-and-greed",
                    "Origin": "https://edition.cnn.com",
                }
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                cnn = json.loads(resp.read().decode())
            for pt in cnn.get("fear_and_greed_historical", {}).get("data", []):
                ts = pt.get("x")
                val = pt.get("y")
                if ts is not None and val is not None:
                    dt = datetime.utcfromtimestamp(ts / 1000).strftime("%Y-%m-%d")
                    cnn_data[dt] = round(val)
        except Exception as e:
            print(f"[SentHist] CNN fetch error: {e}")

        if rng == "1y" and cnn_data:
            return [{"date": d, "value": v} for d, v in sorted(cnn_data.items())]

        try:
            import yfinance as yf
            import math
            period = params["yf_period"]
            data = yf.download(["^VIX", "SPY"], period=period, progress=False, threads=False)
            if data is None or data.empty:
                return [{"date": d, "value": v} for d, v in sorted(cnn_data.items())]

            spy_close = data[("Close", "SPY")].dropna()
            spy_ma125 = spy_close.rolling(125).mean()

            out_map = {}
            for dt_idx in data.index:
                dt = dt_idx.strftime("%Y-%m-%d")
                if dt in cnn_data:
                    out_map[dt] = cnn_data[dt]
                    continue
                try:
                    vix = float(data[("Close", "^VIX")].loc[dt_idx])
                    if math.isnan(vix):
                        continue
                    score = _vix_to_score(vix)
                    spy_val = float(spy_close.loc[dt_idx]) if dt_idx in spy_close.index else 0
                    spy_ma = float(spy_ma125.loc[dt_idx]) if dt_idx in spy_ma125.index and not math.isnan(spy_ma125.loc[dt_idx]) else 0
                    if spy_val and spy_ma:
                        momentum = (spy_val - spy_ma) / spy_ma
                        score += max(-15, min(15, momentum * 100))
                    out_map[dt] = max(0, min(100, round(score)))
                except Exception:
                    continue
            return [{"date": d, "value": v} for d, v in sorted(out_map.items())]
        except Exception as e:
            print(f"[SentHist] Stock extended history error: {e}")
            return [{"date": d, "value": v} for d, v in sorted(cnn_data.items())]

    def _hist_crypto():
        """Crypto F&G history — CMC Pro API (if key available), else alternative.me."""
        config = load_config(CONFIG_PATH)
        cmc_key = get_effective_api_keys(config).get("cmc_api_key", "")
        if cmc_key:
            try:
                limit = params["crypto_limit"] or 2000
                url = f"https://pro-api.coinmarketcap.com/v3/fear-and-greed/historical?limit={limit}"
                req = urllib.request.Request(url, headers={
                    "X-CMC_PRO_API_KEY": cmc_key,
                    "Accept": "application/json",
                })
                with urllib.request.urlopen(req, timeout=15) as resp:
                    body = json.loads(resp.read().decode())
                out = []
                for entry in body.get("data", []):
                    ts = entry.get("timestamp", "")
                    val = entry.get("value")
                    if ts and val is not None:
                        dt = datetime.utcfromtimestamp(int(ts)).strftime("%Y-%m-%d")
                        out.append({"date": dt, "value": int(val)})
                out.sort(key=lambda x: x["date"])
                if out:
                    return out
            except Exception as e:
                print(f"[SentHist] CMC historical failed, falling back: {e}")
        try:
            limit = params["crypto_limit"]
            url = "https://api.alternative.me/fng/?limit=0" if limit == 0 else f"https://api.alternative.me/fng/?limit={limit}"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
            out = []
            for entry in data.get("data", []):
                ts = entry.get("timestamp")
                val = entry.get("value")
                if ts and val:
                    dt = datetime.utcfromtimestamp(int(ts)).strftime("%Y-%m-%d")
                    out.append({"date": dt, "value": int(val)})
            out.sort(key=lambda x: x["date"])
            return out
        except Exception as e:
            print(f"[SentHist] Crypto error: {e}")
            return []

    def _hist_vix():
        """VIX history from yfinance, mapped to 0-100 score."""
        try:
            import yfinance as yf
            tk = yf.Ticker("^VIX")
            hist = tk.history(period=params["yf_period"])
            out = []
            for dt_idx, row in hist.iterrows():
                dt = dt_idx.strftime("%Y-%m-%d")
                vix = float(row["Close"])
                out.append({"date": dt, "value": _vix_to_score(vix)})
            return out
        except Exception as e:
            print(f"[SentHist] VIX error: {e}")
            return []

    def _hist_gold():
        """Gold sentiment history computed from GC=F, DXY, GVZ via yfinance."""
        try:
            import yfinance as yf
            data = yf.download(["GC=F", "DX=F", "^VIX", "^GVZ"],
                               period=params["yf_period"], progress=False, threads=False)
            if data is None or data.empty:
                return []
            out = []
            for dt_idx in data.index:
                dt = dt_idx.strftime("%Y-%m-%d")
                try:
                    gold = float(data[("Close", "GC=F")].loc[dt_idx])
                    dxy = float(data[("Close", "DX=F")].loc[dt_idx]) if ("Close", "DX=F") in data.columns else 0
                    vix = float(data[("Close", "^VIX")].loc[dt_idx]) if ("Close", "^VIX") in data.columns else 0
                    gvz = float(data[("Close", "^GVZ")].loc[dt_idx]) if ("Close", "^GVZ") in data.columns else 0
                    import math
                    if math.isnan(gold):
                        continue
                    dxy = 0 if math.isnan(dxy) else dxy
                    vix = 0 if math.isnan(vix) else vix
                    gvz = 0 if math.isnan(gvz) else gvz
                    score = _compute_gold_sentiment(gold, vix, dxy, gvz)
                    out.append({"date": dt, "value": score})
                except Exception:
                    continue
            return out
        except Exception as e:
            print(f"[SentHist] Gold error: {e}")
            return []

    def _hist_yield_curve():
        """Yield curve spread history from FRED cache (DGS10, DGS2)."""
        try:
            import fred_manager
            config = load_config(CONFIG_PATH)
            api_keys = get_effective_api_keys(config)
            fred_key = os.environ.get("FRED_API_KEY") or api_keys.get("fred_api_key") or ""
            dgs10 = fred_manager.get_series_cached("DGS10", fred_key, BASE, max_age_hours=48)
            dgs2 = fred_manager.get_series_cached("DGS2", fred_key, BASE, max_age_hours=48)
            if not dgs10 or not dgs2:
                return []
            d2_map = {pt["date"]: pt["value"] for pt in dgs2 if pt.get("value") is not None}
            out = []
            for pt in dgs10:
                d = pt["date"]
                v10 = pt.get("value")
                v2 = d2_map.get(d)
                if v10 is not None and v2 is not None:
                    spread = v10 - v2
                    out.append({"date": d, "value": _yield_curve_to_score(spread)})
            yc_days = params["yc_days"]
            return out[-yc_days:] if yc_days > 0 else out
        except Exception as e:
            print(f"[SentHist] Yield curve error: {e}")
            return []

    with ThreadPoolExecutor(max_workers=5) as pool:
        f_cnn = pool.submit(_hist_cnn)
        f_crypto = pool.submit(_hist_crypto)
        f_vix = pool.submit(_hist_vix)
        f_gold = pool.submit(_hist_gold)
        f_yc = pool.submit(_hist_yield_curve)

    result["stock"] = f_cnn.result(timeout=20)
    result["crypto"] = f_crypto.result(timeout=20)
    result["vix"] = f_vix.result(timeout=20)
    result["gold"] = f_gold.result(timeout=30)
    result["yield_curve"] = f_yc.result(timeout=20)

    _sent_hist_cache[rng] = {"data": result, "ts": now}
    return jsonify(result)


# ── CAPE / Shiller P/E ──────────────────────────────────────────────
_cape_cache = {"data": None, "ts": 0}
_CAPE_TTL = 3600 * 6  # 6 hours — CAPE barely changes day-to-day


@bp.route("/api/cape")
def api_cape():
    """Return current + historical CAPE (Shiller P/E) ratio."""
    from flask import jsonify
    import time
    now = time.time()
    if _cape_cache["data"] and (now - _cape_cache["ts"]) < _CAPE_TTL:
        return jsonify(_cape_cache["data"])

    result = _fetch_cape_data()
    if result and result.get("history"):
        _cape_cache["data"] = result
        _cape_cache["ts"] = now
    return jsonify(result or {"current": None, "history": []})


def _fetch_cape_data():
    """Scrape CAPE ratio (current + monthly history) from multpl.com."""
    import urllib.request
    import re

    url = "https://www.multpl.com/shiller-pe/table/by-month"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml",
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"[CAPE] fetch error: {e}")
        return None

    # Parse the HTML table — rows have <td>date</td><td>  value  </td>
    row_pat = re.compile(
        r'<tr[^>]*>\s*<td[^>]*>(.*?)</td>\s*<td[^>]*>(.*?)</td>',
        re.DOTALL,
    )
    from datetime import datetime

    import html as htmlmod

    history = []
    for m in row_pat.finditer(html):
        raw_date = re.sub(r"<[^>]+>", "", m.group(1)).strip()
        try:
            dt = datetime.strptime(raw_date, "%b %d, %Y")
            date_str = dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
        clean_val = htmlmod.unescape(re.sub(r"<[^>]+>", "", m.group(2))).strip()
        try:
            val = round(float(clean_val), 2)
        except ValueError:
            continue
        history.append({"date": date_str, "value": val})

    history.sort(key=lambda x: x["date"])

    current = history[-1]["value"] if history else None

    # Compute context: long-term median is ~16.8
    median = 16.8
    label = "Average"
    if current:
        if current > 30:
            label = "Very Expensive"
        elif current > 25:
            label = "Expensive"
        elif current > 20:
            label = "Above Average"
        elif current > 15:
            label = "Average"
        elif current > 10:
            label = "Below Average"
        else:
            label = "Cheap"

    return {
        "current": current,
        "median": median,
        "label": label,
        "history": history,
    }


# ── Buffett Indicator (Market Cap / GDP) ────────────────────────────
_buffett_cache = {"data": None, "ts": 0}
_BUFFETT_TTL = 3600 * 6


@bp.route("/api/buffett")
def api_buffett():
    """Return current + historical Buffett Indicator (market cap / GDP %)."""
    from flask import jsonify
    import time
    now = time.time()
    if _buffett_cache["data"] and (now - _buffett_cache["ts"]) < _BUFFETT_TTL:
        return jsonify(_buffett_cache["data"])

    result = _fetch_buffett_data()
    if result and result.get("history"):
        _buffett_cache["data"] = result
        _buffett_cache["ts"] = now
    return jsonify(result or {"current": None, "history": []})


def _fetch_buffett_data():
    """Compute Buffett Indicator: total market cap / GDP.

    Uses yfinance Wilshire 5000 + FRED-cached GDP, calibrated with a
    known reference point (Dec 2025: 230%, per currentmarketvaluation.com).
    """
    import json
    from pathlib import Path

    # 1. GDP from FRED cache
    cache_path = Path(BASE) / "price_cache.json"
    gdp_data = []
    if cache_path.exists():
        try:
            with open(cache_path) as f:
                cache = json.load(f)
            gdp_data = cache.get("fred", {}).get("GDP", {}).get("data", [])
        except Exception:
            pass

    if not gdp_data:
        # Try fetching GDP fresh if we have a key
        import fred_manager
        config = load_config(CONFIG_PATH)
        api_keys = get_effective_api_keys(config)
        fred_key = os.environ.get("FRED_API_KEY") or api_keys.get("fred_api_key") or ""
        gdp_data = fred_manager.get_series_cached("GDP", fred_key, BASE, max_age_hours=168)

    if not gdp_data:
        print("[Buffett] no GDP data available")
        return None

    # 2. Wilshire 5000 from yfinance (weekly for smoother history)
    try:
        import yfinance as yf
        w = yf.download("^W5000", period="max", interval="1wk", progress=False)
        if w.empty:
            print("[Buffett] yfinance returned no Wilshire data")
            return None
    except Exception as e:
        print(f"[Buffett] yfinance error: {e}")
        return None

    # Build lookup maps
    gdp_quarters = []
    gdp_map = {}
    for pt in gdp_data:
        d, v = pt.get("date"), pt.get("value")
        if d and v:
            gdp_map[d[:10]] = v
            gdp_quarters.append(d[:10])
    gdp_quarters.sort()

    wilshire_data = {}
    for dt_idx, row in w.iterrows():
        dt_str = dt_idx.strftime("%Y-%m-%d") if hasattr(dt_idx, "strftime") else str(dt_idx)[:10]
        close = row["Close"]
        if hasattr(close, "values"):
            close = close.values[0]
        val = float(close)
        if val > 0:
            wilshire_data[dt_str] = val

    w_dates = sorted(wilshire_data.keys())

    def closest_gdp(target):
        """Find the most recent GDP quarter at or before target date."""
        best = None
        for gd in gdp_quarters:
            if gd <= target:
                best = gd
            else:
                break
        return gdp_map.get(best) if best else None

    # 3. Compute raw ratio for each Wilshire data point using most recent GDP
    raw = []
    for wd in w_dates:
        w_val = wilshire_data[wd]
        gdp_val = closest_gdp(wd)
        if gdp_val and gdp_val > 0:
            raw_ratio = w_val / gdp_val * 100
            raw.append({"date": wd, "raw": raw_ratio})

    if not raw:
        return None

    # Add a current-day estimate using latest Wilshire price + latest GDP
    try:
        import yfinance as yf
        tk = yf.Ticker("^W5000")
        latest_w = tk.fast_info.last_price
        if latest_w and latest_w > 0:
            latest_gdp = gdp_map.get(gdp_quarters[-1]) if gdp_quarters else None
            if latest_gdp and latest_gdp > 0:
                from datetime import date as _date
                today_str_local = _date.today().strftime("%Y-%m-%d")
                raw.append({"date": today_str_local, "raw": latest_w / latest_gdp * 100})
    except Exception:
        pass

    # 4. Calibrate: known reference Dec 2025 ≈ 230%
    ref_raw = None
    for r in reversed(raw):
        if r["date"] <= "2025-12-31":
            ref_raw = r["raw"]
            break
    scale = (230.0 / ref_raw) if ref_raw and ref_raw > 0 else 1.0

    history = []
    seen = set()
    for r in raw:
        if r["date"] not in seen:
            history.append({"date": r["date"], "value": round(r["raw"] * scale, 1)})
            seen.add(r["date"])

    current = history[-1]["value"] if history else None

    median = 120
    label = "Fair Value"
    if current:
        if current > 180:
            label = "Significantly Overvalued"
        elif current > 140:
            label = "Overvalued"
        elif current > 100:
            label = "Fair Value"
        elif current > 70:
            label = "Undervalued"
        else:
            label = "Significantly Undervalued"

    return {
        "current": current,
        "median": median,
        "label": label,
        "history": history,
    }


# ── CME FedWatch (rate probabilities from Fed Funds Futures) ─────────
_fedwatch_cache = {"data": None, "ts": 0}
_FEDWATCH_TTL = 3600 * 2

_FOMC_DATES_2026 = [
    "2026-01-29", "2026-03-18", "2026-05-06", "2026-06-17",
    "2026-07-29", "2026-09-16", "2026-10-28", "2026-12-16",
]

_FF_MONTH_CODES = {
    1: "F", 2: "G", 3: "H", 4: "J", 5: "K", 6: "M",
    7: "N", 8: "Q", 9: "U", 10: "V", 11: "X", 12: "Z",
}


@bp.route("/api/fedwatch")
def api_fedwatch():
    """Compute FedWatch-style rate probabilities from Fed Funds Futures."""
    from flask import jsonify
    import time as _time
    now = _time.time()
    if _fedwatch_cache["data"] and (now - _fedwatch_cache["ts"]) < _FEDWATCH_TTL:
        return jsonify(_fedwatch_cache["data"])

    result = _compute_fedwatch()
    if result and result.get("meetings"):
        _fedwatch_cache["data"] = result
        _fedwatch_cache["ts"] = now
    return jsonify(result or {"meetings": [], "current_rate": None, "error": "Failed to fetch data"})


def _compute_fedwatch():
    """Build a probability tree across FOMC meetings using CME methodology."""
    import yfinance as yf
    from datetime import datetime, date
    import calendar
    import math

    today = date.today()
    today_str = today.strftime("%Y-%m-%d")

    # ── 1. Current effective Fed Funds Rate from FRED ──
    effr = None
    try:
        import fred_manager
        config = load_config(CONFIG_PATH)
        api_keys = get_effective_api_keys(config)
        fred_key = os.environ.get("FRED_API_KEY") or api_keys.get("fred_api_key") or ""
        dff = fred_manager.get_series_cached("DFF", fred_key, BASE, max_age_hours=24)
        if dff:
            for pt in reversed(dff):
                if pt.get("value") is not None:
                    effr = pt["value"]
                    break
    except Exception as e:
        print(f"[FedWatch] FRED EFFR error: {e}")

    if effr is None:
        return None

    current_upper = math.ceil(effr * 4) / 4
    current_lower = current_upper - 0.25
    current_mid = (current_upper + current_lower) / 2

    upcoming = [m for m in _FOMC_DATES_2026 if m > today_str]
    if not upcoming:
        return {"meetings": [], "current_rate": effr,
                "current_range_bps": f"{int(current_lower * 100)}-{int(current_upper * 100)}"}

    # ── 2. Fetch Fed Funds Futures prices from yfinance ──
    last_md = datetime.strptime(upcoming[-1], "%Y-%m-%d").date()
    tickers, month_keys = [], []
    m, y = today.month, today.year
    end_m, end_y = last_md.month + 1, last_md.year
    if end_m > 12:
        end_m, end_y = 1, end_y + 1

    while (y, m) <= (end_y, end_m):
        code = _FF_MONTH_CODES[m]
        tickers.append(f"ZQ{code}{str(y)[2:]}.CBT")
        month_keys.append((y, m))
        m += 1
        if m > 12:
            m, y = 1, y + 1

    implied = {}
    for i, ticker in enumerate(tickers):
        try:
            tk = yf.Ticker(ticker)
            p = tk.fast_info.last_price if tk.fast_info else None
            if p and 80 < p < 105:
                implied[month_keys[i]] = round(100.0 - float(p), 4)
        except Exception:
            pass

    if not implied:
        return {"meetings": [], "current_rate": effr,
                "current_range_bps": f"{int(current_lower * 100)}-{int(current_upper * 100)}",
                "error": "Could not fetch futures prices"}

    # ── 3. Compute isolated cut probability at each meeting ──
    meeting_months = {}
    for ms in upcoming:
        md_ = datetime.strptime(ms, "%Y-%m-%d").date()
        meeting_months[(md_.year, md_.month)] = md_

    def _next_month(y, m):
        return (y, m + 1) if m < 12 else (y + 1, 1)

    prev_rate = effr
    prev_meeting_month = (today.year, today.month)
    isolated = []

    for meeting_str in upcoming:
        md = datetime.strptime(meeting_str, "%Y-%m-%d").date()
        mkey = (md.year, md.month)
        imp = implied.get(mkey)
        if imp is None:
            isolated.append({"date": meeting_str, "md": md, "p_cut": 0.0, "ok": False})
            prev_meeting_month = mkey
            continue

        # Find a non-meeting month between prev meeting and this one for reference
        ref = None
        ry, rm = _next_month(*prev_meeting_month)
        while (ry, rm) < mkey:
            if (ry, rm) not in meeting_months and (ry, rm) in implied:
                ref = implied[(ry, rm)]
            ry, rm = _next_month(ry, rm)
        pre_rate = ref if ref is not None else prev_rate

        days_in = calendar.monthrange(md.year, md.month)[1]
        days_after = days_in - md.day

        if days_after <= 3:
            ny, nm = _next_month(md.year, md.month)
            next_imp = implied.get((ny, nm))
            post = next_imp if next_imp is not None else imp
        else:
            post = (imp * days_in - pre_rate * md.day) / days_after

        change = pre_rate - post  # positive = easing
        if abs(change) > 0.50:
            isolated.append({"date": meeting_str, "md": md, "p_cut": 0.0, "ok": False})
            prev_meeting_month = mkey
            continue

        p_cut = max(0.0, min(1.0, change / 0.25))
        isolated.append({"date": meeting_str, "md": md, "p_cut": p_cut, "post": post, "ok": True})
        prev_rate = post
        prev_meeting_month = mkey

    # ── 4. Build probability tree ──
    dist = {round(current_mid, 4): 100.0}
    meetings_out = []

    for iso in isolated:
        md = iso["md"]
        p_cut = iso["p_cut"] if iso["ok"] else 0.0
        p_hold = 1.0 - p_cut

        new_dist = {}
        for rate, prob in dist.items():
            new_dist[rate] = new_dist.get(rate, 0.0) + prob * p_hold
            cut_rate = round(rate - 0.25, 4)
            if cut_rate >= 0:
                new_dist[cut_rate] = new_dist.get(cut_rate, 0.0) + prob * p_cut
        dist = new_dist

        ranges = []
        cut_t, hold_t, hike_t = 0.0, 0.0, 0.0
        for rate in sorted(dist.keys()):
            prob = dist[rate]
            if prob < 0.05:
                continue
            lo = int(round((rate - 0.125) * 100))
            hi = int(round((rate + 0.125) * 100))
            ranges.append({"range": f"{lo}-{hi}", "lo": lo, "prob": round(prob, 1)})
            if rate < current_mid - 0.001:
                cut_t += prob
            elif rate > current_mid + 0.001:
                hike_t += prob
            else:
                hold_t += prob

        contract_code = f"ZQ{_FF_MONTH_CODES[md.month]}{str(md.year)[2:]}"
        imp_price = implied.get((md.year, md.month))

        meetings_out.append({
            "date": iso["date"],
            "label": md.strftime("%d %b%y").lstrip("0"),
            "contract": contract_code,
            "price": round(imp_price, 4) if imp_price else None,
            "cut": round(cut_t, 1),
            "hold": round(hold_t, 1),
            "hike": round(hike_t, 1),
            "ranges": ranges,
        })

    return {
        "current_rate": effr,
        "current_range_bps": f"{int(current_lower * 100)}-{int(current_upper * 100)}",
        "meetings": meetings_out,
    }


# ── Economic Calendar (upcoming data releases) ──────────────────────
_econ_cal_cache = {}
_ECON_CAL_TTL = 1800  # 30 min so actuals refresh reasonably fast
_ECON_CAL_DISK_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "econ_calendar_cache.json")

_HIGH_IMPACT_KEYWORDS = [
    "cpi", "gdp", "nonfarm", "payroll", "fomc", "fed funds", "interest rate",
    "pce price", "core pce", "unemployment rate", "retail sales",
]
_MEDIUM_IMPACT_KEYWORDS = [
    "ppi", "consumer confidence", "ism", "pmi", "housing starts",
    "building permits", "durable goods", "trade balance", "jolts",
    "initial claims", "jobless claims", "industrial production",
    "consumer sentiment", "michigan", "existing home", "new home",
    "cpi mm", "cpi yy", "core cpi", "personal income", "personal spending",
    "adp", "empire state", "philly fed", "chicago pmi",
]

_MW_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "identity",
    "Referer": "https://www.google.com/",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}


def _classify_impact(event_name: str) -> str:
    low = event_name.lower()
    for kw in _HIGH_IMPACT_KEYWORDS:
        if kw in low:
            return "high"
    for kw in _MEDIUM_IMPACT_KEYWORDS:
        if kw in low:
            return "medium"
    return "low"


def _week_range(offset: int = 0):
    """Return (monday, friday) dates for the week at *offset* from current."""
    from datetime import timedelta
    today = datetime.now().date()
    monday = today - timedelta(days=today.weekday()) + timedelta(weeks=offset)
    friday = monday + timedelta(days=4)
    return monday, friday


def _load_econ_disk_cache():
    try:
        if os.path.exists(_ECON_CAL_DISK_FILE):
            with open(_ECON_CAL_DISK_FILE, "r") as f:
                return json.load(f)
    except Exception as e:
        print(f"[EconCal] Disk cache read error: {e}")
    return {}


def _save_econ_disk_cache(cache_data):
    try:
        import tempfile
        fd, tmp = tempfile.mkstemp(suffix=".json", dir=os.path.dirname(_ECON_CAL_DISK_FILE))
        with os.fdopen(fd, "w") as f:
            json.dump(cache_data, f)
        os.replace(tmp, _ECON_CAL_DISK_FILE)
    except Exception as e:
        print(f"[EconCal] Disk cache write error: {e}")


# ── MarketWatch scraper (this week only, provides actuals) ──────────

_MONTH_MAP = {
    "january": "01", "february": "02", "march": "03", "april": "04",
    "may": "05", "june": "06", "july": "07", "august": "08",
    "september": "09", "october": "10", "november": "11", "december": "12",
}


def _fetch_marketwatch_calendar(**_kwargs):
    """Scrape MarketWatch economic calendar (returns whatever week MW is currently showing).
    MW ignores dateRange params and always shows the upcoming week, so we parse
    whatever they return and let the caller decide which week it belongs to."""
    import urllib.request
    import re
    import html as html_mod
    try:
        req = urllib.request.Request(
            "https://www.marketwatch.com/economy-politics/calendar",
            headers=_MW_HEADERS,
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8")
    except Exception as e:
        print(f"[EconCal] MarketWatch fetch error: {e}")
        return []

    # Extract the <table>…</table>
    start = raw.find("<table")
    if start < 0:
        return []
    end = raw.find("</table>", start)
    if end < 0:
        return []
    table_html = raw[start:end + 8]

    tag_re = re.compile(r"<[^>]+>")
    row_re = re.compile(r"<tr[^>]*>(.*?)</tr>", re.DOTALL)
    td_re = re.compile(r"<td[^>]*>(.*?)</td>", re.DOTALL)
    bold_re = re.compile(r"<b>(.*?)</b>", re.DOTALL | re.IGNORECASE)
    day_header_re = re.compile(
        r"(MONDAY|TUESDAY|WEDNESDAY|THURSDAY|FRIDAY|SATURDAY|SUNDAY),?\s+"
        r"(JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER)\s+(\d{1,2})",
        re.IGNORECASE,
    )

    events = []
    current_date = ""
    year = datetime.now().year

    for row_m in row_re.finditer(table_html):
        row_content = row_m.group(1)
        cells = td_re.findall(row_content)
        if not cells:
            continue

        # Check for day header row (bold text in first cell)
        bold_m = bold_re.search(cells[0])
        if bold_m:
            day_m = day_header_re.search(bold_m.group(1))
            if day_m:
                month_num = _MONTH_MAP.get(day_m.group(2).lower(), "01")
                day_num = day_m.group(3).zfill(2)
                current_date = f"{year}-{month_num}-{day_num}"
            continue

        if not current_date or len(cells) < 6:
            continue

        def _clean(s):
            return html_mod.unescape(tag_re.sub("", s)).strip()

        time_raw = _clean(cells[0])
        event_name = _clean(cells[1])
        actual_val = _clean(cells[3])
        forecast_val = _clean(cells[4])
        previous_val = _clean(cells[5])

        if not event_name or event_name.lower() == "none scheduled":
            continue

        # Convert "8:30 am" -> "08:30", "2:00 pm" -> "14:00"
        time_str = ""
        tm = re.match(r"(\d{1,2}):(\d{2})\s*(am|pm)", time_raw, re.IGNORECASE)
        if tm:
            h = int(tm.group(1))
            m_val = tm.group(2)
            if tm.group(3).lower() == "pm" and h != 12:
                h += 12
            elif tm.group(3).lower() == "am" and h == 12:
                h = 0
            time_str = f"{h:02d}:{m_val}"

        events.append({
            "date": current_date,
            "time": time_str,
            "event": event_name,
            "impact": _classify_impact(event_name),
            "actual": actual_val if actual_val else "",
            "forecast": forecast_val if forecast_val else "-",
            "previous": previous_val if previous_val else "-",
        })

    impact_order = {"high": 0, "medium": 1, "low": 2}
    events.sort(key=lambda e: (e["date"], e["time"], impact_order.get(e["impact"], 3)))
    return events


# ── Faireconomy fallback (schedule only, no actuals) ────────────────

def _parse_faireconomy_events(data):
    events = []
    for item in data:
        if item.get("country") != "USD":
            continue
        impact_raw = (item.get("impact") or "").strip()
        if impact_raw == "Holiday":
            continue
        date_str = (item.get("date") or "")[:10]
        time_str = (item.get("date") or "")[11:16]
        actual_raw = (item.get("actual") or "").strip()
        events.append({
            "date": date_str,
            "time": time_str,
            "event": item.get("title", ""),
            "impact": _classify_impact(item.get("title", "")) if impact_raw == "Low" else impact_raw.lower(),
            "actual": actual_raw if actual_raw else "",
            "forecast": item.get("forecast", "") or "-",
            "previous": item.get("previous", "") or "-",
        })
    impact_order = {"high": 0, "medium": 1, "low": 2}
    events.sort(key=lambda e: (e["date"], e["time"], impact_order.get(e["impact"], 3)))
    return events


def _fetch_faireconomy_calendar(week: str = "thisweek"):
    import urllib.request
    url = f"https://nfs.faireconomy.media/ff_calendar_{week}.json"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
    except Exception as e:
        print(f"[EconCal] Faireconomy fetch error ({week}): {e}")
        return []
    return _parse_faireconomy_events(data)


# ── Investing.com fallback (supports date ranges, has actuals) ──────

_INVESTING_BULL_MAP = {"bull1": "low", "bull2": "medium", "bull3": "high"}

def _fetch_investing_calendar(date_from: str, date_to: str):
    """Fetch US economic calendar from Investing.com for an arbitrary date range.
    date_from / date_to: 'YYYY-MM-DD' strings."""
    import urllib.request
    import re
    import html as html_mod
    try:
        post_data = (
            f"dateFrom={date_from}&dateTo={date_to}"
            "&country%5B%5D=5"
            "&importance%5B%5D=1&importance%5B%5D=2&importance%5B%5D=3"
        ).encode()
        req = urllib.request.Request(
            "https://www.investing.com/economic-calendar/Service/getCalendarFilteredData",
            data=post_data,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/131.0.0.0 Safari/537.36",
                "X-Requested-With": "XMLHttpRequest",
                "Referer": "https://www.investing.com/economic-calendar/",
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode("utf-8")
    except Exception as e:
        print(f"[EconCal] Investing.com fetch error: {e}")
        return []

    try:
        parsed = json.loads(body)
        html_data = parsed.get("data", "")
    except (json.JSONDecodeError, ValueError):
        html_data = body

    tag_re = re.compile(r"<[^>]+>")
    row_re = re.compile(
        r'<tr[^>]*class="[^"]*js-event-item[^"]*"[^>]*>(.*?)</tr>', re.DOTALL
    )
    td_re = re.compile(r"<td[^>]*>(.*?)</td>", re.DOTALL)
    dt_re = re.compile(r'data-event-datetime="(\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2})')
    bull_re = re.compile(r'data-img_key="(bull[123])"')

    events = []
    for row_m in row_re.finditer(html_data):
        row_html = row_m.group(0)
        cells = td_re.findall(row_m.group(1))
        if len(cells) < 7:
            continue

        def _clean(s):
            return html_mod.unescape(tag_re.sub("", s)).strip()

        dt_m = dt_re.search(row_html)
        if not dt_m:
            continue
        raw_dt = dt_m.group(1)
        date_str = raw_dt[:10].replace("/", "-")
        time_str = raw_dt[11:16]

        event_name = _clean(cells[3])
        if not event_name:
            continue

        actual_val = _clean(cells[4])
        forecast_val = _clean(cells[5])
        previous_val = _clean(cells[6])

        bull_m = bull_re.search(row_html)
        impact = _INVESTING_BULL_MAP.get(bull_m.group(1), "low") if bull_m else "low"

        events.append({
            "date": date_str,
            "time": time_str,
            "event": event_name,
            "impact": impact,
            "actual": actual_val if actual_val and actual_val != "\u00a0" else "",
            "forecast": forecast_val if forecast_val else "-",
            "previous": previous_val if previous_val else "-",
        })

    impact_order = {"high": 0, "medium": 1, "low": 2}
    events.sort(key=lambda e: (e["date"], e["time"], impact_order.get(e["impact"], 3)))
    return events


# ── Unified fetcher ─────────────────────────────────────────────────

def _mw_events_week_key(events):
    """Detect which Monday an event list belongs to based on earliest event date."""
    from datetime import timedelta
    for e in events:
        d = e.get("date", "")
        if len(d) >= 10:
            try:
                dt = datetime.strptime(d[:10], "%Y-%m-%d").date()
                mon = dt - timedelta(days=dt.weekday())
                return mon.isoformat()
            except ValueError:
                continue
    return None


def _merge_actuals(new_events, cached_events):
    """Merge actuals from cached events into new events so we never lose
    previously captured actual values when a fallback source lacks them."""
    if not cached_events:
        return new_events
    cached_map = {}
    for e in cached_events:
        key = (e.get("date", ""), e.get("time", ""), e.get("event", ""))
        if e.get("actual"):
            cached_map[key] = e["actual"]
    for e in new_events:
        if not e.get("actual"):
            key = (e.get("date", ""), e.get("time", ""), e.get("event", ""))
            if key in cached_map:
                e["actual"] = cached_map[key]
    return new_events


def _has_actuals(events):
    """True if at least one event in the list has a non-empty actual value."""
    return any(e.get("actual") for e in events)


def _get_econ_week(offset: int):
    """Get events for a given week offset. 0=this, negative=past, positive=next."""
    from datetime import timedelta
    monday, friday = _week_range(offset)
    monday_key = monday.isoformat()
    week_label = f"{monday.strftime('%b %d')} – {friday.strftime('%b %d, %Y')}"
    disk = _load_econ_disk_cache()
    existing_events = (disk.get(monday_key) or {}).get("events", [])

    if offset == 0:
        # Current week: try MarketWatch first (best for actuals during the week).
        mw_events = _fetch_marketwatch_calendar()
        if mw_events:
            actual_key = _mw_events_week_key(mw_events)
            if actual_key == monday_key:
                mw_events = _merge_actuals(mw_events, existing_events)
                disk[monday_key] = {"events": mw_events, "week_label": week_label}
                _save_econ_disk_cache(disk)
                return mw_events, week_label
            else:
                # MW returned a different week (likely next) -- cache it for later
                if actual_key:
                    actual_monday = datetime.strptime(actual_key, "%Y-%m-%d").date()
                    actual_friday = actual_monday + timedelta(days=4)
                    lbl = f"{actual_monday.strftime('%b %d')} – {actual_friday.strftime('%b %d, %Y')}"
                    existing_for_key = (disk.get(actual_key) or {}).get("events", [])
                    mw_events = _merge_actuals(mw_events, existing_for_key)
                    disk[actual_key] = {"events": mw_events, "week_label": lbl}
                    _save_econ_disk_cache(disk)

        # MW didn't have current week -- try Investing.com (has actuals + date ranges)
        inv_events = _fetch_investing_calendar(monday.isoformat(), friday.isoformat())
        if inv_events:
            inv_events = _merge_actuals(inv_events, existing_events)
            disk[monday_key] = {"events": inv_events, "week_label": week_label}
            _save_econ_disk_cache(disk)
            return inv_events, week_label

        # Then try Faireconomy (schedule only, no actuals)
        events = _fetch_faireconomy_calendar("thisweek")
        if events:
            events = _merge_actuals(events, existing_events)
            disk[monday_key] = {"events": events, "week_label": week_label}
            _save_econ_disk_cache(disk)
            return events, week_label

        if existing_events:
            return existing_events, week_label
        return [], week_label

    if offset == 1:
        # Next week: check MW cache, then try live sources.
        if existing_events and _has_actuals(existing_events):
            return existing_events, week_label

        mw_events = _fetch_marketwatch_calendar()
        if mw_events:
            actual_key = _mw_events_week_key(mw_events)
            if actual_key == monday_key:
                mw_events = _merge_actuals(mw_events, existing_events)
                disk[monday_key] = {"events": mw_events, "week_label": week_label}
                _save_econ_disk_cache(disk)
                return mw_events, week_label

        # Investing.com supports arbitrary date ranges
        inv_events = _fetch_investing_calendar(monday.isoformat(), friday.isoformat())
        if inv_events:
            inv_events = _merge_actuals(inv_events, existing_events)
            disk[monday_key] = {"events": inv_events, "week_label": week_label}
            _save_econ_disk_cache(disk)
            return inv_events, week_label

        events = _fetch_faireconomy_calendar("nextweek")
        if events:
            events = _merge_actuals(events, existing_events)
            disk[monday_key] = {"events": events, "week_label": week_label}
            _save_econ_disk_cache(disk)
            return events, week_label

        if existing_events:
            return existing_events, week_label
        return [], week_label

    # Past weeks or offset > 1: check cache first, backfill from Investing.com if needed
    if existing_events and _has_actuals(existing_events):
        return existing_events, week_label

    inv_events = _fetch_investing_calendar(monday.isoformat(), friday.isoformat())
    if inv_events:
        inv_events = _merge_actuals(inv_events, existing_events)
        disk[monday_key] = {"events": inv_events, "week_label": week_label}
        _save_econ_disk_cache(disk)
        return inv_events, week_label

    if existing_events:
        return existing_events, week_label
    return [], week_label


@bp.route("/api/economic-calendar")
def api_economic_calendar():
    from flask import jsonify, request as flask_request
    import time as _time
    now = _time.time()

    try:
        offset = int(flask_request.args.get("offset", "0"))
    except (ValueError, TypeError):
        offset = 0
    offset = max(-8, min(4, offset))

    cache_key = str(offset)
    cached = _econ_cal_cache.get(cache_key)
    if cached and cached.get("data") and (now - cached.get("ts", 0)) < _ECON_CAL_TTL:
        return jsonify(cached["data"])

    events, week_label = _get_econ_week(offset)
    result = {
        "events": events or [],
        "week_label": week_label,
        "offset": offset,
        "updated": datetime.now().isoformat(),
    }
    if events:
        _econ_cal_cache[cache_key] = {"data": result, "ts": now}
    return jsonify(result)

