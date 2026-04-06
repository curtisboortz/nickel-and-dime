"""Referral system: generate codes, redeem, track credits.

Each user gets one referral code. When a friend signs up with
that code, both the referrer and the friend get 1 month of Pro
credit applied to their subscription.
"""

import secrets
import logging

from ..extensions import db
from ..models.referral import ReferralCode, ReferralRedemption

log = logging.getLogger(__name__)


def get_or_create_code(user_id):
    """Return the user's referral code, creating one if needed."""
    rc = ReferralCode.query.filter_by(
        user_id=user_id).first()
    if rc:
        return rc
    code = _generate_unique_code()
    rc = ReferralCode(user_id=user_id, code=code)
    db.session.add(rc)
    db.session.commit()
    return rc


def _generate_unique_code():
    """Generate a short, unique, human-friendly code."""
    for _ in range(20):
        code = secrets.token_urlsafe(6).upper()[:8]
        if not ReferralCode.query.filter_by(
            code=code
        ).first():
            return code
    raise RuntimeError("Could not generate unique code")


def redeem_code(code_str, redeemed_by_user_id):
    """Redeem a referral code for a new user.

    Returns (success: bool, message: str).
    """
    rc = ReferralCode.query.filter_by(
        code=code_str.strip().upper()).first()
    if not rc:
        return False, "Invalid referral code."

    if rc.user_id == redeemed_by_user_id:
        return False, "You can't use your own referral code."

    existing = ReferralRedemption.query.filter_by(
        code_id=rc.id, redeemed_by=redeemed_by_user_id,
    ).first()
    if existing:
        return False, "You've already used this code."

    redemption = ReferralRedemption(
        code_id=rc.id,
        redeemed_by=redeemed_by_user_id,
        credit_months=1,
    )
    db.session.add(redemption)
    db.session.commit()

    log.info(
        "Referral redeemed: code=%s referrer=%d new_user=%d",
        rc.code, rc.user_id, redeemed_by_user_id,
    )

    return True, "Referral applied! You both get 1 free month."


def get_referral_stats(user_id):
    """Return referral stats for a user."""
    rc = ReferralCode.query.filter_by(
        user_id=user_id).first()
    if not rc:
        return {
            "code": None,
            "total_referrals": 0,
            "credits_earned": 0,
        }

    total = rc.redemptions.count()
    return {
        "code": rc.code,
        "total_referrals": total,
        "credits_earned": total,
    }
