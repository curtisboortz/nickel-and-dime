"""User settings, goals, alerts, and customization models."""

from datetime import datetime, timezone
from ..extensions import db


class UserSettings(db.Model):
    """Per-user configuration (replaces config.json)."""
    __tablename__ = "user_settings"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, unique=True)

    # Contribution plan
    contribution_amount = db.Column(db.Float, default=0.0)
    contribution_frequency = db.Column(db.String(20), default="biweekly")
    contribution_plan = db.Column(db.JSON, default=dict)

    # Allocation targets
    targets = db.Column(db.JSON, default=dict)  # {"tactical": {...}, "catchup": {...}}

    # Display preferences
    pulse_order = db.Column(db.JSON, default=list)
    widget_order = db.Column(db.JSON, default=list)
    default_currency = db.Column(db.String(3), default="USD")

    # Category rollup overrides -- {child: parent_or_null}
    bucket_rollup = db.Column(db.JSON, default=dict)

    # Rebalancing
    rebalance_months = db.Column(db.Integer, default=12)

    # Onboarding
    onboarding_completed = db.Column(
        db.Boolean, default=False)

    # External links
    links = db.Column(db.JSON, default=dict)

    # Encrypted API keys for optional user-provided integrations
    coinbase_key_name = db.Column(db.String(255), nullable=True)
    coinbase_private_key = db.Column(db.Text, nullable=True)
    goldapi_key = db.Column(db.String(255), nullable=True)

    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class CustomPulseCard(db.Model):
    """User-added ticker cards on the market pulse bar."""
    __tablename__ = "custom_pulse_cards"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    ticker = db.Column(db.String(20), nullable=False)
    label = db.Column(db.String(50), default="")
    position = db.Column(db.Integer, default=0)


class PriceAlert(db.Model):
    """User-defined price alerts."""
    __tablename__ = "price_alerts"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    ticker = db.Column(db.String(20), nullable=False)
    condition = db.Column(db.String(10), nullable=False)  # above | below
    target_price = db.Column(db.Float, nullable=False)
    active = db.Column(db.Boolean, default=True)
    triggered_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class FinancialGoal(db.Model):
    """Savings / investment goals."""
    __tablename__ = "financial_goals"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False)
    target_amount = db.Column(db.Float, nullable=False)
    current_amount = db.Column(db.Float, default=0.0)
    target_date = db.Column(db.Date, nullable=True)
    category = db.Column(db.String(50), default="general")
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class MonthlyInvestment(db.Model):
    """Monthly investment tracking per category."""
    __tablename__ = "monthly_investments"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    month = db.Column(db.String(7), nullable=False)  # "2026-03"
    category = db.Column(db.String(100), nullable=False)
    bucket = db.Column(db.String(50), nullable=True)
    target = db.Column(db.Float, default=0.0)
    contributed = db.Column(db.Float, default=0.0)
    monthly_budget = db.Column(db.Float, default=0.0)

    __table_args__ = (
        db.UniqueConstraint("user_id", "month", "category", name="uq_monthly_inv"),
    )
