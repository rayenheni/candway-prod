"""HTTP request metrics middleware.

Records every request into the Prometheus ``/metrics`` exporter:
* ``candway_http_requests_total{method, path, status}``
* ``candway_http_request_duration_seconds{method, path}``
* ``candway_http_in_flight_requests``

The ``path`` label is the FastAPI route template (e.g.
``/api/v1/auth/login``), NOT the raw URL — this keeps cardinality
bounded and avoids leaking tokens that landed in the URL.
"""

import time

try:
    from backend.routers.monitoring import (
        http_in_flight,
        http_request_duration_seconds,
        http_requests_total,
    )

    METRICS_AVAILABLE = True
except ImportError:
    METRICS_AVAILABLE = False

from backend.logger import logger

_FALLBACK_PATH = "<unmatched>"


class MetricsMiddleware:
    """Pure ASGI middleware — avoids BaseHTTPMiddleware Content-Length bug."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = None
        path = _FALLBACK_PATH
        route = scope.get("route")
        if route:
            path = getattr(route, "path", _FALLBACK_PATH)
        for hname, hvalue in scope.get("headers", []):
            if hname == b":method":
                method = hvalue.decode()
                break

        if METRICS_AVAILABLE:
            http_in_flight.inc()
        start = time.perf_counter()
        status_code = 500

        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message.get("status", 500)
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception as e:
            logger.error(f"metrics middleware: unhandled {e}")
            raise
        finally:
            elapsed = time.perf_counter() - start
            if METRICS_AVAILABLE:
                try:
                    http_requests_total.labels(
                        method=method,
                        path=path,
                        status=str(status_code),
                    ).inc()
                    http_request_duration_seconds.labels(
                        method=method,
                        path=path,
                    ).observe(elapsed)
                finally:
                    http_in_flight.dec()
