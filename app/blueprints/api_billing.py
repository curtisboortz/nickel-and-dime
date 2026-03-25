"""Billing API routes: Stripe checkout, webhooks, portal.

Handles the full subscription lifecycle:
- Checkout session creation (with 14-day free trial)
- Stripe Customer Portal for self-service management
- Webhook processing for subscription status changes
"""

import logging
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request as flask_request, current_app
from flask_login import login_required, current_user

from ..extensions import db, csrf
from ..models.user import User, Subscription

api_billing_bp = Blueprint("api_billing", __name__)
log = logging.getLogger(__name__)

TRIAL_DAYS = 14


def _get_stripe():
    """Import and configure stripe from app config."""
    import stripe
    stripe.api_key = current_app.config["STRIPE_SECRET_KEY"]
    if not stripe.api_key:
        return None
    return stripe


def _ensure_customer(stripe_mod, user):
    """Ensure the user has a Stripe customer ID."""
    if user.stripe_customer_id:
        return user.stripe_customer_id
    customer = stripe_mod.Customer.create(
        email=user.email,
        name=user.name or user.email.split("@")[0],
        metadata={"user_id": str(user.id)},
    )
    user.stripe_customer_id = customer.id
    db.session.commit()
    return customer.id


@api_billing_bp.route("/create-checkout", methods=["POST"])
@login_required
@csrf.exempt
def create_checkout():
    """Create a Stripe Checkout session for Pro subscription."""
    stripe = _get_stripe()
    if not stripe:
        return jsonify({"error": "Billing is not configured yet."}), 503

    price_id = current_app.config.get("STRIPE_PRO_PRICE_ID")
    if not price_id:
        return jsonify({"error": "No Pro price configured."}), 503

    if current_user.plan == "pro":
        return jsonify({"error": "You are already on the Pro plan."}), 400

    try:
        customer_id = _ensure_customer(stripe, current_user)

        # Check if user has ever had a trial (only one trial per customer)
        had_trial = Subscription.query.filter_by(user_id=current_user.id).first()

        session_params = dict(
            customer=customer_id,
            payment_method_types=["card"],
            line_items=[{"price": price_id, "quantity": 1}],
            mode="subscription",
            success_url=flask_request.host_url + "billing/account?checkout=success",
            cancel_url=flask_request.host_url + "billing/pricing",
            metadata={"user_id": str(current_user.id)},
            allow_promotion_codes=True,
        )

        if not had_trial:
            session_params["subscription_data"] = {
                "trial_period_days": TRIAL_DAYS,
                "metadata": {"user_id": str(current_user.id)},
            }

        session = stripe.checkout.Session.create(**session_params)
        return jsonify({"url": session.url})

    except Exception as e:
        log.error("Stripe checkout error: %s", e)
        return jsonify({"error": "Could not create checkout session."}), 500


@api_billing_bp.route("/billing-portal", methods=["POST"])
@login_required
@csrf.exempt
def billing_portal():
    """Redirect to Stripe Customer Portal for subscription management."""
    stripe = _get_stripe()
    if not stripe:
        return jsonify({"error": "Billing is not configured."}), 503

    if not current_user.stripe_customer_id:
        return jsonify({"error": "No billing account found."}), 404

    try:
        session = stripe.billing_portal.Session.create(
            customer=current_user.stripe_customer_id,
            return_url=flask_request.host_url + "billing/account",
        )
        return jsonify({"url": session.url})
    except Exception as e:
        log.error("Stripe portal error: %s", e)
        return jsonify({"error": "Could not open billing portal."}), 500


@api_billing_bp.route("/subscription-status")
@login_required
def subscription_status():
    """Return the current user's subscription details (for frontend display)."""
    sub = Subscription.query.filter_by(user_id=current_user.id).first()
    return jsonify({
        "plan": current_user.plan,
        "status": sub.status if sub else None,
        "trial_end": sub.current_period_end.isoformat() if sub and sub.status == "trialing" and sub.current_period_end else None,
        "cancel_at_period_end": sub.cancel_at_period_end if sub else False,
        "period_end": sub.current_period_end.isoformat() if sub and sub.current_period_end else None,
    })


@api_billing_bp.route("/stripe-webhook", methods=["POST"])
@csrf.exempt
def stripe_webhook():
    """Handle Stripe webhook events for subscription lifecycle."""
    stripe = _get_stripe()
    if not stripe:
        return jsonify({"error": "Billing not configured"}), 503

    webhook_secret = current_app.config.get("STRIPE_WEBHOOK_SECRET", "")
    payload = flask_request.get_data(as_text=True)
    sig_header = flask_request.headers.get("Stripe-Signature", "")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except ValueError:
        log.warning("Stripe webhook: invalid payload")
        return jsonify({"error": "Invalid payload"}), 400
    except stripe.error.SignatureVerificationError:
        log.warning("Stripe webhook: invalid signature")
        return jsonify({"error": "Invalid signature"}), 400

    event_type = event["type"]
    data_obj = event["data"]["object"]
    log.info("Stripe webhook: %s", event_type)

    handlers = {
        "checkout.session.completed": _handle_checkout_completed,
        "customer.subscription.created": _handle_subscription_updated,
        "customer.subscription.updated": _handle_subscription_updated,
        "customer.subscription.deleted": _handle_subscription_deleted,
        "customer.subscription.trial_will_end": _handle_trial_ending,
        "invoice.payment_failed": _handle_payment_failed,
        "invoice.paid": _handle_invoice_paid,
    }

    handler = handlers.get(event_type)
    if handler:
        try:
            handler(data_obj)
        except Exception as e:
            log.error("Webhook handler error for %s: %s", event_type, e)

    return jsonify({"received": True})


def _handle_checkout_completed(session):
    """Upgrade user to Pro after successful checkout."""
    user_id = session.get("metadata", {}).get("user_id")
    if not user_id:
        return
    user = db.session.get(User, int(user_id))
    if not user:
        return

    user.plan = "pro"
    if not user.stripe_customer_id:
        user.stripe_customer_id = session.get("customer")

    sub = Subscription.query.filter_by(user_id=user.id).first()
    if not sub:
        sub = Subscription(user_id=user.id)
        db.session.add(sub)

    sub.stripe_subscription_id = session.get("subscription")
    sub.plan = "pro"
    sub.status = "active"
    db.session.commit()
    log.info("User %s upgraded to Pro", user.email)


def _handle_subscription_updated(subscription):
    """Sync subscription status changes (active, trialing, past_due, etc.)."""
    sub = Subscription.query.filter_by(
        stripe_subscription_id=subscription["id"]
    ).first()

    if not sub:
        # Try to match by customer ID
        customer_id = subscription.get("customer")
        user = User.query.filter_by(stripe_customer_id=customer_id).first() if customer_id else None
        if not user:
            return
        sub = Subscription.query.filter_by(user_id=user.id).first()
        if not sub:
            sub = Subscription(user_id=user.id)
            db.session.add(sub)
        sub.stripe_subscription_id = subscription["id"]

    sub.status = subscription["status"]
    sub.cancel_at_period_end = subscription.get("cancel_at_period_end", False)

    if subscription.get("current_period_end"):
        sub.current_period_end = datetime.fromtimestamp(
            subscription["current_period_end"], tz=timezone.utc
        )

    # Keep Pro access during active/trialing, downgrade otherwise
    if subscription["status"] in ("active", "trialing"):
        sub.user.plan = "pro"
        sub.plan = "pro"
    elif subscription["status"] in ("canceled", "unpaid"):
        sub.user.plan = "free"
        sub.plan = "free"

    db.session.commit()


def _handle_subscription_deleted(subscription):
    """Downgrade user when subscription is fully canceled."""
    sub = Subscription.query.filter_by(
        stripe_subscription_id=subscription["id"]
    ).first()
    if sub:
        sub.status = "canceled"
        sub.plan = "free"
        sub.user.plan = "free"
        db.session.commit()
        log.info("User %s downgraded (subscription canceled)", sub.user.email)


def _handle_trial_ending(subscription):
    """Log trial ending event (3 days before end). Could send email in future."""
    sub = Subscription.query.filter_by(
        stripe_subscription_id=subscription["id"]
    ).first()
    if sub:
        log.info("Trial ending for user %s", sub.user.email)
        # TODO: Send trial-ending email via mail service


def _handle_payment_failed(invoice):
    """Mark subscription as past_due on payment failure."""
    sub_id = invoice.get("subscription")
    if sub_id:
        sub = Subscription.query.filter_by(stripe_subscription_id=sub_id).first()
        if sub:
            sub.status = "past_due"
            db.session.commit()
            log.warning("Payment failed for user %s", sub.user.email)


def _handle_invoice_paid(invoice):
    """Confirm subscription active after successful payment."""
    sub_id = invoice.get("subscription")
    if sub_id:
        sub = Subscription.query.filter_by(stripe_subscription_id=sub_id).first()
        if sub and sub.status == "past_due":
            sub.status = "active"
            sub.user.plan = "pro"
            db.session.commit()
            log.info("Payment recovered for user %s", sub.user.email)
