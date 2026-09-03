import hashlib
import hmac
import json
import os

import httpx

from backend.config import get_settings
from backend.database import SessionLocal, WebhookIntegration
from backend.logger import logger

WEBHOOK_EVENTS = [
    "application_created",
    "application_status_changed",
    "interview_scheduled",
    "interview_completed",
    "offer_sent",
    "offer_responded",
    "candidate_rated",
    "comment_added",
]

MAX_CONSECUTIVE_FAILURES = 5


def _compute_signature(payload: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


async def dispatch_webhook(event_type: str, payload: dict, company_id: int):
    db = SessionLocal()
    try:
        webhooks = (
            db.query(WebhookIntegration)
            .filter(
                WebhookIntegration.company_id == company_id,
                WebhookIntegration.is_active,
            )
            .all()
        )

        if not webhooks:
            return

        settings = get_settings()
        signing_secret = settings.webhook_signing_secret or os.environ.get(
            "WEBHOOK_SIGNING_SECRET"
        )
        if not signing_secret:
            logger.critical("WEBHOOK_SIGNING_SECRET not set — webhooks disabled")
            return
        json_payload = json.dumps(payload, default=str).encode()
        signature = _compute_signature(json_payload, signing_secret)

        async with httpx.AsyncClient(timeout=10.0) as client:
            for webhook in webhooks:
                try:
                    events = json.loads(webhook.events_json)
                    if event_type not in events:
                        continue

                    response = await client.post(
                        webhook.webhook_url,
                        content=json_payload,
                        headers={
                            "Content-Type": "application/json",
                            "X-Candway-Event": event_type,
                            "X-Candway-Signature": signature,
                            "X-Candway-Timestamp": str(__import__("time").time()),
                        },
                    )

                    if response.status_code in (200, 201, 204):
                        webhook.last_triggered_at = (
                            __import__("datetime")
                            .datetime.now(__import__("datetime").UTC)
                            .replace(tzinfo=None)
                        )
                        webhook.failure_count = 0
                        logger.info(
                            f"Webhook {webhook.id} ({webhook.name}) dispatched "
                            f"{event_type} to {webhook.webhook_url}"
                        )
                    else:
                        webhook.failure_count = (webhook.failure_count or 0) + 1
                        logger.warning(
                            f"Webhook {webhook.id} returned {response.status_code} "
                            f"for {event_type}"
                        )
                        if webhook.failure_count >= MAX_CONSECUTIVE_FAILURES:
                            webhook.is_active = False
                            logger.warning(
                                f"Webhook {webhook.id} deactivated after "
                                f"{MAX_CONSECUTIVE_FAILURES} consecutive failures"
                            )

                except httpx.RequestError as e:
                    webhook.failure_count = (webhook.failure_count or 0) + 1
                    logger.error(
                        f"Webhook {webhook.id} request failed for {event_type}: {e}"
                    )
                    if webhook.failure_count >= MAX_CONSECUTIVE_FAILURES:
                        webhook.is_active = False
                        logger.warning(
                            f"Webhook {webhook.id} deactivated after "
                            f"{MAX_CONSECUTIVE_FAILURES} consecutive failures"
                        )
                except Exception as e:
                    logger.error(
                        f"Webhook {webhook.id} unexpected error for {event_type}: {e}"
                    )

        db.commit()
    finally:
        db.close()
