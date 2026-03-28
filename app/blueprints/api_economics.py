"""Economics API routes: FRED data, economic calendar, FedWatch, sentiment."""

from flask import Blueprint, jsonify, request as flask_request
from flask_login import login_required

from ..extensions import db
from ..models.market import FredCache, EconCalendarCache, SentimentCache

api_economics_bp = Blueprint("api_economics", __name__)


# Free-tier FRED groups (available to all users)
FREE_FRED_GROUPS = {"debt_fiscal", "cpi_pce", "monetary_policy"}


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

    all_cache = FredCache.query.all()
    series_pool = {}
    for c in all_cache:
        if not isinstance(c.data, dict):
            continue
        for sid, points in c.data.items():
            series_pool[sid] = points

    result = {}
    targets = requested if requested else list(series_pool.keys())
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
    import time as _time

    now = _time.time()
    if _fedwatch_cache["data"] and (now - _fedwatch_cache["ts"]) < _FEDWATCH_TTL:
        return jsonify(_fedwatch_cache["data"])

    result = _compute_fedwatch()
    if result and result.get("meetings"):
        _fedwatch_cache["data"] = result
        _fedwatch_cache["ts"] = now
    return jsonify(result or {"meetings": [], "current_rate": None, "error": "Failed to fetch data"})


@api_economics_bp.route("/sentiment")
@login_required
def sentiment():
    """Return sentiment data in the format the dashboard gauges expect.

    Each gauge receives a 0-100 `value` for the needle and a human `label`.
    VIX additionally carries the raw VIX in `score` (used by subtitle).
    Yield curve additionally carries the raw `spread`.

    If cache is empty, triggers a background refresh and returns what we can
    compute from PriceCache alone.
    """
    from ..models.market import PriceCache

    cnn = SentimentCache.query.get("cnn_fg")
    crypto = SentimentCache.query.get("crypto_fg")

    result = {}

    if cnn and cnn.data:
        score = cnn.data.get("score", 0)
        result["stock"] = {
            "value": score,
            "score": score,
            "label": _fg_label(score),
        }
    else:
        try:
            import fear_greed
            data = fear_greed.get()
            score = data.get("score")
            if score is not None:
                score = round(float(score), 1)
                result["stock"] = {
                    "value": score,
                    "score": score,
                    "label": data.get("rating", _fg_label(score)),
                }
                from datetime import datetime, timezone as tz
                existing = SentimentCache.query.get("cnn_fg")
                if existing:
                    existing.data = {"score": score, "rating": data.get("rating", "")}
                    existing.updated_at = datetime.now(tz.utc)
                else:
                    db.session.add(SentimentCache(source="cnn_fg", data={"score": score, "rating": data.get("rating", "")}))
                db.session.commit()
        except Exception:
            pass

    if crypto and crypto.data:
        score = crypto.data.get("score", 0)
        result["crypto"] = {
            "value": score,
            "score": score,
            "label": crypto.data.get("label") or _fg_label(score),
        }
    else:
        try:
            import urllib.request
            import json as _json
            req = urllib.request.Request(
                "https://api.alternative.me/fng/?limit=1",
                headers={"User-Agent": "Mozilla/5.0"},
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                items = _json.loads(resp.read().decode()).get("data", [])
            if items:
                score = int(items[0].get("value", 0))
                label = items[0].get("value_classification", "")
                result["crypto"] = {
                    "value": score,
                    "score": score,
                    "label": label or _fg_label(score),
                }
                from datetime import datetime, timezone as tz
                existing = SentimentCache.query.get("crypto_fg")
                if existing:
                    existing.data = {"score": score, "label": label}
                    existing.updated_at = datetime.now(tz.utc)
                else:
                    db.session.add(SentimentCache(source="crypto_fg", data={"score": score, "label": label}))
                db.session.commit()
        except Exception:
            pass

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
        tk = yf.Ticker("^W5000")
        latest_w = tk.fast_info.last_price
        if latest_w and latest_w > 0:
            latest_gdp = gdp_map.get(gdp_quarters[-1]) if gdp_quarters else None
            if latest_gdp and latest_gdp > 0:
                from datetime import date as _date
                today_str_local = _date.today().strftime("%Y-%m-%d")
                raw.append({"date": today_str_local, "raw": latest_w / latest_gdp * 100})
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

_FOMC_DATES_2026 = [
    "2026-01-29", "2026-03-18", "2026-05-06", "2026-06-17",
    "2026-07-29", "2026-09-16", "2026-10-28", "2026-12-16",
]

_FF_MONTH_CODES = {
    1: "F", 2: "G", 3: "H", 4: "J", 5: "K", 6: "M",
    7: "N", 8: "Q", 9: "U", 10: "V", 11: "X", 12: "Z",
}


def _compute_fedwatch():
    """Build a probability tree across FOMC meetings using CME methodology."""
    import yfinance as yf
    from datetime import datetime, date
    import calendar
    import math

    today = date.today()
    today_str = today.strftime("%Y-%m-%d")

    effr = None
    try:
        all_cache = FredCache.query.all()
        for c in all_cache:
            if isinstance(c.data, dict):
                dff_pts = c.data.get("DFF") or c.data.get("FEDFUNDS")
                if dff_pts:
                    for pt in reversed(dff_pts):
                        if isinstance(pt, (list, tuple)) and len(pt) >= 2 and pt[1] is not None:
                            effr = pt[1]
                            break
            if effr is not None:
                break
    except Exception as e:
        print(f"[FedWatch] FRED EFFR error: {e}")

    if effr is None:
        return None

    current_upper = math.ceil(effr * 4) / 4
    current_lower = current_upper - 0.25
    current_mid = (current_upper + current_lower) / 2

    upcoming = [m for m in _FOMC_DATES_2026 if m > today_str]
    if not upcoming:
        return {"meetings": [], "current_rate": effr,
                "current_range_bps": f"{int(current_lower * 100)}-{int(current_upper * 100)}"}

    last_md = datetime.strptime(upcoming[-1], "%Y-%m-%d").date()
    tickers, month_keys = [], []
    m, y = today.month, today.year
    end_m, end_y = last_md.month + 1, last_md.year
    if end_m > 12:
        end_m, end_y = 1, end_y + 1

    while (y, m) <= (end_y, end_m):
        code = _FF_MONTH_CODES[m]
        tickers.append(f"ZQ{code}{str(y)[2:]}.CBT")
        month_keys.append((y, m))
        m += 1
        if m > 12:
            m, y = 1, y + 1

    implied = {}
    for i, ticker in enumerate(tickers):
        try:
            tk = yf.Ticker(ticker)
            p = tk.fast_info.last_price if tk.fast_info else None
            if p and 80 < p < 105:
                implied[month_keys[i]] = round(100.0 - float(p), 4)
        except Exception:
            pass

    if not implied:
        return {"meetings": [], "current_rate": effr,
                "current_range_bps": f"{int(current_lower * 100)}-{int(current_upper * 100)}",
                "error": "Could not fetch futures prices"}

    meeting_months = {}
    for ms in upcoming:
        md_ = datetime.strptime(ms, "%Y-%m-%d").date()
        meeting_months[(md_.year, md_.month)] = md_

    def _next_month(y, m):
        return (y, m + 1) if m < 12 else (y + 1, 1)

    prev_rate = effr
    prev_meeting_month = (today.year, today.month)
    isolated = []

    for meeting_str in upcoming:
        md = datetime.strptime(meeting_str, "%Y-%m-%d").date()
        mkey = (md.year, md.month)
        imp = implied.get(mkey)
        if imp is None:
            isolated.append({"date": meeting_str, "md": md, "p_cut": 0.0, "ok": False})
            prev_meeting_month = mkey
            continue

        ref = None
        ry, rm = _next_month(*prev_meeting_month)
        while (ry, rm) < mkey:
            if (ry, rm) not in meeting_months and (ry, rm) in implied:
                ref = implied[(ry, rm)]
            ry, rm = _next_month(ry, rm)
        pre_rate = ref if ref is not None else prev_rate

        days_in = calendar.monthrange(md.year, md.month)[1]
        days_after = days_in - md.day

        if days_after <= 3:
            ny, nm = _next_month(md.year, md.month)
            next_imp = implied.get((ny, nm))
            post = next_imp if next_imp is not None else imp
        else:
            post = (imp * days_in - pre_rate * md.day) / days_after

        change = pre_rate - post
        if abs(change) > 0.50:
            isolated.append({"date": meeting_str, "md": md, "p_cut": 0.0, "ok": False})
            prev_meeting_month = mkey
            continue

        p_cut = max(0.0, min(1.0, change / 0.25))
        isolated.append({"date": meeting_str, "md": md, "p_cut": p_cut, "post": post, "ok": True})
        prev_rate = post
        prev_meeting_month = mkey

    dist = {round(current_mid, 4): 100.0}
    meetings_out = []

    for iso in isolated:
        md = iso["md"]
        p_cut = iso["p_cut"] if iso["ok"] else 0.0
        p_hold = 1.0 - p_cut

        new_dist = {}
        for rate, prob in dist.items():
            new_dist[rate] = new_dist.get(rate, 0.0) + prob * p_hold
            cut_rate = round(rate - 0.25, 4)
            if cut_rate >= 0:
                new_dist[cut_rate] = new_dist.get(cut_rate, 0.0) + prob * p_cut
        dist = new_dist

        ranges = []
        cut_t, hold_t, hike_t = 0.0, 0.0, 0.0
        for rate in sorted(dist.keys()):
            prob = dist[rate]
            if prob < 0.05:
                continue
            lo = int(round((rate - 0.125) * 100))
            hi = int(round((rate + 0.125) * 100))
            ranges.append({"range": f"{lo}-{hi}", "lo": lo, "prob": round(prob, 1)})
            if rate < current_mid - 0.001:
                cut_t += prob
            elif rate > current_mid + 0.001:
                hike_t += prob
            else:
                hold_t += prob

        contract_code = f"ZQ{_FF_MONTH_CODES[md.month]}{str(md.year)[2:]}"
        imp_price = implied.get((md.year, md.month))

        meetings_out.append({
            "date": iso["date"],
            "label": md.strftime("%d %b%y").lstrip("0"),
            "contract": contract_code,
            "price": round(imp_price, 4) if imp_price else None,
            "cut": round(cut_t, 1),
            "hold": round(hold_t, 1),
            "hike": round(hike_t, 1),
            "ranges": ranges,
        })

    return {
        "current_rate": effr,
        "current_range_bps": f"{int(current_lower * 100)}-{int(current_upper * 100)}",
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

    cached = _sent_hist_cache.get(rng)
    if cached and cached.get("data") and (now - cached.get("ts", 0)) < _SENT_HIST_TTL:
        return jsonify(cached["data"])

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
