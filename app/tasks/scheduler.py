"""Background task scheduler using APScheduler.

Runs shared data refresh jobs (prices, FRED, calendar, sentiment)
and per-user portfolio snapshots on configurable intervals.

When REDIS_URL is set, each job acquires a distributed lock so only
one Gunicorn worker (or Railway replica) executes the task.
"""

import logging
from apscheduler.schedulers.background import BackgroundScheduler

log = logging.getLogger(__name__)
_scheduler = None
_redis_client = None


def init_scheduler(app):
    """Create and start the background scheduler within the Flask app context."""
    global _scheduler, _redis_client
    if _scheduler is not None:
        return _scheduler

    _redis_client = app.extensions.get("redis")
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
        _run_in_context(app, _sync_coinbase),
        "interval", minutes=10, id="sync_coinbase",
        max_instances=1, replace_existing=True,
    )

    _scheduler.add_job(
        _run_in_context(app, _sync_plaid),
        "interval", hours=2, id="sync_plaid",
        max_instances=1, replace_existing=True,
    )

    _scheduler.add_job(
        _run_in_context(app, _snapshot_portfolios),
        "cron", hour=16, minute=30, timezone="America/New_York",
        id="snapshot_portfolios", max_instances=1, replace_existing=True,
    )

    _scheduler.add_job(
        _run_in_context(app, _snapshot_portfolios),
        "cron", hour="10,11,12,13,14,15", minute=0,
        day_of_week="mon-fri", timezone="America/New_York",
        id="intraday_snapshots", max_instances=1, replace_existing=True,
    )

    _scheduler.add_job(
        _run_in_context(app, _backfill_all),
        "cron", hour=17, minute=0, timezone="America/New_York",
        id="backfill_snapshots", max_instances=1, replace_existing=True,
    )

    _scheduler.add_job(
        _run_in_context(app, _prune_intraday),
        "cron", hour=3, minute=0, timezone="America/New_York",
        id="prune_intraday", max_instances=1, replace_existing=True,
    )

    _scheduler.add_job(
        _run_in_context(app, _email_drip),
        "cron", hour=10, minute=0, timezone="America/New_York",
        id="email_drip", max_instances=1, replace_existing=True,
    )

    _scheduler.add_job(
        _run_in_context(app, _portfolio_digest),
        "cron", hour=7, minute=30, timezone="America/New_York",
        id="portfolio_digest", max_instances=1, replace_existing=True,
    )

    # Run initial refreshes shortly after startup to let gunicorn boot fully
    from datetime import datetime, timedelta
    _scheduler.add_job(
        _run_in_context(app, _refresh_prices),
        "date", run_date=datetime.now() + timedelta(seconds=30),
        id="initial_price_refresh", replace_existing=True,
    )
    _scheduler.add_job(
        _run_in_context(app, _refresh_fred),
        "date", run_date=datetime.now() + timedelta(seconds=45),
        id="initial_fred_refresh", replace_existing=True,
    )
    _scheduler.add_job(
        _run_in_context(app, _refresh_sentiment),
        "date", run_date=datetime.now() + timedelta(seconds=60),
        id="initial_sentiment_refresh", replace_existing=True,
    )

    _scheduler.start()
    log.info("Scheduler started with %d jobs", len(_scheduler.get_jobs()))
    return _scheduler


def _run_in_context(app, func):
    """Wrap a function to run within the Flask app context.

    When Redis is available, acquires a distributed lock so duplicate
    workers/replicas skip the same job.
    """
    def wrapper():
        with app.app_context():
            from ..utils.redis_helpers import RedisLock
            with RedisLock(_redis_client, func.__name__, timeout=300) as acquired:
                if not acquired:
                    log.debug("Skipping %s — another worker holds the lock", func.__name__)
                    return
                func()
    return wrapper


def _refresh_prices():
    from ..services.market_data import refresh_all_prices
    try:
        refresh_all_prices()
        _clear_price_caches()
        log.info("Prices refreshed")
    except Exception as e:
        log.error("Price refresh error: %s", e)


def _clear_price_caches():
    """Invalidate Redis/in-memory caches after a data refresh."""
    try:
        from ..extensions import cache
        for key in ("sentiment", "fedwatch"):
            cache.delete(key)
    except Exception:
        pass


def _refresh_fred():
    from ..services.fred_service import refresh_fred_data
    try:
        refresh_fred_data()
        try:
            from ..extensions import cache
            for h in ("1y", "5y", "max"):
                cache.delete(f"fred:{h}:all")
        except Exception:
            pass
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


def _sync_coinbase():
    from ..services.coinbase_service import sync_all_coinbase_users
    try:
        sync_all_coinbase_users()
        log.info("Coinbase sync completed")
    except Exception as e:
        log.error("Coinbase sync error: %s", e)


def _sync_plaid():
    from ..services.plaid_service import sync_all_plaid_items
    try:
        sync_all_plaid_items()
        log.info("Plaid sync completed")
    except Exception as e:
        log.error("Plaid sync error: %s", e)


def _snapshot_portfolios():
    from ..services.portfolio_service import snapshot_all_users
    try:
        snapshot_all_users()
        log.info("Portfolio snapshots completed")
    except Exception as e:
        log.error("Portfolio snapshot error: %s", e)


def _backfill_all():
    from ..services.portfolio_service import backfill_all_users
    try:
        backfill_all_users()
        log.info("Portfolio backfill completed")
    except Exception as e:
        log.error("Portfolio backfill error: %s", e)


def _prune_intraday():
    from ..services.portfolio_service import prune_intraday_snapshots
    try:
        prune_intraday_snapshots(days_to_keep=30)
    except Exception as e:
        log.error("Intraday prune error: %s", e)


def _portfolio_digest():
    from ..services.digest_service import run_digest_job
    try:
        run_digest_job()
    except Exception as e:
        log.error("Portfolio digest error: %s", e)


def _email_drip():
    """Send lifecycle drip emails based on user signup age.

    Day 0: Welcome (handled at registration, this is the fallback)
    Day 7: Feature highlight
    Day 14: Referral prompt
    """
    from datetime import datetime, timezone, timedelta
    from ..extensions import db
    from ..models.user import User
    from ..services.email_service import send_feature_highlight, send_referral_prompt

    now = datetime.now(timezone.utc)
    sent = 0

    try:
        day7_start = now - timedelta(days=7, hours=2)
        day7_end = now - timedelta(days=7)
        day7_users = User.query.filter(
            User.created_at.between(day7_start, day7_end),
            User.email_verified.is_(True),
        ).all()
        for u in day7_users:
            send_feature_highlight(u)
            sent += 1

        day14_start = now - timedelta(days=14, hours=2)
        day14_end = now - timedelta(days=14)
        day14_users = User.query.filter(
            User.created_at.between(day14_start, day14_end),
            User.email_verified.is_(True),
        ).all()
        for u in day14_users:
            send_referral_prompt(u)
            sent += 1

        if sent:
            log.info("Email drip: sent %d emails", sent)
    except Exception as e:
        log.error("Email drip error: %s", e)
