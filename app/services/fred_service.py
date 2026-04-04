"""FRED data fetching service.

Extracted from fred_manager.py -- fetches Federal Reserve economic data
and caches it in the fred_cache table.
"""

from datetime import datetime, timezone
from ..extensions import db
from ..models.market import FredCache

# Series groups -- must match the series IDs the frontend JS requests.
# Kept in sync with fred_manager.py in the local version.
SERIES_GROUPS = {
    "debt_fiscal": [
        "GFDEBTN", "GFDEGDQ188S", "FYFSD", "A091RC1Q027SBEA",
        "GDP", "W006RC1Q027SBEA", "W068RCQ027SBEA",
        "FYFSGDA188S", "FYONGDA188S", "FYOIGDA188S",
        "FDHBFIN", "MTSDS133FMS",
    ],
    "cpi_pce": [
        "CPIAUCSL", "CPILFESL", "PCEPI",
    ],
    "monetary_policy": [
        "FEDFUNDS", "M2SL", "WALCL",
    ],
    "yield_curve": [
        "DGS1MO", "DGS3MO", "DGS6MO", "DGS1", "DGS2",
        "DGS5", "DGS10", "DGS20", "DGS30",
    ],
    "credit_spreads": [
        "BAMLH0A0HYM2",
    ],
    "real_yields": [
        "DFII10", "T5YIE", "T10YIE",
    ],
    "fed_balance": [
        "WALCL",
    ],
    "sahm_rule": [
        "SAHMREALTIME",
    ],
    "labor": [
        "UNRATE", "ICSA",
    ],
    "growth_sentiment": [
        "A191RL1Q225SBEA", "UMCSENT",
    ],
    "housing": [
        "CSUSHPINSA", "MORTGAGE30US",
    ],
    "wui": [
        "WUIGLOBALWEIGHTAVG",
    ],
}


def refresh_fred_data(api_key=None):
    """Fetch all FRED series groups and update the fred_cache table."""
    import os
    key = api_key or os.environ.get("FRED_API_KEY", "")
    if not key:
        print("[FRED] No API key configured, skipping refresh")
        return

    try:
        from fredapi import Fred
        fred = Fred(api_key=key)
    except Exception as e:
        print(f"[FRED] Init error: {e}")
        return

    for group_name, series_ids in SERIES_GROUPS.items():
        group_data = {}
        for sid in series_ids:
            try:
                data = fred.get_series(sid)
                if data is not None and len(data) > 0:
                    # Convert to list of [date_str, value] pairs
                    points = [
                        [d.isoformat(), float(v)]
                        for d, v in data.items()
                        if v is not None and str(v) != "nan"
                    ]
                    group_data[sid] = points
            except Exception as e:
                print(f"[FRED] Error fetching {sid}: {e}")
                continue

        if group_data:
            existing = FredCache.query.get(group_name)
            if existing:
                existing.data = group_data
                existing.updated_at = datetime.now(timezone.utc)
            else:
                db.session.add(FredCache(
                    series_group=group_name,
                    data=group_data,
                ))

    db.session.commit()
    print(f"[FRED] Refreshed {len(SERIES_GROUPS)} groups")
