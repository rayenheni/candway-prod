import asyncio
import functools
import logging
import os
from datetime import date

logger = logging.getLogger(__name__)

_CUTOFF_VAR = "DEPRECATED_WRITE_CUTOFF"


def deprecated_write(*fields: str):
    """Decorator marking a function that writes to deprecated User columns.

    Logs a warning on every call with the field names being written.
    If the DEPRECATED_WRITE_CUTOFF environment variable is set to an ISO
    date (YYYY-MM-DD) and today is past that date, raises RuntimeError.

    Usage:
        @deprecated_write("user.name", "user.phone")
        def my_endpoint(...):
            user.name = new_name
            user.phone = new_phone
    """
    cutoff = os.environ.get(_CUTOFF_VAR, "")
    deadline = date.fromisoformat(cutoff) if cutoff else None

    def decorator(func):
        msg = f"DEPRECATED WRITE: {func.__name__} writes to {', '.join(fields)}"

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            if deadline and date.today() >= deadline:
                raise RuntimeError(f"{msg} — past cutoff {cutoff}")
            logger.warning(msg)
            return await func(*args, **kwargs)

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            if deadline and date.today() >= deadline:
                raise RuntimeError(f"{msg} — past cutoff {cutoff}")
            logger.warning(msg)
            return func(*args, **kwargs)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator
