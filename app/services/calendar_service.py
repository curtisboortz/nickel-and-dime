"""Economic calendar service.

Fetches calendar events from Investing.com (primary) and Faireconomy
(fallback), stores in econ_calendar_cache table. Migrated from routes.py.
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

_INVESTING_BULL_MAP = {"bull1": "low", "bull2": "medium", "bull3": "high"}


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
    week_label = f"{monday.strftime('%b %d')} – {friday.strftime('%b %d, %Y')}"

    existing = EconCalendarCache.query.get(week_key)
    existing_events = existing.events if existing else []

    events = None

    # Investing.com is the primary source (supports any date range, has actuals)
    events = _fetch_investing(monday.isoformat(), friday.isoformat())
    if events:
        events = _merge_actuals(events, existing_events)

    # Faireconomy as fallback for current/next week
    if not events:
        if offset == 0:
            events = _fetch_faireconomy("thisweek")
        elif offset == 1:
            events = _fetch_faireconomy("nextweek")
        if events:
            events = _merge_actuals(events, existing_events)

    # If we already have cached data with actuals, keep it
    if not events and existing_events and _has_actuals(existing_events):
        return

    if events:
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
        events.append({
            "date": date_str,
            "time": time_str,
            "event": item.get("title", ""),
            "impact": impact_raw.lower() if impact_raw else "low",
            "actual": actual_raw if actual_raw else "",
            "forecast": item.get("forecast", "") or "-",
            "previous": item.get("previous", "") or "-",
        })

    impact_order = {"high": 0, "medium": 1, "low": 2}
    events.sort(key=lambda e: (e["date"], e["time"], impact_order.get(e["impact"], 3)))
    return events


def _merge_actuals(new_events, cached_events):
    """Merge actuals from cached events into new events so we never lose
    previously captured actual values when a fallback source lacks them."""
    if not cached_events:
        return new_events
    cached_map = {}
    for e in cached_events:
        key = (e.get("date", ""), e.get("time", ""), e.get("event", ""))
        if e.get("actual"):
            cached_map[key] = e["actual"]
    for e in new_events:
        if not e.get("actual"):
            key = (e.get("date", ""), e.get("time", ""), e.get("event", ""))
            if key in cached_map:
                e["actual"] = cached_map[key]
    return new_events


def _has_actuals(events):
    """True if at least one event in the list has a non-empty actual value."""
    return any(e.get("actual") for e in events)
