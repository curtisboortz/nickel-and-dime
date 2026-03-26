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
            row = prices.get(f"CG:{ch.symbol}")
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


@api_market_bp.route("/sparklines")
@login_required
def sparklines():
    """Return intraday sparkline data for a given symbol."""
    symbol = flask_request.args.get("symbol", "SPY")
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="1d", interval="5m")
        points = [{"t": str(idx), "y": round(row["Close"], 2)}
                  for idx, row in hist.iterrows()]
    except Exception:
        points = []
    return jsonify({"symbol": symbol, "points": points})


@api_market_bp.route("/historical")
@login_required
def historical():
    """Return OHLC historical data for chart modals."""
    symbol = flask_request.args.get("symbol", "SPY")
    period = flask_request.args.get("period", "1mo")
    interval = flask_request.args.get("interval", "1d")

    try:
        actual_sym = symbol
        if symbol == "DX=F" and period in ("1d", "5d"):
            actual_sym = "DX-Y.NYB"

        ticker = yf.Ticker(actual_sym)
        hist = ticker.history(period=period, interval=interval)
        data = [{"t": str(idx),
                 "o": round(row["Open"], 4),
                 "h": round(row["High"], 4),
                 "l": round(row["Low"], 4),
                 "c": round(row["Close"], 4),
                 "v": int(row.get("Volume", 0))}
                for idx, row in hist.iterrows()]
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
