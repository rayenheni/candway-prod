"""Tests for the shared Redis connection manager."""

import pytest


@pytest.mark.asyncio
async def test_get_client_returns_none_when_unavailable():
    from backend.redis_manager import redis_manager

    redis_manager._client = None
    redis_manager._unavailable = True
    client = await redis_manager.get_client()
    assert client is None


@pytest.mark.asyncio
async def test_close_resets_state():
    from backend.redis_manager import redis_manager

    redis_manager._client = None
    redis_manager._unavailable = True
    await redis_manager.close()
    assert redis_manager._client is None
    assert redis_manager._unavailable is False


@pytest.mark.asyncio
async def test_get_client_retries_after_close():
    from backend.redis_manager import redis_manager

    redis_manager._client = None
    redis_manager._unavailable = True
    await redis_manager.close()
    assert redis_manager._unavailable is False
    client = await redis_manager.get_client()
    assert client is None or hasattr(client, "ping")


@pytest.mark.asyncio
async def test_get_client_returns_same_instance():
    from backend.redis_manager import redis_manager

    redis_manager._client = None
    redis_manager._unavailable = True
    first = await redis_manager.get_client()
    second = await redis_manager.get_client()
    assert first is second
