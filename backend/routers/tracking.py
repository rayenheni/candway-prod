import base64
import hashlib
import hmac
import os
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.database import Application
from backend.dependencies import get_db

router = APIRouter(prefix="/track", tags=["tracking"])

TRACKING_PIXEL_PATH = os.path.join(os.getcwd(), "assets", "pixel.png")

_rate_limit_buckets: dict[str, list[float]] = {}
_RATE_LIMIT = 30
_RATE_WINDOW = 60


def _rate_limit(request: Request):
    ip = request.client.host if request.client else "unknown"
    now = datetime.now(UTC).timestamp()
    bucket = _rate_limit_buckets.setdefault(ip, [])
    bucket[:] = [t for t in bucket if t > now - _RATE_WINDOW]
    if len(bucket) >= _RATE_LIMIT:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    bucket.append(now)


def make_tracking_token(app_id: int) -> str:
    """Generate a signed tracking token for an application."""
    secret = get_settings().secret_key
    sig = hmac.new(secret.encode(), str(app_id).encode(), hashlib.sha256).hexdigest()[
        :8
    ]
    payload = f"{app_id}:{sig}"
    return base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")


def _resolve_tracking_token(token: str) -> int:
    """Verify a tracking token and return the application id."""
    try:
        padding = 4 - len(token) % 4 if len(token) % 4 else 0
        decoded = base64.urlsafe_b64decode((token + "=" * padding).encode()).decode()
        app_id_str, signature = decoded.rsplit(":", 1)
        app_id = int(app_id_str)
    except (ValueError, Exception):
        raise HTTPException(status_code=404, detail="Tracking link not found")

    secret = get_settings().secret_key
    expected = hmac.new(
        secret.encode(), str(app_id).encode(), hashlib.sha256
    ).hexdigest()[:8]
    if not hmac.compare_digest(signature, expected):
        raise HTTPException(status_code=404, detail="Tracking link not found")
    return app_id


@router.get("/open/{tracking_token}")
def track_open(
    tracking_token: str,
    request: Request,
    db: Session = Depends(get_db),
):
    _rate_limit(request)
    app_id = _resolve_tracking_token(tracking_token)
    app = db.query(Application).filter(Application.id == app_id).first()
    if app and not app.opened_at:
        app.opened_at = datetime.now(UTC)
        db.commit()

    if os.path.exists(TRACKING_PIXEL_PATH):
        return FileResponse(TRACKING_PIXEL_PATH, media_type="image/png")

    return Response(
        content=b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82",
        media_type="image/png",
    )


@router.get("/click/{tracking_token}")
def track_click(
    tracking_token: str,
    request: Request,
    token: str = None,
    db: Session = Depends(get_db),
):
    _rate_limit(request)
    app_id = _resolve_tracking_token(tracking_token)
    app = db.query(Application).filter(Application.id == app_id).first()
    if app and not app.clicked_at:
        app.clicked_at = datetime.now(UTC)
        db.commit()

    url = f"{get_settings().frontend_url}/auth/interview-access?app_id={app_id}"
    if token:
        url += f"&token={token}"

    email = request.query_params.get("email") or (app.email if app else None)
    if email:
        url += f"&email={email}"

    return RedirectResponse(url=url)
