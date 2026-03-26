"""Economics API routes: FRED data, economic calendar, FedWatch, sentiment."""

from flask import Blueprint, jsonify, request as flask_request
from flask_login import login_required

from ..extensions import db
from ..models.market import FredCache, EconCalendarCache, SentimentCache

api_economics_bp = Blueprint("api_economics", __name__)


# Free-tier FRED groups (available to all users)
FREE_FRED_GROUPS = {"debt_fiscal", "cpi_pce", "monetary_policy"}


@api_economics_bp.route("/fred-data")
@login_required
def fred_data():
    """Return cached FRED series data."""
    from ..utils.auth import is_pro
    group = flask_request.args.get("group", "")

    if not is_pro() and group and group not in FREE_FRED_GROUPS:
        return jsonify({
            "error": "Pro plan required for this data group.",
            "upgrade": True,
        }), 403

    if group:
        cached = FredCache.query.get(group)
        return jsonify({"group": group, "data": cached.data if cached else None})

    # Return all groups (filter by tier)
    all_cache = FredCache.query.all()
    result = {}
    for c in all_cache:
        if is_pro() or c.series_group in FREE_FRED_GROUPS:
            result[c.series_group] = c.data
    return jsonify({"data": result})


@api_economics_bp.route("/economic-calendar")
@login_required
def economic_calendar():
    """Return economic calendar events for a given week offset."""
    offset = flask_request.args.get("offset", "0", type=int)
    offset = max(-8, min(4, offset))

    # TODO: Migrate calendar_service logic here (currently in routes.py)
    # For now, read from DB cache
    from datetime import datetime, timedelta
    today = datetime.now().date()
    monday = today - timedelta(days=today.weekday()) + timedelta(weeks=offset)
    friday = monday + timedelta(days=4)
    week_key = monday.isoformat()
    week_label = f"{monday.strftime('%b %d')} – {friday.strftime('%b %d, %Y')}"

    cached = EconCalendarCache.query.get(week_key)
    return jsonify({
        "events": cached.events if cached else [],
        "week_label": week_label,
        "offset": offset,
    })


@api_economics_bp.route("/fedwatch")
@login_required
def fedwatch():
    """Return FedWatch probability data."""
    # TODO: Migrate from routes.py
    return jsonify({"meetings": [], "current_rate": None})


@api_economics_bp.route("/sentiment")
@login_required
def sentiment():
    """Return sentiment data in the format the dashboard gauges expect."""
    from ..models.market import PriceCache

    cnn = SentimentCache.query.get("cnn_fg")
    crypto = SentimentCache.query.get("crypto_fg")

    result = {}

    if cnn and cnn.data:
        score = cnn.data.get("score", 0)
        result["stock"] = {
            "value": score,
            "score": score,
            "label": _fg_label(score),
        }

    if crypto and crypto.data:
        score = crypto.data.get("score", 0)
        result["crypto"] = {
            "value": score,
            "score": score,
            "label": crypto.data.get("label") or _fg_label(score),
        }

    vix_row = PriceCache.query.get("^VIX")
    if vix_row and vix_row.price:
        vix = vix_row.price
        vix_score = max(0, min(100, 100 - ((vix - 12) / 28) * 100))
        if vix < 15:
            lbl = "Extreme Greed"
        elif vix < 20:
            lbl = "Greed"
        elif vix < 25:
            lbl = "Neutral"
        elif vix < 30:
            lbl = "Fear"
        else:
            lbl = "Extreme Fear"
        result["vix"] = {"value": round(vix, 2), "score": round(vix_score), "label": lbl}

    gold_row = PriceCache.query.get("GC=F")
    if gold_row and gold_row.price and gold_row.change_pct is not None:
        chg = gold_row.change_pct
        score = max(0, min(100, 50 + chg * 10))
        result["gold"] = {
            "value": round(gold_row.price, 2),
            "score": round(score),
            "label": "Rising" if chg > 0.5 else ("Falling" if chg < -0.5 else "Stable"),
        }

    tnx_10 = PriceCache.query.get("^TNX")
    tnx_2 = PriceCache.query.get("2YY=F")
    if tnx_10 and tnx_2 and tnx_10.price and tnx_2.price:
        spread = tnx_10.price - tnx_2.price
        if spread < -0.5:
            lbl, score = "Inverted", 15
        elif spread < 0:
            lbl, score = "Flat/Inverted", 35
        elif spread < 0.5:
            lbl, score = "Flat", 50
        else:
            lbl, score = "Normal", 75
        result["yield_curve"] = {
            "value": round(spread, 2), "score": score, "label": lbl,
            "spread": round(spread, 2),
        }

    return jsonify(result)


def _fg_label(score):
    if score >= 75:
        return "Extreme Greed"
    if score >= 55:
        return "Greed"
    if score >= 45:
        return "Neutral"
    if score >= 25:
        return "Fear"
    return "Extreme Fear"


@api_economics_bp.route("/cape")
@login_required
def cape():
    """Return Shiller CAPE ratio data."""
    # TODO: Migrate from routes.py (multpl.com scraper)
    return jsonify({"cape": None})


@api_economics_bp.route("/buffett")
@login_required
def buffett():
    """Return Buffett indicator data."""
    # TODO: Migrate from routes.py
    return jsonify({"indicator": None})
