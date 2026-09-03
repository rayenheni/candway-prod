"""Optimistic-locking helpers for entity tables with version_id_col.

Usage:
    with retry_on_stale(max_retries=3) as retry:
        while retry():
            # read, modify, flush — StaleDataError causes a retry
            ...
"""

import logging
import time

from sqlalchemy.orm.exc import StaleDataError

logger = logging.getLogger(__name__)


def retry_stale(max_retries: int = 3, delay_ms: int = 50):
    """Decorator: retry a function when StaleDataError is raised.

    Works with both sync and async functions.
    The decorated function must accept ``db`` as first positional arg
    or as keyword argument, because on StaleDataError the session
    must be rolled back before retrying.
    """
    import asyncio
    import functools

    def _get_db(args, kwargs):
        db = kwargs.get("db")
        if db is not None and hasattr(db, "rollback"):
            return db
        for arg in args:
            if hasattr(arg, "rollback"):
                return arg
        return None

    def _handle_stale(exc, attempt, args, kwargs):
        logger.warning(
            "StaleDataError on attempt %d/%d: %s",
            attempt,
            max_retries,
            exc,
        )
        db = _get_db(args, kwargs)
        if db:
            try:
                db.rollback()
            except Exception:
                pass

    def decorator(fn):
        if asyncio.iscoroutinefunction(fn):

            @functools.wraps(fn)
            async def async_wrapper(*args, **kwargs):
                last_exc = None
                for attempt in range(1, max_retries + 1):
                    try:
                        return await fn(*args, **kwargs)
                    except StaleDataError as e:
                        last_exc = e
                        if attempt < max_retries:
                            _handle_stale(e, attempt, args, kwargs)
                            await asyncio.sleep(delay_ms / 1000.0)
                raise last_exc

            return async_wrapper
        else:

            @functools.wraps(fn)
            def sync_wrapper(*args, **kwargs):
                last_exc = None
                for attempt in range(1, max_retries + 1):
                    try:
                        return fn(*args, **kwargs)
                    except StaleDataError as e:
                        last_exc = e
                        if attempt < max_retries:
                            _handle_stale(e, attempt, args, kwargs)
                            time.sleep(delay_ms / 1000.0)
                raise last_exc

            return sync_wrapper

    return decorator
