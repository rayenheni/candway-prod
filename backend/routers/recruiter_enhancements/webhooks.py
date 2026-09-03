import ipaddress
import json
import re
import socket
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import desc
from sqlalchemy.orm import Session

from backend.database import User, WebhookIntegration
from backend.dependencies import get_db, require_recruiter
from backend.security import sanitize_content
from backend.tenant import get_current_company_id

router = APIRouter(tags=["Recruiter Enhancements - Webhooks"])


class WebhookCreate(BaseModel):
    name: str
    provider: str
    webhook_url: str
    events_json: List[str]


class WebhookUpdate(BaseModel):
    name: Optional[str] = None
    webhook_url: Optional[str] = None
    events_json: Optional[List[str]] = None
    is_active: Optional[bool] = None


def _mask_webhook_url(url: str) -> str:
    """Mask webhook URL for security"""
    if len(url) > 20:
        return url[:10] + "..." + url[-10:]
    return url


# S1 FIX: prevent SSRF by rejecting private/loopback/link-local IPs
_ALLOWED_SCHEMES = {"https", "http"}
_BLOCKED_HOSTS = re.compile(
    r"^(localhost|127\.|0\.|10\.|172\.(1[6-9]|2[0-9]|3[01])\.|192\.168\.|"
    r"169\.254\.|::1|fc00:|fe80:)",
    re.IGNORECASE,
)


def _validate_webhook_url(url: str) -> None:
    """Raise HTTPException if the URL targets an internal/private resource."""
    from urllib.parse import urlparse

    parsed = urlparse(url)
    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise HTTPException(
            status_code=400,
            detail=f"Webhook URL must use http or https (got '{parsed.scheme}')",
        )
    hostname = parsed.hostname or ""
    if not hostname:
        raise HTTPException(status_code=400, detail="Webhook URL has no hostname")

    # Block obvious private hostnames
    if _BLOCKED_HOSTS.match(hostname):
        raise HTTPException(
            status_code=400,
            detail="Webhook URL must not point to a private or loopback address",
        )

    # Resolve to IP and block private ranges (defence against DNS rebinding)
    try:
        ip_str = socket.gethostbyname(hostname)
        ip = ipaddress.ip_address(ip_str)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            raise HTTPException(
                status_code=400,
                detail="Webhook URL resolves to a private or reserved address",
            )
    except HTTPException:
        raise
    except OSError:
        # DNS resolution failure — let httpx handle the connection error below
        pass


@router.get("/webhooks")
def get_webhooks(
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
    company_id: int = Depends(get_current_company_id),
):
    """Get all webhook integrations"""
    webhooks = (
        db.query(WebhookIntegration)
        .filter(WebhookIntegration.company_id == company_id)
        .order_by(desc(WebhookIntegration.created_at))
        .all()
    )

    return [
        {
            "id": w.id,
            "name": w.name,
            "provider": w.provider,
            "webhook_url": _mask_webhook_url(w.webhook_url),
            "events": json.loads(w.events_json),
            "is_active": w.is_active,
            "last_triggered_at": w.last_triggered_at.isoformat()
            if w.last_triggered_at
            else None,
            "failure_count": w.failure_count,
            "created_at": w.created_at.isoformat(),
        }
        for w in webhooks
    ]


@router.post("/webhooks", status_code=status.HTTP_201_CREATED)
async def create_webhook(
    data: WebhookCreate,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
    company_id: int = Depends(get_current_company_id),
):
    """Create a webhook integration"""
    import httpx

    # S1 FIX: validate URL before making any outbound request
    _validate_webhook_url(data.webhook_url)

    # Test the webhook URL
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                data.webhook_url,
                json={"test": True, "event": "webhook_test"},
                headers={"Content-Type": "application/json"},
            )
            if response.status_code not in (200, 201, 204):
                raise HTTPException(
                    status_code=400,
                    detail=f"Webhook URL returned status {response.status_code}",
                )
    except httpx.RequestError:
        raise HTTPException(status_code=400, detail="Failed to reach webhook URL")

    webhook = WebhookIntegration(
        recruiter_id=recruiter.id,
        company_id=company_id,
        name=sanitize_content(data.name),
        provider=data.provider,
        webhook_url=data.webhook_url,
        events_json=json.dumps(data.events_json),
    )
    db.add(webhook)
    db.commit()
    db.refresh(webhook)

    return {"success": True, "webhook_id": webhook.id}


@router.patch("/webhooks/{webhook_id}")
def update_webhook(
    webhook_id: int,
    data: WebhookUpdate,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
    company_id: int = Depends(get_current_company_id),
):
    """Update a webhook integration"""
    webhook = (
        db.query(WebhookIntegration)
        .filter(
            WebhookIntegration.id == webhook_id,
            WebhookIntegration.company_id == company_id,
        )
        .first()
    )
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")

    if data.name is not None:
        webhook.name = sanitize_content(data.name)
    if data.webhook_url is not None:
        webhook.webhook_url = data.webhook_url
    if data.events_json is not None:
        webhook.events_json = json.dumps(data.events_json)
    if data.is_active is not None:
        webhook.is_active = data.is_active

    db.commit()
    return {"success": True}


@router.delete("/webhooks/{webhook_id}")
def delete_webhook(
    webhook_id: int,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
    company_id: int = Depends(get_current_company_id),
):
    """Delete a webhook integration"""
    webhook = (
        db.query(WebhookIntegration)
        .filter(
            WebhookIntegration.id == webhook_id,
            WebhookIntegration.company_id == company_id,
        )
        .first()
    )
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")

    db.delete(webhook)
    db.commit()
    return {"success": True}
