"""Plaid integration model: linked brokerage/bank items."""

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
    products = db.Column(db.JSON, default=list)
    status = db.Column(db.String(30), default="good")
    error_code = db.Column(db.String(80), nullable=True)
    cursor = db.Column(db.Text, nullable=True)
    last_synced_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (db.Index("ix_plaid_user", "user_id"),)
