"""
Unsubscribe endpoint for email compliance (HMAC-signed tokens)
"""

import base64
import hashlib
import hmac
import html
from datetime import UTC, datetime
from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.database import Application
from backend.dependencies import get_db

router = APIRouter(prefix="/unsubscribe", tags=["unsubscribe"])


def _verify_unsubscribe_token(token: str) -> Optional[int]:
    """Verify HMAC-signed unsubscribe token and return app_id or None."""
    try:
        payload = base64.urlsafe_b64decode(token + "==").decode()
        app_id_str, expiry_str, sig = payload.rsplit(":", 2)
        app_id = int(app_id_str)
        expiry = int(expiry_str)
        if datetime.now(UTC).timestamp() > expiry:
            return None
        secret = get_settings().secret_key
        msg = f"{app_id}:{expiry}".encode()
        expected = hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()[:16]
        if not hmac.compare_digest(sig, expected):
            return None
        return app_id
    except Exception:
        return None


@router.get("/{token}")
async def unsubscribe(token: str, db: Session = Depends(get_db)):
    """
    Unsubscribe endpoint for CAN-SPAM / GDPR compliance.
    Accepts HMAC-signed token instead of raw app_id.
    """
    app_id = _verify_unsubscribe_token(token)
    if app_id is None:
        return HTMLResponse(
            content="""
        <html>
            <head><title>Unsubscribe</title></head>
            <body style="font-family: sans-serif; max-width: 600px; margin: 50px auto; padding: 20px;">
                <h1 style="color: #dc2626;">Invalid or Expired Link</h1>
                <p>The unsubscribe link is invalid or has expired.</p>
            </body>
        </html>
        """,
            status_code=404,
        )

    app = db.query(Application).filter(Application.id == app_id).first()

    if not app:
        return HTMLResponse(
            content="""
        <html>
            <head><title>Unsubscribe</title></head>
            <body style="font-family: sans-serif; max-width: 600px; margin: 50px auto; padding: 20px;">
                <h1 style="color: #dc2626;">Application Not Found</h1>
                <p>The unsubscribe link is invalid or has expired.</p>
            </body>
        </html>
        """,
            status_code=404,
        )

    # Mark as unsubscribed
    app.status = "withdrawn"
    db.commit()

    safe_email = html.escape(app.email or "")
    return HTMLResponse(
        content=f"""
    <html>
        <head><title>Unsubscribed Successfully</title></head>
        <body style="font-family: sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; text-align: center;">
            <h1 style="color: #10b981;">✓ Unsubscribed Successfully</h1>
            <p>You have been unsubscribed from emails regarding this job opportunity.</p>
            <p style="color: #6b7280; font-size: 14px; margin-top: 40px;">
                Email: {safe_email}<br>
                You will no longer receive emails about this application.
            </p>
        </body>
    </html>
    """
    )
