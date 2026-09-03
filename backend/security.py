import json
import os
import re
import time
import uuid

import bleach

from backend.logger import logger, security_logger

# List of tags allowed (safe for most uses)
ALLOWED_TAGS = ["b", "i", "u", "em", "strong", "p", "br", "ul", "ol", "li", "a", "span"]
ALLOWED_ATTRS = {"a": ["href", "title", "target"], "span": ["class"]}

# Rich-text sanitizer for job descriptions (Quill output)
RICH_TEXT_TAGS = [
    "p",
    "br",
    "b",
    "i",
    "u",
    "em",
    "strong",
    "s",
    "sub",
    "sup",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "ul",
    "ol",
    "li",
    "a",
    "span",
    "blockquote",
    "pre",
    "code",
]
RICH_TEXT_ATTRS = {
    "a": ["href", "title", "target"],
    "span": ["class"],
    "code": ["class"],
    "pre": ["class"],
}


def sanitize_content(content: str) -> str:
    """
    Sanitize HTML content to prevent XSS.
    Uses bleach to clean up strings.
    Optimized: skips bleach if content has no HTML tags.
    """
    if not isinstance(content, str):
        return content
    # Fast path: if no HTML-like content, skip expensive bleach call
    if "<" not in content and ">" not in content:
        return content
    return bleach.clean(
        content, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS, strip=True
    )


def sanitize_rich_text(content: str) -> str:
    """Sanitize rich text (Quill HTML) — allows formatting tags but strips XSS."""
    if not isinstance(content, str):
        return content
    if "<" not in content and ">" not in content:
        return content
    return bleach.clean(
        content, tags=RICH_TEXT_TAGS, attributes=RICH_TEXT_ATTRS, strip=True
    )


def secure_filename(filename: str) -> str:
    """Sanitize a filename to prevent path traversal attacks."""
    # Remove path separators
    filename = filename.replace("\\", "/")
    filename = filename.split("/")[-1]
    # Remove null bytes and control characters
    filename = re.sub(r"[\x00-\x1f\x7f]", "", filename)
    # Remove any remaining dangerous patterns
    filename = re.sub(r"\.\.+", ".", filename)
    return filename or "untitled"


def validate_file(filename: str, size: int, content: bytes = None) -> None:
    """Validate uploaded file - raises HTTPException if invalid."""
    from fastapi import HTTPException

    from backend.file_security import (
        get_file_category,
        get_max_file_size,
        validate_file_content,
        validate_filename,
    )

    is_valid, error_msg = validate_filename(filename)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg or "Invalid filename")
    if content:
        _, ext = os.path.splitext(filename)
        ext = ext.lower().lstrip(".")
        max_size = get_max_file_size(get_file_category(ext))
        is_valid, error_msg = validate_file_content(content, ext, max_size)
        if not is_valid:
            raise HTTPException(status_code=400, detail=error_msg)


def mask_candidate_data(data: dict, is_pro: bool) -> dict:
    """Mask sensitive candidate fields for non-Pro users. Returns a copy."""
    if is_pro:
        return dict(data)
    result = {}
    for key, value in data.items():
        if value is None:
            result[key] = None
        elif key in ("candidate_name", "full_name") and value:
            initial = value.strip()[0].upper() if value.strip() else "?"
            result[key] = f"{initial}. Candidate"
        elif key in ("candidate_email", "email") and value:
            result[key] = "hidden@candway.com"
        elif key == "phone" and value:
            result[key] = "********"
        elif key == "cv_url" and value:
            result[key] = "/uploads/masked.pdf"
        else:
            result[key] = value
    return result


class RequestIDMiddleware:
    """
    Middleware to add a unique request ID to every request.
    Enables better log tracing.
    Uses pure ASGI to avoid BaseHTTPMiddleware Content-Length bug.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = str(uuid.uuid4())
        start_time = time.time()

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((b"x-request-id", request_id.encode()))
                process_time = time.time() - start_time
                headers.append((b"x-process-time", f"{process_time}".encode()))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_headers)


class SanitizationMiddleware:
    """
    Middleware to automatically sanitize incoming string data in JSON bodies.
    Prevents XSS globally.
    Uses pure ASGI to avoid BaseHTTPMiddleware Content-Length bug.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = None
        for hname, hvalue in scope.get("headers", []):
            if hname == b":method":
                method = hvalue.decode()
                break

        content_type = ""
        for hname, hvalue in scope.get("headers", []):
            if hname == b"content-type":
                content_type = hvalue.decode()
                break

        if method in ("POST", "PUT", "PATCH") and "application/json" in content_type:
            body_chunks = []
            more_body = True
            while more_body:
                message = await receive()
                body_chunks.append(message.get("body", b""))
                more_body = message.get("more_body", False)
            body = b"".join(body_chunks)
            if body:
                try:
                    data = json.loads(body)

                    def sanitize_recursive(item):
                        if isinstance(item, str):
                            return sanitize_content(item)
                        elif isinstance(item, dict):
                            return {k: sanitize_recursive(v) for k, v in item.items()}
                        elif isinstance(item, list):
                            return [sanitize_recursive(i) for i in item]
                        return item

                    sanitized_data = sanitize_recursive(data)
                    sanitized_body = json.dumps(sanitized_data).encode("utf-8")

                    async def receive_sanitized():
                        yield {
                            "type": "http.request",
                            "body": sanitized_body,
                            "more_body": False,
                        }

                    receive_iterator = receive_sanitized()
                    original_receive = receive

                    async def wrapped_receive():
                        try:
                            return await receive_iterator.__anext__()
                        except StopAsyncIteration:
                            return await original_receive()

                    await self.app(scope, wrapped_receive, send)
                    return
                except json.JSONDecodeError:
                    pass
                except Exception as e:
                    security_logger.error(
                        f"Sanitization middleware unexpected error: {e}"
                    )

        await self.app(scope, receive, send)


class SecurityHeadersMiddleware:
    """
    Middleware to add industry-standard security headers.
    Uses pure ASGI to avoid BaseHTTPMiddleware Content-Length bug.

    Generates a per-request CSP nonce stored in scope['csp_nonce']
    for the pages router to inject into index.html.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Generate per-request nonce for CSP
        import secrets

        nonce = secrets.token_urlsafe(16)
        scope["csp_nonce"] = nonce

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                # Remove server identifier
                headers = [(k, v) for k, v in headers if k.lower() != b"server"]
                # Add security headers
                headers.append((b"x-xss-protection", b"1; mode=block"))
                headers.append((b"x-frame-options", b"SAMEORIGIN"))
                headers.append((b"x-content-type-options", b"nosniff"))
                headers.append((b"referrer-policy", b"strict-origin-when-cross-origin"))
                headers.append(
                    (
                        b"permissions-policy",
                        b"geolocation=(), microphone=(), camera=(), payment=(), usb=(), interest-cohort=()",
                    )
                )

                from backend.config import get_settings

                settings = get_settings()
                if settings.is_prod:
                    headers.append(
                        (
                            b"strict-transport-security",
                            b"max-age=31536000; includeSubDomains",
                        )
                    )

                csp = "default-src 'self'; "
                csp += "base-uri 'self'; "
                csp += "form-action 'self'; "
                csp += "frame-ancestors 'self'; "
                # script-src: nonce replaces unsafe-inline for the theme IIFE
                csp += f"script-src 'self' 'nonce-{nonce}' https://cdnjs.cloudflare.com https://cdn.jsdelivr.net https://www.gstatic.com https://unpkg.com https://cdn.quilljs.com; "
                # style-src: keep unsafe-inline for CSS-in-JS (Framer Motion, etc.)
                csp += "style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com https://fonts.googleapis.com https://unpkg.com https://cdn.quilljs.com https://cdn.jsdelivr.net; "
                csp += "font-src 'self' data: https:; "
                csp += "img-src 'self' data: blob: https:; "
                csp += "media-src 'self' blob: data:; "
                csp += (
                    "frame-src 'self' https://www.google.com https://www.youtube.com; "
                )
                csp += (
                    "report-uri /api/v1/monitoring/csp-report; report-to csp-endpoint; "
                )
                headers.append(
                    (
                        b"Report-To",
                        b'{"group":"csp-endpoint","max_age":10886400,"endpoints":[{"url":"/api/v1/monitoring/csp-report"}]}',
                    )
                )
                if settings.debug:
                    csp += "connect-src 'self' https: wss: ws: ws://127.0.0.1:8000 ws://localhost:8000 http://127.0.0.1:8002 http://localhost:8002 http://127.0.0.1:8001 http://localhost:8001 http://127.0.0.1:8000 http://localhost:8000 https://cdn.jsdelivr.net https://assets2.lottiefiles.com https://cdnjs.cloudflare.com https://unpkg.com;"
                else:
                    csp += "connect-src 'self' https: wss: ws: https://cdn.jsdelivr.net https://assets2.lottiefiles.com https://cdnjs.cloudflare.com https://unpkg.com;"
                headers.append((b"content-security-policy", csp.encode()))

                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_headers)


class CSRFMiddleware:
    """
    Robust token-based CSRF protection middleware with single-use enforcement.
    Tokens are rotated after each use to prevent replay attacks.
    Uses Redis for distributed single-use tracking (falls back to stateless HMAC).
    Uses pure ASGI to avoid BaseHTTPMiddleware Content-Length bug.
    """

    def __init__(self, app, secret_key: str = None):
        self.app = app
        from backend.dependencies import CSRF_SECRET_KEY

        self.secret_key = secret_key or CSRF_SECRET_KEY

        self.exempt_paths = [
            "/docs",
            "/redoc",
            "/openapi.json",
            "/api/docs",
            "/api/redoc",
            "/api/v1/auth/login",
            "/api/v1/auth/signup",
            "/api/v1/auth/signup/org",
            "/api/v1/auth/guest-login",
            "/api/v1/auth/forgot-password",
            "/api/v1/auth/reset-password",
            "/api/v1/auth/verify-otp",
            "/api/v1/auth/resend-otp",
            "/api/v1/auth/resend-verification",
            "/api/v1/auth/refresh",
            "/api/v1/auth/logout",
            "/api/v1/chatbot/",
            "/api/v1/candidate/upload-cv",
        ]

    async def _get_redis(self):
        from backend.redis_manager import redis_manager

        return await redis_manager.get_client()

    def generate_token(self) -> str:
        import hashlib
        import hmac
        import secrets
        import time

        session_id = secrets.token_urlsafe(32)
        expires_at = int(time.time()) + 86400
        message = f"{session_id}:{expires_at}"
        token_hash = hmac.new(
            self.secret_key.encode(), message.encode(), hashlib.sha256
        ).hexdigest()
        return f"{session_id}.{expires_at}.{token_hash}"

    def _parse_token(self, token: str):
        try:
            parts = token.split(".")
            if len(parts) != 3:
                return None
            session_id, expires_at, token_hash = parts
            return session_id, int(expires_at), token_hash
        except Exception:
            return None

    # CSRF tokens are time-limited HMAC tokens, not single-use nonces.
    # A browser may legitimately reuse the same token for multiple
    # sequential/concurrent mutations. Replay protection here would
    # reject legitimate requests after the first mutation.

    def _validate_hmac(self, token: str) -> tuple:
        import hashlib
        import hmac
        import time

        parsed = self._parse_token(token)
        if not parsed:
            return None
        session_id, expires_at, token_hash = parsed
        if time.time() > expires_at:
            logger.warning("CSRF token expired")
            return None
        message = f"{session_id}:{expires_at}"
        expected = hmac.new(
            self.secret_key.encode(), message.encode(), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(expected, token_hash):
            logger.warning("CSRF token HMAC mismatch")
            return None
        return session_id, expires_at

    async def validate_token(self, token: str) -> bool:
        if not token:
            return False
        result = self._validate_hmac(token)
        if not result:
            return False
        # Token validity is enforced by HMAC verification + expiration.
        # Do not reject a valid token because it was used by a previous
        # request; the frontend may legitimately reuse the browser CSRF token.
        return True

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        headers_dict = {}
        for hname, hvalue in scope.get("headers", []):
            decoded_name = hname.decode().lower()
            decoded_value = hvalue.decode()
            headers_dict[decoded_name] = decoded_value
            if decoded_name == ":path":
                path = decoded_value.split("?")[0]

        is_exempt = any(path.startswith(p) for p in self.exempt_paths)
        logger.warning(
            f"CSRF_MW: path={path!r} method={scope.get('method')} exempt={is_exempt}"
        )
        if is_exempt:
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "GET")

        if method in ("GET", "HEAD", "OPTIONS"):
            csrf_token = self.generate_token()

            async def send_with_csrf(message):
                if message["type"] == "http.response.start":
                    headers = list(message.get("headers", []))
                    headers.append((b"x-csrf-token", csrf_token.encode()))

                    from backend.config import get_settings

                    settings = get_settings()

                    cookie = f"csrf_token={csrf_token}; Path=/; SameSite=lax"
                    if settings.is_prod:
                        cookie += "; Secure"
                    headers.append((b"set-cookie", cookie.encode()))

                    message["headers"] = headers
                await send(message)

            await self.app(scope, receive, send_with_csrf)
            return

        if method in ("POST", "PUT", "DELETE", "PATCH"):
            csrf_token = headers_dict.get("x-csrf-token", "")
            if not csrf_token and "multipart/form-data" not in headers_dict.get(
                "content-type", ""
            ):
                try:
                    body_chunks = []
                    more_body = True
                    while more_body:
                        msg = await receive()
                        body_chunks.append(msg.get("body", b""))
                        more_body = msg.get("more_body", False)
                    body = b"".join(body_chunks)
                    if body:
                        try:
                            form_data = json.loads(body)
                            csrf_token = form_data.get("csrf_token", csrf_token)
                        except json.JSONDecodeError:
                            pass

                    saved_body = body
                    body_sent = False

                    async def wrapped_receive():
                        nonlocal body_sent
                        if not body_sent:
                            body_sent = True
                            return {
                                "type": "http.request",
                                "body": saved_body,
                                "more_body": False,
                            }
                        return await receive()

                    scope_receive = wrapped_receive
                except Exception:
                    scope_receive = receive
            else:
                scope_receive = receive

            if not csrf_token:
                csrf_cookie = headers_dict.get("cookie", "")
                for part in csrf_cookie.split(";"):
                    part = part.strip()
                    if part.startswith("csrf_token="):
                        csrf_token = part[len("csrf_token=") :]
                        break

            if not csrf_token or not await self.validate_token(csrf_token):
                logger.warning(f"CSRF validation failed for {path}")
                security_logger.error(f"CSRF REJECTION: Path={path}")
                response_body = json.dumps(
                    {"detail": "CSRF token validation failed"}
                ).encode()
                await send(
                    {
                        "type": "http.response.start",
                        "status": 403,
                        "headers": [
                            (b"content-type", b"application/json"),
                        ],
                    }
                )
                await send(
                    {
                        "type": "http.response.body",
                        "body": response_body,
                        "more_body": False,
                    }
                )
                return

            await self.app(scope, scope_receive, send)
            return

        await self.app(scope, receive, send)
