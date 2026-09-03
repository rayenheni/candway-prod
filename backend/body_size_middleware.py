"""
Body-size limits for incoming requests.

The audit noted that the platform had no global body-size cap, meaning
a candidate could POST a 200 MB blob to ``/qualifications/upload`` and
exhaust disk. The CV upload path already enforced a 10 MB cap in-line,
but that lived in the route handler — easy to forget on the next
upload endpoint, and not consistent with how Nginx/Cloudflare would
be configured in production.

This middleware enforces:

  * 1 MB hard cap on JSON / text bodies (most endpoints)
  * 25 MB hard cap on multipart bodies (file uploads)
  * 1 MB on URLs themselves (defence-in-depth against billion-laughs
    query strings)

Bodies that exceed the cap are rejected with ``413 Payload Too Large``
before the route handler runs. ``Content-Length`` is honoured when
present so we can short-circuit cheaply; for chunked uploads we fall
back to a streaming byte counter.
"""

import json
import logging
import os

logger = logging.getLogger(__name__)

DEFAULT_JSON_LIMIT_BYTES = 1 * 1024 * 1024
DEFAULT_MULTIPART_LIMIT_BYTES = 25 * 1024 * 1024
DEFAULT_URL_LIMIT_BYTES = 1 * 1024 * 1024

_PATH_OVERRIDES = {
    "/qualifications/upload": 25 * 1024 * 1024,
    "/cv/upload": 25 * 1024 * 1024,
    "/cv/analyze": 25 * 1024 * 1024,
    "/ai-interview/upload": 50 * 1024 * 1024,
    "/recruiter/jobs/bulk": 5 * 1024 * 1024,
    "/admin/import": 25 * 1024 * 1024,
}

_PATH_SKIP = {
    "/uploads",
    "/static",
    "/static-files",
    "/health",
    "/readyz",
    "/livez",
}


def _resolve_limit(path: str, content_type: str | None) -> int:
    for prefix, limit in _PATH_OVERRIDES.items():
        if path.startswith(prefix):
            env_key = (
                f"CANDWAY_BODY_LIMIT_{prefix.strip('/').replace('/', '_').upper()}"
            )
            return int(os.getenv(env_key, limit))
    ct = (content_type or "").lower()
    if ct.startswith("multipart/"):
        return DEFAULT_MULTIPART_LIMIT_BYTES
    if ct.startswith("application/json") or ct.startswith("text/"):
        return DEFAULT_JSON_LIMIT_BYTES
    return DEFAULT_JSON_LIMIT_BYTES


def _json_response(
    status_code: int, body: dict, headers: dict | None = None
) -> tuple[list, bytes]:
    """Build ASGI headers and body for a JSON error response."""
    body_bytes = json.dumps(body).encode("utf-8")
    hdrs = [
        (b"content-type", b"application/json"),
        (b"content-length", str(len(body_bytes)).encode("latin-1")),
    ]
    if headers:
        for k, v in headers.items():
            hdrs.append(
                (
                    k.encode("latin-1") if isinstance(k, str) else k,
                    v.encode("latin-1") if isinstance(v, str) else v,
                )
            )
    return hdrs, body_bytes


class _BodyTooLarge(Exception):
    def __init__(self, limit: int):
        self.limit = limit


class BodySizeLimitMiddleware:
    """Pure ASGI middleware — avoids BaseHTTPMiddleware Content-Length bug."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        for skip in _PATH_SKIP:
            if path == skip or path.startswith(skip + "/"):
                await self.app(scope, receive, send)
                return

        method = None
        content_type = ""
        content_length_hdr = None
        for hname, hvalue in scope.get("headers", []):
            if hname == b":method":
                method = hvalue.decode()
            elif hname == b"content-type":
                content_type = hvalue.decode()
            elif hname == b"content-length":
                content_length_hdr = hvalue.decode()

        query = scope.get("query_string", b"").decode()
        url_length = len(path) + len(query)

        # URL length check
        if url_length > DEFAULT_URL_LIMIT_BYTES:
            logger.warning(f"[BODY-LIMIT] URL too long: {url_length} bytes for {path}")
            hdrs, body = _json_response(414, {"detail": "URL too long"})
            await send({"type": "http.response.start", "status": 414, "headers": hdrs})
            await send({"type": "http.response.body", "body": body, "more_body": False})
            return

        limit = _resolve_limit(path, content_type)

        # GET/DELETE/HEAD body check
        if method in ("GET", "HEAD", "DELETE", "OPTIONS") and content_length_hdr:
            try:
                cl = int(content_length_hdr)
            except ValueError:
                cl = 0
            if cl > DEFAULT_JSON_LIMIT_BYTES:
                logger.warning(
                    f"[BODY-LIMIT] {method} body too large: {cl} bytes for {path}"
                )
                hdrs, body = _json_response(
                    413, {"detail": "Payload Too Large"}, {"connection": "close"}
                )
                await send(
                    {"type": "http.response.start", "status": 413, "headers": hdrs}
                )
                await send(
                    {"type": "http.response.body", "body": body, "more_body": False}
                )
                return

        # Content-Length short-circuit
        if content_length_hdr:
            try:
                cl = int(content_length_hdr)
            except ValueError:
                cl = 0
            if cl > limit:
                logger.warning(
                    f"[BODY-LIMIT] {method} {path} body {cl} bytes > {limit} cap"
                )
                hdrs, body = _json_response(
                    413,
                    {
                        "detail": f"Payload Too Large. Max {limit} bytes for this endpoint.",
                        "max_bytes": limit,
                    },
                    {"connection": "close"},
                )
                await send(
                    {"type": "http.response.start", "status": 413, "headers": hdrs}
                )
                await send(
                    {"type": "http.response.body", "body": body, "more_body": False}
                )
                return

        # Streaming byte count for chunked/unknown-length bodies
        if method in ("POST", "PUT", "PATCH"):
            ct = (content_type or "").lower()
            if (
                ct.startswith("multipart/")
                or ct.startswith("application/json")
                or ct.startswith("text/")
            ):
                received = 0
                over_limit = False

                async def counting_receive():
                    nonlocal received, over_limit
                    msg = await receive()
                    if msg["type"] == "http.request":
                        chunk = msg.get("body", b"") or b""
                        received += len(chunk)
                        if received > limit:
                            raise _BodyTooLarge(limit)
                    return msg

                try:
                    await self.app(scope, counting_receive, send)
                except _BodyTooLarge as exc:
                    logger.warning(
                        f"[BODY-LIMIT] {method} {path} body exceeds {exc.limit} bytes (streamed)"
                    )
                    hdrs, body = _json_response(
                        413,
                        {
                            "detail": f"Payload Too Large. Max {exc.limit} bytes for this endpoint.",
                            "max_bytes": exc.limit,
                        },
                        {"connection": "close"},
                    )
                    # Drain remaining body
                    try:
                        while True:
                            msg = await receive()
                            if not msg.get("more_body", False):
                                break
                    except Exception:
                        pass
                    await send(
                        {"type": "http.response.start", "status": 413, "headers": hdrs}
                    )
                    await send(
                        {"type": "http.response.body", "body": body, "more_body": False}
                    )
                return

        await self.app(scope, receive, send)
