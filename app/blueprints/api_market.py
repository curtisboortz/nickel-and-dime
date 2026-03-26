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
    for card in custom_cards:
        row = prices.get(card.ticker)
        if row:
            result[f"custom-{card.id}"] = row.price

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

    result = {}
    for key in keys:
        lkey = key.lower()
        if lkey.startswith("custom-"):
            card_id = key.split("-", 1)[1]
            card = CustomPulseCard.query.filter_by(id=card_id).first()
            yf_sym = card.ticker if card else key
        else:
            yf_sym = SPARK_SYMBOL_MAP.get(lkey, key)
        try:
            ticker = yf.Ticker(yf_sym)
            hist = ticker.history(period="5d", interval="30m")
            if hist.empty:
                hist = ticker.history(period="1mo", interval="1d")
            closes = [round(row["Close"], 4) for _, row in hist.iterrows()]
            if len(closes) > 1:
                result[key] = closes
        except Exception:
            pass

    return jsonify(result)


@api_market_bp.route("/historical")
@login_required
def historical():
    """Return OHLC historical data for chart modals."""
    symbol = flask_request.args.get("symbol", "SPY")
    period = flask_request.args.get("period", "1mo")
    interval = flask_request.args.get("interval", "1d")

    try:
        dxy_syms = ["DX-Y.NYB", "DX=F"] if symbol == "DX=F" else [symbol]
        data = []
        for actual_sym in dxy_syms:
            ticker = yf.Ticker(actual_sym)
            hist = ticker.history(period=period, interval=interval)
            if not hist.empty:
                data = [{"t": str(idx),
                         "o": round(row["Open"], 4),
                         "h": round(row["High"], 4),
                         "l": round(row["Low"], 4),
                         "c": round(row["Close"], 4),
                         "v": int(row.get("Volume", 0))}
                        for idx, row in hist.iterrows()]
                if data:
                    break
    except Exception:
        data = []

    return jsonify({"symbol": symbol, "period": period, "data": data})


@api_market_bp.route("/pulse-order", methods=["POST"])
@login_required
@csrf.exempt
def save_pulse_order():
    """Persist the user's pulse card order."""
    from ..models.settings import UserSettings
    data = flask_request.get_json(silent=True) or {}
    order = data.get("order", [])
    settings = UserSettings.query.filter_by(user_id=current_user.id).first()
    if settings:
        settings.pulse_order = order
        db.session.commit()
    return jsonify({"success": True})


@api_market_bp.route("/pulse-cards", methods=["POST"])
@login_required
@csrf.exempt
def add_pulse_card():
    """Add a custom ticker to the pulse bar."""
    from ..models.settings import CustomPulseCard
    data = flask_request.get_json(silent=True) or {}
    ticker = (data.get("ticker") or "").strip().upper()
    label = (data.get("label") or ticker).strip()
    if not ticker:
        return jsonify({"error": "Ticker is required"}), 400
    existing = CustomPulseCard.query.filter_by(
        user_id=current_user.id, ticker=ticker
    ).first()
    if existing:
        return jsonify({"error": f"{ticker} is already on your pulse bar"}), 400
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
