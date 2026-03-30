"""Factory Boy factories for Nickel&Dime models."""

import factory
from datetime import datetime, timezone, timedelta

from app.extensions import db
from app.models.user import User, Subscription
from app.models.portfolio import Holding, CryptoHolding, PhysicalMetal, BlendedAccount
from app.models.market import PriceCache
from app.models.settings import UserSettings, CustomPulseCard


class BaseFactory(factory.alchemy.SQLAlchemyModelFactory):
    class Meta:
        sqlalchemy_session = None
        sqlalchemy_session_persistence = "commit"

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        cls._meta.sqlalchemy_session = db.session
        return super()._create(model_class, *args, **kwargs)


class UserFactory(BaseFactory):
    class Meta:
        model = User

    email = factory.Sequence(lambda n: f"user{n}@example.com")
    name = factory.Sequence(lambda n: f"User {n}")
    plan = "free"
    password_hash = ""

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        password = kwargs.pop("password", "password123")
        cls._meta.sqlalchemy_session = db.session
        obj = super()._create(model_class, *args, **kwargs)
        obj.set_password(password)
        db.session.commit()
        return obj


class SubscriptionFactory(BaseFactory):
    class Meta:
        model = Subscription

    user_id = factory.LazyAttribute(lambda o: o.user.id if hasattr(o, "user") else None)
    plan = "pro"
    status = "trialing"
    current_period_end = factory.LazyFunction(
        lambda: datetime.now(timezone.utc) + timedelta(days=14)
    )


class HoldingFactory(BaseFactory):
    class Meta:
        model = Holding

    user_id = factory.LazyAttribute(lambda o: o.user.id if hasattr(o, "user") else 1)
    ticker = "AAPL"
    shares = 10.0
    cost_basis = 150.0
    account = "Fidelity"
    bucket = "Equities"


class CryptoHoldingFactory(BaseFactory):
    class Meta:
        model = CryptoHolding

    user_id = factory.LazyAttribute(lambda o: o.user.id if hasattr(o, "user") else 1)
    symbol = "BTC"
    quantity = 0.5
    source = "manual"


class PhysicalMetalFactory(BaseFactory):
    class Meta:
        model = PhysicalMetal

    user_id = factory.LazyAttribute(lambda o: o.user.id if hasattr(o, "user") else 1)
    metal = "Gold"
    form = "Coin"
    oz = 1.0
    purchase_price = 2000.0


class BlendedAccountFactory(BaseFactory):
    class Meta:
        model = BlendedAccount

    user_id = factory.LazyAttribute(lambda o: o.user.id if hasattr(o, "user") else 1)
    name = "Vanguard 401k"
    value = 50000.0
    allocations = {"Equities": 60, "Gold": 20, "Cash": 20}


class PriceCacheFactory(BaseFactory):
    class Meta:
        model = PriceCache

    symbol = factory.Sequence(lambda n: f"SYM{n}")
    price = 100.0
    change_pct = 0.5
    source = "yfinance"


class UserSettingsFactory(BaseFactory):
    class Meta:
        model = UserSettings

    user_id = factory.LazyAttribute(lambda o: o.user.id if hasattr(o, "user") else 1)


class CustomPulseCardFactory(BaseFactory):
    class Meta:
        model = CustomPulseCard

    user_id = factory.LazyAttribute(lambda o: o.user.id if hasattr(o, "user") else 1)
    ticker = "TSLA"
    label = "Tesla"
    position = 0
