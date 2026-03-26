"""Settings & integrations API routes.

Manage Coinbase API keys, trigger manual sync, and other user settings.
"""

from flask import Blueprint, jsonify, request as flask_request
from flask_login import login_required, current_user

from ..extensions import db, csrf
from ..utils.auth import requires_pro
from ..models.settings import UserSettings

api_settings_bp = Blueprint("api_settings", __name__)


@api_settings_bp.route("/settings/integrations")
@login_required
@requires_pro
def get_integrations():
    """Return current integration status (connected or not, no secrets)."""
    settings = UserSettings.query.filter_by(user_id=current_user.id).first()
    coinbase_connected = bool(
        settings
        and settings.coinbase_key_name
        and settings.coinbase_private_key
    )
    return jsonify({
        "coinbase": {
            "connected": coinbase_connected,
            "key_hint": (settings.coinbase_key_name[:20] + "...")
                        if coinbase_connected else None,
        },
    })


@api_settings_bp.route("/settings/coinbase-keys", methods=["POST"])
@login_required
@requires_pro
@csrf.exempt
def save_coinbase_keys():
    """Save Coinbase API key name and private key."""
    data = flask_request.get_json(silent=True) or {}
    key_name = (data.get("key_name") or "").strip()
    private_key = (data.get("private_key") or "").strip()

    if not key_name or not private_key:
        return jsonify({"error": "Both key_name and private_key are required"}), 400

    if "BEGIN" not in private_key and "PRIVATE" not in private_key:
        return jsonify({"error": "private_key should be a PEM-formatted EC private key"}), 400

    settings = UserSettings.query.filter_by(user_id=current_user.id).first()
    if not settings:
        settings = UserSettings(user_id=current_user.id)
        db.session.add(settings)

    settings.coinbase_key_name = key_name
    settings.coinbase_private_key = private_key
    db.session.commit()

    return jsonify({"success": True, "message": "Coinbase keys saved"})


@api_settings_bp.route("/settings/coinbase-keys", methods=["DELETE"])
@login_required
@requires_pro
@csrf.exempt
def delete_coinbase_keys():
    """Remove stored Coinbase API keys."""
    settings = UserSettings.query.filter_by(user_id=current_user.id).first()
    if settings:
        settings.coinbase_key_name = None
        settings.coinbase_private_key = None
        db.session.commit()
    return jsonify({"success": True, "message": "Coinbase keys removed"})


@api_settings_bp.route("/coinbase-sync", methods=["POST"])
@login_required
@requires_pro
@csrf.exempt
def trigger_coinbase_sync():
    """Manually trigger a Coinbase balance sync for the current user."""
    from ..services.coinbase_service import sync_user_coinbase
    result = sync_user_coinbase(current_user.id)
    if "error" in result:
        return jsonify(result), 400
    return jsonify({"success": True, **result})
