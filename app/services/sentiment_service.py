"""Sentiment data fetching service.

Fetches CNN Fear & Greed, crypto Fear & Greed, and caches results.
"""

from datetime import datetime, timezone
from ..extensions import db
from ..models.market import SentimentCache


def refresh_sentiment():
    """Refresh all sentiment indicators."""
    _refresh_cnn_fear_greed()
    _refresh_crypto_fear_greed()


def _refresh_cnn_fear_greed():
    """Fetch CNN Fear & Greed Index."""
    import urllib.request
    import json
    try:
        url = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json",
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        score = data.get("fear_and_greed", {}).get("score")
        rating = data.get("fear_and_greed", {}).get("rating")
        if score is not None:
            _upsert_sentiment("cnn_fg", {
                "score": round(float(score), 1),
                "rating": rating or "",
                "timestamp": data.get("fear_and_greed", {}).get("timestamp", ""),
            })
    except Exception as e:
        print(f"[Sentiment] CNN F&G error: {e}")


def _refresh_crypto_fear_greed():
    """Fetch crypto Fear & Greed from CoinMarketCap API."""
    import os
    import urllib.request
    import json

    api_key = os.environ.get("CMC_API_KEY", "")
    if not api_key:
        print("[Sentiment] CMC_API_KEY not set, skipping crypto F&G")
        return

    try:
        url = "https://pro-api.coinmarketcap.com/v3/fear-and-greed/historical?limit=1"
        req = urllib.request.Request(url, headers={
            "X-CMC_PRO_API_KEY": api_key,
            "Accept": "application/json",
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read().decode())

        items = body.get("data", [])
        if items:
            latest = items[0]
            _upsert_sentiment("crypto_fg", {
                "score": int(latest.get("value", 0)),
                "label": latest.get("value_classification", ""),
            })
    except Exception as e:
        print(f"[Sentiment] CMC Crypto F&G error: {e}")


def _upsert_sentiment(source, data):
    """Insert or update sentiment cache."""
    existing = SentimentCache.query.get(source)
    if existing:
        existing.data = data
        existing.updated_at = datetime.now(timezone.utc)
    else:
        db.session.add(SentimentCache(source=source, data=data))
    db.session.commit()
