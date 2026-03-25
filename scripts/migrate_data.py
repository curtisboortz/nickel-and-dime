"""Migrate data from flat-file config.json + price_history.json into the database.

Usage:
    flask seed --email you@example.com --password yourpass
    (or call migrate_all() directly)
"""

import json
import os
from datetime import date, datetime, timezone

from app.extensions import db
from app.models.user import User
from app.models.settings import UserSettings, CustomPulseCard, PriceAlert, FinancialGoal, MonthlyInvestment
from app.models.portfolio import Holding, CryptoHolding, PhysicalMetal, Account, BlendedAccount
from app.models.budget import BudgetConfig, Transaction, RecurringTransaction
from app.models.snapshot import PortfolioSnapshot


def migrate_all(config_path, history_path, email, password):
    """Run the full migration: create user, import config, import history."""
    if not os.path.exists(config_path):
        print(f"[Migrate] Config file not found: {config_path}")
        return

    db.create_all()

    existing = User.query.filter_by(email=email).first()
    if existing:
        print(f"[Migrate] User {email} already exists (id={existing.id}). Skipping user creation.")
        user = existing
    else:
        user = User(email=email, name=email.split("@")[0], email_verified=True)
        user.set_password(password)
        db.session.add(user)
        db.session.flush()
        print(f"[Migrate] Created user {email} (id={user.id})")

    with open(config_path, "r") as f:
        config = json.load(f)

    _import_settings(user, config)
    _import_holdings(user, config)
    _import_crypto(user, config)
    _import_metals(user, config)
    _import_blended(user, config)
    _import_budget(user, config)
    _import_transactions(user, config)
    _import_recurring(user, config)
    _import_goals(user, config)
    _import_monthly_investments(user, config)
    _import_custom_pulse_cards(user, config)
    _import_price_alerts(user, config)

    if os.path.exists(history_path):
        _import_price_history(user, history_path)

    db.session.commit()
    print(f"[Migrate] Done! All data imported for {email}")


def _import_settings(user, config):
    """Import contribution plan, targets, links, api keys."""
    settings = UserSettings.query.filter_by(user_id=user.id).first()
    if not settings:
        settings = UserSettings(user_id=user.id)
        db.session.add(settings)

    contrib = config.get("contribution", {})
    settings.contribution_amount = contrib.get("amount", 0)
    settings.contribution_frequency = contrib.get("frequency", "biweekly")
    settings.targets = config.get("targets", {})
    settings.contribution_plan = config.get("contribution_plan", {})
    settings.links = config.get("links", {})
    settings.pulse_order = config.get("pulse_card_order", [])

    api_keys = config.get("api_keys", {})
    settings.coinbase_key_name = api_keys.get("coinbase_key_name", "")
    settings.coinbase_private_key = api_keys.get("coinbase_private_key", "")
    settings.goldapi_key = api_keys.get("goldapi_io", "")

    db.session.flush()
    print(f"  Settings: imported")


def _import_holdings(user, config):
    """Import stock/ETF holdings."""
    # Clear existing
    Holding.query.filter_by(user_id=user.id).delete()

    for h in config.get("holdings", []):
        ticker = h.get("ticker", "")
        if not ticker:
            continue
        db.session.add(Holding(
            user_id=user.id,
            ticker=ticker,
            shares=h.get("qty") or 0,
            cost_basis=h.get("value_override"),
            account=h.get("account", ""),
            bucket=_map_bucket(h.get("asset_class", "Equities")),
        ))

    count = len(config.get("holdings", []))
    db.session.flush()
    print(f"  Holdings: {count} imported")


def _import_crypto(user, config):
    """Import crypto holdings."""
    CryptoHolding.query.filter_by(user_id=user.id).delete()

    for c in config.get("crypto_holdings", []):
        symbol = c.get("symbol", "")
        if not symbol:
            continue
        # CoinGecko uses lowercase full names; map common tickers
        cg_id = _ticker_to_coingecko(symbol)
        db.session.add(CryptoHolding(
            user_id=user.id,
            symbol=cg_id,
            quantity=c.get("qty", 0),
            source="manual",
        ))

    count = len(config.get("crypto_holdings", []))
    db.session.flush()
    print(f"  Crypto: {count} imported")


def _import_metals(user, config):
    """Import physical metal holdings."""
    PhysicalMetal.query.filter_by(user_id=user.id).delete()

    for m in config.get("physical_metals", []):
        metal_type = (m.get("metal") or "gold").lower()
        db.session.add(PhysicalMetal(
            user_id=user.id,
            metal=metal_type,
            oz=m.get("qty_oz", 0),
            purchase_price=m.get("cost_per_oz"),
            purchase_date=_parse_date(m.get("date")),
            description=m.get("note", ""),
        ))

    count = len(config.get("physical_metals", []))
    db.session.flush()
    print(f"  Physical metals: {count} imported")


def _import_blended(user, config):
    """Import blended accounts."""
    BlendedAccount.query.filter_by(user_id=user.id).delete()

    for b in config.get("blended_accounts", []):
        db.session.add(BlendedAccount(
            user_id=user.id,
            name=b.get("name", "Blended"),
            value=b.get("value", 0),
            allocations=b.get("allocation", {}),
        ))

    count = len(config.get("blended_accounts", []))
    db.session.flush()
    print(f"  Blended accounts: {count} imported")


def _import_budget(user, config):
    """Import budget configuration."""
    BudgetConfig.query.filter_by(user_id=user.id).delete()

    budget = config.get("budget", {})
    if budget:
        db.session.add(BudgetConfig(
            user_id=user.id,
            monthly_income=budget.get("monthly_income", 0),
            categories=budget.get("categories", []),
        ))
        db.session.flush()
        print(f"  Budget: imported ({len(budget.get('categories', []))} categories)")
    else:
        print(f"  Budget: none found")


def _import_transactions(user, config):
    """Import transactions."""
    existing_count = Transaction.query.filter_by(user_id=user.id).count()
    if existing_count > 0:
        print(f"  Transactions: skipped ({existing_count} already exist)")
        return

    for t in config.get("transactions", []):
        db.session.add(Transaction(
            user_id=user.id,
            date=_parse_date(t.get("date")) or date.today(),
            description=t.get("description", ""),
            amount=t.get("amount", 0),
            category=t.get("category", "Other"),
            source="migration",
        ))

    count = len(config.get("transactions", []))
    db.session.flush()
    print(f"  Transactions: {count} imported")


def _import_recurring(user, config):
    """Import recurring transactions."""
    RecurringTransaction.query.filter_by(user_id=user.id).delete()

    for r in config.get("recurring_transactions", []):
        db.session.add(RecurringTransaction(
            user_id=user.id,
            description=r.get("description", ""),
            amount=r.get("amount", 0),
            frequency=r.get("frequency", "monthly"),
            category=r.get("category", "Other"),
        ))

    count = len(config.get("recurring_transactions", []))
    db.session.flush()
    print(f"  Recurring transactions: {count} imported")


def _import_goals(user, config):
    """Import financial goals."""
    FinancialGoal.query.filter_by(user_id=user.id).delete()

    for g in config.get("financial_goals", []):
        db.session.add(FinancialGoal(
            user_id=user.id,
            name=g.get("name", ""),
            target_amount=g.get("target", 0),
            current_amount=g.get("current", 0),
            target_date=_parse_date(g.get("target_date")),
        ))

    count = len(config.get("financial_goals", []))
    db.session.flush()
    print(f"  Financial goals: {count} imported")


def _import_monthly_investments(user, config):
    """Import monthly investment tracking."""
    MonthlyInvestment.query.filter_by(user_id=user.id).delete()

    mi_data = config.get("monthly_investments", {})
    if isinstance(mi_data, dict) and "month" in mi_data:
        # Single-month dict format: {month, allocation_percentages, contributions}
        month = mi_data.get("month", "")
        alloc = mi_data.get("allocation_percentages", {})
        contribs = mi_data.get("contributions", {})
        count = 0
        for category in set(list(alloc.keys()) + list(contribs.keys())):
            target_pct = alloc.get(category, 0)
            contributed = contribs.get(category, 0)
            db.session.add(MonthlyInvestment(
                user_id=user.id,
                month=month,
                category=category,
                target=target_pct,
                contributed=contributed,
            ))
            count += 1
        db.session.flush()
        print(f"  Monthly investments: {count} categories for {month}")
    elif isinstance(mi_data, list):
        for mi in mi_data:
            db.session.add(MonthlyInvestment(
                user_id=user.id,
                month=mi.get("month", ""),
                category=mi.get("category", ""),
                target=mi.get("target", 0),
                contributed=mi.get("contributed", 0),
            ))
        db.session.flush()
        print(f"  Monthly investments: {len(mi_data)} imported")
    else:
        print(f"  Monthly investments: none found")


def _import_custom_pulse_cards(user, config):
    """Import custom pulse cards."""
    CustomPulseCard.query.filter_by(user_id=user.id).delete()

    for i, cp in enumerate(config.get("custom_pulse_cards", [])):
        db.session.add(CustomPulseCard(
            user_id=user.id,
            ticker=cp.get("ticker", ""),
            label=cp.get("label", ""),
            position=i,
        ))

    count = len(config.get("custom_pulse_cards", []))
    db.session.flush()
    print(f"  Custom pulse cards: {count} imported")


def _import_price_alerts(user, config):
    """Import price alerts."""
    PriceAlert.query.filter_by(user_id=user.id).delete()

    for a in config.get("price_alerts", []):
        db.session.add(PriceAlert(
            user_id=user.id,
            ticker=a.get("ticker", ""),
            condition=a.get("condition", "above"),
            target_price=a.get("target", 0),
            active=a.get("active", True),
        ))

    count = len(config.get("price_alerts", []))
    db.session.flush()
    print(f"  Price alerts: {count} imported")


def _import_price_history(user, history_path):
    """Import portfolio OHLC history snapshots."""
    existing_count = PortfolioSnapshot.query.filter_by(user_id=user.id).count()
    if existing_count > 0:
        print(f"  Price history: skipped ({existing_count} snapshots already exist)")
        return

    with open(history_path, "r") as f:
        data = json.load(f)

    entries = data.get("history", data) if isinstance(data, dict) else data
    if not isinstance(entries, list):
        print(f"  Price history: unexpected format")
        return

    for entry in entries:
        snap_date = _parse_date(entry.get("date"))
        if not snap_date:
            continue
        db.session.add(PortfolioSnapshot(
            user_id=user.id,
            date=snap_date,
            total=entry.get("total", 0),
            open=entry.get("open", entry.get("total", 0)),
            high=entry.get("high", entry.get("total", 0)),
            low=entry.get("low", entry.get("total", 0)),
            close=entry.get("close", entry.get("total", 0)),
            gold_price=entry.get("gold"),
            silver_price=entry.get("silver"),
            tnx_10y=entry.get("tnx_10y"),
            tnx_2y=entry.get("tnx_2y"),
        ))

    db.session.flush()
    print(f"  Price history: {len(entries)} snapshots imported")


# ── Helpers ──

_BUCKET_MAP = {
    "cash": "Cash", "equities": "Equities", "gold": "Gold", "silver": "Silver",
    "crypto": "Crypto", "realassets": "RealAssets", "real assets": "RealAssets",
    "art": "Art", "bonds": "Equities",
}


def _map_bucket(asset_class):
    """Normalize asset_class string to a standard bucket name."""
    return _BUCKET_MAP.get((asset_class or "").lower().strip(), asset_class or "Equities")


_COINGECKO_MAP = {
    "BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana", "XRP": "ripple",
    "ADA": "cardano", "DOT": "polkadot", "AVAX": "avalanche-2",
    "MATIC": "matic-network", "LINK": "chainlink", "UNI": "uniswap",
    "CBETH": "coinbase-wrapped-staked-eth", "DOGE": "dogecoin",
    "SHIB": "shiba-inu", "LTC": "litecoin", "ATOM": "cosmos",
}


def _ticker_to_coingecko(symbol):
    """Map a crypto ticker symbol to CoinGecko ID."""
    return _COINGECKO_MAP.get(symbol.upper(), symbol.lower())


def _parse_date(date_str):
    """Safely parse a date string."""
    if not date_str:
        return None
    try:
        return date.fromisoformat(date_str[:10])
    except (ValueError, TypeError):
        return None
