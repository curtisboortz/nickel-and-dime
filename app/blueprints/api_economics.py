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
    """Return cached sentiment data (CNN F&G, crypto F&G)."""
    cnn = SentimentCache.query.get("cnn_fg")
    crypto = SentimentCache.query.get("crypto_fg")
    return jsonify({
        "cnn": cnn.data if cnn else None,
        "crypto": crypto.data if crypto else None,
    })


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
