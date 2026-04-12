"""Portfolio digest email service.

Builds digest context from portfolio data and sends digest emails
to users who have opted in.
"""

import logging
from datetime import datetime, timezone

from flask import current_app

from ..extensions import db
from ..models.user import User
from ..models.settings import UserSettings
from .insights_service import generate_insights
from .email_service import send_email

log = logging.getLogger("nd.digest")


def build_digest_context(user_id):
    """Build template context dict for a portfolio digest email.

    Returns dict with keys: total, change_pct, allocations, risk_score,
    risk_label, movers, date, frequency.
    """
    insights = generate_insights(user_id)
    total = insights.get("total", 0)
    weights = insights.get("weights", {})
    risk = insights.get("risk_score", {})

    allocations = []
    for bucket, w in sorted(weights.items(), key=lambda x: -x[1]):
        if w > 0:
            allocations.append({
                "name": bucket,
                "pct": round(w * 100, 1),
                "value": f"{total * w:,.0f}",
            })

    return {
        "total": f"{total:,.2f}",
        "change_pct": None,
        "allocations": allocations,
        "risk_score": risk.get("score"),
        "risk_label": risk.get("label", "N/A"),
        "movers": [],
        "date": datetime.now(timezone.utc).strftime("%B %d, %Y"),
    }


def send_digest(user, settings):
    """Send a portfolio digest email to one user."""
    try:
        ctx = build_digest_context(user.id)
        ctx["user"] = user
        ctx["frequency"] = settings.digest_frequency or "weekly"

        send_email(
            to=user.email,
            subject="Your Portfolio Digest",
            template="email/portfolio_digest",
            **ctx,
        )
        settings.last_digest_sent = datetime.now(timezone.utc)
        db.session.commit()
        return True
    except Exception:
        log.exception("Failed to send digest to user %s", user.id)
        return False


def run_digest_job():
    """Check all users with digest enabled and send if due.

    Called by the scheduler. Handles daily, weekly, and monthly frequencies.
    """
    now = datetime.now(timezone.utc)
    today_weekday = now.strftime("%A").lower()
    today_day = now.day

    users_with_digest = (
        db.session.query(User, UserSettings)
        .join(UserSettings, User.id == UserSettings.user_id)
        .filter(
            UserSettings.digest_enabled.is_(True),
            User.plan == "pro",
        )
        .all()
    )

    sent = 0
    for user, settings in users_with_digest:
        if not user.email_verified:
            continue

        if settings.last_digest_sent:
            hours_since = (now - settings.last_digest_sent).total_seconds() / 3600
            if hours_since < 20:
                continue

        freq = settings.digest_frequency or "weekly"

        if freq == "daily":
            pass
        elif freq == "weekly":
            target_day = (settings.digest_day or "monday").lower()
            if today_weekday != target_day:
                continue
        elif freq == "monthly":
            if today_day != 1:
                continue
        else:
            continue

        if send_digest(user, settings):
            sent += 1

    if sent:
        log.info("Portfolio digest: sent %d emails", sent)
