"""Referral code and redemption models."""

from datetime import datetime, timezone
from ..extensions import db


class ReferralCode(db.Model):
    __tablename__ = "referral_codes"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"),
        nullable=False, index=True,
    )
    code = db.Column(
        db.String(20), nullable=False, unique=True,
    )
    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
    )
    redemptions = db.relationship(
        "ReferralRedemption", backref="referral_code",
        lazy="dynamic",
    )


class ReferralRedemption(db.Model):
    __tablename__ = "referral_redemptions"

    id = db.Column(db.Integer, primary_key=True)
    code_id = db.Column(
        db.Integer, db.ForeignKey("referral_codes.id"),
        nullable=False, index=True,
    )
    redeemed_by = db.Column(
        db.Integer, db.ForeignKey("users.id"),
        nullable=False,
    )
    redeemed_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
    )
    credit_months = db.Column(
        db.Integer, default=1,
    )
