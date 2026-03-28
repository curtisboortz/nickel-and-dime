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
    """Fetch CNN Fear & Greed Index via fear-greed library, with raw URL fallback."""
    try:
        import fear_greed
        data = fear_greed.get()
        score = data.get("score")
        rating = data.get("rating", "")
        if score is not None:
            _upsert_sentiment("cnn_fg", {
                "score": round(float(score), 1),
                "rating": rating,
            })
            print(f"[Sentiment] CNN F&G via library: {score} ({rating})")
            return
    except Exception as e:
        print(f"[Sentiment] fear-greed library error: {e}")

    import urllib.request
    import json
    for url in [
        "https://production.dataviz.cnn.io/index/fearandgreed/graphdata",
        "https://production.dataviz.cnn.io/index/fearandgreed/current",
    ]:
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json",
            })
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
            fg = data.get("fear_and_greed", data)
            score = fg.get("score")
            rating = fg.get("rating", "")
            if score is not None:
                _upsert_sentiment("cnn_fg", {
                    "score": round(float(score), 1),
                    "rating": rating,
                })
                print(f"[Sentiment] CNN F&G via {url}: {score}")
                return
        except Exception as e:
            print(f"[Sentiment] CNN F&G fallback ({url}) error: {e}")
            continue
    print("[Sentiment] All CNN F&G sources failed")


def _refresh_crypto_fear_greed():
    """Fetch crypto Fear & Greed -- CoinMarketCap first, alternative.me fallback."""
    import os
    import urllib.request
    import json
    import logging

    log = logging.getLogger("nd.sentiment")

    api_key = os.environ.get("CMC_API_KEY", "")
    if api_key:
        for endpoint in (
            "https://pro-api.coinmarketcap.com/v3/fear-and-greed/latest",
            "https://pro-api.coinmarketcap.com/v3/fear-and-greed/historical?limit=1",
        ):
            try:
                req = urllib.request.Request(endpoint, headers={
                    "X-CMC_PRO_API_KEY": api_key,
                    "Accept": "application/json",
                })
                with urllib.request.urlopen(req, timeout=10) as resp:
                    body = json.loads(resp.read().decode())

                log.info("CMC %s raw response keys: %s", endpoint.split("/")[-1], list(body.keys()))
                data = body.get("data", {})
                log.info("CMC data type=%s content=%s", type(data).__name__, str(data)[:300])

                if isinstance(data, dict) and "value" in data:
                    val = int(data["value"])
                    cls = data.get("value_classification", "")
                    _upsert_sentiment("crypto_fg", {"score": val, "label": cls})
                    log.info("Crypto F&G via CMC latest: %d (%s)", val, cls)
                    return
                elif isinstance(data, list) and data:
                    latest = data[0] if isinstance(data[0], dict) else {}
                    val = int(latest.get("value", 0))
                    cls = latest.get("value_classification", "")
                    if val:
                        _upsert_sentiment("crypto_fg", {"score": val, "label": cls})
                        log.info("Crypto F&G via CMC list: %d (%s)", val, cls)
                        return
                else:
                    log.warning("CMC %s: unexpected data shape, trying next endpoint", endpoint.split("/")[-1])
            except Exception as e:
                log.warning("CMC %s error: %s", endpoint.split("/")[-1], e)
                continue
    else:
        log.warning("CMC_API_KEY not set, skipping CoinMarketCap")

    try:
        url = "https://api.alternative.me/fng/?limit=1"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        items = data.get("data", [])
        if items:
            val = int(items[0].get("value", 0))
            cls = items[0].get("value_classification", "")
            _upsert_sentiment("crypto_fg", {"score": val, "label": cls})
            log.info("Crypto F&G via alternative.me (fallback): %d (%s)", val, cls)
    except Exception as e:
        log.error("alternative.me F&G fallback error: %s", e)


def _upsert_sentiment(source, data):
    """Insert or update sentiment cache."""
    existing = SentimentCache.query.get(source)
    if existing:
        existing.data = data
        existing.updated_at = datetime.now(timezone.utc)
    else:
        db.session.add(SentimentCache(source=source, data=data))
    db.session.commit()
