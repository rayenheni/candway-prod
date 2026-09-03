"""
RATE LIMITING MIDDLEWARE
P0-003 FIX: Uses Redis for distributed rate limiting in production.
FAILS OPEN when Redis is unavailable (consistent with other rate limiters).
Memory fallback ONLY in development (single-worker).
Pure ASGI — avoids BaseHTTPMiddleware Content-Length bug.
"""

import asyncio
import json
import logging
import os
import time
from collections import defaultdict
from datetime import datetime, timedelta

try:
    from backend.logger import logger
except ImportError:
    logger = logging.getLogger("candway_app.rate_limit_middleware")

from backend.client_ip import get_client_ip
from backend.redis_manager import redis_manager

try:
    from backend.config import get_settings

    _settings = get_settings()
    _CONFIG_REDIS_URL = _settings.redis_url
except Exception:
    _CONFIG_REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")


class RateLimitMiddleware:
    """Pure ASGI middleware — avoids BaseHTTPMiddleware Content-Length bug."""

    def __init__(self, app, requests_per_minute=60, requests_per_hour=1000):
        self.app = app
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour

        self.is_prod = os.getenv("ENVIRONMENT", "").lower() in ("prod", "production")
        self.use_redis = bool(_CONFIG_REDIS_URL)

        self.minute_requests = defaultdict(list)
        self.hour_requests = defaultdict(list)

        self.auth_endpoints = [
            "/api/v1/auth/login",
            "/api/v1/auth/signup",
            "/api/v1/auth/register",
            "/api/v1/auth/forgot-password",
            "/api/v1/auth/reset-password",
            "/api/v1/auth/guest-login",
        ]
        self.auth_requests_per_minute = 10

        self.static_exemptions = [
            "/css/",
            "/js/",
            "/assets/",
            "/uploads/",
            "/favicon.ico",
        ]

        if self.is_prod and not self.use_redis:
            logger.critical(
                "PRODUCTION MODE: Rate limiting falling back to in-memory - "
                "this is INSECURE with multiple workers!"
            )
        elif self.use_redis:
            logger.info("Rate limiting: Using Redis backend")
        else:
            logger.warning("Rate limiting: Using in-memory fallback (dev mode)")

        self._redis_client = None
        self._redis_lock = asyncio.Lock()
        self._cleanup_task_started = False

    async def _get_redis(self):
        # RedisManager owns the shared client and handles event-loop
        # lifecycle. Do not cache the client again in this middleware.
        return await redis_manager.get_client()

    def _get_client_ip(self, scope: dict) -> str:
        """Resolve the real client IP.

        Uses the shared trusted-proxy-aware resolver: never trusts a
        client-supplied ``X-Forwarded-For`` first value, so spoofed headers
        cannot bypass rate limits. nginx appends the real peer as the last
        XFF entry (see backend/client_ip.py).
        """
        headers = {k.decode(): v.decode() for k, v in scope.get("headers", [])}
        forwarded = headers.get("x-forwarded-for")
        client = scope.get("client")
        return get_client_ip(forwarded, client[0] if client else None)

    async def _check_redis_rate_limit(self, client_ip: str) -> tuple[bool, int]:
        redis_client = await self._get_redis()
        if not redis_client:
            logger.warning(
                "Rate limiter: Redis unavailable — falling back to allow (fail-open)."
            )
            return True, 0

        now = time.time()
        key_minute = f"ratelimit:minute:{client_ip}"
        key_hour = f"ratelimit:hour:{client_ip}"

        try:
            pipe = redis_client.pipeline()
            pipe.zremrangebyscore(key_minute, 0, now - 60)
            pipe.zcard(key_minute)
            results = await pipe.execute()
            minute_count = results[1]

            if minute_count >= self.requests_per_minute:
                return False, 60

            pipe = redis_client.pipeline()
            pipe.zremrangebyscore(key_hour, 0, now - 3600)
            pipe.zcard(key_hour)
            results = await pipe.execute()
            hour_count = results[1]

            if hour_count >= self.requests_per_hour:
                return False, 3600

            pipe = redis_client.pipeline()
            pipe.zadd(key_minute, {str(now): now})
            pipe.expire(key_minute, 60)
            pipe.zadd(key_hour, {str(now): now})
            pipe.expire(key_hour, 3600)
            await pipe.execute()

            return True, 0

        except Exception as e:
            logger.error(f"Redis rate limit check failed: {e}")
            return True, 0

    def _check_memory_rate_limit(
        self, client_ip: str, limit: int | None = None
    ) -> tuple[bool, int]:
        """In-memory fallback for single-worker development.

        ``limit`` defaults to ``requests_per_minute``; callers pass the
        auth budget for auth endpoints so the fallback honours the same
        per-minute budget as the Redis backend.
        """
        if limit is None:
            limit = self.requests_per_minute

        current_time = datetime.now()
        self._cleanup_old_requests(client_ip, current_time)

        minute_ago = current_time - timedelta(minutes=1)
        recent_minute = [
            ts for ts in self.minute_requests[client_ip] if ts > minute_ago
        ]

        if len(recent_minute) >= limit:
            return False, 60

        hour_ago = current_time - timedelta(hours=1)
        recent_hour = [ts for ts in self.hour_requests[client_ip] if ts > hour_ago]

        if len(recent_hour) >= self.requests_per_hour:
            return False, 3600

        self.minute_requests[client_ip].append(current_time)
        self.hour_requests[client_ip].append(current_time)

        return True, 0

    async def _check_redis_auth(self, client_ip: str) -> tuple[bool, int]:
        redis_client = await self._get_redis()
        if not redis_client:
            logger.warning(
                "Auth rate limiter: Redis unavailable — falling back to allow (fail-open)."
            )
            return True, 0
        try:
            now = time.time()
            key = f"ratelimit:auth:{client_ip}"
            pipe = redis_client.pipeline()
            pipe.zremrangebyscore(key, 0, now - 60)
            pipe.zcard(key)
            results = await pipe.execute()
            auth_count = results[1]
            if auth_count >= self.auth_requests_per_minute:
                return False, 60
            pipe2 = redis_client.pipeline()
            pipe2.zadd(key, {str(now): now})
            pipe2.expire(key, 60)
            await pipe2.execute()
            return True, 0
        except Exception as e:
            logger.error(f"Redis auth rate limit check failed: {e}")
            return True, 0

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        if not self._cleanup_task_started:
            self._cleanup_task_started = True
            asyncio.create_task(self._periodic_cleanup())

        if os.getenv("TESTING") == "true":
            await self.app(scope, receive, send)
            return

        client_ip = self._get_client_ip(scope)

        path = scope.get("path", "")

        for ex in self.static_exemptions:
            if path.startswith(ex):
                await self.app(scope, receive, send)
                return

        is_auth = any(path.startswith(ep) for ep in self.auth_endpoints)
        rate_limited = False
        retry_after = 0

        try:
            if is_auth:
                if self.use_redis:
                    allowed, ra = await self._check_redis_auth(client_ip)
                else:
                    allowed, ra = self._check_memory_rate_limit(
                        f"auth:{client_ip}", self.auth_requests_per_minute
                    )
                if not allowed:
                    rate_limited = True
                    retry_after = ra

            if not rate_limited:
                if self.use_redis:
                    allowed, ra = await self._check_redis_rate_limit(client_ip)
                else:
                    allowed, ra = self._check_memory_rate_limit(client_ip)
                if not allowed:
                    rate_limited = True
                    retry_after = ra

        except Exception as e:
            logger.error(f"Rate limit middleware error: {e}", exc_info=True)

        if rate_limited:
            detail = (
                "Too many authentication attempts. Please wait 60 seconds."
                if is_auth
                else f"Rate limit exceeded. Retry after {retry_after} seconds."
            )
            body = json.dumps({"detail": detail}).encode("utf-8")
            hdrs = [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode("latin-1")),
                (b"retry-after", str(retry_after).encode()),
            ]
            await send({"type": "http.response.start", "status": 429, "headers": hdrs})
            await send({"type": "http.response.body", "body": body, "more_body": False})
            return

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                hs = list(message.get("headers", []))
                status = message.get("status", 200)
                if not is_auth and status < 400:
                    hs.append(
                        (
                            b"x-ratelimit-limit",
                            str(self.requests_per_minute).encode("latin-1"),
                        )
                    )
                    hs.append((b"x-ratelimit-policy", b"minute;hour"))
                message["headers"] = hs
            await send(message)

        await self.app(scope, receive, send_with_headers)

    def _cleanup_old_requests(self, client_ip: str, current_time: datetime):
        hour_ago = current_time - timedelta(hours=1)

        if client_ip in self.minute_requests:
            self.minute_requests[client_ip] = [
                ts for ts in self.minute_requests[client_ip] if ts > hour_ago
            ]
            if not self.minute_requests[client_ip]:
                del self.minute_requests[client_ip]

        if client_ip in self.hour_requests:
            self.hour_requests[client_ip] = [
                ts for ts in self.hour_requests[client_ip] if ts > hour_ago
            ]
            if not self.hour_requests[client_ip]:
                del self.hour_requests[client_ip]

    async def _periodic_cleanup(self):
        while True:
            await asyncio.sleep(300)
            try:
                now = datetime.now()
                hour_ago = now - timedelta(hours=1)
                stale_minute = [
                    ip
                    for ip, ts_list in self.minute_requests.items()
                    if not any(ts > hour_ago for ts in ts_list)
                ]
                for ip in stale_minute:
                    del self.minute_requests[ip]
                stale_hour = [
                    ip
                    for ip, ts_list in self.hour_requests.items()
                    if not any(ts > hour_ago for ts in ts_list)
                ]
                for ip in stale_hour:
                    del self.hour_requests[ip]
                if stale_minute or stale_hour:
                    logger.debug(
                        f"Rate-limit cleanup: removed {len(stale_minute)} minute / {len(stale_hour)} hour entries"
                    )
            except Exception as e:
                logger.error(f"Rate-limit periodic cleanup error: {e}")
