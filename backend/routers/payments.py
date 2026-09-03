"""P1-01 FIX: unified payments router.

Routes:

* ``POST /payments/stripe/create-intent`` — create a Stripe
  PaymentIntent and a ``Transaction`` row in ``pending`` state.
* ``POST /payments/stripe/webhook`` — handle Stripe webhook events
  (``payment_intent.succeeded`` / ``payment_intent.payment_failed``)
  with idempotency so duplicate webhook deliveries do not
  double-apply the candidate's subscription.
* ``POST /payments/konnect/create`` — Konnect checkout-session
  creator that wraps :class:`backend.konnect_service.KonnectService`
  with an idempotency-key.
* ``POST /payments/{provider}/webhook`` — generic webhook
  dispatcher used by the Konnect callback in
  ``routers/courses.py`` (kept there to preserve the existing
  route shape and avoid breaking production).

All endpoints are gated by a single ``require_user`` dependency
plus the env-flag ``CANDWAY_PAYMENTS_ENABLED``. When payments are
disabled, the endpoints return 503 so the candidate is forced
onto the manual-receipt flow during a phased rollout.
"""

import logging
import os
import uuid
from datetime import UTC, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import (
    AuditLog,
    SubscriptionPlan,
    Transaction,
    User,
)
from backend.dependencies import get_current_user, get_db
from backend.routers.admin.invoices import _create_invoice_internal

logger = logging.getLogger("candway_app.payments")
router = APIRouter(prefix="/payments", tags=["payments"])


def _payments_enabled() -> bool:
    return os.getenv("CANDWAY_PAYMENTS_ENABLED", "0") == "1"


# ---------------------------------------------------------------------------
# Stripe
# ---------------------------------------------------------------------------

try:
    import stripe  # type: ignore

    STRIPE_AVAILABLE = True
except ImportError:  # pragma: no cover - optional
    STRIPE_AVAILABLE = False


def _stripe_secret() -> Optional[str]:
    return os.getenv("STRIPE_SECRET_KEY")


class StripeIntentRequest(BaseModel):
    plan_id: int
    idempotency_key: Optional[str] = None


@router.post("/stripe/create-intent")
def stripe_create_intent(
    body: StripeIntentRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a Stripe PaymentIntent for a candidate subscription
    plan. The Transaction is written in ``pending`` state and
    updated to ``succeeded`` / ``failed`` by the webhook."""
    if not _payments_enabled():
        raise HTTPException(
            status_code=503,
            detail="Online payments are not enabled. Use the manual receipt flow.",
        )
    if not STRIPE_AVAILABLE or not _stripe_secret():
        raise HTTPException(
            status_code=503,
            detail="Stripe is not configured. Set STRIPE_SECRET_KEY.",
        )

    plan = (
        db.query(SubscriptionPlan).filter(SubscriptionPlan.id == body.plan_id).first()
    )
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    # Idempotency: same key from the same user reuses the existing
    # intent instead of double-charging.
    if body.idempotency_key:
        existing = (
            db.query(Transaction)
            .filter(
                Transaction.user_id == current_user.id,
                Transaction.idempotency_key == body.idempotency_key,
            )
            .first()
        )
        if existing:
            return {
                "transaction_id": existing.id,
                "status": existing.status,
                "client_secret": getattr(existing, "stripe_client_secret", None),
                "idempotent": True,
            }

    stripe.api_key = _stripe_secret()
    try:
        intent = stripe.PaymentIntent.create(
            amount=int(plan.price_monthly * 100),  # cents
            currency="usd",
            automatic_payment_methods={"enabled": True},
            metadata={
                "user_id": current_user.id,
                "plan_slug": plan.slug,
                "plan_id": plan.id,
            },
            idempotency_key=body.idempotency_key or str(uuid.uuid4()),
        )
    except Exception as e:  # noqa: BLE001
        logger.error(f"[STRIPE] PaymentIntent failed: {e}")
        raise HTTPException(status_code=502, detail="Stripe error")

    tx = Transaction(
        user_id=current_user.id,
        amount=float(plan.price_monthly),
        currency="USD",
        status="pending",
        description=f"Stripe upgrade to {plan.name}",
        proof_url=intent.id,  # the PaymentIntent id doubles as proof
        idempotency_key=body.idempotency_key,
        amount_ttc=float(plan.price_monthly),
    )
    db.add(tx)
    db.add(
        AuditLog(
            user_id=current_user.id,
            action="stripe_intent_created",
            target_id=str(tx.id),
            details=f"plan={plan.slug} intent={intent.id}",
            ip_address=request.client.host,
        )
    )
    db.commit()

    return {
        "transaction_id": tx.id,
        "client_secret": intent.client_secret,
        "status": "pending",
    }


@router.post("/stripe/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """Handle Stripe webhook events. Idempotent on the
    ``event.id`` (the Stripe-Signature header is verified when
    the webhook secret is configured)."""
    if not _payments_enabled() or not STRIPE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Stripe disabled")

    raw = await request.body()
    sig = request.headers.get("stripe-signature", "")
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")

    if webhook_secret:
        try:
            event = stripe.Webhook.construct_event(raw, sig, webhook_secret)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[STRIPE] webhook signature failed: {e}")
            raise HTTPException(status_code=400, detail="bad signature")
    else:
        logger.critical(
            "[STRIPE] STRIPE_WEBHOOK_SECRET not set — rejecting unauthenticated webhook"
        )
        raise HTTPException(status_code=503, detail="stripe webhook not configured")

    event_id = event.get("id") or event.get("data", {}).get("object", {}).get("id")
    event_type = event.get("type", "")

    # Idempotency: refuse to process the same Stripe event twice.
    if event_id:
        replay = (
            db.query(Transaction)
            .filter(Transaction.proof_url == f"stripe_evt:{event_id}")
            .first()
        )
        if replay:
            return {"status": "processed", "idempotent": True}

    intent = event.get("data", {}).get("object", {})
    intent_id = intent.get("id")
    if not intent_id:
        return {"status": "ignored", "reason": "no intent id"}

    tx = db.query(Transaction).filter(Transaction.proof_url == intent_id).first()
    if not tx:
        return {"status": "ignored", "reason": "transaction not found"}

    # Lock the row.
    tx = db.query(Transaction).filter(Transaction.id == tx.id).with_for_update().first()
    if not tx:
        return {"status": "ignored", "reason": "transaction vanished"}

    if event_type == "payment_intent.succeeded":
        if tx.status == "succeeded":
            return {"status": "processed", "idempotent": True}
        tx.status = "succeeded"
        tx.approved_at = datetime.now(UTC)
        # Bump user tier to pro for the year.
        plan_slug = (intent.get("metadata") or {}).get("plan_slug")
        if plan_slug:
            user = db.query(User).filter(User.id == tx.user_id).first()
            plan = (
                db.query(SubscriptionPlan)
                .filter(SubscriptionPlan.slug == plan_slug)
                .first()
            )
            if user and plan:
                from backend.models.evaluation.profile import RecruiterProfile

                rp = (
                    db.query(RecruiterProfile)
                    .filter(RecruiterProfile.user_id == user.id)
                    .first()
                )
                if rp:
                    rp.tier = "pro"
                    rp.subscription_status = "active"
                    rp.subscription_end = datetime.now(UTC).replace(
                        year=datetime.now(UTC).year + 1
                    )
                    rp.current_plan_id = plan.id
                    rp.subscription_plan = plan.slug
        tx.proof_url = f"stripe_evt:{event_id}"
        db.add(
            AuditLog(
                user_id=tx.user_id,
                action="stripe_payment_succeeded",
                target_id=str(tx.id),
                details=f"event={event_id}",
            )
        )
        db.commit()
        try:
            _create_invoice_internal(db, tx.user_id, tx.amount, tx.id, company_id=tx.company_id)
        except Exception as e:  # noqa: BLE001
            logger.error(f"[STRIPE] invoice failed: {e}")
        return {"status": "processed"}

    if event_type == "payment_intent.payment_failed":
        if tx.status == "Failed":
            return {"status": "processed", "idempotent": True}
        tx.status = "Failed"
        tx.rejected_at = datetime.now(UTC)
        tx.proof_url = f"stripe_evt:{event_id}"
        db.commit()
        return {"status": "processed"}

    return {"status": "ignored", "reason": f"event_type={event_type}"}


# ---------------------------------------------------------------------------
# Konnect passthrough
# ---------------------------------------------------------------------------


class KonnectCreateRequest(BaseModel):
    plan_id: int
    idempotency_key: Optional[str] = None


@router.post("/konnect/create")
def konnect_create(
    body: KonnectCreateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not _payments_enabled():
        raise HTTPException(
            status_code=503,
            detail="Online payments are not enabled. Use the manual receipt flow.",
        )

    if body.idempotency_key:
        existing = (
            db.query(Transaction)
            .filter(
                Transaction.user_id == current_user.id,
                Transaction.idempotency_key == body.idempotency_key,
            )
            .first()
        )
        if existing:
            return {
                "transaction_id": existing.id,
                "status": existing.status,
                "idempotent": True,
            }

    plan = (
        db.query(SubscriptionPlan).filter(SubscriptionPlan.id == body.plan_id).first()
    )
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    from backend.konnect_service import konnect_service

    payment = konnect_service.init_payment(
        amount=float(plan.price_monthly),
        currency="TND",
        user_email=current_user.email,
    )
    if not payment or "payUrl" not in payment:
        raise HTTPException(
            status_code=502,
            detail="Konnect did not return a payment URL",
        )

    tx = Transaction(
        user_id=current_user.id,
        amount=float(plan.price_monthly),
        currency="TND",
        status="pending",
        description=f"Konnect upgrade to {plan.name}",
        proof_url=payment.get("paymentRef") or payment.get("payUrl"),
        idempotency_key=body.idempotency_key,
        amount_ttc=float(plan.price_monthly),
    )
    db.add(tx)
    db.add(
        AuditLog(
            user_id=current_user.id,
            action="konnect_payment_created",
            target_id=str(tx.id),
            details=f"plan={plan.slug}",
            ip_address=request.client.host,
        )
    )
    db.commit()

    return {
        "transaction_id": tx.id,
        "pay_url": payment["payUrl"],
        "status": "pending",
    }
