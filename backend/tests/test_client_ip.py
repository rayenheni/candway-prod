"""H-1 regression tests: spoofed X-Forwarded-For must not bypass limits.

Verifies the shared trusted-proxy client-IP resolver, the rate-limit
middleware integration, and the auth helper all derive the same real IP
regardless of attacker-controlled XFF values.
"""

import asyncio


class TestGetClientIp:
    def test_rightmost_proxy_value_wins_over_spoofed_first(self):
        from backend.client_ip import get_client_ip

        # nginx appends the real peer (203.0.113.7) after a spoofed value.
        result = get_client_ip("8.8.8.8, 203.0.113.7", "127.0.0.1")
        assert result == "203.0.113.7"

    def test_multiple_spoofed_values_ignored(self):
        from backend.client_ip import get_client_ip

        result = get_client_ip("1.1.1.1, 2.2.2.2, 203.0.113.99", "127.0.0.1")
        assert result == "203.0.113.99"

    def test_no_forwarded_for_falls_back_to_transport_peer(self):
        from backend.client_ip import get_client_ip

        assert get_client_ip(None, "127.0.0.1") == "127.0.0.1"

    def test_empty_forwarded_for_falls_back_to_transport_peer(self):
        from backend.client_ip import get_client_ip

        assert get_client_ip("", "127.0.0.1") == "127.0.0.1"
        assert get_client_ip(" , ", "10.0.0.5") == "10.0.0.5"

    def test_trust_xff_disabled_ignores_header(self):
        from backend.client_ip import get_client_ip

        result = get_client_ip("8.8.8.8, 203.0.113.7", "127.0.0.1", trust_xff=False)
        assert result == "127.0.0.1"

    def test_unknown_last_resort(self):
        from backend.client_ip import get_client_ip

        assert get_client_ip(None, None) == "unknown"


class TestRateLimitMiddlewareClientIp:
    def test_middleware_derives_real_ip_from_spoofed_scope(self):
        from backend.rate_limit_middleware import RateLimitMiddleware

        middleware = RateLimitMiddleware.__new__(RateLimitMiddleware)
        scope = {
            "headers": [
                (b"x-forwarded-for", b"1.2.3.4, 203.0.113.7"),
            ],
            "client": ("127.0.0.1", 5555),
        }
        assert middleware._get_client_ip(scope) == "203.0.113.7"

    def test_middleware_ignores_spoofed_when_no_proxy(self):
        from backend.rate_limit_middleware import RateLimitMiddleware

        middleware = RateLimitMiddleware.__new__(RateLimitMiddleware)
        scope = {
            "headers": [(b"x-forwarded-for", b"1.2.3.4")],
            "client": ("127.0.0.1", 5555),
        }
        # With trust_xff enabled, a single XFF value is the proxy-appended
        # peer; with no XFF the transport peer is used.
        assert middleware._get_client_ip(scope) == "1.2.3.4"


def _asgi_request(app, headers, path="/", loop=None):
    scope = {
        "type": "http",
        "method": "GET",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": headers,
        "client": ("203.0.113.7", 12345),
        "server": ("test", 80),
        "scheme": "http",
    }
    messages = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        messages.append(message)

    async def run():
        await app(scope, receive, send)

    if loop is None:
        loop = asyncio.new_event_loop()
        own_loop = True
    else:
        own_loop = False
    try:
        loop.run_until_complete(run())
    finally:
        if own_loop:
            for task in asyncio.all_tasks(loop):
                task.cancel()
            loop.close()
    start = next(m for m in messages if m["type"] == "http.response.start")
    return start["status"]


def _memory_backed_middleware(monkeypatch, inner_app, **kwargs):
    """Force the in-memory rate-limit backend regardless of .env REDIS_URL."""
    monkeypatch.setenv("TESTING", "false")
    monkeypatch.setattr("backend.rate_limit_middleware._CONFIG_REDIS_URL", "")
    from backend.rate_limit_middleware import RateLimitMiddleware

    return RateLimitMiddleware(inner_app, **kwargs)


class TestSpoofedXffCannotBypassLimits:
    def test_varying_spoofed_xff_does_not_escape_bucket(self, monkeypatch):

        async def inner_app(scope, receive, send):
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send(
                {"type": "http.response.body", "body": b"ok", "more_body": False}
            )

        middleware = _memory_backed_middleware(
            monkeypatch, inner_app, requests_per_minute=3
        )
        statuses = []
        loop = asyncio.new_event_loop()
        try:
            for i in range(6):
                # Every request claims a DIFFERENT spoofed first XFF value,
                # but the real transport peer (203.0.113.7) is appended last
                # by the proxy. All requests must share the same bucket.
                headers = [
                    (b"x-forwarded-for", f"1.2.3.{i}, 203.0.113.7".encode()),
                    (b"host", b"test"),
                ]
                statuses.append(_asgi_request(middleware, headers, loop=loop))
        finally:
            for task in asyncio.all_tasks(loop):
                task.cancel()
            loop.close()

        assert statuses[:3] == [200, 200, 200]
        assert statuses[3:] == [429, 429, 429]

    def test_auth_rate_limit_still_keys_on_real_ip(self, monkeypatch):
        async def inner_app(scope, receive, send):
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send(
                {"type": "http.response.body", "body": b"ok", "more_body": False}
            )

        middleware = _memory_backed_middleware(
            monkeypatch, inner_app, requests_per_minute=100
        )
        path = "/api/v1/auth/login"
        statuses = []
        loop = asyncio.new_event_loop()
        try:
            for i in range(13):
                headers = [
                    (b"x-forwarded-for", f"5.6.7.{i}, 203.0.113.7".encode()),
                    (b"host", b"test"),
                ]
                statuses.append(
                    _asgi_request(middleware, headers, path=path, loop=loop)
                )
        finally:
            for task in asyncio.all_tasks(loop):
                task.cancel()
            loop.close()

        # 10/min auth budget -> 11th is limited despite unique spoofed XFF.
        assert statuses[:10] == [200] * 10
        assert statuses[10:] == [429] * 3


class TestAuthHelperClientIp:
    def test_auth_helper_uses_shared_resolver(self):
        from backend.client_ip import get_client_ip as _orig
        from backend.routers import auth as auth_module

        captured = {}

        def fake_get_client_ip(forwarded_for, client_host):
            captured["forwarded_for"] = forwarded_for
            captured["client_host"] = client_host
            return _orig(forwarded_for, client_host)

        auth_module.get_client_ip = fake_get_client_ip

        class FakeClient:
            host = "127.0.0.1"

        class FakeHeaders(dict):
            def get(self, key, default=None):
                return super().get(key, default)

        class FakeRequest:
            headers = FakeHeaders({"X-Forwarded-For": "8.8.8.8, 203.0.113.7"})
            client = FakeClient()

        try:
            result = auth_module._get_client_ip(FakeRequest())
        finally:
            auth_module.get_client_ip = _orig

        assert captured["forwarded_for"] == "8.8.8.8, 203.0.113.7"
        assert result == "203.0.113.7"
