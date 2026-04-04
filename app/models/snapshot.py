"""Portfolio snapshot model for historical tracking."""

from datetime import datetime, timezone
from ..extensions import db


class PortfolioSnapshot(db.Model):
    """Daily portfolio value snapshot (one per user per day)."""
    __tablename__ = "portfolio_snapshots"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    date = db.Column(db.Date, nullable=False)
    total = db.Column(db.Float, nullable=False)
    open_val = db.Column("open", db.Float, nullable=True)
    high = db.Column(db.Float, nullable=True)
    low = db.Column(db.Float, nullable=True)
    close = db.Column(db.Float, nullable=True)
    gold_price = db.Column(db.Float, nullable=True)
    silver_price = db.Column(db.Float, nullable=True)
    tnx_10y = db.Column(db.Float, nullable=True)
    tnx_2y = db.Column(db.Float, nullable=True)
    breakdown = db.Column(db.JSON, nullable=True)

    __table_args__ = (
        db.UniqueConstraint("user_id", "date", name="uq_snapshot_user_date"),
        db.Index("ix_snapshot_user_date", "user_id", "date"),
    )
