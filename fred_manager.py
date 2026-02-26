"""
FRED (Federal Reserve Economic Data) API integration with caching.
Fetches macroeconomic series and caches in price_cache.json under key "fred".
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional


def _price_cache_path(base: Path) -> Path:
    return base / "price_cache.json"


def load_price_cache(base: Path) -> dict:
    """Load full price cache (includes 'fred' key)."""
    path = _price_cache_path(base)
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def save_price_cache(base: Path, cache: dict) -> None:
    """Write full price cache to disk."""
    path = _price_cache_path(base)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2)


def get_fred_cache(base: Path) -> dict:
    """Return the 'fred' section of price cache: series_id -> {updated, data}."""
    cache = load_price_cache(base)
    return cache.get("fred", {})


def set_fred_series(base: Path, series_id: str, data: list[dict]) -> None:
    """Update cache with one series; merge into existing cache."""
    cache = load_price_cache(base)
    fred = cache.get("fred", {})
    fred[series_id] = {
        "updated": datetime.now().isoformat(),
        "data": data,
    }
    cache["fred"] = fred
    save_price_cache(base, cache)


def is_cache_stale(updated_iso: Optional[str], max_age_hours: float = 24) -> bool:
    """True if cache entry is older than max_age_hours."""
    if not updated_iso:
        return True
    try:
        updated = datetime.fromisoformat(updated_iso.replace("Z", "+00:00"))
        if updated.tzinfo:
            updated = updated.replace(tzinfo=None)
    except (ValueError, TypeError):
        return True
    return (datetime.now() - updated) > timedelta(hours=max_age_hours)


def fetch_series(series_id: str, api_key: str, **kwargs: Any) -> list[dict]:
    """
    Fetch series observations from FRED API. Returns list of {date, value}.
    kwargs can include observation_start, observation_end, limit, etc.
    """
    try:
        from fredapi import Fred
    except ImportError:
        return []

    if not api_key or not api_key.strip():
        return []

    try:
        fred = Fred(api_key=api_key.strip())
        series = fred.get_series(series_id, **kwargs)
        if series is None or series.empty:
            return []
        out = []
        for dt, val in series.items():
            if hasattr(dt, "strftime"):
                date_str = dt.strftime("%Y-%m-%d")
            else:
                date_str = str(dt)[:10]
            try:
                import math
                v = float(val) if val is not None and str(val).strip() != "." else None
                if v is not None and (math.isnan(v) or math.isinf(v)):
                    v = None
            except (TypeError, ValueError):
                v = None
            out.append({"date": date_str, "value": v})
        out.sort(key=lambda x: x["date"])
        return out
    except Exception:
        return []


def get_series_cached(
    series_id: str,
    api_key: str,
    base: Path,
    max_age_hours: float = 24,
    **fetch_kwargs: Any,
) -> list[dict]:
    """
    Get series data from cache if fresh; otherwise fetch from FRED and cache.
    Returns list of {date, value}.
    """
    fred = get_fred_cache(base)
    entry = fred.get(series_id)
    if entry and not is_cache_stale(entry.get("updated"), max_age_hours):
        return entry.get("data", [])

    data = fetch_series(series_id, api_key, **fetch_kwargs)
    if data:
        set_fred_series(base, series_id, data)
    return data


# Series IDs used by the Economics dashboard (for reference / bulk fetch)
DEBT_SERIES = [
    "GFDEBTN",           # Federal Debt: Total Public Debt (millions)
    "FYFSD",             # Federal Surplus or Deficit (annual, millions)
    "FDHBFIN",           # Federal Debt Held by Foreign & International
    "A091RC1Q027SBEA",   # Federal Government Interest Payments (quarterly)
    "GDP",                # Gross Domestic Product
    "GFDEGDQ188S",       # Federal Debt to GDP Ratio
    "FYOIGDA188S",       # Federal Net Interest as % of GDP (annual)
    "FYFSGDA188S",       # Federal Surplus or Deficit as % of GDP (annual)
    "FYONGDA188S",       # Federal Net Outlays (spending) as % of GDP (annual)
    "MTSDS133FMS",       # Monthly Treasury Statement: Deficit
    "W006RC1Q027SBEA",   # Federal Government Total Receipts
    "W068RCQ027SBEA",    # Federal Government Total Expenditures
]
INFLATION_SERIES = ["CPIAUCSL", "CPILFESL", "PCEPI"]
MONETARY_SERIES = ["FEDFUNDS", "M2SL", "WALCL"]
# Yield curve: Treasury constant maturity rates (monthly)
YIELD_CURVE_SERIES = ["DGS1MO", "DGS3MO", "DGS6MO", "DGS1", "DGS2", "DGS5", "DGS10", "DGS20", "DGS30"]
LABOR_SERIES = ["UNRATE", "ICSA"]
GROWTH_SENTIMENT_SERIES = ["A191RL1Q225SBEA", "UMCSENT"]  # Real GDP growth, Consumer Sentiment
CREDIT_SERIES = ["BAMLH0A0HYM2"]  # ICE BofA US High Yield OAS
REAL_YIELDS_SERIES = ["DFII10", "T5YIE", "T10YIE"]  # 10Y TIPS yield, 5Y/10Y breakeven inflation
RECESSION_SERIES = ["SAHMREALTIME"]  # Sahm Rule Recession Indicator
HOUSING_SERIES = ["CSUSHPINSA", "MORTGAGE30US"]

ALL_FRED_SERIES = (
    DEBT_SERIES
    + INFLATION_SERIES
    + MONETARY_SERIES
    + YIELD_CURVE_SERIES
    + CREDIT_SERIES
    + REAL_YIELDS_SERIES
    + RECESSION_SERIES
    + LABOR_SERIES
    + GROWTH_SENTIMENT_SERIES
    + HOUSING_SERIES
)
