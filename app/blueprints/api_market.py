"""Market data API routes: live prices, sparklines, historical charts."""

import threading
import yfinance as yf
from flask import Blueprint, jsonify, request as flask_request, current_app
from flask_login import login_required, current_user

from ..extensions import db, csrf
from ..models.market import PriceCache

api_market_bp = Blueprint("api_market", __name__)

SYMBOL_MAP = {
    "GC=F": "gold", "SI=F": "silver", "BTC-USD": "btc",
    "SPY": "spy", "DX=F": "dxy", "^VIX": "vix",
    "CL=F": "oil", "HG=F": "copper", "^TNX": "tnx_10y", "2YY=F": "tnx_2y",
}


@api_market_bp.route("/live-data")
@login_required
def live_data():
    """Return full dashboard payload: portfolio total, pulse prices, crypto, holdings."""
    from ..services.portfolio_service import compute_portfolio_value
    from ..models.portfolio import CryptoHolding
    from ..models.snapshot import PortfolioSnapshot
    from ..models.settings import CustomPulseCard
    from datetime import date

    prices = {p.symbol: p for p in PriceCache.query.all()}
    result = {}

    for symbol, key in SYMBOL_MAP.items():
        row = prices.get(symbol)
        result[key] = row.price if row else None

    gold = result.get("gold") or 0
    silver = result.get("silver") or 0
    oil = result.get("oil") or 0
    result["gold_silver_ratio"] = round(gold / silver, 2) if silver else None
    result["gold_oil_ratio"] = round(gold / oil, 2) if oil else None

    custom_cards = CustomPulseCard.query.filter_by(user_id=current_user.id).all()
    ratio_ids = set()
    for card in custom_cards:
        resolved = _normalize_ticker(card.ticker)
        if "/" in card.ticker:
            ratio_ids.add(card.id)
            parts = card.ticker.split("/", 1)
            num_sym = _normalize_ticker(parts[0])
            den_sym = _normalize_ticker(parts[1])
            num_row = prices.get(num_sym)
            den_row = prices.get(den_sym)
            if num_row and den_row and den_row.price and den_row.price > 0:
                result[f"custom-{card.id}"] = round(num_row.price / den_row.price, 4)
        else:
            row = prices.get(resolved) or prices.get(card.ticker)
            if row:
                result[f"custom-{card.id}"] = row.price
    result["_ratio_ids"] = [f"custom-{rid}" for rid in ratio_ids]

    pv = compute_portfolio_value(current_user.id)
    result["total"] = pv["total"]
    result["buckets"] = pv.get("breakdown", {})

    yesterday = PortfolioSnapshot.query.filter_by(user_id=current_user.id)\
        .filter(PortfolioSnapshot.date < date.today())\
        .order_by(PortfolioSnapshot.date.desc()).first()
    if yesterday and yesterday.close and yesterday.close > 0:
        result["daily_change"] = pv["total"] - yesterday.close
        result["daily_change_pct"] = (result["daily_change"] / yesterday.close) * 100
    else:
        result["daily_change"] = 0
        result["daily_change_pct"] = 0

    crypto_holdings = CryptoHolding.query.filter_by(user_id=current_user.id).all()
    if crypto_holdings:
        cp = {}
        for ch in crypto_holdings:
            cg_key = f"CG:{ch.coingecko_id}" if ch.coingecko_id else f"CG:{ch.symbol.lower()}"
            row = prices.get(cg_key)
            if row:
                cp[ch.symbol] = row.price
        result["crypto_prices"] = cp

    return jsonify(result)


@api_market_bp.route("/bg-refresh", methods=["POST"])
@login_required
@csrf.exempt
def bg_refresh():
    """Kick off a background price refresh (non-blocking)."""
    from ..services.market_data import refresh_all_prices

    app = current_app._get_current_object()

    def _run():
        with app.app_context():
            try:
                refresh_all_prices()
            except Exception as e:
                print(f"[bg-refresh] error: {e}")

    threading.Thread(target=_run, daemon=True).start()
    return jsonify({"started": True})


SPARK_SYMBOL_MAP = {
    "gold": "GC=F", "silver": "SI=F", "spy": "SPY", "btc": "BTC-USD",
    "dxy": "DX=F", "vix": "^VIX", "oil": "CL=F", "copper": "HG=F",
    "tnx_10y": "^TNX", "tnx_2y": "2YY=F",
}


@api_market_bp.route("/sparklines")
@login_required
def sparklines():
    """Return intraday sparkline data for one or more symbols.

    Accepts ?symbols=gold,silver,spy (internal names or Yahoo tickers)
    or ?symbol=SPY (single ticker, legacy).
    Returns {symbol_key: [close1, close2, ...], ...}
    """
    raw = flask_request.args.get("symbols", flask_request.args.get("symbol", ""))
    keys = [s.strip() for s in raw.split(",") if s.strip()]
    if not keys:
        return jsonify({})

    from ..models.settings import CustomPulseCard

    _SPARK_FALLBACKS = [
        ("5d", "30m"),
        ("5d", "1h"),
        ("1mo", "1d"),
        ("3mo", "1d"),
    ]

    result = {}
    for key in keys:
        lkey = key.lower()
        if lkey.startswith("custom-"):
            card_id = key.split("-", 1)[1]
            card = CustomPulseCard.query.filter_by(id=int(card_id), user_id=current_user.id).first()
            if not card:
                continue
            if "/" in card.ticker:
                _spark_ratio(result, key, card.ticker)
                continue
            yf_sym = _normalize_ticker(card.ticker)
        else:
            yf_sym = SPARK_SYMBOL_MAP.get(lkey, key)
        for period, interval in _SPARK_FALLBACKS:
            try:
                hist = yf.Ticker(yf_sym).history(period=period, interval=interval)
                if not hist.empty:
                    closes = [round(row["Close"], 4) for _, row in hist.iterrows()]
                    if len(closes) > 1:
                        result[key] = closes
                        break
            except Exception:
                continue

    return jsonify(result)


def _spark_ratio(result, key, ratio_ticker):
    """Build sparkline data for a ratio like GOLD/SILVER."""
    _RATIO_FALLBACKS = [("5d", "30m"), ("5d", "1h"), ("1mo", "1d"), ("3mo", "1d")]
    parts = ratio_ticker.split("/", 1)
    num_sym = _normalize_ticker(parts[0])
    den_sym = _normalize_ticker(parts[1])
    for period, interval in _RATIO_FALLBACKS:
        try:
            num_hist = yf.Ticker(num_sym).history(period=period, interval=interval)
            den_hist = yf.Ticker(den_sym).history(period=period, interval=interval)
            if num_hist.empty or den_hist.empty:
                continue
            merged = num_hist[["Close"]].rename(columns={"Close": "num"}).join(
                den_hist[["Close"]].rename(columns={"Close": "den"}), how="inner"
            )
            points = []
            for _, row in merged.iterrows():
                if row["den"] and row["den"] > 0:
                    points.append(round(row["num"] / row["den"], 4))
            if len(points) > 1:
                result[key] = points
                return
        except Exception:
            continue


_HIST_FALLBACKS = {
    ("1d", "1m"):   [("1d", "2m"), ("1d", "5m"), ("5d", "15m"), ("5d", "30m")],
    ("1d", "2m"):   [("1d", "5m"), ("5d", "15m"), ("5d", "30m")],
    ("5d", "5m"):   [("5d", "15m"), ("5d", "30m"), ("1mo", "1d")],
    ("5d", "15m"):  [("5d", "30m"), ("1mo", "1d")],
    ("1mo", "15m"): [("1mo", "30m"), ("1mo", "1d")],
    ("1mo", "30m"): [("1mo", "1d")],
    ("3mo", "1d"):  [("3mo", "1wk")],
    ("6mo", "1d"):  [("6mo", "1wk")],
    ("1y", "1d"):   [("1y", "1wk")],
    ("5y", "1wk"):  [("5y", "1mo"), ("max", "1mo")],
    ("max", "1mo"): [("max", "3mo")],
}


def _yf_fetch(symbols, period, interval):
    """Try fetching OHLC from yfinance for a list of symbol alternatives.
    Returns (data_list, actual_period, actual_interval) or ([], p, i)."""
    for sym in symbols:
        try:
            hist = yf.Ticker(sym).history(period=period, interval=interval)
            if not hist.empty:
                data = [{"date": str(idx),
                         "o": round(row["Open"], 4),
                         "h": round(row["High"], 4),
                         "l": round(row["Low"], 4),
                         "c": round(row["Close"], 4),
                         "v": int(row.get("Volume", 0))}
                        for idx, row in hist.iterrows()]
                if data:
                    return data, period, interval
        except Exception:
            continue
    return [], period, interval


@api_market_bp.route("/historical")
@login_required
def historical():
    """Return OHLC historical data for chart modals."""
    symbol = flask_request.args.get("symbol", "SPY")
    period = flask_request.args.get("period", "1mo")
    interval = flask_request.args.get("interval", "1d")

    if symbol.startswith("custom-"):
        from ..models.settings import CustomPulseCard
        card_id = symbol.split("-", 1)[1]
        card = CustomPulseCard.query.filter_by(id=int(card_id), user_id=current_user.id).first()
        if card and "/" in card.ticker:
            return _historical_ratio(card.ticker, period, interval, symbol)
        symbol = _normalize_ticker(card.ticker) if card else symbol

    dxy_syms = ["DX-Y.NYB", "DX=F"] if symbol == "DX=F" else [symbol]

    data, actual_p, actual_i = _yf_fetch(dxy_syms, period, interval)

    if not data:
        for fb_p, fb_i in _HIST_FALLBACKS.get((period, interval), []):
            data, actual_p, actual_i = _yf_fetch(dxy_syms, fb_p, fb_i)
            if data:
                break

    return jsonify({
        "symbol": symbol,
        "period": actual_p,
        "interval": actual_i,
        "data": data,
    })


def _historical_ratio(ratio_ticker, period, interval, label):
    """Return historical OHLC-ish data for a ratio like GOLD/SILVER."""
    parts = ratio_ticker.split("/", 1)
    num_sym = _normalize_ticker(parts[0])
    den_sym = _normalize_ticker(parts[1])

    attempts = [(period, interval)] + _HIST_FALLBACKS.get((period, interval), [])

    for try_p, try_i in attempts:
        try:
            num_hist = yf.Ticker(num_sym).history(period=try_p, interval=try_i)
            den_hist = yf.Ticker(den_sym).history(period=try_p, interval=try_i)
            if num_hist.empty or den_hist.empty:
                continue
            merged = num_hist[["Open", "High", "Low", "Close"]].join(
                den_hist[["Open", "High", "Low", "Close"]], how="inner", lsuffix="_n", rsuffix="_d"
            )
            data = []
            for idx, row in merged.iterrows():
                d_open = row["Open_d"] or 1
                d_high = row["High_d"] or 1
                d_low = row["Low_d"] or 1
                d_close = row["Close_d"] or 1
                if d_open > 0 and d_close > 0:
                    data.append({
                        "date": str(idx),
                        "o": round(row["Open_n"] / d_open, 4),
                        "h": round(row["High_n"] / d_low, 4),
                        "l": round(row["Low_n"] / d_high, 4),
                        "c": round(row["Close_n"] / d_close, 4),
                        "v": 0,
                    })
            if data:
                return jsonify({"symbol": label, "period": try_p, "interval": try_i, "data": data})
        except Exception:
            continue

    return jsonify({"symbol": label, "period": period, "interval": interval, "data": []})


@api_market_bp.route("/pulse-order", methods=["POST"])
@login_required
@csrf.exempt
def save_pulse_order():
    """Persist the user's pulse card order."""
    from ..models.settings import UserSettings
    data = flask_request.get_json(silent=True) or {}
    order = data.get("order", [])
    settings = UserSettings.query.filter_by(user_id=current_user.id).first()
    if not settings:
        settings = UserSettings(user_id=current_user.id)
        db.session.add(settings)
    settings.pulse_order = order
    db.session.commit()
    return jsonify({"success": True})


CRYPTO_SUFFIXES = {
    "BTC", "ETH", "SOL", "XRP", "ADA", "DOGE", "DOT", "AVAX",
    "MATIC", "LINK", "UNI", "ATOM", "NEAR", "LTC", "XLM", "ALGO",
    "FIL", "ICP", "HBAR", "VET", "SAND", "MANA", "APE", "SHIB",
    "TRX", "ETC", "BCH", "XMR", "FTM", "CRO", "AAVE", "MKR",
    "COMP", "SNX", "GRT", "RNDR", "OP", "ARB", "SUI", "SEI", "PEPE",
}

COMMODITY_ALIAS = {
    "GOLD": "GC=F", "SILVER": "SI=F", "OIL": "CL=F", "COPPER": "HG=F",
    "DXY": "DX=F", "VIX": "^VIX", "BITCOIN": "BTC-USD",
}


def _normalize_ticker(raw):
    """Normalize user input to a valid Yahoo Finance symbol."""
    t = raw.strip().upper()
    if "/" in t:
        return t
    if t in COMMODITY_ALIAS:
        return COMMODITY_ALIAS[t]
    if t in CRYPTO_SUFFIXES and not t.endswith("-USD"):
        return t + "-USD"
    return t


@api_market_bp.route("/pulse-cards", methods=["POST"])
@login_required
@csrf.exempt
def add_pulse_card():
    """Add a custom ticker to the pulse bar."""
    from ..models.settings import CustomPulseCard
    data = flask_request.get_json(silent=True) or {}
    raw_ticker = (data.get("ticker") or "").strip().upper()
    label = (data.get("label") or "").strip()
    if not raw_ticker:
        return jsonify({"error": "Ticker is required"}), 400
    ticker = _normalize_ticker(raw_ticker)
    if not label:
        label = raw_ticker
    existing = CustomPulseCard.query.filter_by(
        user_id=current_user.id, ticker=ticker
    ).first()
    if existing:
        return jsonify({"error": f"{raw_ticker} is already on your pulse bar"}), 400
    max_pos = db.session.query(db.func.max(CustomPulseCard.position)).filter_by(
        user_id=current_user.id
    ).scalar() or 0
    card = CustomPulseCard(
        user_id=current_user.id, ticker=ticker, label=label, position=max_pos + 1
    )
    db.session.add(card)
    db.session.commit()
    return jsonify({"success": True, "id": card.id})


@api_market_bp.route("/pulse-cards/<card_id>", methods=["DELETE"])
@login_required
@csrf.exempt
def remove_pulse_card(card_id):
    """Remove a pulse card (custom or hide a default)."""
    from ..models.settings import CustomPulseCard, UserSettings
    card = None
    if card_id.isdigit():
        card = CustomPulseCard.query.filter_by(id=int(card_id), user_id=current_user.id).first()
    if card:
        db.session.delete(card)
        db.session.commit()
        return jsonify({"success": True})
    settings = UserSettings.query.filter_by(user_id=current_user.id).first()
    if not settings:
        settings = UserSettings(user_id=current_user.id)
        db.session.add(settings)
    wo = dict(settings.widget_order or {}) if isinstance(settings.widget_order, dict) else {}
    hidden = list(wo.get("hidden_pulse", []))
    if card_id not in hidden:
        hidden.append(card_id)
    wo["hidden_pulse"] = hidden
    settings.widget_order = wo
    db.session.commit()
    return jsonify({"success": True})


@api_market_bp.route("/pulse-cards/restore-all", methods=["POST"])
@login_required
@csrf.exempt
def restore_all_pulse_cards():
    """Restore all hidden default pulse cards."""
    from ..models.settings import UserSettings
    settings = UserSettings.query.filter_by(user_id=current_user.id).first()
    if settings:
        wo = dict(settings.widget_order or {}) if isinstance(settings.widget_order, dict) else {}
        wo["hidden_pulse"] = []
        settings.widget_order = wo
        db.session.commit()
    return jsonify({"success": True})


@api_market_bp.route("/pulse-size", methods=["POST"])
@login_required
@csrf.exempt
def save_pulse_size():
    """Save the user's preferred pulse card size."""
    from ..models.settings import UserSettings
    data = flask_request.get_json(silent=True) or {}
    size = data.get("size", "default")
    if size not in ("compact", "default", "large"):
        size = "default"
    settings = UserSettings.query.filter_by(user_id=current_user.id).first()
    if not settings:
        settings = UserSettings(user_id=current_user.id)
        db.session.add(settings)
    widget_order = dict(settings.widget_order or {}) if isinstance(settings.widget_order, dict) else {}
    widget_order["pulse_size"] = size
    settings.widget_order = widget_order
    db.session.commit()
    return jsonify({"success": True})


@api_market_bp.route("/refresh", methods=["POST"])
@login_required
@csrf.exempt
def refresh_prices():
    """Trigger an on-demand price refresh and portfolio snapshot."""
    from ..services.market_data import refresh_all_prices
    from ..services.portfolio_service import snapshot_portfolio
    try:
        refresh_all_prices()
        snapshot_portfolio(current_user.id)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


_FX_CACHE = {}
_FX_CACHE_TTL = 300

@api_market_bp.route("/fx-rate")
@login_required
def fx_rate():
    """Return USD-to-target exchange rate via yfinance."""
    import time
    target = flask_request.args.get("to", "EUR").upper().strip()
    if target == "USD":
        return jsonify({"rate": 1, "currency": "USD"})
    allowed = {"EUR", "GBP", "JPY", "CAD", "AUD", "CHF", "CNY", "INR", "KRW", "MXN", "BRL", "SEK", "NOK", "NZD"}
    if target not in allowed:
        return jsonify({"error": "unsupported currency"}), 400

    cached = _FX_CACHE.get(target)
    if cached and (time.time() - cached["ts"]) < _FX_CACHE_TTL:
        return jsonify({"rate": cached["rate"], "currency": target})

    try:
        pair = f"{target}=X"
        tk = yf.Ticker(pair)
        raw = tk.fast_info.last_price
        if raw and raw > 0:
            rate = 1.0 / raw
            _FX_CACHE[target] = {"rate": rate, "ts": time.time()}
            return jsonify({"rate": rate, "currency": target})
        return jsonify({"error": "rate unavailable"}), 502
    except Exception as e:
        return jsonify({"error": str(e)}), 502
