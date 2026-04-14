"""MFA (TOTP) setup and verification API routes."""

import io
import time
import base64

import pyotp
import qrcode
from flask import Blueprint, jsonify, request as flask_request, session
from flask_login import login_required, current_user

from ..extensions import db
from ..utils.encryption import encrypt, decrypt
from ..utils.audit import log_event
from ..utils.auth import requires_mfa_recent

api_mfa_bp = Blueprint("api_mfa", __name__)


@api_mfa_bp.route("/mfa/setup", methods=["POST"])
@login_required
def mfa_setup():
    """Generate a new TOTP secret and return the provisioning URI + QR code."""
    secret = pyotp.random_base32()
    totp = pyotp.TOTP(secret)
    uri = totp.provisioning_uri(
        name=current_user.email, issuer_name="Nickel&Dime"
    )

    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    qr_b64 = base64.b64encode(buf.getvalue()).decode()

    session["_mfa_pending_secret"] = secret

    return jsonify({
        "secret": secret,
        "uri": uri,
        "qr_code": f"data:image/png;base64,{qr_b64}",
    })


@api_mfa_bp.route("/mfa/confirm", methods=["POST"])
@login_required
def mfa_confirm():
    """Verify a TOTP code against the pending secret and enable MFA."""
    data = flask_request.get_json(silent=True) or {}
    code = (data.get("code") or "").strip()
    pending_secret = session.get("_mfa_pending_secret")

    if not pending_secret:
        return jsonify({"error": "No MFA setup in progress"}), 400

    if not code:
        return jsonify({"error": "Code is required"}), 400

    totp = pyotp.TOTP(pending_secret)
    if not totp.verify(code, valid_window=1):
        return jsonify({"error": "Invalid code"}), 400

    current_user.totp_secret = encrypt(pending_secret)
    current_user.mfa_enabled = True
    db.session.commit()

    session.pop("_mfa_pending_secret", None)
    session["_mfa_verified"] = True
    log_event("mfa_enabled")

    return jsonify({"success": True, "message": "MFA enabled"})


@api_mfa_bp.route("/mfa/verify", methods=["POST"])
@login_required
def mfa_verify():
    """Verify a TOTP code during login (called after password auth)."""
    data = flask_request.get_json(silent=True) or {}
    code = (data.get("code") or "").strip()

    if not current_user.mfa_enabled or not current_user.totp_secret:
        return jsonify({"error": "MFA not enabled"}), 400

    if not code:
        return jsonify({"error": "Code is required"}), 400

    secret = decrypt(current_user.totp_secret)
    totp = pyotp.TOTP(secret)
    if not totp.verify(code, valid_window=1):
        return jsonify({"error": "Invalid code"}), 400

    session["_mfa_verified"] = True
    return jsonify({"success": True})


@api_mfa_bp.route("/mfa/step-up", methods=["POST"])
@login_required
def mfa_step_up():
    """Re-verify TOTP for sensitive action gating (step-up auth)."""
    if not current_user.mfa_enabled or not current_user.totp_secret:
        return jsonify({"error": "MFA not enabled"}), 400

    data = flask_request.get_json(silent=True) or {}
    code = (data.get("code") or "").strip()
    if not code:
        return jsonify({"error": "Code is required"}), 400

    secret = decrypt(current_user.totp_secret)
    totp = pyotp.TOTP(secret)
    if not totp.verify(code, valid_window=1):
        return jsonify({"error": "Invalid code"}), 400

    session["_mfa_step_up_at"] = time.time()
    return jsonify({"success": True})


@api_mfa_bp.route("/mfa/disable", methods=["POST"])
@login_required
@requires_mfa_recent
def mfa_disable():
    """Disable MFA for the current user (requires current TOTP code)."""
    data = flask_request.get_json(silent=True) or {}
    code = (data.get("code") or "").strip()

    if not current_user.mfa_enabled or not current_user.totp_secret:
        return jsonify({"error": "MFA not enabled"}), 400

    if not code:
        return jsonify({"error": "Code is required"}), 400

    secret = decrypt(current_user.totp_secret)
    totp = pyotp.TOTP(secret)
    if not totp.verify(code, valid_window=1):
        return jsonify({"error": "Invalid code"}), 400

    current_user.totp_secret = None
    current_user.mfa_enabled = False
    db.session.commit()
    log_event("mfa_disabled")

    session.pop("_mfa_verified", None)
    return jsonify({"success": True, "message": "MFA disabled"})


@api_mfa_bp.route("/mfa/status")
@login_required
def mfa_status():
    """Return whether MFA is enabled for the current user."""
    return jsonify({
        "enabled": bool(current_user.mfa_enabled),
        "verified": session.get("_mfa_verified", False),
    })
