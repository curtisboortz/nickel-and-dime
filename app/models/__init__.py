"""SQLAlchemy models for Nickel&Dime.

Import all models here so Alembic / Flask-Migrate can discover them.
"""

from .user import User, Subscription, PromoCode  # noqa: F401
from .portfolio import (  # noqa: F401
    Holding, CryptoHolding, PhysicalMetal, Account, BlendedAccount,
    InvestmentTransaction, TaxLot,
)
from .budget import BudgetConfig, Transaction, RecurringTransaction, CategoryRule  # noqa: F401
from .market import PriceCache, FredCache, EconCalendarCache, SentimentCache  # noqa: F401
from .settings import UserSettings, CustomPulseCard, PriceAlert, WatchlistItem, FinancialGoal, MonthlyInvestment  # noqa: F401
from .snapshot import PortfolioSnapshot, IntradaySnapshot  # noqa: F401
from .plaid import PlaidItem, PlaidAccount  # noqa: F401
from .referral import ReferralCode, ReferralRedemption  # noqa: F401
from .blog import BlogPost  # noqa: F401
from .ai import AIConversation, AIMessage, AIUsage  # noqa: F401
from .audit import AuditLog  # noqa: F401
