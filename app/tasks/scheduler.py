"""Background task scheduler using APScheduler.

Runs shared data refresh jobs (prices, FRED, calendar, sentiment)
and per-user portfolio snapshots on configurable intervals.
"""

import logging
from apscheduler.schedulers.background import BackgroundScheduler

log = logging.getLogger(__name__)
_scheduler = None


def init_scheduler(app):
    """Create and start the background scheduler within the Flask app context."""
    global _scheduler
    if _scheduler is not None:
        return _scheduler

    _scheduler = BackgroundScheduler(daemon=True)

    _scheduler.add_job(
        _run_in_context(app, _refresh_prices),
        "interval", minutes=5, id="refresh_prices",
        max_instances=1, replace_existing=True,
    )

    _scheduler.add_job(
        _run_in_context(app, _refresh_fred),
        "interval", hours=6, id="refresh_fred",
        max_instances=1, replace_existing=True,
    )

    _scheduler.add_job(
        _run_in_context(app, _refresh_calendar),
        "interval", minutes=30, id="refresh_calendar",
        max_instances=1, replace_existing=True,
    )

    _scheduler.add_job(
        _run_in_context(app, _refresh_sentiment),
        "interval", minutes=15, id="refresh_sentiment",
        max_instances=1, replace_existing=True,
    )

    _scheduler.add_job(
        _run_in_context(app, _snapshot_portfolios),
        "cron", hour=16, minute=30, timezone="America/New_York",
        id="snapshot_portfolios", max_instances=1, replace_existing=True,
    )

    # Run an initial price refresh 30s after startup to let gunicorn boot fully
    from datetime import datetime, timedelta
    _scheduler.add_job(
        _run_in_context(app, _refresh_prices),
        "date", run_date=datetime.now() + timedelta(seconds=30),
        id="initial_price_refresh", replace_existing=True,
    )

    _scheduler.start()
    log.info("Scheduler started with %d jobs", len(_scheduler.get_jobs()))
    return _scheduler


def _run_in_context(app, func):
    """Wrap a function to run within the Flask app context."""
    def wrapper():
        with app.app_context():
            func()
    return wrapper


def _refresh_prices():
    from ..services.market_data import refresh_all_prices
    try:
        refresh_all_prices()
        log.info("Prices refreshed")
    except Exception as e:
        log.error("Price refresh error: %s", e)


def _refresh_fred():
    from ..services.fred_service import refresh_fred_data
    try:
        refresh_fred_data()
    except Exception as e:
        log.error("FRED refresh error: %s", e)


def _refresh_calendar():
    from ..services.calendar_service import refresh_calendar
    try:
        refresh_calendar()
    except Exception as e:
        log.error("Calendar refresh error: %s", e)


def _refresh_sentiment():
    from ..services.sentiment_service import refresh_sentiment
    try:
        refresh_sentiment()
    except Exception as e:
        log.error("Sentiment refresh error: %s", e)


def _snapshot_portfolios():
    from ..services.portfolio_service import snapshot_all_users
    try:
        snapshot_all_users()
        log.info("Portfolio snapshots completed")
    except Exception as e:
        log.error("Portfolio snapshot error: %s", e)
