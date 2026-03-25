"""Shared market data cache models (not per-user)."""

from datetime import datetime, timezone
from ..extensions import db


class PriceCache(db.Model):
    """Latest price for any tracked symbol (shared across all users)."""
    __tablename__ = "price_cache"

    symbol = db.Column(db.String(30), primary_key=True)
    price = db.Column(db.Float, nullable=True)
    change_pct = db.Column(db.Float, nullable=True)
    prev_close = db.Column(db.Float, nullable=True)
    source = db.Column(db.String(30), default="yfinance")  # yfinance | coingecko | goldapi
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class FredCache(db.Model):
    """Cached FRED series data (shared)."""
    __tablename__ = "fred_cache"

    series_group = db.Column(db.String(50), primary_key=True)  # e.g. "debt_fiscal", "cpi_pce"
    data = db.Column(db.JSON, nullable=True)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class EconCalendarCache(db.Model):
    """Economic calendar events by week (shared)."""
    __tablename__ = "econ_calendar_cache"

    week_key = db.Column(db.String(10), primary_key=True)  # Monday ISO date, e.g. "2026-03-23"
    events = db.Column(db.JSON, nullable=True)
    week_label = db.Column(db.String(80), default="")
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class SentimentCache(db.Model):
    """Cached sentiment data (CNN F&G, crypto F&G, etc.)."""
    __tablename__ = "sentiment_cache"

    source = db.Column(db.String(30), primary_key=True)  # "cnn_fg", "crypto_fg"
    data = db.Column(db.JSON, nullable=True)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
