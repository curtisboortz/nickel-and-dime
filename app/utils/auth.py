"""Authentication and authorization helpers."""

from functools import wraps
from flask import jsonify, abort
from flask_login import current_user


PLAN_FREE = "free"
PLAN_PRO = "pro"


def requires_pro(f):
    """Decorator: reject requests from free-tier users with a 403 + upgrade hint."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            abort(401)
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
    return u.plan != PLAN_FREE
