"""Authentication and authorization helpers."""

import time
from functools import wraps
from datetime import datetime, timezone
from flask import jsonify, abort, session
from flask_login import current_user


PLAN_FREE = "free"
PLAN_PRO = "pro"


def _check_trial_expiry(user):
    """Downgrade user to free if their trial has expired. Admins are exempt."""
    if user.plan != PLAN_PRO:
        return
    if getattr(user, "is_admin", False):
        return
    sub = user.subscription
    if not sub:
        return
    if sub.status == "trialing" and sub.current_period_end:
        end = sub.current_period_end
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > end:
            from ..extensions import db
            user.plan = PLAN_FREE
            sub.plan = PLAN_FREE
            sub.status = "expired"
            db.session.commit()


def requires_pro(f):
    """Decorator: reject requests from free-tier users with a 403 + upgrade hint."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            abort(401)
        _check_trial_expiry(current_user)
        if current_user.plan == PLAN_FREE:
            return jsonify({
                "error": "This feature requires a Pro subscription.",
                "upgrade": True,
                "upgrade_url": "/billing/pricing",
            }), 403
        return f(*args, **kwargs)
    return decorated


def is_pro(user=None):
    """Template / service helper: does this user have Pro access?"""
    u = user or current_user
    if not u or not u.is_authenticated:
        return False
    _check_trial_expiry(u)
    return u.plan != PLAN_FREE


MFA_STEP_UP_WINDOW = 300  # 5 minutes


def requires_mfa_recent(f):
    """Decorator: require recent MFA re-verification for sensitive actions.

    No-op if the user doesn't have MFA enabled.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            abort(401)
        if current_user.mfa_enabled:
            verified_at = session.get("_mfa_step_up_at")
            if not verified_at or (time.time() - verified_at) > MFA_STEP_UP_WINDOW:
                return jsonify({
                    "error": "MFA verification required",
                    "mfa_required": True,
                }), 403
        return f(*args, **kwargs)
    return decorated
