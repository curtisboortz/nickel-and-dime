"""Tests for SQLAlchemy models."""

from datetime import datetime, timezone, timedelta

from app.models.user import User, Subscription
from app.models.portfolio import Holding, CryptoHolding, PhysicalMetal, BlendedAccount
from app.models.market import PriceCache
from app.models.settings import UserSettings, CustomPulseCard


class TestUserModel:
    def test_create_user(self, db):
        u = User(email="a@b.com", name="Alice", plan="free")
        u.set_password("secret123")
        db.session.add(u)
        db.session.commit()

        assert u.id is not None
        assert u.email == "a@b.com"
        assert u.plan == "free"
        assert not u.is_pro

    def test_password_hashing(self, db):
        u = User(email="hash@test.com", name="Hash")
        u.set_password("correcthorse")
        db.session.add(u)
        db.session.commit()

        assert u.check_password("correcthorse")
        assert not u.check_password("wrongpassword")
        assert u.password_hash != "correcthorse"

    def test_is_pro_property(self, db):
        u = User(email="pro@test.com", name="Pro", plan="pro")
        u.set_password("pass1234")
        db.session.add(u)
        db.session.commit()

        assert u.is_pro

    def test_is_admin_property(self, db, monkeypatch):
        monkeypatch.setenv("ADMIN_EMAILS", "admin@test.com,boss@test.com")
        u = User(email="admin@test.com", name="Admin", plan="pro")
        u.set_password("pass1234")
        db.session.add(u)
        db.session.commit()

        assert u.is_admin

    def test_non_admin(self, db, monkeypatch):
        monkeypatch.setenv("ADMIN_EMAILS", "admin@test.com")
        u = User(email="regular@test.com", name="Regular")
        u.set_password("pass1234")
        db.session.add(u)
        db.session.commit()

        assert not u.is_admin

    def test_unique_email(self, db):
        u1 = User(email="dup@test.com", name="One")
        u1.set_password("pass1234")
        db.session.add(u1)
        db.session.commit()

        u2 = User(email="dup@test.com", name="Two")
        u2.set_password("pass1234")
        db.session.add(u2)

        import pytest
        from sqlalchemy.exc import IntegrityError
        with pytest.raises(IntegrityError):
            db.session.commit()


class TestSubscriptionModel:
    def test_create_subscription(self, db, user):
        sub = Subscription(
            user_id=user.id,
            plan="pro",
            status="trialing",
            current_period_end=datetime.now(timezone.utc) + timedelta(days=14),
        )
        db.session.add(sub)
        db.session.commit()

        assert sub.id is not None
        assert sub.plan == "pro"
        assert sub.status == "trialing"
        assert sub.user.email == user.email

    def test_subscription_backref(self, db, pro_user):
        assert pro_user.subscription is not None
        assert pro_user.subscription.status == "trialing"

    def test_cancel_at_period_end_default(self, db, user):
        sub = Subscription(user_id=user.id, plan="free", status="active")
        db.session.add(sub)
        db.session.commit()

        assert sub.cancel_at_period_end is False


class TestHoldingModel:
    def test_create_holding(self, db, user):
        h = Holding(
            user_id=user.id,
            ticker="AAPL",
            shares=10.0,
            cost_basis=150.0,
            account="Fidelity",
            bucket="Equities",
        )
        db.session.add(h)
        db.session.commit()

        assert h.id is not None
        assert h.ticker == "AAPL"
        assert h.cost_basis == 150.0

    def test_holding_relationship(self, db, user):
        h = Holding(user_id=user.id, ticker="MSFT", shares=5.0)
        db.session.add(h)
        db.session.commit()

        assert user.holdings.count() == 1
        assert user.holdings.first().ticker == "MSFT"

    def test_value_override(self, db, user):
        h = Holding(
            user_id=user.id,
            ticker="FUND",
            shares=100.0,
            value_override=25000.0,
        )
        db.session.add(h)
        db.session.commit()

        assert h.value_override == 25000.0


class TestCryptoHoldingModel:
    def test_create_crypto(self, db, user):
        c = CryptoHolding(
            user_id=user.id,
            symbol="BTC",
            quantity=0.5,
            cost_basis=30000.0,
            source="coinbase",
        )
        db.session.add(c)
        db.session.commit()

        assert c.symbol == "BTC"
        assert c.quantity == 0.5

    def test_crypto_default_source(self, db, user):
        c = CryptoHolding(user_id=user.id, symbol="ETH", quantity=2.0)
        db.session.add(c)
        db.session.commit()

        assert c.source == "manual"


class TestPhysicalMetalModel:
    def test_create_metal(self, db, user):
        m = PhysicalMetal(
            user_id=user.id,
            metal="Gold",
            form="1oz Eagle",
            oz=1.0,
            purchase_price=2100.0,
            note="2024 American Eagle",
        )
        db.session.add(m)
        db.session.commit()

        assert m.metal == "Gold"
        assert m.note == "2024 American Eagle"


class TestPriceCacheModel:
    def test_create_price(self, db):
        p = PriceCache(
            symbol="AAPL",
            price=175.50,
            change_pct=1.2,
            source="yfinance",
        )
        db.session.add(p)
        db.session.commit()

        fetched = db.session.get(PriceCache, "AAPL")
        assert fetched.price == 175.50

    def test_price_primary_key_is_symbol(self, db):
        p = PriceCache(symbol="SPY", price=500.0)
        db.session.add(p)
        db.session.commit()

        p.price = 501.0
        db.session.commit()

        fetched = db.session.get(PriceCache, "SPY")
        assert fetched.price == 501.0


class TestBlendedAccountModel:
    def test_create_blended(self, db, user):
        b = BlendedAccount(
            user_id=user.id,
            name="Vanguard TDF",
            value=50000.0,
            allocations={"Equities": 60, "Gold": 20, "Cash": 20},
        )
        db.session.add(b)
        db.session.commit()

        assert b.allocations["Equities"] == 60
        assert sum(b.allocations.values()) == 100


class TestUserSettingsModel:
    def test_create_settings(self, db, user):
        s = UserSettings(user_id=user.id)
        db.session.add(s)
        db.session.commit()

        assert s.default_currency == "USD"
        assert user.settings is not None


class TestCustomPulseCardModel:
    def test_create_pulse_card(self, db, user):
        c = CustomPulseCard(
            user_id=user.id,
            ticker="TSLA",
            label="Tesla",
            position=0,
        )
        db.session.add(c)
        db.session.commit()

        assert c.ticker == "TSLA"
        assert c.user_id == user.id
