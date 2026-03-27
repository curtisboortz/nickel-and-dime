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
    """Return sentiment data in the format the dashboard gauges expect.

    Each gauge receives a 0-100 `value` for the needle and a human `label`.
    VIX additionally carries the raw VIX in `score` (used by subtitle).
    Yield curve additionally carries the raw `spread`.
    """
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
    vix_val = vix_row.price if vix_row and vix_row.price else 0
    if vix_val:
        vix_score = _vix_to_score(vix_val)
        result["vix"] = {
            "value": round(vix_val, 1),
            "score": vix_score,
            "label": _fg_label(vix_score),
        }

    gold_row = PriceCache.query.get("GC=F")
    dxy_row = PriceCache.query.get("DX=F")
    gvz_row = PriceCache.query.get("^GVZ")
    gold_price = gold_row.price if gold_row and gold_row.price else 0
    dxy = dxy_row.price if dxy_row and dxy_row.price else 0
    gvz = gvz_row.price if gvz_row and gvz_row.price else 0
    if gold_price:
        gold_score = _compute_gold_sentiment(gold_price, vix_val, dxy, gvz)
        result["gold"] = {"value": gold_score, "label": _fg_label(gold_score)}

    tnx_10 = PriceCache.query.get("^TNX")
    tnx_2 = PriceCache.query.get("2YY=F")
    if tnx_10 and tnx_2 and tnx_10.price and tnx_2.price:
        spread = tnx_10.price - tnx_2.price
        yc_score = _yield_curve_to_score(spread)
        result["yield_curve"] = {
            "value": yc_score,
            "spread": round(spread, 2),
            "label": _fg_label(yc_score),
        }

    return jsonify(result)


def _vix_to_score(vix):
    """Map VIX to 0-100 sentiment (low VIX = greed, high VIX = fear)."""
    if vix <= 12:
        return 100
    elif vix <= 20:
        return int(60 + (20 - vix) * 5)
    elif vix <= 30:
        return int(60 - (vix - 20) * 4)
    elif vix <= 40:
        return int(20 - (vix - 30) * 2)
    else:
        return 0


def _compute_gold_sentiment(gold_price, vix, dxy, gvz):
    """Compute a 0-100 gold sentiment score from available signals.

    Higher = more bullish/greed for gold.
    Signals: low DXY, high VIX (safe-haven demand), low GVZ (calm accumulation),
    high gold price (momentum).
    """
    score = 50

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
    """Map 10Y-2Y spread to 0-100 sentiment. Inverted = fear, steep = greed."""
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


def _fg_label(score):
    if score <= 25:
        return "Extreme Fear"
    if score <= 45:
        return "Fear"
    if score <= 55:
        return "Neutral"
    if score <= 75:
        return "Greed"
    return "Extreme Greed"


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
