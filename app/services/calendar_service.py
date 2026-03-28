"""Economic calendar service.

Fetches calendar events from MarketWatch (primary, best for actuals),
Investing.com (supports date ranges), and Faireconomy (fallback).
Stores in econ_calendar_cache table.
"""

import json
import logging
import re
import html as html_mod
import urllib.request
from datetime import datetime, timezone, timedelta

from ..extensions import db
from ..models.market import EconCalendarCache

log = logging.getLogger(__name__)

_HIGH_IMPACT_KEYWORDS = [
    "cpi", "gdp", "nonfarm", "payroll", "fomc", "fed funds", "interest rate",
    "pce price", "core pce", "unemployment rate", "retail sales",
]
_MEDIUM_IMPACT_KEYWORDS = [
    "ppi", "consumer confidence", "ism", "pmi", "housing starts",
    "building permits", "durable goods", "trade balance", "jolts",
    "initial claims", "jobless claims", "industrial production",
    "consumer sentiment", "michigan", "existing home", "new home",
    "cpi mm", "cpi yy", "core cpi", "personal income", "personal spending",
    "adp", "empire state", "philly fed", "chicago pmi",
]

_INVESTING_BULL_MAP = {"bull1": "low", "bull2": "medium", "bull3": "high"}

_MW_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "identity",
    "Referer": "https://www.google.com/",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

_MONTH_MAP = {
    "january": "01", "february": "02", "march": "03", "april": "04",
    "may": "05", "june": "06", "july": "07", "august": "08",
    "september": "09", "october": "10", "november": "11", "december": "12",
}


def _classify_impact(event_name):
    low = event_name.lower()
    for kw in _HIGH_IMPACT_KEYWORDS:
        if kw in low:
            return "high"
    for kw in _MEDIUM_IMPACT_KEYWORDS:
        if kw in low:
            return "medium"
    return "low"


def refresh_calendar():
    """Refresh economic calendar data for current and adjacent weeks."""
    for offset in [-1, 0, 1, 2]:
        try:
            _refresh_week(offset)
        except Exception as e:
            log.error("Calendar refresh error for offset %d: %s", offset, e)


def _refresh_week(offset):
    """Fetch and cache events for a single week offset."""
    monday, friday = _week_range(offset)
    week_key = monday.isoformat()
    week_label = f"{monday.strftime('%b %d')} \u2013 {friday.strftime('%b %d, %Y')}"

    existing = EconCalendarCache.query.get(week_key)
    existing_events = existing.events if existing else []

    events = None

    if offset == 0:
        # Current week: MarketWatch first (best for actuals during the week)
        mw_events = _fetch_marketwatch()
        if mw_events:
            actual_key = _detect_week_key(mw_events)
            if actual_key == week_key:
                events = _deep_merge(mw_events, existing_events)
            else:
                # MW returned a different week -- cache it separately, keep looking
                if actual_key:
                    _save_week(actual_key, mw_events)

    if not events:
        inv_events = _fetch_investing(monday.isoformat(), friday.isoformat())
        if inv_events:
            events = _deep_merge(inv_events, existing_events)

    if not events and offset in (0, 1):
        fe_week = "thisweek" if offset == 0 else "nextweek"
        fe_events = _fetch_faireconomy(fe_week)
        if fe_events:
            events = _deep_merge(fe_events, existing_events)

    if not events and offset not in (0, 1):
        inv_events = _fetch_investing(monday.isoformat(), friday.isoformat())
        if inv_events:
            events = _deep_merge(inv_events, existing_events)

    # If we already have cached data with actuals and got nothing better, keep it
    if not events and existing_events:
        return

    if events:
        _save_week(week_key, events, week_label)


def _save_week(week_key, events, week_label=None):
    """Persist events for a week key."""
    if not week_label:
        try:
            monday = datetime.strptime(week_key, "%Y-%m-%d").date()
            friday = monday + timedelta(days=4)
            week_label = f"{monday.strftime('%b %d')} \u2013 {friday.strftime('%b %d, %Y')}"
        except ValueError:
            week_label = week_key

    existing = EconCalendarCache.query.get(week_key)
    if existing:
        existing.events = events
        existing.week_label = week_label
        existing.updated_at = datetime.now(timezone.utc)
    else:
        db.session.add(EconCalendarCache(
            week_key=week_key, events=events, week_label=week_label,
        ))
    db.session.commit()


def _week_range(offset=0):
    today = datetime.now().date()
    monday = today - timedelta(days=today.weekday()) + timedelta(weeks=offset)
    friday = monday + timedelta(days=4)
    return monday, friday


def _detect_week_key(events):
    """Detect which Monday an event list belongs to based on earliest event date."""
    for e in events:
        d = e.get("date", "")
        if len(d) >= 10:
            try:
                dt = datetime.strptime(d[:10], "%Y-%m-%d").date()
                mon = dt - timedelta(days=dt.weekday())
                return mon.isoformat()
            except ValueError:
                continue
    return None


# ── MarketWatch (primary for current week, best actuals) ────────────

def _fetch_marketwatch():
    """Scrape MarketWatch economic calendar. Returns whatever week MW shows."""
    try:
        req = urllib.request.Request(
            "https://www.marketwatch.com/economy-politics/calendar",
            headers=_MW_HEADERS,
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8")
    except Exception as e:
        log.warning("MarketWatch fetch error: %s", e)
        return []

    start = raw.find("<table")
    if start < 0:
        return []
    end = raw.find("</table>", start)
    if end < 0:
        return []
    table_html = raw[start:end + 8]

    tag_re = re.compile(r"<[^>]+>")
    row_re = re.compile(r"<tr[^>]*>(.*?)</tr>", re.DOTALL)
    td_re = re.compile(r"<td[^>]*>(.*?)</td>", re.DOTALL)
    bold_re = re.compile(r"<b>(.*?)</b>", re.DOTALL | re.IGNORECASE)
    day_header_re = re.compile(
        r"(MONDAY|TUESDAY|WEDNESDAY|THURSDAY|FRIDAY|SATURDAY|SUNDAY),?\s+"
        r"(JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|"
        r"OCTOBER|NOVEMBER|DECEMBER)\s+(\d{1,2})",
        re.IGNORECASE,
    )

    def _clean(s):
        return html_mod.unescape(tag_re.sub("", s)).strip()

    events = []
    current_date = ""
    year = datetime.now().year

    for row_m in row_re.finditer(table_html):
        row_content = row_m.group(1)
        cells = td_re.findall(row_content)
        if not cells:
            continue

        bold_m = bold_re.search(cells[0])
        if bold_m:
            day_m = day_header_re.search(bold_m.group(1))
            if day_m:
                month_num = _MONTH_MAP.get(day_m.group(2).lower(), "01")
                day_num = day_m.group(3).zfill(2)
                current_date = f"{year}-{month_num}-{day_num}"
            continue

        if not current_date or len(cells) < 6:
            continue

        time_raw = _clean(cells[0])
        event_name = _clean(cells[1])
        actual_val = _clean(cells[3])
        forecast_val = _clean(cells[4])
        previous_val = _clean(cells[5])

        if not event_name or event_name.lower() == "none scheduled":
            continue

        time_str = ""
        tm = re.match(r"(\d{1,2}):(\d{2})\s*(am|pm)", time_raw, re.IGNORECASE)
        if tm:
            h = int(tm.group(1))
            m_val = tm.group(2)
            if tm.group(3).lower() == "pm" and h != 12:
                h += 12
            elif tm.group(3).lower() == "am" and h == 12:
                h = 0
            time_str = f"{h:02d}:{m_val}"

        events.append({
            "date": current_date,
            "time": time_str,
            "event": event_name,
            "impact": _classify_impact(event_name),
            "actual": actual_val if actual_val else "",
            "forecast": forecast_val if forecast_val else "-",
            "previous": previous_val if previous_val else "-",
        })

    impact_order = {"high": 0, "medium": 1, "low": 2}
    events.sort(key=lambda e: (e["date"], e["time"], impact_order.get(e["impact"], 3)))
    return events


# ── Investing.com (supports date ranges, has actuals) ───────────────

def _fetch_investing(date_from, date_to):
    """Fetch US economic calendar from Investing.com AJAX endpoint."""
    try:
        post_data = (
            f"dateFrom={date_from}&dateTo={date_to}"
            "&country%5B%5D=5"
            "&importance%5B%5D=1&importance%5B%5D=2&importance%5B%5D=3"
        ).encode()
        req = urllib.request.Request(
            "https://www.investing.com/economic-calendar/Service/getCalendarFilteredData",
            data=post_data,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/131.0.0.0 Safari/537.36",
                "X-Requested-With": "XMLHttpRequest",
                "Referer": "https://www.investing.com/economic-calendar/",
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode("utf-8")
    except Exception as e:
        log.warning("Investing.com fetch error: %s", e)
        return []

    try:
        parsed = json.loads(body)
        html_data = parsed.get("data", "")
    except (json.JSONDecodeError, ValueError):
        html_data = body

    tag_re = re.compile(r"<[^>]+>")
    row_re = re.compile(
        r'<tr[^>]*class="[^"]*js-event-item[^"]*"[^>]*>(.*?)</tr>', re.DOTALL
    )
    td_re = re.compile(r"<td[^>]*>(.*?)</td>", re.DOTALL)
    dt_re = re.compile(r'data-event-datetime="(\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2})')
    bull_re = re.compile(r'data-img_key="(bull[123])"')

    def _clean(s):
        return html_mod.unescape(tag_re.sub("", s)).strip()

    events = []
    for row_m in row_re.finditer(html_data):
        row_html = row_m.group(0)
        cells = td_re.findall(row_m.group(1))
        if len(cells) < 7:
            continue

        dt_m = dt_re.search(row_html)
        if not dt_m:
            continue
        raw_dt = dt_m.group(1)
        date_str = raw_dt[:10].replace("/", "-")
        time_str = raw_dt[11:16]

        event_name = _clean(cells[3])
        if not event_name:
            continue

        actual_val = _clean(cells[4])
        forecast_val = _clean(cells[5])
        previous_val = _clean(cells[6])

        bull_m = bull_re.search(row_html)
        impact = _INVESTING_BULL_MAP.get(bull_m.group(1), "low") if bull_m else "low"

        events.append({
            "date": date_str,
            "time": time_str,
            "event": event_name,
            "impact": impact,
            "actual": actual_val if actual_val and actual_val != "\u00a0" else "",
            "forecast": forecast_val if forecast_val else "-",
            "previous": previous_val if previous_val else "-",
        })

    impact_order = {"high": 0, "medium": 1, "low": 2}
    events.sort(key=lambda e: (e["date"], e["time"], impact_order.get(e["impact"], 3)))
    return events


# ── Faireconomy (fallback, schedule + some actuals) ─────────────────

def _fetch_faireconomy(week):
    """Fetch from Faireconomy CDN (thisweek / nextweek)."""
    url = f"https://nfs.faireconomy.media/ff_calendar_{week}.json"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
    except Exception as e:
        log.warning("Faireconomy fetch error (%s): %s", week, e)
        return []

    events = []
    for item in data:
        if item.get("country") != "USD":
            continue
        impact_raw = (item.get("impact") or "").strip()
        if impact_raw == "Holiday":
            continue
        date_str = (item.get("date") or "")[:10]
        time_str = (item.get("date") or "")[11:16]
        actual_raw = (item.get("actual") or "").strip()

        if impact_raw.lower() == "low":
            impact = _classify_impact(item.get("title", ""))
        else:
            impact = impact_raw.lower() if impact_raw else "low"

        events.append({
            "date": date_str,
            "time": time_str,
            "event": item.get("title", ""),
            "impact": impact,
            "actual": actual_raw if actual_raw else "",
            "forecast": item.get("forecast", "") or "-",
            "previous": item.get("previous", "") or "-",
        })

    impact_order = {"high": 0, "medium": 1, "low": 2}
    events.sort(key=lambda e: (e["date"], e["time"], impact_order.get(e["impact"], 3)))
    return events


# ── Merge logic ─────────────────────────────────────────────────────

def _deep_merge(new_events, cached_events):
    """Merge new events with cached events.

    - Preserves actuals from cache when new source lacks them
    - Preserves cached events that are missing from the new source
    - Prefers new actual values when both exist
    """
    if not cached_events:
        return new_events
    if not new_events:
        return cached_events

    cached_map = {}
    for e in cached_events:
        key = _event_key(e)
        cached_map[key] = e

    seen_keys = set()
    merged = []
    for e in new_events:
        key = _event_key(e)
        seen_keys.add(key)
        old = cached_map.get(key)
        if old:
            if not e.get("actual") and old.get("actual"):
                e["actual"] = old["actual"]
            if e.get("impact") == "low" and old.get("impact") in ("medium", "high"):
                e["impact"] = old["impact"]
        merged.append(e)

    for e in cached_events:
        key = _event_key(e)
        if key not in seen_keys and e.get("actual"):
            merged.append(e)

    impact_order = {"high": 0, "medium": 1, "low": 2}
    merged.sort(key=lambda e: (e.get("date", ""), e.get("time", ""), impact_order.get(e.get("impact"), 3)))
    return merged


def _event_key(e):
    """Create a matching key for an event. Normalizes event name slightly."""
    name = (e.get("event") or "").lower().strip()
    # Collapse common variations
    name = re.sub(r"\s+", " ", name)
    return (e.get("date", ""), e.get("time", ""), name)


def _has_actuals(events):
    """True if at least one event in the list has a non-empty actual value."""
    return any(e.get("actual") for e in events)
