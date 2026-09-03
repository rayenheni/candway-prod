"""
Shared Redis Connection Manager
================================
Singleton async Redis connection pool shared across all Candway services.
Prevents connection proliferation (was 12+ independent pools).

Usage:
    from backend.redis_manager import redis_manager

    client = await redis_manager.get_client()
    if client:
        await client.setex("key", 60, "value")
"""

import logging
import os

logger = logging.getLogger("candway_app")

try:
    import redis.asyncio as aioredis

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


class RedisManager:
    def __init__(self):
        self._client = None
        self._unavailable = False
        # redis.asyncio clients/pools are tied to the event loop in which
        # they are first used. TestClient can create a fresh loop per client.
        self._loop = None

    async def get_client(self):
        if not REDIS_AVAILABLE:
            return None

        import asyncio

        current_loop = asyncio.get_running_loop()

        # A redis.asyncio client/pool must not be reused across event loops.
        # This is especially important with FastAPI TestClient, which may
        # create a fresh loop for each TestClient instance.
        if self._client is not None and self._loop is not current_loop:
            old_client = self._client
            old_loop = self._loop

            self._client = None
            self._loop = None
            self._unavailable = False

            # Close the stale Redis client while its original event loop is
            # still available. If that loop has already been closed, avoid
            # scheduling cleanup on it; the new loop must never reuse it.
            try:
                if old_loop is not None and not old_loop.is_closed():
                    await old_client.aclose()
            except Exception:
                # Best-effort cleanup. Never let stale-loop cleanup break
                # the request using the new event loop.
                pass

        if self._client is not None:
            return self._client

        if self._unavailable:
            return None

        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        max_connections = int(os.getenv("REDIS_MAX_CONNECTIONS", "50"))

        try:
            self._client = aioredis.from_url(
                redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=2,
                # BRPOP is a blocking Redis command. The socket timeout
                # must be longer than the queue's blocking timeout.
                socket_timeout=10,
                retry_on_timeout=False,
                max_connections=max_connections,
            )

            await self._client.ping()
            self._loop = current_loop
            return self._client

        except Exception as e:
            logger.warning(f"Redis unavailable: {e}")
            self._unavailable = True
            self._client = None
            self._loop = None
            return None

    async def close(self):
        client = self._client
        loop = self._loop

        self._client = None
        self._loop = None
        self._unavailable = False

        if client:
            try:
                # Redis asyncio cleanup must happen before the owning loop
                # disappears. If the loop is already closed, calling aclose()
                # can itself schedule callbacks onto a dead loop.
                if loop is None or not loop.is_closed():
                    await client.aclose()
            except Exception:
                pass


redis_manager = RedisManager()
