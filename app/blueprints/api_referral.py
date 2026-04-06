"""Referral system API routes."""

from flask import Blueprint, jsonify, request as flask_request
from flask_login import login_required, current_user

api_referral_bp = Blueprint("api_referral", __name__)


@api_referral_bp.route("/referral/code", methods=["GET"])
@login_required
def get_referral_code():
    """Get or create the user's referral code."""
    from ..services.referral_service import (
        get_or_create_code,
    )
    rc = get_or_create_code(current_user.id)
    return jsonify({"code": rc.code})


@api_referral_bp.route(
    "/referral/stats", methods=["GET"]
)
@login_required
def referral_stats():
    """Get referral stats for the current user."""
    from ..services.referral_service import (
        get_referral_stats,
    )
    return jsonify(get_referral_stats(current_user.id))


@api_referral_bp.route(
    "/referral/redeem", methods=["POST"]
)
@login_required
def redeem_referral():
    """Redeem a referral code."""
    from ..services.referral_service import redeem_code

    data = flask_request.get_json(silent=True) or {}
    code = data.get("code", "")
    if not code:
        return jsonify({"error": "Code is required"}), 400

    ok, msg = redeem_code(code, current_user.id)
    if not ok:
        return jsonify({"error": msg}), 400
    return jsonify({"success": True, "message": msg})
