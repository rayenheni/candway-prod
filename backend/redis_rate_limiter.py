"""
Redis-Based Distributed Rate Limiter for Candway Platform
Redis-only distributed rate limiting for Candway Platform.

Features:
- Distributed rate limiting across multiple workers/servers
- Token bucket algorithm for smooth rate limiting
- Sliding window for accurate rate tracking
- Automatic cleanup of expired entries
"""

import os
import time
from typing import Dict, Tuple

from backend.logger import logger
from backend.redis_manager import redis_manager


class RedisRateLimiter:
    """
    Production-ready Redis-based rate limiter.
    Uses sliding window algorithm for accurate rate limiting.
    """

    def __init__(
        self,
        key_prefix: str = "candway_ratelimit",
    ):
        self.key_prefix = key_prefix

    async def _get_redis(self):
        return await redis_manager.get_client()

    def _make_key(self, identifier: str, window: str) -> str:
        """Create a Redis key for rate limiting."""
        return f"{self.key_prefix}:{window}:{identifier}"

    async def is_allowed(
        self, identifier: str, max_requests: int, window_seconds: int, cost: int = 1
    ) -> Tuple[bool, Dict]:
        """
        Check if request is allowed using sliding window algorithm.

        Args:
            identifier: Unique identifier (IP, user_id, etc.)
            max_requests: Maximum requests allowed in window
            window_seconds: Time window in seconds
            cost: Cost of this request (default 1)

        Returns:
            Tuple of (is_allowed, metadata_dict)
        """
        redis_client = await self._get_redis()

        now = time.time()
        window_start = now - window_seconds
        key = self._make_key(identifier, f"{max_requests}_{window_seconds}")

        try:
            # Use Redis pipeline for atomic operations
            pipe = redis_client.pipeline()

            # Remove old entries outside the window
            pipe.zremrangebyscore(key, 0, window_start)

            # Count current entries
            pipe.zcard(key)

            # Execute pipeline
            results = await pipe.execute()
            current_count = results[1]

            # Check if allowed
            if current_count + cost > max_requests:
                # Get oldest entry to calculate retry_after
                oldest = await redis_client.zrange(key, 0, 0, withscores=True)
                retry_after = 0
                if oldest:
                    oldest_time = oldest[0][1]
                    retry_after = max(0, int(oldest_time + window_seconds - now) + 1)

                return False, {
                    "allowed": False,
                    "current": current_count,
                    "limit": max_requests,
                    "remaining": 0,
                    "reset_at": int(now + retry_after),
                    "retry_after": retry_after,
                }

            # Add new entry
            await redis_client.zadd(key, {f"{now}_{cost}": now})

            # Set expiry
            await redis_client.expire(key, window_seconds + 1)

            return True, {
                "allowed": True,
                "current": current_count + cost,
                "limit": max_requests,
                "remaining": max(0, max_requests - current_count - cost),
                "reset_at": int(now + window_seconds),
                "retry_after": 0,
            }

        except Exception as e:
            logger.error(f"Redis rate limit error: {e}")
            # If Redis is down, allow the request rather than blocking all traffic.
            # Production deployments must ensure Redis is running for rate limiting.
            return True, {
                "allowed": True,
                "error": "Rate limiter unavailable",
                "retry_after": 0,
            }

    async def reset(self, identifier: str, max_requests: int, window_seconds: int):
        """Reset rate limit for an identifier."""
        redis_client = await self._get_redis()
        if redis_client:
            key = self._make_key(identifier, f"{max_requests}_{window_seconds}")
            await redis_client.delete(key)

    async def get_stats(
        self, identifier: str, max_requests: int, window_seconds: int
    ) -> Dict:
        """Get current rate limit stats for an identifier."""
        redis_client = await self._get_redis()
        if redis_client is None:
            return {"error": "Redis not connected"}

        now = time.time()
        window_start = now - window_seconds
        key = self._make_key(identifier, f"{max_requests}_{window_seconds}")

        try:
            # Clean old entries and count
            await redis_client.zremrangebyscore(key, 0, window_start)
            count = await redis_client.zcard(key)

            return {
                "current": count,
                "limit": max_requests,
                "remaining": max(0, max_requests - count),
                "window_seconds": window_seconds,
            }
        except Exception:
            return {"error": "Rate limiter unavailable"}


class TokenBucketRateLimiter:
    """
    Token bucket rate limiter for smooth rate limiting.
    Good for AI API rate limiting where burst handling is needed.
    """

    def __init__(self, key_prefix: str = "candway_bucket"):
        self.key_prefix = key_prefix

    async def _get_redis(self):
        return await redis_manager.get_client()

    async def consume(
        self, identifier: str, bucket_size: int, refill_rate: float, tokens: int = 1
    ) -> Tuple[bool, Dict]:
        """
        Try to consume tokens from bucket.

        Args:
            identifier: Unique identifier
            bucket_size: Maximum tokens in bucket
            refill_rate: Tokens added per second
            tokens: Tokens to consume

        Returns:
            Tuple of (success, metadata)
        """
        redis_client = await self._get_redis()
        key = f"{self.key_prefix}:{identifier}"
        now = time.time()

        try:
            # Get current bucket state
            data = await redis_client.hgetall(key)

            if data:
                current_tokens = float(data.get("tokens", bucket_size))
                last_update = float(data.get("last_update", now))

                # Calculate tokens to add
                elapsed = now - last_update
                tokens_to_add = elapsed * refill_rate
                current_tokens = min(bucket_size, current_tokens + tokens_to_add)
            else:
                current_tokens = bucket_size

            # Check if we can consume
            if current_tokens < tokens:
                # Calculate time until enough tokens
                tokens_needed = tokens - current_tokens
                wait_time = tokens_needed / refill_rate

                return False, {
                    "allowed": False,
                    "tokens_available": current_tokens,
                    "tokens_needed": tokens,
                    "wait_seconds": wait_time,
                }

            # Consume tokens
            new_tokens = current_tokens - tokens
            await redis_client.hset(
                key, mapping={"tokens": str(new_tokens), "last_update": str(now)}
            )
            await redis_client.expire(key, 3600)  # 1 hour expiry

            return True, {
                "allowed": True,
                "tokens_remaining": new_tokens,
                "tokens_consumed": tokens,
            }

        except Exception as e:
            logger.error(f"Token bucket error: {e}")
            # Allow on error
            return True, {"allowed": True, "error": "Rate limiter unavailable"}


# ============================================
# GLOBAL RATE LIMITER INSTANCES
# ============================================

# General API rate limiter
api_rate_limiter = RedisRateLimiter(key_prefix="candway_api")

# AI-specific rate limiter (more restrictive)
ai_rate_limiter = RedisRateLimiter(key_prefix="candway_ai")

# Groq API rate limiter (token bucket for smooth handling)
groq_bucket_limiter = TokenBucketRateLimiter(key_prefix="candway_groq_bucket")


# ============================================
# CONVENIENCE FUNCTIONS
# ============================================


async def check_rate_limit(
    identifier: str, max_requests: int = 60, window_seconds: int = 60
) -> Tuple[bool, Dict]:
    """
    Check if a request is allowed.

    Args:
        identifier: IP address or user ID
        max_requests: Maximum requests in window
        window_seconds: Window in seconds

    Returns:
        Tuple of (is_allowed, metadata)
    """
    return await api_rate_limiter.is_allowed(identifier, max_requests, window_seconds)


async def check_ai_rate_limit(
    user_id: str, max_requests: int = 10, window_seconds: int = 60
) -> Tuple[bool, Dict]:
    """
    Check AI request rate limit.
    More restrictive to prevent cost explosion.
    """
    return await ai_rate_limiter.is_allowed(
        f"ai_{user_id}", max_requests, window_seconds
    )


async def check_groq_rate_limit(max_requests_per_minute: int = 30) -> Tuple[bool, Dict]:
    """
    Check Groq API rate limit using token bucket.
    Ensures smooth distribution of API calls.
    """
    # Use a shared identifier for global Groq rate limiting
    return await groq_bucket_limiter.consume(
        identifier="global",
        bucket_size=max_requests_per_minute,
        refill_rate=max_requests_per_minute / 60.0,  # Tokens per second
        tokens=1,
    )


# ============================================
# FASTAPI DEPENDENCIES
# ============================================

from fastapi import HTTPException, Request, status  # noqa: E402


async def rate_limit_dependency(
    request: Request, max_requests: int = 60, window_seconds: int = 60
):
    """
    FastAPI dependency for rate limiting.
    Use in route handlers:

    @router.get("/endpoint")
    async def endpoint(_: None = Depends(rate_limit_dependency)):
        ...
    """

    # Never enforce production rate limits during automated tests.
    # The middleware already follows the same TESTING contract.
    if os.getenv("TESTING") == "true":
        return {
            "allowed": True,
            "testing": True,
            "retry_after": 0,
        }

    # Get client identifier
    identifier = request.client.host if request.client else "unknown"

    # Add user ID if authenticated
    user = getattr(request.state, "user", None)
    if user:
        identifier = f"{identifier}_{user.id}"

    is_allowed, metadata = await check_rate_limit(
        identifier, max_requests, window_seconds
    )

    if not is_allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "Rate limit exceeded",
                "retry_after": metadata.get("retry_after", 60),
            },
            headers={"Retry-After": str(metadata.get("retry_after", 60))},
        )

    return metadata


def rate_limit(max_requests: int = 60, window_seconds: int = 60):
    """
    Factory that returns a FastAPI dependency with custom rate limit parameters.

    Usage:

        @router.get("/endpoint")
        async def endpoint(_: None = Depends(rate_limit(max_requests=5, window_seconds=3600))):
            ...
    """

    async def _dependency(request: Request):
        return await rate_limit_dependency(request, max_requests, window_seconds)

    return _dependency


async def ai_rate_limit_dependency(request: Request):
    """
    Stricter rate limit for AI endpoints.
    """
    user = getattr(request.state, "user", None)
    user_id = (
        str(user.id)
        if user
        else (request.client.host if request.client else "anonymous")
    )

    is_allowed, metadata = await check_ai_rate_limit(
        user_id, max_requests=10, window_seconds=60
    )

    if not is_allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "AI rate limit exceeded. Please wait before making more AI requests.",
                "retry_after": metadata.get("retry_after", 60),
            },
            headers={"Retry-After": str(metadata.get("retry_after", 60))},
        )

    return metadata
