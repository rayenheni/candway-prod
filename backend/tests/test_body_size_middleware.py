"""
Tests for BodySizeLimitMiddleware.

The middleware should:
  * Reject JSON bodies over the 1 MB cap with 413.
  * Reject multipart bodies over 25 MB (or the per-endpoint cap).
  * Honour the per-endpoint override (e.g. /qualifications/upload = 25 MB).
  * Allow small bodies through.
  * Be skipped for /uploads, /static, /health.
"""

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test_secret_key_for_jwt_encoding_12345")
os.environ.setdefault("TESTING", "true")


import pytest  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from backend.body_size_middleware import (  # noqa: E402
    BodySizeLimitMiddleware,
    _resolve_limit,
)


def _build_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(BodySizeLimitMiddleware)

    @app.post("/echo")
    async def echo(request_data: dict):
        return {"size": len(str(request_data))}

    @app.post("/qualifications/upload")
    async def quals():
        return {"ok": True}

    @app.get("/uploads/test.pdf")
    async def uploads():
        return {"ok": True}

    @app.get("/health")
    async def health():
        return {"ok": True}

    return app


@pytest.fixture
def client():
    return TestClient(_build_app(), raise_server_exceptions=True)


def test_small_json_passes(client):
    r = client.post("/echo", json={"hello": "world"})
    assert r.status_code == 200


def test_oversized_json_rejected(client):
    big = {"x": "a" * (1_200_000)}  # > 1 MB
    r = client.post("/echo", json=big)
    assert r.status_code == 413
    body = r.json()
    assert "max_bytes" in body
    assert body["max_bytes"] >= 1_000_000


def test_content_length_short_circuit(client):
    # Send a 5 MB blob with an honest Content-Length. The middleware
    # should 413 it without buffering the body.
    big = b"x" * (5 * 1024 * 1024)
    r = client.post(
        "/echo",
        content=big,
        headers={"Content-Type": "application/json"},
    )
    assert r.status_code == 413


def test_qualifications_override_allows_20mb(client):
    # 20 MB < 25 MB cap, so it should pass through to the handler.
    # We send raw bytes because we don't have a real file upload
    # handler here; the middleware just needs to see the body.
    big = b"x" * (20 * 1024 * 1024)
    r = client.post(
        "/qualifications/upload",
        content=big,
        headers={"Content-Type": "multipart/form-data; boundary=xxx"},
    )
    # Either 200 (handler accepted) or 422 (FastAPI couldn't parse
    # multipart shape) — anything but 413.
    assert r.status_code != 413, r.text


def test_qualifications_override_caps_at_25mb(client):
    big = b"x" * (30 * 1024 * 1024)
    r = client.post(
        "/qualifications/upload",
        content=big,
        headers={"Content-Type": "multipart/form-data; boundary=xxx"},
    )
    assert r.status_code == 413


def test_uploads_skipped(client):
    r = client.get("/uploads/test.pdf")
    assert r.status_code == 200


def test_health_skipped(client):
    r = client.get("/health")
    assert r.status_code == 200


def test_resolve_limit_json():
    assert _resolve_limit("/jobs/apply", "application/json") == 1 * 1024 * 1024


def test_resolve_limit_multipart():
    assert (
        _resolve_limit("/jobs/apply", "multipart/form-data; boundary=x")
        == 25 * 1024 * 1024
    )


def test_resolve_limit_qualifications():
    assert (
        _resolve_limit("/qualifications/upload", "multipart/form-data; boundary=x")
        == 25 * 1024 * 1024
    )


def test_resolve_limit_cv():
    assert (
        _resolve_limit("/cv/upload", "multipart/form-data; boundary=x")
        == 25 * 1024 * 1024
    )
