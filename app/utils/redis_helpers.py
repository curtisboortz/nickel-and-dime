"""Redis utility helpers — distributed lock, cache invalidation, health check."""

import logging

log = logging.getLogger(__name__)


def get_redis(app=None):
    """Return the shared Redis client (or None if Redis is not configured)."""
    if app is None:
        from flask import current_app
        app = current_app
    return app.extensions.get("redis")


class RedisLock:
    """Simple distributed lock using Redis SET NX EX.

    Usage::

        with RedisLock(redis_client, "my-lock", timeout=60):
            do_exclusive_work()

    If the lock cannot be acquired the body is skipped (context
    manager yields False).
    """

    def __init__(self, redis_client, name, timeout=300):
        self.redis = redis_client
        self.key = f"nd:lock:{name}"
        self.timeout = timeout
        self.acquired = False

    def __enter__(self):
        if self.redis is None:
            self.acquired = True
            return True
        try:
            self.acquired = bool(
                self.redis.set(self.key, "1", nx=True, ex=self.timeout)
            )
        except Exception as exc:
            log.warning("Redis lock acquire failed (%s): %s", self.key, exc)
            self.acquired = True
        return self.acquired

    def __exit__(self, *exc_info):
        if self.acquired and self.redis is not None:
            try:
                self.redis.delete(self.key)
            except Exception:
                pass


def cache_key_user(endpoint_name, user_id):
    """Build a per-user cache key."""
    return f"nd:cache:u:{user_id}:{endpoint_name}"


def invalidate_user_cache(user_id, app=None):
    """Delete all per-user cache entries after a data change."""
    r = get_redis(app)
    if r is None:
        from ..extensions import cache
        cache.clear()
        return
    try:
        pattern = f"nd:cache:u:{user_id}:*"
        keys = list(r.scan_iter(match=pattern, count=200))
        if keys:
            r.delete(*keys)
    except Exception as exc:
        log.warning("Cache invalidation failed for user %s: %s", user_id, exc)


def redis_health(app=None):
    """Return True if Redis is reachable (or not configured)."""
    r = get_redis(app)
    if r is None:
        return True
    try:
        return r.ping()
    except Exception:
        return False
