"""Plaid integration models: linked brokerage/bank items and accounts."""

from datetime import datetime, timezone
from ..extensions import db


class PlaidItem(db.Model):
    """A Plaid-linked institution for a user (one row per connection)."""
    __tablename__ = "plaid_items"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"),
        nullable=False, index=True)
    item_id = db.Column(db.String(120), nullable=False, unique=True)
    access_token = db.Column(db.Text, nullable=False)
    institution_id = db.Column(db.String(80), default="")
    institution_name = db.Column(db.String(200), default="")
    logo_base64 = db.Column(db.Text, nullable=True)
    primary_color = db.Column(db.String(20), default="")
    products = db.Column(db.JSON, default=list)
    status = db.Column(db.String(30), default="good")
    error_code = db.Column(db.String(80), nullable=True)
    cursor = db.Column(db.Text, nullable=True)
    last_synced_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))

    accounts = db.relationship("PlaidAccount", backref="plaid_item",
                               cascade="all, delete-orphan", lazy="dynamic")

    __table_args__ = (db.Index("ix_plaid_user", "user_id"),)


class PlaidAccount(db.Model):
    """A single account within a PlaidItem (e.g. IRA, Brokerage, Checking)."""
    __tablename__ = "plaid_accounts"

    id = db.Column(db.Integer, primary_key=True)
    plaid_item_id = db.Column(
        db.Integer, db.ForeignKey("plaid_items.id"),
        nullable=False, index=True)
    account_id = db.Column(db.String(120), nullable=False, unique=True)
    name = db.Column(db.String(200), default="")
    official_name = db.Column(db.String(300), nullable=True)
    mask = db.Column(db.String(10), nullable=True)
    type = db.Column(db.String(50), default="")
    subtype = db.Column(db.String(50), default="")

    balance_current = db.Column(db.Float, nullable=True)
    balance_available = db.Column(db.Float, nullable=True)
    balance_limit = db.Column(db.Float, nullable=True)

    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))
