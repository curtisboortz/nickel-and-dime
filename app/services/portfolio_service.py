"""Portfolio valuation and analytics service.

Extracted from finance_manager.py -- computes portfolio values,
allocation percentages, and generates daily snapshots.
"""

import logging
from datetime import datetime, date, timedelta, timezone
from ..extensions import db
from ..models.portfolio import Holding, CryptoHolding, PhysicalMetal, Account, BlendedAccount
from ..models.market import PriceCache
from ..models.snapshot import PortfolioSnapshot, IntradaySnapshot
from ..models.settings import UserSettings

log = logging.getLogger("nd")


def compute_portfolio_value(user_id):
    """Compute total portfolio value for a user using cached prices."""
    total = 0.0
    breakdown = {}

    from ..utils.buckets import normalize_bucket as _normalize_bucket

    holdings = Holding.query.filter_by(user_id=user_id).all()
    crypto = CryptoHolding.query.filter_by(user_id=user_id).all()
    metals = PhysicalMetal.query.filter_by(user_id=user_id).all()

    needed_symbols = set()
    for h in holdings:
        if h.ticker and h.shares and not h.value_override:
            needed_symbols.add(h.ticker)
    for c in crypto:
        cg_key = f"CG:{c.coingecko_id}" if c.coingecko_id else f"CG:{c.symbol.lower()}"
        needed_symbols.add(cg_key)
    needed_symbols.update(["GC=F", "SI=F"])

    price_map = {}
    if needed_symbols:
        rows = PriceCache.query.filter(PriceCache.symbol.in_(list(needed_symbols))).all()
        price_map = {r.symbol: r for r in rows}

    for h in holdings:
        if h.value_override:
            value = h.value_override
        elif h.shares:
            price_row = price_map.get(h.ticker)
            price = price_row.price if price_row else 0
            value = h.shares * price
            if value == 0 and h.institution_value:
                value = h.institution_value
        else:
            value = h.institution_value or 0
        total += value
        bucket = _normalize_bucket(h.bucket) or "Equities"
        breakdown.setdefault(bucket, 0)
        breakdown[bucket] += value

    blended = BlendedAccount.query.filter_by(user_id=user_id).all()
    for b in blended:
        total += b.value
        alloc = b.allocations or {}
        if "asset_class" in alloc:
            bucket = _normalize_bucket(alloc["asset_class"])
            breakdown.setdefault(bucket, 0)
            breakdown[bucket] += b.value
        else:
            for raw_bucket, pct in alloc.items():
                try:
                    pct_val = float(pct)
                except (TypeError, ValueError):
                    continue
                bucket = _normalize_bucket(raw_bucket)
                breakdown.setdefault(bucket, 0)
                breakdown[bucket] += b.value * (pct_val / 100.0)

    for c in crypto:
        cg_key = f"CG:{c.coingecko_id}" if c.coingecko_id else f"CG:{c.symbol.lower()}"
        price_row = price_map.get(cg_key)
        price = price_row.price if price_row else 0
        value = c.quantity * price
        total += value
        breakdown.setdefault("Crypto", 0)
        breakdown["Crypto"] += value

    for m in metals:
        sym = "GC=F" if m.metal.lower() == "gold" else "SI=F"
        price_row = price_map.get(sym)
        price_per_oz = price_row.price if price_row else 0
        value = m.oz * price_per_oz
        total += value
        bucket = "Gold" if m.metal.lower() == "gold" else "Silver"
        breakdown.setdefault(bucket, 0)
        breakdown[bucket] += value

    accounts = Account.query.filter_by(user_id=user_id).all()
    for a in accounts:
        if a.account_type in ("checking", "savings"):
            total += a.balance
            breakdown.setdefault("Cash", 0)
            breakdown["Cash"] += a.balance

    return {"total": total, "breakdown": breakdown}


def snapshot_portfolio(user_id):
    """Create or update today's portfolio snapshot with per-bucket breakdown."""
    today = date.today()
    value_data = compute_portfolio_value(user_id)
    total = value_data["total"]
    breakdown = {k: round(v, 2) for k, v in value_data.get("breakdown", {}).items() if v}

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
        existing.breakdown = breakdown
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
            breakdown=breakdown,
        ))

    if total and total > 0:
        db.session.add(IntradaySnapshot(
            user_id=user_id,
            timestamp=datetime.now(timezone.utc),
            total=total,
        ))

    db.session.commit()


def prune_intraday_snapshots(days_to_keep=30):
    """Delete intraday snapshots older than the retention window."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days_to_keep)
    deleted = IntradaySnapshot.query.filter(
        IntradaySnapshot.timestamp < cutoff
    ).delete(synchronize_session=False)
    db.session.commit()
    if deleted:
        log.info("Pruned %d intraday snapshots older than %d days", deleted, days_to_keep)
    return deleted


def snapshot_all_users():
    """Snapshot portfolios for every registered user. Called by daily scheduler."""
    from ..models.user import User
    users = User.query.all()
    for user in users:
        try:
            snapshot_portfolio(user.id)
        except Exception as e:
            log.error("Snapshot error for user %s: %s", user.id, e)


def backfill_snapshots(user_id, max_days=90):
    """Fill gaps in snapshot history using yfinance historical close prices.

    Uses the user's current holdings to compute what the portfolio value
    would have been on each missing date. This is an approximation that
    doesn't account for trades made on those days, but eliminates chart gaps.
    """
    import yfinance as yf
    from ..utils.buckets import normalize_bucket as _normalize_bucket

    today = date.today()
    cutoff = today - timedelta(days=max_days)

    existing_dates = set(
        row.date for row in
        PortfolioSnapshot.query
        .filter(
            PortfolioSnapshot.user_id == user_id,
            PortfolioSnapshot.date >= cutoff,
        )
        .with_entities(PortfolioSnapshot.date)
        .all()
    )

    missing_dates = []
    d = cutoff
    while d < today:
        if d.weekday() < 5 and d not in existing_dates:
            missing_dates.append(d)
        d += timedelta(days=1)

    if not missing_dates:
        return 0

    holdings = Holding.query.filter_by(user_id=user_id).all()
    crypto = CryptoHolding.query.filter_by(user_id=user_id).all()
    metals = PhysicalMetal.query.filter_by(user_id=user_id).all()
    accounts = Account.query.filter_by(user_id=user_id).all()
    blended = BlendedAccount.query.filter_by(user_id=user_id).all()

    cash_total = sum(
        a.balance for a in accounts
        if a.account_type in ("checking", "savings")
    )
    blended_total = sum(b.value for b in blended)

    tickers = set()
    for h in holdings:
        if h.ticker and h.shares and not h.value_override:
            t = h.ticker
            if t.startswith("PRIV:"):
                continue
            tickers.add(t)
    tickers.add("GC=F")
    tickers.add("SI=F")

    if not tickers:
        return 0

    start_str = (missing_dates[0] - timedelta(days=1)).isoformat()
    end_str = (missing_dates[-1] + timedelta(days=1)).isoformat()

    try:
        hist = yf.download(
            list(tickers), start=start_str, end=end_str,
            progress=False, auto_adjust=True, threads=True,
        )
    except Exception as e:
        log.error("yfinance backfill download failed: %s", e)
        return 0

    if hist.empty:
        return 0

    is_multi = isinstance(hist.columns, __import__("pandas").MultiIndex)

    def _get_close(ticker, dt):
        try:
            ts = __import__("pandas").Timestamp(dt)
            if is_multi:
                return float(hist.loc[ts, ("Close", ticker)])
            elif len(tickers) == 1:
                return float(hist.loc[ts, "Close"])
        except (KeyError, TypeError, ValueError):
            pass
        return None

    filled = 0
    for d in missing_dates:
        total = cash_total + blended_total

        for h in holdings:
            if h.value_override:
                total += h.value_override
                continue
            if not h.shares or not h.ticker:
                continue
            if h.ticker.startswith("PRIV:"):
                total += h.value_override or 0
                continue
            price = _get_close(h.ticker, d)
            if price is None:
                continue
            total += h.shares * price

        gold_price = _get_close("GC=F", d)
        silver_price = _get_close("SI=F", d)

        for m in metals:
            spot = gold_price if m.metal.lower() == "gold" else silver_price
            if spot:
                total += m.oz * spot

        for c in crypto:
            pass

        if total <= 0:
            continue

        db.session.add(PortfolioSnapshot(
            user_id=user_id,
            date=d,
            total=round(total, 2),
            open_val=round(total, 2),
            high=round(total, 2),
            low=round(total, 2),
            close=round(total, 2),
            gold_price=gold_price,
            silver_price=silver_price,
        ))
        filled += 1

    if filled:
        db.session.commit()
        log.info("Backfilled %d snapshots for user %s", filled, user_id)

    return filled


def backfill_all_users():
    """Run backfill for every registered user. Called by daily scheduler."""
    from ..models.user import User
    users = User.query.all()
    total_filled = 0
    for user in users:
        try:
            total_filled += backfill_snapshots(user.id)
        except Exception as e:
            log.error("Backfill error for user %s: %s", user.id, e)
            db.session.rollback()
    if total_filled:
        log.info("Backfill complete: %d total snapshots filled", total_filled)
