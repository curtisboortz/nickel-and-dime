"""Plaid integration API routes.

Link token creation, public token exchange, account listing,
manual sync, disconnect, and webhook receiver.
"""

import hashlib
import hmac
import json
import logging
import os
import time

import requests as http_requests
from flask import Blueprint, jsonify, request as flask_request
from flask_login import login_required, current_user

from ..extensions import csrf, db
from ..models.plaid import PlaidItem
from ..utils.auth import requires_pro, requires_mfa_recent
from ..utils.audit import log_event

api_plaid_bp = Blueprint("api_plaid", __name__)
log = logging.getLogger(__name__)

_jwk_cache: dict = {}


def _verify_plaid_webhook(request) -> bool:
    """Verify Plaid webhook signature using JWK-based JWT verification.

    Returns True if verification passes or if Plaid credentials are not
    configured (allows local/sandbox development without verification).
    Returns False if verification fails.
    """
    from jose import jwt as jose_jwt, JWTError

    client_id = os.environ.get("PLAID_CLIENT_ID", "")
    secret = os.environ.get("PLAID_SECRET", "")
    if not client_id or not secret:
        return True

    signed_jwt = request.headers.get("Plaid-Verification")
    if not signed_jwt:
        log.warning("Plaid webhook missing Plaid-Verification header")
        return False

    try:
        unverified_header = jose_jwt.get_unverified_header(signed_jwt)
    except JWTError:
        log.warning("Plaid webhook: invalid JWT header")
        return False

    kid = unverified_header.get("kid")
    if not kid:
        log.warning("Plaid webhook: JWT header missing kid")
        return False

    if kid not in _jwk_cache or (
        _jwk_cache[kid].get("expired_at") is not None
    ):
        env_name = os.environ.get("PLAID_ENV", "sandbox").lower()
        base_urls = {
            "sandbox": "https://sandbox.plaid.com",
            "development": "https://development.plaid.com",
            "production": "https://production.plaid.com",
        }
        base_url = base_urls.get(env_name, "https://sandbox.plaid.com")
        try:
            resp = http_requests.post(
                f"{base_url}/webhook_verification_key/get",
                json={"client_id": client_id, "secret": secret, "key_id": kid},
                timeout=10,
            )
            if resp.status_code != 200:
                log.warning("Plaid JWK fetch failed: %s", resp.status_code)
                return False
            key_data = resp.json().get("key", {})
            _jwk_cache[kid] = key_data
        except Exception:
            log.exception("Plaid JWK fetch error")
            return False

    key = _jwk_cache.get(kid)
    if not key:
        return False

    if key.get("expired_at") is not None:
        log.warning("Plaid webhook: JWK key %s is expired", kid)
        return False

    try:
        claims = jose_jwt.decode(signed_jwt, key, algorithms=["ES256"])
    except JWTError:
        log.warning("Plaid webhook: JWT signature verification failed")
        return False

    if claims.get("iat", 0) < time.time() - 5 * 60:
        log.warning("Plaid webhook: JWT is too old (iat=%s)", claims.get("iat"))
        return False

    body_hash = hashlib.sha256(request.get_data()).hexdigest()
    claimed_hash = claims.get("request_body_sha256", "")
    if not hmac.compare_digest(body_hash, claimed_hash):
        log.warning("Plaid webhook: body hash mismatch")
        return False

    return True


@api_plaid_bp.route("/plaid/link-token", methods=["POST"])
@login_required
@requires_pro
@requires_mfa_recent
def create_link_token():
    """Create a Plaid Link token for the current user."""
    from ..services.plaid_service import create_link_token as _create

    try:
        result = _create(current_user.id)
        return jsonify({"link_token": result.get("link_token")})
    except RuntimeError:
        log.exception("Link token creation failed (config error)")
        return jsonify({"error": "Failed to create link token"}), 500
    except Exception as e:
        log.error("Link token creation failed: %s", e)
        return jsonify({"error": "Failed to create link token"}), 500


@api_plaid_bp.route("/plaid/exchange-token", methods=["POST"])
@login_required
@requires_pro
@requires_mfa_recent
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
        log_event("plaid_linked", detail={"institution": item.institution_name})
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
        log_event("plaid_unlinked", detail={"institution": item.institution_name})
        return jsonify({"success": True})
    except Exception as e:
        log.error("Plaid disconnect failed for item %d: %s", item_id, e)
        return jsonify({"error": "Disconnect failed"}), 500


@api_plaid_bp.route("/plaid/webhook", methods=["POST"])
@csrf.exempt
def plaid_webhook():
    """Receive Plaid webhooks for item status and data updates."""
    if not _verify_plaid_webhook(flask_request):
        return jsonify({"error": "Invalid webhook signature"}), 401

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
