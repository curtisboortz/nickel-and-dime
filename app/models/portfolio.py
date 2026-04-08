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
    source = db.Column(db.String(50), default="manual")


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
    institution_value = db.Column(db.Float, nullable=True)
    source = db.Column(db.String(50), default="manual")
    plaid_item_id = db.Column(db.Integer, db.ForeignKey("plaid_items.id"), nullable=True)
    plaid_account_id = db.Column(db.Integer, db.ForeignKey("plaid_accounts.id"), nullable=True)
    security_name = db.Column(db.String(255), nullable=True)
    security_type = db.Column(db.String(50), nullable=True)
    isin = db.Column(db.String(20), nullable=True)
    cusip = db.Column(db.String(20), nullable=True)
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


class InvestmentTransaction(db.Model):
    """Investment-specific transactions from Plaid (buys, sells, dividends, fees)."""
    __tablename__ = "investment_transactions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    plaid_item_id = db.Column(db.Integer, db.ForeignKey("plaid_items.id"), nullable=True)
    plaid_account_id = db.Column(db.Integer, db.ForeignKey("plaid_accounts.id"), nullable=True)
    investment_transaction_id = db.Column(db.String(120), nullable=False, unique=True)
    date = db.Column(db.Date, nullable=False)
    type = db.Column(db.String(30), nullable=False)
    subtype = db.Column(db.String(50), nullable=True)
    ticker = db.Column(db.String(20), nullable=True)
    security_name = db.Column(db.String(255), nullable=True)
    quantity = db.Column(db.Float, nullable=True)
    amount = db.Column(db.Float, nullable=True)
    price = db.Column(db.Float, nullable=True)
    fees = db.Column(db.Float, nullable=True)
    description = db.Column(db.String(500), default="")
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class TaxLot(db.Model):
    """Individual tax lots built from investment buy transactions."""
    __tablename__ = "tax_lots"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    holding_id = db.Column(db.Integer, db.ForeignKey("holdings.id"), nullable=True)
    date_acquired = db.Column(db.Date, nullable=False)
    quantity = db.Column(db.Float, nullable=False, default=0.0)
    cost_per_share = db.Column(db.Float, nullable=False, default=0.0)
    investment_transaction_id = db.Column(
        db.Integer, db.ForeignKey("investment_transactions.id"), nullable=True)
    sold_quantity = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
