"""Plaid integration API routes.

Link token creation, public token exchange, account listing,
manual sync, disconnect, and webhook receiver.
"""

import logging

from flask import Blueprint, jsonify, request as flask_request
from flask_login import login_required, current_user

from ..extensions import csrf, db
from ..models.plaid import PlaidItem
from ..utils.auth import requires_pro

api_plaid_bp = Blueprint("api_plaid", __name__)
log = logging.getLogger(__name__)


@api_plaid_bp.route("/plaid/link-token", methods=["POST"])
@login_required
@requires_pro
def create_link_token():
    """Create a Plaid Link token for the current user."""
    from ..services.plaid_service import create_link_token as _create

    try:
        result = _create(current_user.id)
        return jsonify({"link_token": result.get("link_token")})
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        log.error("Link token creation failed: %s", e)
        return jsonify({"error": "Failed to create link token"}), 500


@api_plaid_bp.route("/plaid/exchange-token", methods=["POST"])
@login_required
@requires_pro
def exchange_token():
    """Exchange a Plaid public token for an access token and start initial sync."""
    from ..services.plaid_service import exchange_public_token, sync_plaid_item

    data = flask_request.get_json(silent=True) or {}
    public_token = data.get("public_token")
    metadata = data.get("metadata", {})

    if not public_token:
        return jsonify({"error": "public_token is required"}), 400

    try:
        item = exchange_public_token(current_user.id, public_token, metadata)
        result = sync_plaid_item(current_user.id, item)
        return jsonify({
            "success": True,
            "item_id": item.id,
            "institution": item.institution_name,
            "sync": result,
        })
    except Exception as e:
        log.error("Token exchange failed: %s", e)
        return jsonify({"error": "Failed to link account"}), 500


@api_plaid_bp.route("/plaid/accounts", methods=["GET"])
@login_required
@requires_pro
def list_accounts():
    """List the current user's connected Plaid institutions."""
    try:
        items = (PlaidItem.query.filter_by(user_id=current_user.id)
                 .order_by(PlaidItem.created_at).all())
    except Exception:
        db.session.rollback()
        items = []
    out = []
    for item in items:
        entry = {
            "id": item.id,
            "institution_name": item.institution_name,
            "institution_id": item.institution_id,
            "status": item.status,
            "error_code": item.error_code,
            "products": item.products or [],
            "last_synced_at": (item.last_synced_at.isoformat()
                              if item.last_synced_at else None),
            "created_at": item.created_at.isoformat() if item.created_at else None,
        }
        if hasattr(item, "logo_base64"):
            entry["logo_base64"] = item.logo_base64
        if hasattr(item, "primary_color"):
            entry["primary_color"] = item.primary_color
        out.append(entry)
    return jsonify({"accounts": out})


@api_plaid_bp.route("/plaid/sync/<int:item_id>", methods=["POST"])
@login_required
@requires_pro
def sync_item(item_id):
    """Manually trigger a sync for one connected institution."""
    from ..services.plaid_service import sync_plaid_item

    item = PlaidItem.query.filter_by(id=item_id, user_id=current_user.id).first()
    if not item:
        return jsonify({"error": "Account not found"}), 404

    try:
        result = sync_plaid_item(current_user.id, item)
        return jsonify({"success": True, "sync": result})
    except Exception as e:
        log.error("Manual Plaid sync failed for item %d: %s", item_id, e)
        return jsonify({"error": "Sync failed"}), 500


@api_plaid_bp.route("/plaid/accounts/<int:item_id>", methods=["DELETE"])
@login_required
@requires_pro
def disconnect_account(item_id):
    """Disconnect a Plaid institution and remove its associated data."""
    from ..services.plaid_service import remove_item

    item = PlaidItem.query.filter_by(id=item_id, user_id=current_user.id).first()
    if not item:
        return jsonify({"error": "Account not found"}), 404

    try:
        remove_item(item)
        return jsonify({"success": True})
    except Exception as e:
        log.error("Plaid disconnect failed for item %d: %s", item_id, e)
        return jsonify({"error": "Disconnect failed"}), 500


@api_plaid_bp.route("/plaid/webhook", methods=["POST"])
@csrf.exempt
def plaid_webhook():
    """Receive Plaid webhooks for item status and data updates.

    Plaid signs webhooks with JWKs but for MVP we just process known types.
    In production, verify the webhook signature.
    """
    data = flask_request.get_json(silent=True) or {}
    webhook_type = data.get("webhook_type", "")
    webhook_code = data.get("webhook_code", "")
    item_id_str = data.get("item_id", "")

    log.info("Plaid webhook: type=%s code=%s item=%s",
             webhook_type, webhook_code, item_id_str)

    if not item_id_str:
        return jsonify({"received": True})

    item = PlaidItem.query.filter_by(item_id=item_id_str).first()
    if not item:
        log.warning("Webhook for unknown item_id: %s", item_id_str)
        return jsonify({"received": True})

    if webhook_type == "ITEM":
        if webhook_code == "ERROR":
            error = data.get("error", {})
            item.status = "error"
            item.error_code = error.get("error_code", "UNKNOWN")
            db.session.commit()
        elif webhook_code == "PENDING_EXPIRATION":
            item.status = "login_required"
            db.session.commit()

    elif webhook_type in ("HOLDINGS", "INVESTMENTS_TRANSACTIONS"):
        from ..services.plaid_service import sync_plaid_item
        try:
            sync_plaid_item(item.user_id, item)
        except Exception as e:
            log.error("Webhook-triggered sync failed: %s", e)

    elif webhook_type == "TRANSACTIONS":
        txn_codes = ("SYNC_UPDATES_AVAILABLE",
                     "DEFAULT_UPDATE", "HISTORICAL_UPDATE")
        if webhook_code in txn_codes:
            from ..services.plaid_service import sync_transactions
            try:
                sync_transactions(item.user_id, item)
            except Exception as e:
                log.error("Webhook-triggered txn sync failed: %s", e)

    return jsonify({"received": True})
