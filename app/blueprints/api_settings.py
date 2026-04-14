"""Settings & integrations API routes.

Manage Coinbase API keys, trigger manual sync, and other user settings.
"""

from flask import Blueprint, jsonify, request as flask_request
from flask_login import login_required, current_user

from ..extensions import db
from ..utils.auth import requires_pro, requires_mfa_recent
from ..models.settings import UserSettings
from ..utils.audit import log_event

api_settings_bp = Blueprint("api_settings", __name__)


@api_settings_bp.route("/settings/integrations")
@login_required
@requires_pro
def get_integrations():
    """Return current integration status (connected or not, no secrets)."""
    from ..utils.encryption import decrypt
    settings = UserSettings.query.filter_by(user_id=current_user.id).first()
    coinbase_connected = bool(
        settings
        and settings.coinbase_key_name
        and settings.coinbase_private_key
    )
    key_hint = None
    if coinbase_connected:
        plain = decrypt(settings.coinbase_key_name)
        key_hint = (plain[:20] + "...") if plain else None
    return jsonify({
        "coinbase": {
            "connected": coinbase_connected,
            "key_hint": key_hint,
        },
    })


@api_settings_bp.route("/settings/coinbase-keys", methods=["POST"])
@login_required
@requires_pro
@requires_mfa_recent
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

    from ..utils.encryption import encrypt
    settings.coinbase_key_name = encrypt(key_name)
    settings.coinbase_private_key = encrypt(private_key)
    db.session.commit()
    log_event("coinbase_keys_saved")

    return jsonify({"success": True, "message": "Coinbase keys saved"})


@api_settings_bp.route("/settings/coinbase-keys", methods=["DELETE"])
@login_required
@requires_pro
@requires_mfa_recent
def delete_coinbase_keys():
    """Remove stored Coinbase API keys."""
    settings = UserSettings.query.filter_by(user_id=current_user.id).first()
    if settings:
        settings.coinbase_key_name = None
        settings.coinbase_private_key = None
        db.session.commit()
        log_event("coinbase_keys_deleted")
    return jsonify({"success": True, "message": "Coinbase keys removed"})


@api_settings_bp.route("/settings/bucket-rollup")
@login_required
def get_bucket_rollup():
    """Return the user's category rollup overrides merged with defaults."""
    from ..utils.buckets import BUCKET_PARENTS, STANDARD_BUCKETS
    settings = UserSettings.query.filter_by(user_id=current_user.id).first()
    overrides = (settings.bucket_rollup or {}) if settings else {}
    effective = dict(BUCKET_PARENTS)
    for child, parent in overrides.items():
        if parent is None:
            effective.pop(child, None)
        else:
            effective[child] = parent
    return jsonify({
        "defaults": BUCKET_PARENTS,
        "overrides": overrides,
        "effective": effective,
        "standard_buckets": STANDARD_BUCKETS,
    })


@api_settings_bp.route("/settings/bucket-rollup", methods=["POST"])
@login_required
def save_bucket_rollup():
    """Save the user's category rollup overrides."""
    data = flask_request.get_json(silent=True) or {}
    overrides = data.get("overrides", {})
    settings = UserSettings.query.filter_by(user_id=current_user.id).first()
    if not settings:
        settings = UserSettings(user_id=current_user.id)
        db.session.add(settings)
    settings.bucket_rollup = overrides
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(settings, "bucket_rollup")
    db.session.commit()
    return jsonify({"success": True})


@api_settings_bp.route("/coinbase-sync", methods=["POST"])
@login_required
@requires_pro
def trigger_coinbase_sync():
    """Manually trigger a Coinbase balance sync for the current user."""
    from ..services.coinbase_service import sync_user_coinbase
    result = sync_user_coinbase(current_user.id)
    if "error" in result:
        return jsonify(result), 400
    return jsonify({"success": True, **result})


@api_settings_bp.route("/settings/category-colors")
@login_required
def get_category_colors():
    """Return the user's custom category color overrides."""
    settings = UserSettings.query.filter_by(user_id=current_user.id).first()
    wo = (settings.widget_order if settings and isinstance(settings.widget_order, dict) else {}) or {}
    return jsonify({"colors": wo.get("category_colors", {})})


@api_settings_bp.route("/settings/category-colors", methods=["POST"])
@login_required
def save_category_colors():
    """Save the user's custom category color overrides."""
    data = flask_request.get_json(silent=True) or {}
    colors = data.get("colors", {})
    settings = UserSettings.query.filter_by(user_id=current_user.id).first()
    if not settings:
        settings = UserSettings(user_id=current_user.id, widget_order={})
        db.session.add(settings)
    wo = settings.widget_order if isinstance(settings.widget_order, dict) else {}
    wo["category_colors"] = colors
    settings.widget_order = wo
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(settings, "widget_order")
    db.session.commit()
    return jsonify({"success": True})


@api_settings_bp.route("/settings/digest", methods=["POST"])
@login_required
@requires_pro
def save_digest_prefs():
    """Save email digest preferences."""
    data = flask_request.get_json(silent=True) or {}
    settings = UserSettings.query.filter_by(user_id=current_user.id).first()
    if not settings:
        settings = UserSettings(user_id=current_user.id)
        db.session.add(settings)
    settings.digest_enabled = bool(data.get("enabled", False))
    freq = data.get("frequency", "weekly")
    if freq not in ("daily", "weekly", "monthly"):
        freq = "weekly"
    settings.digest_frequency = freq
    day = data.get("day", "monday")
    if day not in ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"):
        day = "monday"
    settings.digest_day = day
    db.session.commit()
    return jsonify({"ok": True})


@api_settings_bp.route("/settings/digest/test", methods=["POST"])
@login_required
@requires_pro
def test_digest():
    """Send a test portfolio digest email to the current user."""
    from ..services.digest_service import send_digest
    settings = UserSettings.query.filter_by(user_id=current_user.id).first()
    if not settings:
        settings = UserSettings(user_id=current_user.id)
        db.session.add(settings)
        db.session.commit()
    ok = send_digest(current_user, settings)
    if ok:
        return jsonify({"ok": True, "message": "Test digest sent to " + current_user.email})
    return jsonify({"ok": False, "error": "Failed to send digest. Check email config."}), 500


@api_settings_bp.route(
    "/settings/onboarding-complete", methods=["POST"]
)
@login_required
def mark_onboarding_complete():
    """Mark the current user's onboarding as done."""
    settings = UserSettings.query.filter_by(
        user_id=current_user.id).first()
    if not settings:
        settings = UserSettings(user_id=current_user.id)
        db.session.add(settings)
    settings.onboarding_completed = True
    db.session.commit()
    return jsonify({"success": True})


# ── Admin: Promo Codes ──────────────────────────────────────────────

@api_settings_bp.route("/admin/promo-codes", methods=["GET"])
@login_required
def list_promo_codes():
    if not getattr(current_user, "is_admin", False):
        return jsonify({"error": "forbidden"}), 403
    from ..models.user import PromoCode
    codes = PromoCode.query.order_by(PromoCode.created_at.desc()).all()
    return jsonify({"codes": [
        {
            "id": c.id, "code": c.code, "trial_days": c.trial_days,
            "max_uses": c.max_uses, "times_used": c.times_used,
            "expires_at": c.expires_at.isoformat() if c.expires_at else None,
            "active": c.active, "is_valid": c.is_valid, "note": c.note,
        } for c in codes
    ]})


@api_settings_bp.route("/admin/promo-codes", methods=["POST"])
@login_required
def create_promo_code():
    if not getattr(current_user, "is_admin", False):
        return jsonify({"error": "forbidden"}), 403
    from datetime import datetime as _dt, timezone as _tz
    from ..models.user import PromoCode

    data = flask_request.get_json(silent=True) or {}
    code = (data.get("code") or "").strip().upper()
    if not code:
        return jsonify({"error": "code is required"}), 400
    if PromoCode.query.filter_by(code=code).first():
        return jsonify({"error": "code already exists"}), 409

    trial_days = int(data.get("trial_days", 14))
    max_uses = data.get("max_uses")
    expires_at = None
    if data.get("expires_at"):
        try:
            expires_at = _dt.fromisoformat(data["expires_at"]).replace(tzinfo=_tz.utc)
        except (ValueError, TypeError):
            pass

    promo = PromoCode(
        code=code, trial_days=trial_days,
        max_uses=int(max_uses) if max_uses else None,
        expires_at=expires_at, active=True,
        note=data.get("note", ""),
    )
    db.session.add(promo)
    db.session.commit()
    return jsonify({"ok": True, "id": promo.id, "code": promo.code}), 201


@api_settings_bp.route("/admin/promo-codes/<int:promo_id>", methods=["DELETE"])
@login_required
def deactivate_promo_code(promo_id):
    if not getattr(current_user, "is_admin", False):
        return jsonify({"error": "forbidden"}), 403
    from ..models.user import PromoCode
    promo = PromoCode.query.get_or_404(promo_id)
    promo.active = False
    db.session.commit()
    return jsonify({"ok": True})


@api_settings_bp.route("/admin/audit-log", methods=["GET"])
@login_required
def admin_audit_log():
    """Query recent audit log entries (admin only)."""
    if not getattr(current_user, "is_admin", False):
        return jsonify({"error": "forbidden"}), 403

    from ..models.audit import AuditLog

    limit = min(int(flask_request.args.get("limit", 50)), 200)
    action_filter = flask_request.args.get("action")
    user_filter = flask_request.args.get("user_id", type=int)

    q = AuditLog.query.order_by(AuditLog.created_at.desc())
    if action_filter:
        q = q.filter_by(action=action_filter)
    if user_filter:
        q = q.filter_by(user_id=user_filter)

    entries = q.limit(limit).all()
    return jsonify({"entries": [
        {
            "id": e.id,
            "user_id": e.user_id,
            "action": e.action,
            "detail": e.detail,
            "ip_address": e.ip_address,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        } for e in entries
    ]})
