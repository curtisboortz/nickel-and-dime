"""Market data API routes: live prices, sparklines, historical charts."""

import yfinance as yf
from flask import Blueprint, jsonify, request as flask_request
from flask_login import login_required, current_user

from ..extensions import db, csrf
from ..models.market import PriceCache

api_market_bp = Blueprint("api_market", __name__)


@api_market_bp.route("/live-data")
@login_required
def live_data():
    """Return latest cached prices for the pulse bar and dashboard cards."""
    prices = {p.symbol: {"price": p.price, "change_pct": p.change_pct,
                         "source": p.source}
              for p in PriceCache.query.all()}
    return jsonify({"prices": prices})


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
