"""Security audit logging utility."""

import logging

from flask import request, has_request_context
from flask_login import current_user

from ..extensions import db
from ..models.audit import AuditLog

log = logging.getLogger("nd.audit")


def log_event(action, detail=None, user_id=None):
    """Record a security-relevant event to the audit log.

    Falls back gracefully if called outside a request context.
    """
    uid = user_id
    if uid is None and has_request_context():
        try:
            if current_user and current_user.is_authenticated:
                uid = current_user.id
        except Exception:
            pass

    ip = None
    ua = None
    if has_request_context():
        ip = request.remote_addr
        ua = (request.user_agent.string or "")[:300]

    entry = AuditLog(
        user_id=uid,
        action=action,
        detail=detail,
        ip_address=ip,
        user_agent=ua,
    )
    try:
        db.session.add(entry)
        db.session.commit()
    except Exception:
        db.session.rollback()
        log.exception("Failed to write audit log for action=%s", action)
