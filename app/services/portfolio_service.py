"""Portfolio valuation and analytics service.

Extracted from finance_manager.py -- computes portfolio values,
allocation percentages, and generates daily snapshots.
"""

from datetime import datetime, date, timezone
from ..extensions import db
from ..models.portfolio import Holding, CryptoHolding, PhysicalMetal, Account, BlendedAccount
from ..models.market import PriceCache
from ..models.snapshot import PortfolioSnapshot
from ..models.settings import UserSettings


def compute_portfolio_value(user_id):
    """Compute total portfolio value for a user using cached prices."""
    total = 0.0
    breakdown = {}

    # Stock / ETF holdings
    holdings = Holding.query.filter_by(user_id=user_id).all()
    for h in holdings:
        if h.value_override:
            value = h.value_override
        elif h.shares:
            price_row = PriceCache.query.get(h.ticker)
            price = price_row.price if price_row else 0
            value = h.shares * price
        else:
            value = 0
        total += value
        breakdown.setdefault(h.bucket or "Equities", 0)
        breakdown[h.bucket or "Equities"] += value

    # Blended accounts
    blended = BlendedAccount.query.filter_by(user_id=user_id).all()
    for b in blended:
        total += b.value
        for bucket, pct in (b.allocations or {}).items():
            breakdown.setdefault(bucket, 0)
            breakdown[bucket] += b.value * (pct / 100.0)

    # Crypto
    crypto = CryptoHolding.query.filter_by(user_id=user_id).all()
    for c in crypto:
        price_row = PriceCache.query.get(f"CG:{c.symbol}")
        price = price_row.price if price_row else 0
        value = c.quantity * price
        total += value
        breakdown.setdefault("Crypto", 0)
        breakdown["Crypto"] += value

    # Physical metals
    metals = PhysicalMetal.query.filter_by(user_id=user_id).all()
    for m in metals:
        sym = "GC=F" if m.metal == "gold" else "SI=F"
        price_row = PriceCache.query.get(sym)
        price_per_oz = price_row.price if price_row else 0
        value = m.oz * price_per_oz
        total += value
        bucket = "Gold" if m.metal == "gold" else "Silver"
        breakdown.setdefault(bucket, 0)
        breakdown[bucket] += value

    # Cash in accounts
    accounts = Account.query.filter_by(user_id=user_id).all()
    for a in accounts:
        if a.account_type in ("checking", "savings"):
            total += a.balance
            breakdown.setdefault("Cash", 0)
            breakdown["Cash"] += a.balance

    return {"total": total, "breakdown": breakdown}


def snapshot_portfolio(user_id):
    """Create or update today's portfolio snapshot."""
    today = date.today()
    value_data = compute_portfolio_value(user_id)
    total = value_data["total"]

    existing = PortfolioSnapshot.query.filter_by(
        user_id=user_id, date=today
    ).first()

    gold = PriceCache.query.get("GC=F")
    silver = PriceCache.query.get("SI=F")
    tnx10 = PriceCache.query.get("^TNX")
    tnx2 = PriceCache.query.get("2YY=F")

    if existing:
        existing.close = total
        existing.high = max(existing.high or total, total)
        existing.low = min(existing.low or total, total)
        existing.gold_price = gold.price if gold else None
        existing.silver_price = silver.price if silver else None
        existing.tnx_10y = tnx10.price if tnx10 else None
        existing.tnx_2y = tnx2.price if tnx2 else None
    else:
        db.session.add(PortfolioSnapshot(
            user_id=user_id,
            date=today,
            total=total,
            open_val=total,
            high=total,
            low=total,
            close=total,
            gold_price=gold.price if gold else None,
            silver_price=silver.price if silver else None,
            tnx_10y=tnx10.price if tnx10 else None,
            tnx_2y=tnx2.price if tnx2 else None,
        ))

    db.session.commit()


def snapshot_all_users():
    """Snapshot portfolios for every registered user. Called by daily scheduler."""
    from ..models.user import User
    users = User.query.all()
    for user in users:
        try:
            snapshot_portfolio(user.id)
        except Exception as e:
            print(f"[Snapshot] Error for user {user.id}: {e}")
