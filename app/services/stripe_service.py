"""Stripe billing service helpers."""

import logging
from flask import current_app

log = logging.getLogger(__name__)


def get_stripe():
    """Return configured stripe module, or None if key is not set."""
    import stripe
    key = current_app.config.get("STRIPE_SECRET_KEY", "")
    if not key:
        return None
    stripe.api_key = key
    return stripe


def get_or_create_customer(user):
    """Ensure user has a Stripe customer ID. Returns customer_id or None."""
    stripe = get_stripe()
    if not stripe:
        return None
    if user.stripe_customer_id:
        return user.stripe_customer_id

    from ..extensions import db
    try:
        customer = stripe.Customer.create(
            email=user.email,
            name=user.name or user.email.split("@")[0],
            metadata={"user_id": str(user.id)},
        )
        user.stripe_customer_id = customer.id
        db.session.commit()
        return customer.id
    except Exception as e:
        log.error("Failed to create Stripe customer for user %s: %s", user.email, e)
        return None


def sync_subscription_status(user):
    """Fetch the latest subscription state from Stripe and sync to our DB.

    Useful as a fallback if webhooks miss an event.
    """
    stripe = get_stripe()
    if not stripe or not user.stripe_customer_id:
        return

    from ..extensions import db
    from ..models.user import Subscription
    from datetime import datetime, timezone

    try:
        subs = stripe.Subscription.list(
            customer=user.stripe_customer_id,
            status="all",
            limit=1,
        )
        if not subs.data:
            return

        latest = subs.data[0]
        sub = Subscription.query.filter_by(user_id=user.id).first()
        if not sub:
            sub = Subscription(user_id=user.id)
            db.session.add(sub)

        sub.stripe_subscription_id = latest.id
        sub.status = latest.status
        sub.cancel_at_period_end = latest.cancel_at_period_end
        if latest.current_period_end:
            sub.current_period_end = datetime.fromtimestamp(
                latest.current_period_end, tz=timezone.utc
            )

        if latest.status in ("active", "trialing"):
            user.plan = "pro"
            sub.plan = "pro"
        else:
            user.plan = "free"
            sub.plan = "free"

        db.session.commit()
    except Exception as e:
        log.error("Failed to sync subscription for user %s: %s", user.email, e)
