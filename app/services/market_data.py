"""Market data fetching service.

Extracted from finance_manager.py -- fetches stock, crypto, metals, and
treasury prices from yfinance, CoinGecko, and GoldAPI.
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
        symbols = list(set(
            standard
            + [t[0] for t in user_tickers if t[0]]
            + [t[0] for t in custom_tickers if t[0]]
        ))
    else:
        symbols = list(set(standard + symbols))

    # Filter out non-yfinance symbols
    yf_symbols = [s for s in symbols if not s.startswith("CG:")]

    if yf_symbols:
        _fetch_yfinance_batch(yf_symbols)

    # Crypto via CoinGecko
    _fetch_coingecko_prices()

    # DXY spot preference
    _apply_dxy_preference()


def _fetch_yfinance_batch(symbols):
    """Batch-fetch prices via yfinance and update price_cache."""
    import yfinance as yf
    try:
        tickers = yf.Tickers(" ".join(symbols))
        for sym in symbols:
            try:
                info = tickers.tickers[sym].fast_info
                price = info.get("lastPrice") or info.get("regularMarketPrice")
                prev = info.get("regularMarketPreviousClose") or info.get("previousClose")
                if price and price > 0:
                    change_pct = ((price - prev) / prev * 100) if prev else 0
                    _upsert_price(sym, price, change_pct, prev)
            except Exception:
                continue
    except Exception as e:
        print(f"[MarketData] yfinance batch error: {e}")


def _fetch_coingecko_prices():
    """Fetch crypto prices via CoinGecko free API."""
    import urllib.request
    import json
    from ..models.portfolio import CryptoHolding

    crypto_ids = db.session.query(CryptoHolding.symbol).distinct().all()
    if not crypto_ids:
        return

    ids_str = ",".join(c[0] for c in crypto_ids)
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={ids_str}&vs_currencies=usd&include_24hr_change=true"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        for coin_id, vals in data.items():
            price = vals.get("usd", 0)
            change = vals.get("usd_24h_change", 0)
            if price:
                _upsert_price(f"CG:{coin_id}", price, change, source="coingecko")
    except Exception as e:
        print(f"[MarketData] CoinGecko error: {e}")


def _apply_dxy_preference():
    """Prefer DX-Y.NYB (spot DXY) over DX=F (futures) for display."""
    spot = PriceCache.query.get("DX-Y.NYB")
    if spot and spot.price and spot.price > 0:
        _upsert_price("DX=F", spot.price, spot.change_pct, spot.prev_close)


def _upsert_price(symbol, price, change_pct=None, prev_close=None, source="yfinance"):
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
    db.session.commit()
