"""Market data fetching service.

Fetches stock, crypto, metals, and treasury prices via yfinance and CoinGecko.
Gold (GC=F) and silver (SI=F) are fetched through yfinance -- no GoldAPI needed.
"""

from datetime import datetime, timezone
from ..extensions import db
from ..models.market import PriceCache


def refresh_all_prices(symbols=None):
    """Fetch latest prices for all tracked symbols and update the price_cache table.

    Called by the background scheduler. Builds a union of all user-held symbols
    plus the standard pulse bar symbols.
    """
    import yfinance as yf

    # Standard symbols always fetched (pulse bar + macro)
    standard = [
        "SPY", "DX=F", "DX-Y.NYB", "^VIX", "CL=F", "HG=F",
        "GC=F", "SI=F", "^GVZ", "^TNX", "2YY=F", "BTC-USD",
    ]

    if symbols is None:
        # Build union from all users' holdings + custom pulse cards
        from ..models.portfolio import Holding
        from ..models.settings import CustomPulseCard
        user_tickers = db.session.query(Holding.ticker).distinct().all()
        custom_tickers = db.session.query(CustomPulseCard.ticker).distinct().all()
        from ..blueprints.api_market import _normalize_ticker
        custom_syms = []
        for t in custom_tickers:
            if not t[0]:
                continue
            tk = t[0]
            if "/" in tk:
                for p in tk.split("/"):
                    custom_syms.append(_normalize_ticker(p.strip()))
            else:
                custom_syms.append(_normalize_ticker(tk))
        raw_user = [t[0] for t in user_tickers if t[0]]
        symbols = list(set(standard + raw_user + custom_syms))
    else:
        symbols = list(set(standard + symbols))

    yf_symbols = [s for s in symbols
                  if not s.startswith("CG:")
                  and not s.startswith("PRIV:")
                  and not s.startswith("CASH:")]

    if yf_symbols:
        _fetch_yfinance_batch(yf_symbols)

    # Crypto via CoinGecko
    _fetch_coingecko_prices()

    # DXY spot preference
    _apply_dxy_preference()


def _yf_symbol(sym):
    """Convert a Plaid/internal ticker to yfinance format (BRK.B -> BRK-B)."""
    return sym.replace(".", "-") if sym else sym


def _fetch_yfinance_batch(symbols):
    """Batch-fetch prices via yfinance download and update price_cache."""
    import yfinance as yf
    if not symbols:
        return

    yf_to_db = {}
    yf_syms = []
    for s in symbols:
        yf_s = _yf_symbol(s)
        yf_to_db[yf_s] = s
        yf_syms.append(yf_s)

    try:
        df = yf.download(yf_syms, period="2d", group_by="ticker", progress=False, threads=True)
        if df is None or df.empty:
            return
        is_single = len(yf_syms) == 1
        for yf_s in yf_syms:
            db_sym = yf_to_db[yf_s]
            try:
                if is_single:
                    sdf = df
                else:
                    if yf_s not in df.columns.get_level_values(0):
                        continue
                    sdf = df[yf_s]
                if sdf.empty or len(sdf) < 1:
                    continue
                import math
                closes = sdf["Close"].dropna()
                if closes.empty:
                    continue
                price = float(closes.iloc[-1])
                prev = float(closes.iloc[-2]) if len(closes) >= 2 else None
                if math.isnan(price) or not price or price <= 0:
                    continue
                if prev is not None and (math.isnan(prev) or prev <= 0):
                    prev = None
                change_pct = ((price - prev) / prev * 100) if prev and prev > 0 else 0
                _upsert_price(db_sym, price, change_pct, prev, _commit=False)
            except Exception:
                continue
        db.session.commit()
    except Exception as e:
        print(f"[MarketData] yfinance batch error: {e}")


def _fetch_coingecko_prices():
    """Fetch crypto prices via CoinGecko free API using coingecko_id."""
    import urllib.request
    import json
    from ..models.portfolio import CryptoHolding

    rows = (db.session.query(CryptoHolding.coingecko_id)
            .filter(CryptoHolding.coingecko_id.isnot(None),
                    CryptoHolding.coingecko_id != "")
            .distinct().all())
    if not rows:
        return

    cg_ids = [r[0] for r in rows if r[0]]
    if not cg_ids:
        return

    ids_str = ",".join(cg_ids)
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={ids_str}&vs_currencies=usd&include_24hr_change=true"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        for coin_id, vals in data.items():
            price = vals.get("usd", 0)
            change = vals.get("usd_24h_change", 0)
            if price:
                _upsert_price(f"CG:{coin_id}", price, change, source="coingecko", _commit=False)
        db.session.commit()
    except Exception as e:
        print(f"[MarketData] CoinGecko error: {e}")


def _apply_dxy_preference():
    """Prefer DX-Y.NYB (spot DXY) over DX=F (futures) for display."""
    spot = PriceCache.query.get("DX-Y.NYB")
    if spot and spot.price and spot.price > 0:
        _upsert_price("DX=F", spot.price, spot.change_pct, spot.prev_close)


def _upsert_price(symbol, price, change_pct=None, prev_close=None, source="yfinance", _commit=True):
    """Insert or update a price in the cache table."""
    existing = PriceCache.query.get(symbol)
    if existing:
        existing.price = price
        existing.change_pct = change_pct
        existing.prev_close = prev_close
        existing.source = source
        existing.updated_at = datetime.now(timezone.utc)
    else:
        db.session.add(PriceCache(
            symbol=symbol, price=price, change_pct=change_pct,
            prev_close=prev_close, source=source,
        ))
    if _commit:
        db.session.commit()
