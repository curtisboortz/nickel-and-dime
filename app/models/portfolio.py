"""Portfolio-related models: holdings, crypto, physical metals, accounts."""

from datetime import datetime, timezone
from ..extensions import db


class Account(db.Model):
    """Brokerage / bank accounts (e.g. Fidelity IRA, Checking)."""
    __tablename__ = "accounts"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    account_type = db.Column(db.String(50), default="brokerage")  # brokerage | ira | checking | savings | crypto
    balance = db.Column(db.Float, default=0.0)
    institution = db.Column(db.String(120), default="")
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class BlendedAccount(db.Model):
    """Accounts with mixed allocation (e.g. a target-date fund)."""
    __tablename__ = "blended_accounts"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    value = db.Column(db.Float, default=0.0)
    allocations = db.Column(db.JSON, default=dict)  # {"Equities": 60, "Gold": 20, ...}


class Holding(db.Model):
    """Stock / ETF holdings."""
    __tablename__ = "holdings"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    ticker = db.Column(db.String(20), nullable=False)
    shares = db.Column(db.Float, nullable=True, default=0.0)
    cost_basis = db.Column(db.Float, nullable=True)
    account = db.Column(db.String(120), default="")
    bucket = db.Column(db.String(50), default="Equities")
    value_override = db.Column(db.Float, nullable=True)
    notes = db.Column(db.String(255), default="")
    added_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class CryptoHolding(db.Model):
    """Cryptocurrency holdings."""
    __tablename__ = "crypto_holdings"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    symbol = db.Column(db.String(20), nullable=False)
    quantity = db.Column(db.Float, nullable=False, default=0.0)
    coingecko_id = db.Column(db.String(80), default="")
    cost_basis = db.Column(db.Float, nullable=True)
    source = db.Column(db.String(50), default="manual")


class PhysicalMetal(db.Model):
    """Physical gold / silver holdings."""
    __tablename__ = "physical_metals"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    metal = db.Column(db.String(10), nullable=False)
    form = db.Column(db.String(80), default="")
    oz = db.Column(db.Float, nullable=False, default=0.0)
    purchase_price = db.Column(db.Float, nullable=True)
    purchase_date = db.Column(db.Date, nullable=True)
    date = db.Column(db.String(30), default="")
    description = db.Column(db.String(255), default="")
    note = db.Column(db.String(255), default="")
