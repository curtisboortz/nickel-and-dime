"""Economics API routes: FRED data, economic calendar, FedWatch, sentiment."""

import logging

from flask import Blueprint, jsonify, request as flask_request
from flask_login import login_required, current_user

log = logging.getLogger(__name__)

from ..extensions import db, cache
from ..models.market import FredCache, EconCalendarCache, SentimentCache
from ..services.fred_service import SERIES_GROUPS

api_economics_bp = Blueprint("api_economics", __name__)


FREE_FRED_GROUPS = {"debt_fiscal", "cpi_pce", "monetary_policy"}
_FREE_SERIES_IDS = set()
for _grp in FREE_FRED_GROUPS:
    _FREE_SERIES_IDS.update(SERIES_GROUPS.get(_grp, []))


@api_economics_bp.route("/fred-data")
@login_required
def fred_data():
    """Return FRED series data keyed by individual series ID.

    Accepts:
      ?series_ids=GFDEBTN,GFDEGDQ188S,...  (specific series)
      ?horizon=1y|5y|max                   (trim length)
      ?refresh=1                           (force re-fetch)

    Returns { "GFDEBTN": { "data": [{date, value}, ...] }, ... }
    """
    import math as _math

    series_ids_raw = flask_request.args.get("series_ids", "")
    horizon = flask_request.args.get("horizon", "1y").lower()
    refresh = flask_request.args.get("refresh", "").lower() in ("1", "true")

    requested = [s.strip() for s in series_ids_raw.split(",") if s.strip()] if series_ids_raw else None

    is_free = getattr(current_user, "plan", "pro") == "free"

    if horizon == "max":
        max_pts = 3780
    elif horizon == "5y":
        max_pts = 1260
    else:
        max_pts = 252

    if refresh:
        import os
        from ..services.fred_service import refresh_fred_data
        refresh_fred_data(os.environ.get("FRED_API_KEY", ""))

    tier_tag = "free" if is_free else "pro"
    cache_key = f"fred:{tier_tag}:{horizon}:{series_ids_raw or 'all'}"
    if not refresh:
        cached = cache.get(cache_key)
        if cached is not None:
            return jsonify(cached)

    all_cache = FredCache.query.all()
    series_pool = {}
    for c in all_cache:
        if not isinstance(c.data, dict):
            continue
        if is_free and c.series_group not in FREE_FRED_GROUPS:
            continue
        for sid, points in c.data.items():
            series_pool[sid] = points

    result = {}
    targets = requested if requested else list(series_pool.keys())
    if is_free:
        targets = [s for s in targets if s in _FREE_SERIES_IDS]
    for sid in targets[:50]:
        raw = series_pool.get(sid)
        if not raw:
            result[sid] = {"data": None}
            continue
        data = []
        for pt in raw:
            if isinstance(pt, (list, tuple)) and len(pt) >= 2:
                d, v = pt[0], pt[1]
                if v is not None and not (isinstance(v, float) and (_math.isnan(v) or _math.isinf(v))):
                    data.append({"date": d, "value": v})
        if len(data) > max_pts:
            data = data[-max_pts:]
        result[sid] = {"data": data}

    cache.set(cache_key, result, timeout=600)
    return jsonify(result)


@api_economics_bp.route("/economic-calendar")
@login_required
def economic_calendar():
    """Return economic calendar events for a given week offset."""
    offset = flask_request.args.get("offset", "0", type=int)
    offset = max(-8, min(4, offset))

    # TODO: Migrate calendar_service logic here (currently in routes.py)
    # For now, read from DB cache
    from datetime import datetime, timedelta
    today = datetime.now().date()
    monday = today - timedelta(days=today.weekday()) + timedelta(weeks=offset)
    friday = monday + timedelta(days=4)
    week_key = monday.isoformat()
    week_label = f"{monday.strftime('%b %d')} – {friday.strftime('%b %d, %Y')}"

    cached = EconCalendarCache.query.get(week_key)
    return jsonify({
        "events": cached.events if cached else [],
        "week_label": week_label,
        "offset": offset,
    })


@api_economics_bp.route("/fedwatch")
@login_required
def fedwatch():
    """Compute FedWatch-style rate probabilities from Fed Funds Futures."""
    cached = cache.get("fedwatch")
    if cached is not None:
        return jsonify(cached)

    result = _compute_fedwatch()
    if result and result.get("meetings"):
        cache.set("fedwatch", result, timeout=_FEDWATCH_TTL)
    return jsonify(result or {"meetings": [], "current_rate": None, "error": "Failed to fetch data"})


@api_economics_bp.route("/sentiment")
@login_required
def sentiment():
    """Return sentiment data in the format the dashboard gauges expect.

    VIX, Gold, and Yield Curve are computed instantly from PriceCache.
    CNN and Crypto F&G are read from SentimentCache. If cache is empty,
    a background thread is kicked off to populate it (never blocks response).
    """
    try:
        refresh = flask_request.args.get("refresh", "").lower() in ("1", "true")
        if refresh:
            from ..services.sentiment_service import refresh_sentiment
            refresh_sentiment()
            cache.delete("sentiment")

        cached = cache.get("sentiment")
        if cached is not None and not refresh:
            return jsonify(cached)

        resp = _build_sentiment_response()
        cache.set("sentiment", resp.get_json(), timeout=120)
        return resp
    except Exception:
        log.exception("Sentiment endpoint error")
        return jsonify({"_error": "Failed to load sentiment data"}), 500


def _build_sentiment_response():
    from ..models.market import PriceCache

    result = {}

    # --- Instant gauges from PriceCache (no network, always fast) ---

    vix_row = PriceCache.query.get("^VIX")
    vix_val = vix_row.price if vix_row and vix_row.price else 0
    if vix_val:
        vix_score = _vix_to_score(vix_val)
        result["vix"] = {
            "value": round(vix_val, 1),
            "score": vix_score,
            "label": _fg_label(vix_score),
        }

    gold_row = PriceCache.query.get("GC=F")
    dxy_row = PriceCache.query.get("DX=F")
    gvz_row = PriceCache.query.get("^GVZ")
    gold_price = gold_row.price if gold_row and gold_row.price else 0
    dxy = dxy_row.price if dxy_row and dxy_row.price else 0
    gvz = gvz_row.price if gvz_row and gvz_row.price else 0
    if gold_price:
        gold_score = _compute_gold_sentiment(gold_price, vix_val, dxy, gvz)
        result["gold"] = {"value": gold_score, "label": _fg_label(gold_score)}

    tnx_10 = PriceCache.query.get("^TNX")
    tnx_2 = PriceCache.query.get("2YY=F")
    if tnx_10 and tnx_2 and tnx_10.price and tnx_2.price:
        spread = tnx_10.price - tnx_2.price
        yc_score = _yield_curve_to_score(spread)
        result["yield_curve"] = {
            "value": yc_score,
            "spread": round(spread, 2),
            "label": _fg_label(yc_score),
        }

    # --- Cached gauges from SentimentCache (DB read, fast) ---

    cnn = SentimentCache.query.get("cnn_fg")
    if cnn and cnn.data and cnn.data.get("score"):
        score = cnn.data["score"]
        result["stock"] = {
            "value": score,
            "score": score,
            "label": _fg_label(score),
        }

    crypto = SentimentCache.query.get("crypto_fg")
    if crypto and crypto.data and crypto.data.get("score"):
        score = crypto.data["score"]
        result["crypto"] = {
            "value": score,
            "score": score,
            "label": crypto.data.get("label") or _fg_label(score),
        }

    # If CNN or Crypto cache is empty, kick off a background refresh
    if "stock" not in result or "crypto" not in result:
        import threading
        from flask import current_app
        app = current_app._get_current_object()

        def _bg_refresh():
            with app.app_context():
                try:
                    from ..services.sentiment_service import refresh_sentiment
                    refresh_sentiment()
                except Exception as e:
                    print(f"[Sentiment] bg refresh error: {e}")

        threading.Thread(target=_bg_refresh, daemon=True).start()

    return jsonify(result)


def _vix_to_score(vix):
    """Map VIX to 0-100 sentiment (low VIX = greed, high VIX = fear)."""
    if vix <= 12:
        return 100
    elif vix <= 20:
        return int(60 + (20 - vix) * 5)
    elif vix <= 30:
        return int(60 - (vix - 20) * 4)
    elif vix <= 40:
        return int(20 - (vix - 30) * 2)
    else:
        return 0


def _compute_gold_sentiment(gold_price, vix, dxy, gvz):
    """Compute a 0-100 gold sentiment score from available signals.

    Higher = more bullish/greed for gold.
    Signals: low DXY, high VIX (safe-haven demand), low GVZ (calm accumulation),
    high gold price (momentum).
    """
    score = 50

    if dxy:
        if dxy < 100:
            score += min(15, (100 - dxy) * 1.5)
        else:
            score -= min(15, (dxy - 100) * 1.5)

    if vix:
        if vix > 25:
            score += min(10, (vix - 25) * 1.0)
        elif vix < 15:
            score -= min(10, (15 - vix) * 1.5)

    if gvz:
        if gvz < 15:
            score += 8
        elif gvz > 25:
            score -= min(10, (gvz - 25) * 1.0)

    if gold_price:
        if gold_price > 2500:
            score += min(10, (gold_price - 2500) / 100)
        elif gold_price < 1800:
            score -= min(10, (1800 - gold_price) / 100)

    return max(0, min(100, round(score)))


def _yield_curve_to_score(spread):
    """Map 10Y-2Y spread to 0-100 sentiment. Inverted = fear, steep = greed."""
    if spread < -1.0:
        return 0
    elif spread < 0:
        return int(25 + spread * 25)
    elif spread < 0.5:
        return int(25 + spread * 60)
    elif spread < 1.5:
        return int(55 + (spread - 0.5) * 35)
    else:
        return min(100, int(90 + (spread - 1.5) * 10))


def _fg_label(score):
    if score <= 25:
        return "Extreme Fear"
    if score <= 45:
        return "Fear"
    if score <= 55:
        return "Neutral"
    if score <= 75:
        return "Greed"
    return "Extreme Greed"


# ── CAPE Ratio ───────────────────────────────────────────────────────
_cape_cache = {"data": None, "ts": 0}
_CAPE_TTL = 3600 * 6


def _fetch_cape_data():
    """Scrape CAPE ratio (current + monthly history) from multpl.com."""
    import urllib.request
    import re
    import html as htmlmod
    from datetime import datetime

    url = "https://www.multpl.com/shiller-pe/table/by-month"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml",
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw_html = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"[CAPE] fetch error: {e}")
        return None

    row_pat = re.compile(
        r'<tr[^>]*>\s*<td[^>]*>(.*?)</td>\s*<td[^>]*>(.*?)</td>',
        re.DOTALL,
    )

    history = []
    for m in row_pat.finditer(raw_html):
        raw_date = re.sub(r"<[^>]+>", "", m.group(1)).strip()
        try:
            dt = datetime.strptime(raw_date, "%b %d, %Y")
            date_str = dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
        clean_val = htmlmod.unescape(re.sub(r"<[^>]+>", "", m.group(2))).strip()
        try:
            val = round(float(clean_val), 2)
        except ValueError:
            continue
        history.append({"date": date_str, "value": val})

    history.sort(key=lambda x: x["date"])
    current = history[-1]["value"] if history else None

    median = 16.8
    label = "Average"
    if current:
        if current > 30:
            label = "Very Expensive"
        elif current > 25:
            label = "Expensive"
        elif current > 20:
            label = "Above Average"
        elif current > 15:
            label = "Average"
        elif current > 10:
            label = "Below Average"
        else:
            label = "Cheap"

    return {
        "current": current,
        "median": median,
        "label": label,
        "history": history,
    }


# ── Buffett Indicator ────────────────────────────────────────────────
_buffett_cache = {"data": None, "ts": 0}
_BUFFETT_TTL = 3600 * 6


def _fetch_buffett_data():
    """Compute Buffett Indicator: total market cap / GDP.

    Uses yfinance Wilshire 5000 + FRED-cached GDP, calibrated with a
    known reference point (Dec 2025: 230%).
    """
    gdp_data = []
    all_cache = FredCache.query.all()
    for c in all_cache:
        if isinstance(c.data, dict) and "GDP" in c.data:
            raw_pts = c.data["GDP"]
            for pt in raw_pts:
                if isinstance(pt, (list, tuple)) and len(pt) >= 2:
                    gdp_data.append({"date": pt[0], "value": pt[1]})
            break

    if not gdp_data:
        print("[Buffett] no GDP data available")
        return None

    try:
        import yfinance as yf
        w = yf.download("^W5000", period="max", interval="1wk", progress=False)
        if w.empty:
            print("[Buffett] yfinance returned no Wilshire data")
            return None
    except Exception as e:
        print(f"[Buffett] yfinance error: {e}")
        return None

    gdp_quarters = []
    gdp_map = {}
    for pt in gdp_data:
        d, v = pt.get("date"), pt.get("value")
        if d and v:
            gdp_map[d[:10]] = v
            gdp_quarters.append(d[:10])
    gdp_quarters.sort()

    wilshire_data = {}
    for dt_idx, row in w.iterrows():
        dt_str = dt_idx.strftime("%Y-%m-%d") if hasattr(dt_idx, "strftime") else str(dt_idx)[:10]
        close = row["Close"]
        if hasattr(close, "values"):
            close = close.values[0]
        val = float(close)
        if val > 0:
            wilshire_data[dt_str] = val

    w_dates = sorted(wilshire_data.keys())

    def closest_gdp(target):
        best = None
        for gd in gdp_quarters:
            if gd <= target:
                best = gd
            else:
                break
        return gdp_map.get(best) if best else None

    raw = []
    for wd in w_dates:
        w_val = wilshire_data[wd]
        gdp_val = closest_gdp(wd)
        if gdp_val and gdp_val > 0:
            raw_ratio = w_val / gdp_val * 100
            raw.append({"date": wd, "raw": raw_ratio})

    if not raw:
        return None

    try:
        import yfinance as yf
        from datetime import date as _date

        daily = yf.download("^W5000", period="5d", interval="1d", progress=False)
        if not daily.empty:
            last_idx = daily.index[-1]
            last_date = last_idx.strftime("%Y-%m-%d") if hasattr(last_idx, "strftime") else str(last_idx)[:10]
            last_close = daily.iloc[-1]["Close"]
            if hasattr(last_close, "values"):
                last_close = last_close.values[0]
            last_close = float(last_close)
            if last_close > 0 and last_date not in wilshire_data:
                latest_gdp = gdp_map.get(gdp_quarters[-1]) if gdp_quarters else None
                if latest_gdp and latest_gdp > 0:
                    raw.append({"date": last_date, "raw": last_close / latest_gdp * 100})
    except Exception:
        pass

    ref_raw = None
    for r in reversed(raw):
        if r["date"] <= "2025-12-31":
            ref_raw = r["raw"]
            break
    scale = (230.0 / ref_raw) if ref_raw and ref_raw > 0 else 1.0

    history = []
    seen = set()
    for r in raw:
        if r["date"] not in seen:
            history.append({"date": r["date"], "value": round(r["raw"] * scale, 1)})
            seen.add(r["date"])

    current = history[-1]["value"] if history else None

    median = 120
    label = "Fair Value"
    if current:
        if current > 180:
            label = "Significantly Overvalued"
        elif current > 140:
            label = "Overvalued"
        elif current > 100:
            label = "Fair Value"
        elif current > 70:
            label = "Undervalued"
        else:
            label = "Significantly Undervalued"

    return {
        "current": current,
        "median": median,
        "label": label,
        "history": history,
    }


# ── FedWatch (rate probabilities from Fed Funds Futures) ─────────────
_fedwatch_cache = {"data": None, "ts": 0}
_FEDWATCH_TTL = 3600 * 2


def _compute_fedwatch():
    """Fetch FedWatch probabilities via cme-fedwatch library.

    Uses CME settlement prices, FRED EFFR, and dynamic FOMC
    dates from the Federal Reserve.
    """
    from cme_fedwatch import get_probabilities
    from datetime import datetime

    try:
        raw = get_probabilities()
    except Exception as e:
        log.error("cme-fedwatch fetch failed: %s", e)
        return None

    if not raw or not raw.get("meetings"):
        return None

    effr = raw.get("effr")
    current_target = raw.get("current_target", "")
    parts = current_target.replace("%", "").split("-")
    try:
        lo_pct = float(parts[0])
        hi_pct = float(parts[1])
    except (IndexError, ValueError):
        lo_pct, hi_pct = 0, 0
    current_bps = f"{int(lo_pct * 100)}-{int(hi_pct * 100)}"

    meetings_out = []
    for m in raw["meetings"]:
        md = datetime.strptime(m["date"], "%Y-%m-%d")
        probs = m.get("probabilities", {})

        ranges = []
        cut_t, hold_t, hike_t = 0.0, 0.0, 0.0
        for rng_label, prob in sorted(
            probs.items(),
            key=lambda x: float(
                x[0].split("-")[0].replace("%", "")
            ),
        ):
            rng_parts = (
                rng_label.replace("%", "").split("-")
            )
            try:
                rng_lo = float(rng_parts[0])
                rng_hi = float(rng_parts[1])
            except (IndexError, ValueError):
                continue
            lo_bps = int(rng_lo * 100)
            hi_bps = int(rng_hi * 100)
            bps_label = f"{lo_bps}-{hi_bps}"
            ranges.append({
                "range": bps_label,
                "lo": lo_bps,
                "prob": round(prob, 1),
            })
            if rng_lo < lo_pct - 0.001:
                cut_t += prob
            elif rng_lo > lo_pct + 0.001:
                hike_t += prob
            else:
                hold_t += prob

        meetings_out.append({
            "date": m["date"],
            "label": md.strftime("%d %b%y").lstrip("0"),
            "contract": m.get("contract", ""),
            "price": None,
            "cut": round(cut_t, 1),
            "hold": round(hold_t, 1),
            "hike": round(hike_t, 1),
            "ranges": ranges,
        })

    return {
        "current_rate": effr,
        "current_range_bps": current_bps,
        "meetings": meetings_out,
    }


_sent_hist_cache = {}
_SENT_HIST_TTL = 3600 * 6

_SENT_RANGE_MAP = {
    "1y":  {"yf_period": "1y",  "crypto_limit": 365,  "yc_days": 252},
    "3y":  {"yf_period": "3y",  "crypto_limit": 1095, "yc_days": 756},
    "5y":  {"yf_period": "5y",  "crypto_limit": 1825, "yc_days": 1260},
    "max": {"yf_period": "max", "crypto_limit": 0,    "yc_days": 0},
}


@api_economics_bp.route("/sentiment-history")
@login_required
def sentiment_history():
    """Return daily history for each sentiment gauge. ?range=1y|3y|5y|max"""
    import time as _time
    import os
    now = _time.time()

    rng = flask_request.args.get("range", "1y")
    if rng not in _SENT_RANGE_MAP:
        rng = "1y"
    params = _SENT_RANGE_MAP[rng]

    cache_key = f"sent_hist:{rng}"
    cached_result = cache.get(cache_key)
    if cached_result is not None:
        return jsonify(cached_result)

    from concurrent.futures import ThreadPoolExecutor
    import urllib.request
    import json as _json
    from datetime import datetime as _dt
    import math as _math

    result = {}

    def _hist_cnn():
        cnn_data = {}
        try:
            import fear_greed
            hist = fear_greed.get_history(last={"1y": "1y", "3y": "3y", "5y": "5y", "max": "1y"}.get(rng, "1y"))
            for pt in hist:
                d = pt.get("date")
                s = pt.get("score")
                if d and s is not None:
                    cnn_data[d] = round(s)
        except Exception as e:
            print(f"[SentHist] fear-greed library error: {e}")

        if not cnn_data:
            try:
                req = urllib.request.Request(
                    "https://production.dataviz.cnn.io/index/fearandgreed/graphdata",
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                        "Accept": "application/json",
                    }
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    cnn = _json.loads(resp.read().decode())
                for pt in cnn.get("fear_and_greed_historical", {}).get("data", []):
                    ts, val = pt.get("x"), pt.get("y")
                    if ts is not None and val is not None:
                        dt = _dt.utcfromtimestamp(ts / 1000).strftime("%Y-%m-%d")
                        cnn_data[dt] = round(val)
            except Exception as e:
                print(f"[SentHist] CNN URL fallback error: {e}")

        if rng == "1y" and cnn_data:
            return [{"date": d, "value": v} for d, v in sorted(cnn_data.items())]

        try:
            import yfinance as yf
            data = yf.download(["^VIX", "SPY"], period=params["yf_period"], progress=False, threads=False)
            if data is None or data.empty:
                return [{"date": d, "value": v} for d, v in sorted(cnn_data.items())]
            spy_close = data[("Close", "SPY")].dropna()
            spy_ma125 = spy_close.rolling(125).mean()
            out_map = {}
            for dt_idx in data.index:
                dt = dt_idx.strftime("%Y-%m-%d")
                if dt in cnn_data:
                    out_map[dt] = cnn_data[dt]
                    continue
                try:
                    vix = float(data[("Close", "^VIX")].loc[dt_idx])
                    if _math.isnan(vix):
                        continue
                    score = _vix_to_score(vix)
                    spy_val = float(spy_close.loc[dt_idx]) if dt_idx in spy_close.index else 0
                    spy_ma = float(spy_ma125.loc[dt_idx]) if dt_idx in spy_ma125.index and not _math.isnan(spy_ma125.loc[dt_idx]) else 0
                    if spy_val and spy_ma:
                        momentum = (spy_val - spy_ma) / spy_ma
                        score += max(-15, min(15, momentum * 100))
                    out_map[dt] = max(0, min(100, round(score)))
                except Exception:
                    continue
            return [{"date": d, "value": v} for d, v in sorted(out_map.items())]
        except Exception as e:
            print(f"[SentHist] Stock extended error: {e}")
            return [{"date": d, "value": v} for d, v in sorted(cnn_data.items())]

    def _hist_crypto():
        cmc_key = os.environ.get("CMC_API_KEY", "")
        if cmc_key:
            try:
                limit = params["crypto_limit"] or 2000
                url = f"https://pro-api.coinmarketcap.com/v3/fear-and-greed/historical?limit={limit}"
                req = urllib.request.Request(url, headers={
                    "X-CMC_PRO_API_KEY": cmc_key,
                    "Accept": "application/json",
                })
                with urllib.request.urlopen(req, timeout=15) as resp:
                    body = _json.loads(resp.read().decode())
                out = []
                for entry in body.get("data", []):
                    ts = entry.get("timestamp", "")
                    val = entry.get("value")
                    if ts and val is not None:
                        dt = _dt.utcfromtimestamp(int(ts)).strftime("%Y-%m-%d")
                        out.append({"date": dt, "value": int(val)})
                out.sort(key=lambda x: x["date"])
                if out:
                    return out
            except Exception as e:
                print(f"[SentHist] CMC historical error: {e}")
        try:
            limit = params["crypto_limit"]
            url = "https://api.alternative.me/fng/?limit=0" if limit == 0 else f"https://api.alternative.me/fng/?limit={limit}"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = _json.loads(resp.read().decode())
            out = []
            for entry in data.get("data", []):
                ts = entry.get("timestamp")
                val = entry.get("value")
                if ts and val:
                    dt = _dt.utcfromtimestamp(int(ts)).strftime("%Y-%m-%d")
                    out.append({"date": dt, "value": int(val)})
            out.sort(key=lambda x: x["date"])
            return out
        except Exception as e:
            print(f"[SentHist] Crypto fallback error: {e}")
            return []

    def _hist_vix():
        try:
            import yfinance as yf
            tk = yf.Ticker("^VIX")
            hist = tk.history(period=params["yf_period"])
            out = []
            for dt_idx, row in hist.iterrows():
                dt = dt_idx.strftime("%Y-%m-%d")
                vix = float(row["Close"])
                out.append({"date": dt, "value": _vix_to_score(vix)})
            return out
        except Exception as e:
            print(f"[SentHist] VIX error: {e}")
            return []

    def _hist_gold():
        try:
            import yfinance as yf
            data = yf.download(["GC=F", "DX=F", "^VIX", "^GVZ"],
                               period=params["yf_period"], progress=False, threads=False)
            if data is None or data.empty:
                return []
            out = []
            for dt_idx in data.index:
                dt = dt_idx.strftime("%Y-%m-%d")
                try:
                    gold = float(data[("Close", "GC=F")].loc[dt_idx])
                    dxy = float(data[("Close", "DX=F")].loc[dt_idx]) if ("Close", "DX=F") in data.columns else 0
                    vix = float(data[("Close", "^VIX")].loc[dt_idx]) if ("Close", "^VIX") in data.columns else 0
                    gvz = float(data[("Close", "^GVZ")].loc[dt_idx]) if ("Close", "^GVZ") in data.columns else 0
                    if _math.isnan(gold):
                        continue
                    dxy = 0 if _math.isnan(dxy) else dxy
                    vix = 0 if _math.isnan(vix) else vix
                    gvz = 0 if _math.isnan(gvz) else gvz
                    score = _compute_gold_sentiment(gold, vix, dxy, gvz)
                    out.append({"date": dt, "value": score})
                except Exception:
                    continue
            return out
        except Exception as e:
            print(f"[SentHist] Gold error: {e}")
            return []

    def _hist_yield_curve():
        try:
            all_cache = FredCache.query.all()
            dgs10_pts, dgs2_pts = [], []
            for c in all_cache:
                if not isinstance(c.data, dict):
                    continue
                if "DGS10" in c.data:
                    dgs10_pts = c.data["DGS10"]
                if "DGS2" in c.data:
                    dgs2_pts = c.data["DGS2"]
            if not dgs10_pts or not dgs2_pts:
                return []
            d2_map = {}
            for pt in dgs2_pts:
                if isinstance(pt, (list, tuple)) and len(pt) >= 2 and pt[1] is not None:
                    d2_map[pt[0]] = pt[1]
            out = []
            for pt in dgs10_pts:
                if isinstance(pt, (list, tuple)) and len(pt) >= 2 and pt[1] is not None:
                    d = pt[0]
                    v2 = d2_map.get(d)
                    if v2 is not None:
                        spread = pt[1] - v2
                        out.append({"date": d, "value": _yield_curve_to_score(spread)})
            yc_days = params["yc_days"]
            return out[-yc_days:] if yc_days > 0 else out
        except Exception as e:
            print(f"[SentHist] Yield curve error: {e}")
            return []

    with ThreadPoolExecutor(max_workers=5) as pool:
        f_cnn = pool.submit(_hist_cnn)
        f_crypto = pool.submit(_hist_crypto)
        f_vix = pool.submit(_hist_vix)
        f_gold = pool.submit(_hist_gold)
        f_yc = pool.submit(_hist_yield_curve)

    result["stock"] = f_cnn.result(timeout=30)
    result["crypto"] = f_crypto.result(timeout=30)
    result["vix"] = f_vix.result(timeout=30)
    result["gold"] = f_gold.result(timeout=30)
    result["yield_curve"] = f_yc.result(timeout=30)

    _sent_hist_cache[rng] = {"data": result, "ts": now}
    cache.set(cache_key, result, timeout=_SENT_HIST_TTL)
    return jsonify(result)


@api_economics_bp.route("/cape")
@login_required
def cape():
    """Return current + historical CAPE (Shiller P/E) ratio."""
    import time as _time

    now = _time.time()
    if _cape_cache["data"] and (now - _cape_cache["ts"]) < _CAPE_TTL:
        return jsonify(_cape_cache["data"])

    result = _fetch_cape_data()
    if result and result.get("history"):
        _cape_cache["data"] = result
        _cape_cache["ts"] = now
    return jsonify(result or {"current": None, "history": []})


@api_economics_bp.route("/buffett")
@login_required
def buffett():
    """Return current + historical Buffett Indicator (market cap / GDP %)."""
    import time as _time

    now = _time.time()
    if _buffett_cache["data"] and (now - _buffett_cache["ts"]) < _BUFFETT_TTL:
        return jsonify(_buffett_cache["data"])

    result = _fetch_buffett_data()
    if result and result.get("history"):
        _buffett_cache["data"] = result
        _buffett_cache["ts"] = now
    return jsonify(result or {"current": None, "history": []})
