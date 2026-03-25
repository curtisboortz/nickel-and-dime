"""Budget, transaction, and categorization models."""

from datetime import datetime, timezone
from ..extensions import db


class BudgetConfig(db.Model):
    """Per-user monthly budget configuration."""
    __tablename__ = "budget_configs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    monthly_income = db.Column(db.Float, default=0.0)
    categories = db.Column(db.JSON, default=list)  # [{"name": "Housing", "limit": 1500}, ...]
    rollover_enabled = db.Column(db.Boolean, default=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (db.UniqueConstraint("user_id", name="uq_budget_user"),)


class Transaction(db.Model):
    """Individual spending / income transactions."""
    __tablename__ = "transactions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    date = db.Column(db.Date, nullable=False, index=True)
    description = db.Column(db.String(500), nullable=False)
    amount = db.Column(db.Float, nullable=False)  # negative = expense, positive = income
    category = db.Column(db.String(100), default="Other")
    account = db.Column(db.String(120), default="")
    source = db.Column(db.String(30), default="manual")  # manual | csv_import | statement_import
    import_hash = db.Column(db.String(64), nullable=True)  # dedup key for imports
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (db.Index("ix_txn_user_date", "user_id", "date"),)


class RecurringTransaction(db.Model):
    """Detected or user-defined recurring bills/income."""
    __tablename__ = "recurring_transactions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    description = db.Column(db.String(500), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    frequency = db.Column(db.String(20), default="monthly")  # weekly | biweekly | monthly | quarterly | annual
    category = db.Column(db.String(100), default="Other")
    next_due = db.Column(db.Date, nullable=True)
    active = db.Column(db.Boolean, default=True)


class CategoryRule(db.Model):
    """Keyword-based auto-categorization rules for statement imports."""
    __tablename__ = "category_rules"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    keyword = db.Column(db.String(200), nullable=False)  # case-insensitive substring match
    category = db.Column(db.String(100), nullable=False)
    priority = db.Column(db.Integer, default=0)  # higher = checked first

    __table_args__ = (db.Index("ix_catrule_user", "user_id"),)
