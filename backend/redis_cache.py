"""
Redis-based API Response Cache
================================
Cache-aside pattern for frequently-accessed, slowly-changing data.
Reduces DB load for public endpoints (jobs, courses, stats) and user dashboards.

Usage:
    from backend.redis_cache import cached, clear_cache

    @router.get("/jobs/public")
    @cached(ttl_seconds=60)
    async def public_jobs():
        ...

    # Invalidate on mutation:
    await clear_cache("/api/v1/jobs/public")
"""

import hashlib
import json
import logging
from functools import wraps
from typing import Callable

logger = logging.getLogger("candway_app")

from backend.redis_manager import redis_manager  # noqa: E402


async def _get_client():
    return await redis_manager.get_client()


def _cache_key(
    endpoint_path: str, query_params: dict = None, user_id: int = None
) -> str:
    """Generate deterministic cache key from endpoint + query params."""
    raw = endpoint_path
    if query_params:
        sorted_params = sorted(query_params.items())
        raw += "?" + "&".join(f"{k}={v}" for k, v in sorted_params if v is not None)
    if user_id:
        raw += f"#user={user_id}"
    return f"api_cache:{hashlib.sha256(raw.encode()).hexdigest()[:24]}"


def cached(ttl_seconds: int = 30):
    """
    Decorator that caches the JSON response of a GET endpoint in Redis.
    Cache is keyed by request path + query params + optional user_id.
    Skips caching if Redis is unavailable (falls through to original handler).
    """

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Only cache GET-like endpoints
            request = kwargs.get("request")
            if request and request.method not in ("GET", "HEAD"):
                return await func(*args, **kwargs)

            # Build cache key from request path
            path = str(request.url.path) if request else ""
            query = (
                dict(request.query_params)
                if request and hasattr(request, "query_params")
                else None
            )
            user = kwargs.get("current_user") or kwargs.get("user")
            uid = user.id if user and hasattr(user, "id") else None

            key = _cache_key(path, query, uid)
            redis = await _get_client()

            # Try cache hit
            if redis:
                try:
                    cached_data = await redis.get(key)
                    if cached_data:
                        import json as _json

                        logger.debug(f"Cache HIT: {path}")
                        from fastapi.responses import JSONResponse

                        return JSONResponse(content=_json.loads(cached_data))
                except Exception:
                    pass

            # Cache miss - call original handler
            response = await func(*args, **kwargs)

            # Store in Redis if we got a successful response
            if (
                redis
                and response
                and hasattr(response, "status_code")
                and response.status_code == 200
            ):
                try:
                    content = json.dumps(
                        response.body.decode()
                        if hasattr(response, "body")
                        else str(response)
                    )
                    await redis.setex(key, ttl_seconds, content)
                    logger.debug(f"Cache SET: {path} (TTL={ttl_seconds}s)")
                except Exception:
                    pass

            return response

        return wrapper

    return decorator


async def clear_cache(pattern: str = "*"):
    """
    Invalidate cached responses matching a key pattern.
    Examples:
        await clear_cache("api_cache:/api/v1/jobs/*")
        await clear_cache("api_cache:*")  # Flush all
    """
    redis = await _get_client()
    if not redis:
        return 0
    try:
        keys = await redis.keys(f"api_cache:{pattern}")
        if keys:
            await redis.delete(*keys)
            count = len(keys)
            logger.info(f"Cache cleared: {count} keys matching '{pattern}'")
            return count
        return 0
    except Exception as e:
        logger.error(f"Cache clear error: {e}")
        return 0
