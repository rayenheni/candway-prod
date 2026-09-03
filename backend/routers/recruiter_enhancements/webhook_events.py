from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import User, WebhookIntegration
from backend.dependencies import get_db, require_recruiter
from backend.logger import logger
from backend.webhook_dispatcher import WEBHOOK_EVENTS, dispatch_webhook

router = APIRouter(tags=["Recruiter Enhancements - Webhook Events"])


@router.get("/webhooks/events")
def get_webhook_events():
    return {"events": WEBHOOK_EVENTS}


@router.post("/webhooks/test-event/{webhook_id}")
async def test_webhook_event(
    webhook_id: int,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    webhook = (
        db.query(WebhookIntegration)
        .filter(
            WebhookIntegration.id == webhook_id,
            WebhookIntegration.recruiter_id == recruiter.id,
            WebhookIntegration.company_id == getattr(recruiter, "_company_id", None),
        )
        .first()
    )
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")

    test_payload = {
        "event": "webhook_test",
        "timestamp": __import__("datetime")
        .datetime.now(__import__("datetime").UTC)
        .isoformat(),
        "data": {
            "message": "This is a test event from Candway",
            "webhook_id": webhook.id,
            "webhook_name": webhook.name,
        },
    }

    try:
        await dispatch_webhook(
            "webhook_test", test_payload, getattr(recruiter, "_company_id", None), db
        )
        logger.info(f"Test event sent to webhook {webhook_id}")
        return {"success": True, "message": "Test event dispatched"}
    except Exception as e:
        logger.error(f"Test event failed for webhook {webhook_id}: {e}")
        raise HTTPException(status_code=500, detail="Webhook test event failed")
