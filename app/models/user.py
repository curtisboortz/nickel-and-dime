"""User and subscription models."""

from datetime import datetime, timezone
from flask_login import UserMixin
from ..extensions import db, bcrypt


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(120), nullable=False, default="")
    plan = db.Column(db.String(20), nullable=False, default="free")  # free | pro
    email_verified = db.Column(db.Boolean, default=False)
    stripe_customer_id = db.Column(db.String(255), unique=True, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    last_login = db.Column(db.DateTime, nullable=True)

    # Password reset / email verification tokens
    reset_token = db.Column(db.String(255), nullable=True)
    reset_token_expiry = db.Column(db.DateTime, nullable=True)
    verify_token = db.Column(db.String(255), nullable=True)

    # Relationships
    subscription = db.relationship("Subscription", backref="user", uselist=False, lazy=True)
    settings = db.relationship("UserSettings", backref="user", uselist=False, lazy=True)
    holdings = db.relationship("Holding", backref="user", lazy="dynamic")
    crypto_holdings = db.relationship("CryptoHolding", backref="user", lazy="dynamic")
    physical_metals = db.relationship("PhysicalMetal", backref="user", lazy="dynamic")
    accounts = db.relationship("Account", backref="user", lazy="dynamic")
    transactions = db.relationship("Transaction", backref="user", lazy="dynamic")
    snapshots = db.relationship("PortfolioSnapshot", backref="user", lazy="dynamic")

    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode("utf-8")

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)

    @property
    def is_pro(self):
        return self.plan == "pro"

    @property
    def is_admin(self):
        import os
        admins = os.environ.get("ADMIN_EMAILS", "").lower().split(",")
        return self.email and self.email.lower() in admins

    def __repr__(self):
        return f"<User {self.email} ({self.plan})>"


class Subscription(db.Model):
    __tablename__ = "subscriptions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, unique=True)
    stripe_subscription_id = db.Column(db.String(255), unique=True, nullable=True)
    plan = db.Column(db.String(20), nullable=False, default="free")
    status = db.Column(db.String(30), nullable=False, default="active")  # active | past_due | canceled | trialing
    current_period_end = db.Column(db.DateTime, nullable=True)
    cancel_at_period_end = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, onupdate=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<Subscription user={self.user_id} plan={self.plan} status={self.status}>"
