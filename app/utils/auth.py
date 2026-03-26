"""Authentication and authorization helpers."""

from functools import wraps
from datetime import datetime, timezone
from flask import jsonify, abort
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
        if datetime.now(timezone.utc) > sub.current_period_end:
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
