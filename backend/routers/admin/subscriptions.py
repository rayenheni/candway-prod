from datetime import UTC, datetime, timedelta
import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from backend.database import (
    AuditLog,
    Subscription,
    SubscriptionHistory,
    SubscriptionPlan,
    Transaction,
    User,
)
from backend.dependencies import get_current_user, get_db
from backend.email_service import email_service
from backend.logger import logger
from backend.profile_helpers import (
    get_user_email,
    get_user_name,
    get_user_subscription_plan,
)
from backend.routers.admin.common import check_permission, paginate
from backend.routers.admin.invoices import _create_invoice_internal
from backend.subscription_lifecycle_service import (
    activate_subscription,
    expire_subscription,
    get_or_create_subscription,
    log_subscription_history,
    reinstate_subscription,
)
from backend.subscription_lifecycle_service import (
    cancel_subscription as lifecycle_cancel_subscription,
)

router = APIRouter(tags=["admin"])


class RejectSubscriptionRequest(BaseModel):
    reason: Optional[str] = None


def _parse_credit_topup(tx: Transaction) -> Optional[int]:
    """Return the credit count if ``tx`` is a credit top-up purchase, else None.

    Convention: description starts with ``Credit top-up:`` followed by the
    credit amount (e.g. ``Credit top-up: 500 credits``). ``Optional[int]``
    so callers can distinguish a genuine top-up (0 is not a valid amount).
    """
    desc = (tx.description or "").strip().lower()
    marker = "credit top-up:"
    if not desc.startswith(marker):
        return None
    rest = desc[len(marker) :].split()
    if not rest:
        return None
    try:
        count = int(float(rest[0]))
    except (TypeError, ValueError):
        return None
    return count if count > 0 else None


@router.get("/subscriptions")
def get_pending_subscriptions(
    page: int = 1,
    per_page: int = 30,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "manage_finance")
    try:
        query = (
            db.query(Transaction)
            .options(joinedload(Transaction.user))
            .filter(Transaction.status == "pending")
        )
        result = paginate(query, page, per_page)
        return {
            "total": result["total"],
            "page": result["page"],
            "per_page": result["per_page"],
            "total_pages": result["total_pages"],
            "subscriptions": [
                {
                    "id": tx.id,
                    "user_id": tx.user_id,
                    "user_name": get_user_name(tx.user) if tx.user else "Unknown",
                    "user_email": get_user_email(tx.user) if tx.user else "Unknown",
                    "amount": tx.amount,
                    "proof_url": tx.proof_url,
                    "date": tx.created_at,
                    "type": "Subscription Upgrade",
                    "description": tx.description,
                }
                for tx in result["items"]
            ],
        }
    except Exception as e:
        logger.error(f"Failed to fetch pending subscriptions: {e}", exc_info=True)
        return {
            "total": 0,
            "page": 1,
            "per_page": 30,
            "total_pages": 0,
            "subscriptions": [],
        }


@router.post("/subscriptions/{tx_id}/approve")
def approve_subscription(
    tx_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    P0-05 FIX: Idempotent subscription approval.

    Locks the Transaction row with ``SELECT ... FOR UPDATE`` to
    serialise concurrent admin clicks, then refuses to double-apply
    if the tx is already in a terminal state. Re-submission of the
    SAME request (network retry) returns the same 200 response
    without re-extending the subscription window.

    A client may also pass an ``Idempotency-Key`` header — the key
    is recorded on the row and reused if the same admin retries.
    """
    check_permission(current_user, "manage_finance")
    idempotency_key = request.headers.get("Idempotency-Key")

    # Lock the row for the duration of this transaction.
    tx = db.query(Transaction).filter(Transaction.id == tx_id).with_for_update().first()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")

    # Idempotency-Key replay: same admin, same key, same outcome.
    if idempotency_key and tx.idempotency_key == idempotency_key:
        logger.info(
            f"[IDEMPOTENT] tx {tx_id} replay by admin {current_user.id} "
            f"with key {idempotency_key[:8]}... — returning cached outcome."
        )
        return {
            "message": "Subscription approved (idempotent replay)",
            "idempotent": True,
        }

    # Terminal state: already approved.
    if tx.status == "succeeded":
        if tx.approved_at and tx.approved_by:
            logger.info(
                f"[IDEMPOTENT] tx {tx_id} was already approved at "
                f"{tx.approved_at} by admin {tx.approved_by}."
            )
            return {
                "message": "Subscription already approved",
                "approved_at": tx.approved_at.isoformat(),
                "approved_by": tx.approved_by,
                "idempotent": True,
            }
        # No approved_at set yet (legacy row): fix the metadata
        # but do not re-apply the side effects.
        tx.approved_at = datetime.now(UTC)
        tx.approved_by = current_user.id
        if idempotency_key:
            tx.idempotency_key = idempotency_key
        db.commit()
        return {
            "message": "Subscription already approved (metadata backfilled)",
            "idempotent": True,
        }

    # Terminal state: already rejected.
    if tx.status == "Failed":
        raise HTTPException(
            status_code=409,
            detail=(
                "Transaction is in a terminal 'Failed' state. "
                "Create a new transaction to retry the payment."
            ),
        )

    # From here on, status must be 'pending' or 'unknown' to proceed.
    user = db.query(User).filter(User.id == tx.user_id).first()

    # Company subscription (org portal): description follows the
    # "Company subscription to <plan>" convention and tx.company_id is set.
    # Approval activates the company plan, raises the seat limit and issues
    # a B2B invoice — no per-recruiter plan change.
    from backend.routers.org.billing import approve_company_subscription

    if tx.description and tx.description.strip().startswith("Company subscription"):
        if not tx.company_id:
            raise HTTPException(
                status_code=400, detail="Company transaction missing company_id"
            )
        result = approve_company_subscription(db, tx, admin_user_id=current_user.id)
        tx.status = "succeeded"
        tx.proof_status = "verified"
        tx.proof_verified_at = datetime.now(UTC)
        tx.proof_verified_by = current_user.id
        tx.approved_at = datetime.now(UTC)
        tx.approved_by = current_user.id
        if idempotency_key:
            tx.idempotency_key = idempotency_key
        db.add(
            AuditLog(
                user_id=current_user.id,
                action="approve_subscription",
                target_id=str(tx_id),
                details=(
                    f"Admin {get_user_email(current_user)} approved company subscription "
                    f"tx #{tx_id} for company #{tx.company_id}"
                ),
                ip_address=request.client.host,
            )
        )
        db.commit()
        return result

    # Credit top-up purchase (design 2.4): description follows the
    # "Credit top-up: N credits" convention. Grant credits, do NOT touch
    # subscription/plan — the buyer is paying for a credit pack.
    credit_pack = _parse_credit_topup(tx)
    if credit_pack is not None:
        from backend.credit_service import grant_credits

        try:
            ctx = grant_credits(
                db,
                user,
                credit_pack,
                provider="manual",
                provider_ref=f"tx-{tx.id}",
                note=f"Credit top-up approved from tx #{tx.id}",
                tx_type="topup",
                actor_type="admin",
                actor_id=current_user.id,
            )
        except Exception as credit_e:
            logger.error(f"Failed to grant credit top-up for tx {tx_id}: {credit_e}")
            raise HTTPException(status_code=500, detail="Failed to grant credit top-up")
        tx.status = "succeeded"
        tx.proof_status = "verified"
        tx.proof_verified_at = datetime.now(UTC)
        tx.proof_verified_by = current_user.id
        tx.approved_at = datetime.now(UTC)
        tx.approved_by = current_user.id
        if idempotency_key:
            tx.idempotency_key = idempotency_key
        db.add(
            AuditLog(
                user_id=current_user.id,
                action="approve_credit_topup",
                target_id=str(tx_id),
                details=(
                    f"Admin {get_user_email(current_user)} approved credit top-up "
                    f"tx #{tx_id} for user #{tx.user_id} ({credit_pack} credits) — "
                    f"ledger tx #{ctx.id}"
                ),
                ip_address=request.client.host,
            )
        )
        db.commit()
        if user:
            try:
                _create_invoice_internal(db, user.id, tx.amount, tx.id, company_id=tx.company_id)
            except Exception as inv_e:
                logger.error(f"Failed to generate auto-invoice for tx {tx_id}: {inv_e}")
            email_service.send_subscription_status_email(user, "Succeeded")
        return {"message": "Credit top-up approved"}

    if user:
        plan_slug = get_user_subscription_plan(user)
        if not plan_slug:
            raise HTTPException(
                status_code=400,
                detail="No subscription plan associated with this transaction",
            )

        db_plan = (
            db.query(SubscriptionPlan)
            .filter(SubscriptionPlan.slug == plan_slug)
            .first()
        )
        if not db_plan:
            raise HTTPException(
                status_code=404, detail=f"Subscription plan '{plan_slug}' not found"
            )

        rp = getattr(user, "recruiter_profile", None)
        if rp:
            rp.tier = "pro"
            rp.subscription_status = "active"
            rp.subscription_end = datetime.now(UTC) + timedelta(days=365)
            rp.current_plan_id = db_plan.id

    tx.status = "succeeded"
    tx.proof_status = "verified"
    tx.proof_verified_at = datetime.now(UTC)
    tx.proof_verified_by = current_user.id
    tx.approved_at = datetime.now(UTC)
    tx.approved_by = current_user.id
    if idempotency_key:
        tx.idempotency_key = idempotency_key

    # S3: create/update the Subscription lifecycle row + history + credits.
    if user and db_plan:
        try:
            activate_subscription(
                db,
                user,
                db_plan,
                billing_cycle="yearly",
                transaction=tx,
                admin_user_id=current_user.id,
            )
        except Exception as sub_e:
            logger.error(f"Failed to activate subscription row for tx {tx_id}: {sub_e}")

    db.add(
        AuditLog(
            user_id=current_user.id,
            action="approve_subscription",
            target_id=str(tx_id),
            details=(
                f"Admin {get_user_email(current_user)} approved subscription "
                f"tx #{tx_id} for user #{tx.user_id}"
            ),
            ip_address=request.client.host,
        )
    )
    db.commit()

    if user:
        try:
            _create_invoice_internal(db, user.id, tx.amount, tx.id, company_id=tx.company_id)
        except Exception as inv_e:
            logger.error(f"Failed to generate auto-invoice for tx {tx_id}: {inv_e}")

        email_service.send_subscription_status_email(user, "Succeeded")

    return {"message": "Subscription approved"}


@router.post("/subscriptions/{tx_id}/reject")
def reject_subscription(
    tx_id: int,
    request: Request,
    payload: Optional[RejectSubscriptionRequest] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "manage_finance")
    tx = db.query(Transaction).filter(Transaction.id == tx_id).with_for_update().first()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")

    if tx.status == "succeeded":
        raise HTTPException(
            status_code=409,
            detail=(
                "Transaction is already approved. Reverse the approval "
                "via /subscriptions/{id}/cancel before rejecting."
            ),
        )
    if tx.status == "Failed" and tx.rejected_at:
        return {
            "message": "Transaction already rejected",
            "rejected_at": tx.rejected_at.isoformat(),
            "rejected_by": tx.rejected_by,
            "idempotent": True,
        }

    user = db.query(User).filter(User.id == tx.user_id).with_for_update().first()
    tx.status = "Failed"
    tx.proof_status = "rejected"
    tx.rejected_at = datetime.now(UTC)
    tx.rejected_by = current_user.id
    tx.rejection_reason = payload.reason if payload else None
    if user:
        rp = getattr(user, "recruiter_profile", None)
        if rp:
            rp.subscription_status = "rejected"

    db.add(
        AuditLog(
            user_id=current_user.id,
            action="reject_subscription",
            target_id=str(tx_id),
            details=(
                f"Admin {get_user_email(current_user)} rejected subscription "
                f"tx #{tx_id} for user #{tx.user_id}"
            ),
            ip_address=request.client.host,
        )
    )
    db.commit()

    if user:
        email_service.send_subscription_status_email(
            user, "Failed", reason=(payload.reason if payload else None)
        )

    return {"message": "Subscription rejected"}


@router.get("/subscriptions/active")
def get_active_subscriptions(
    page: int = 1,
    per_page: int = 30,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "manage_finance")
    try:
        active_user_ids = (
            db.query(Subscription.user_id)
            .filter(
                Subscription.status.in_(["active", "trialing", "past_due", "pending"])
            )
            .distinct()
            .subquery()
        )
        query = db.query(User).filter(
            User.role == "recruiter", User.id.in_(active_user_ids)
        )
        result = paginate(query, page, per_page)
        user_ids = [u.id for u in result["items"]]

        sub_map = {}
        if user_ids:
            latest_subs = (
                db.query(Subscription)
                .filter(Subscription.user_id.in_(user_ids))
                .order_by(Subscription.user_id, Subscription.id.desc())
                .all()
            )
            for s in latest_subs:
                if s.user_id not in sub_map:
                    sub_map[s.user_id] = s

        return {
            "total": result["total"],
            "page": result["page"],
            "per_page": result["per_page"],
            "total_pages": result["total_pages"],
            "subscriptions": [
                {
                    "id": u.id,
                    "name": get_user_name(u),
                    "email": get_user_email(u),
                    "subscription_end": (
                        sub_map[u.id].current_period_end.strftime("%Y-%m-%d")
                    )
                    if (u.id in sub_map and sub_map[u.id].current_period_end)
                    else "N/A",
                    "status": sub_map[u.id].status if u.id in sub_map else "unknown",
                }
                for u in result["items"]
            ],
        }
    except Exception as e:
        logger.error(f"Failed to fetch active subscriptions: {e}", exc_info=True)
        return {
            "total": 0,
            "page": 1,
            "per_page": 30,
            "total_pages": 0,
            "subscriptions": [],
        }


@router.get("/subscriptions/{user_id}/history")
def get_subscription_history(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "manage_finance")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    history = (
        db.query(SubscriptionHistory)
        .filter(SubscriptionHistory.user_id == user_id)
        .order_by(SubscriptionHistory.created_at.desc())
        .limit(25)
        .all()
    )
    return {
        "user_id": user_id,
        "user_name": get_user_name(user),
        "history": [
            {
                "id": item.id,
                "action": item.action,
                "from_plan_id": item.from_plan_id,
                "to_plan_id": item.to_plan_id,
                "amount_paid": item.amount_paid,
                "transaction_id": item.transaction_id,
                "admin_user_id": item.admin_user_id,
                "notes": item.notes,
                "created_at": item.created_at,
            }
            for item in history
        ],
    }


@router.post("/subscriptions/{user_id}/cancel")
def cancel_subscription(
    user_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "manage_finance")
    user = db.query(User).filter(User.id == user_id).with_for_update().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    rp = getattr(user, "recruiter_profile", None)
    if rp:
        rp.tier = "free"
        rp.subscription_status = "canceled"
        rp.subscription_end = datetime.now(UTC)

    sub = (
        db.query(Subscription)
        .filter(
            Subscription.user_id == user_id,
            Subscription.status.in_(["active", "past_due", "pending", "trialing"]),
        )
        .order_by(Subscription.id.desc())
        .first()
    )
    if sub:
        try:
            lifecycle_cancel_subscription(
                db,
                sub,
                reason="Canceled by admin",
                admin_user_id=current_user.id,
                immediate=True,
            )
        except Exception as sub_e:
            logger.error(
                f"Failed to cancel subscription row for user {user_id}: {sub_e}"
            )

    audit = AuditLog(
        user_id=current_user.id,
        action="cancel_subscription",
        target_id=str(user_id),
        details=f"Admin {get_user_email(current_user)} canceled subscription for user #{user_id}",
        ip_address=request.client.host,
    )
    db.add(audit)
    db.commit()
    return {"message": "Subscription canceled"}


@router.post("/subscriptions/{user_id}/extend")
def extend_subscription(
    user_id: int,
    request: Request,
    days: int = 30,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "manage_finance")

    if days < 1 or days > 730:
        raise HTTPException(status_code=400, detail="Days must be between 1 and 730")

    user = db.query(User).filter(User.id == user_id).with_for_update().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    rp = getattr(user, "recruiter_profile", None)
    if not rp:
        raise HTTPException(status_code=404, detail="Recruiter profile not found")

    if not rp.subscription_end or rp.subscription_end < datetime.now(UTC):
        rp.subscription_end = datetime.now(UTC)

    rp.tier = "pro"
    rp.subscription_status = "active"
    rp.subscription_end += timedelta(days=days)

    sub = (
        db.query(Subscription)
        .filter(
            Subscription.user_id == user_id,
            Subscription.status.in_(["active", "past_due", "pending", "trialing"]),
        )
        .order_by(Subscription.id.desc())
        .first()
    )
    if sub:
        try:
            from datetime import timedelta as _td

            sub.current_period_end = (
                sub.current_period_end or datetime.now(UTC)
            ) + _td(days=days)
            sub.status = "active"
            sub.grace_end = None
            sub.renewal_reminder_sent = False
            log_subscription_history(
                db,
                sub,
                "extended",
                admin_user_id=current_user.id,
                notes=f"Extended by {days} days",
            )
        except Exception as sub_e:
            logger.error(
                f"Failed to extend subscription row for user {user_id}: {sub_e}"
            )

    audit = AuditLog(
        user_id=current_user.id,
        action="extend_subscription",
        target_id=str(user_id),
        details=f"Admin {get_user_email(current_user)} extended subscription for user #{user_id} by {days} days",
        ip_address=request.client.host,
    )
    db.add(audit)
    db.commit()
    return {"message": f"Subscription extended by {days} days"}


@router.post("/subscriptions/{user_id}/change-plan")
def change_plan(
    user_id: int,
    request: Request,
    plan_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Upgrade/downgrade a user's plan (manual, admin-driven)."""
    check_permission(current_user, "manage_finance")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    new_plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id).first()
    if not new_plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    sub = (
        db.query(Subscription)
        .filter(
            Subscription.user_id == user_id,
            Subscription.status.in_(["active", "past_due", "pending", "trialing"]),
        )
        .order_by(Subscription.id.desc())
        .first()
    )
    action = (
        "upgraded"
        if sub and sub.plan_id and sub.plan_id < new_plan.id
        else "downgraded"
    )
    from_plan_id = sub.plan_id if sub else None

    if not sub:
        sub = get_or_create_subscription(db, user)

    sub.plan_id = new_plan.id
    if sub.status not in ("active", "trialing"):
        sub.status = "active"

    log_subscription_history(
        db,
        sub,
        action,
        admin_user_id=current_user.id,
        from_plan_id=from_plan_id,
        to_plan_id=new_plan.id,
        notes=f"Plan changed to {new_plan.name}",
    )

    # Keep the cached profile mirror in sync.
    rp = getattr(user, "recruiter_profile", None)
    if rp:
        rp.tier = "pro" if new_plan.slug != "free_recruiter" else "free"
        rp.current_plan_id = new_plan.id
    cp = getattr(user, "candidate_profile", None)
    if cp and hasattr(cp, "subscription_status"):
        cp.subscription_status = (
            "active" if new_plan.slug != "free-candidate" else "free"
        )

    db.add(
        AuditLog(
            user_id=current_user.id,
            action="change_plan",
            target_id=str(user_id),
            details=f"Admin {get_user_email(current_user)} changed user #{user_id} plan to {new_plan.name}",
            ip_address=request.client.host,
        )
    )
    db.commit()
    return {"message": f"Plan changed to {new_plan.name}"}


@router.post("/subscriptions/{user_id}/expire")
def expire_user_subscription(
    user_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "manage_finance")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    sub = (
        db.query(Subscription)
        .filter(Subscription.user_id == user_id)
        .order_by(Subscription.id.desc())
        .first()
    )
    if sub:
        try:
            expire_subscription(db, sub, admin_user_id=current_user.id)
        except Exception as sub_e:
            logger.error(
                f"Failed to expire subscription row for user {user_id}: {sub_e}"
            )

    rp = getattr(user, "recruiter_profile", None)
    if rp:
        rp.tier = "free"
        rp.subscription_status = "expired"

    db.add(
        AuditLog(
            user_id=current_user.id,
            action="expire_subscription",
            target_id=str(user_id),
            details=f"Admin {get_user_email(current_user)} expired subscription for user #{user_id}",
            ip_address=request.client.host,
        )
    )
    db.commit()
    return {"message": "Subscription expired"}


@router.post("/subscriptions/{user_id}/reinstate")
def reinstate_user_subscription(
    user_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "manage_finance")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    sub = (
        db.query(Subscription)
        .filter(
            Subscription.user_id == user_id,
            Subscription.status.in_(["past_due"]),
        )
        .order_by(Subscription.id.desc())
        .first()
    )
    if not sub:
        raise HTTPException(
            status_code=404, detail="No past_due subscription to reinstate"
        )
    try:
        reinstate_subscription(db, sub, admin_user_id=current_user.id)
    except ValueError as ve:
        raise HTTPException(status_code=409, detail=str(ve))

    rp = getattr(user, "recruiter_profile", None)
    if rp:
        rp.tier = "pro"
        rp.subscription_status = "active"

    db.add(
        AuditLog(
            user_id=current_user.id,
            action="reinstate_subscription",
            target_id=str(user_id),
            details=f"Admin {get_user_email(current_user)} reinstated subscription for user #{user_id}",
            ip_address=request.client.host,
        )
    )
    db.commit()
    return {"message": "Subscription reinstated"}


@router.post("/subscriptions/{user_id}/start-trial")
def start_trial(
    user_id: int,
    request: Request,
    plan_id: int,
    days: int = 14,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Admin-activated trial (no card, no webhook)."""
    check_permission(current_user, "manage_finance")
    if days < 1 or days > 90:
        raise HTTPException(
            status_code=400, detail="Trial days must be between 1 and 90"
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    now = datetime.now(UTC)
    sub = (
        db.query(Subscription)
        .filter(
            Subscription.user_id == user_id,
            Subscription.status.in_(["active", "past_due", "pending", "trialing"]),
        )
        .order_by(Subscription.id.desc())
        .first()
    )
    if not sub:
        sub = get_or_create_subscription(db, user)

    sub.plan_id = plan.id
    sub.status = "trialing"
    sub.started_at = now
    sub.current_period_start = now
    sub.current_period_end = now + timedelta(days=days)

    log_subscription_history(
        db,
        sub,
        "trial_started",
        admin_user_id=current_user.id,
        to_plan_id=plan.id,
        notes=f"{days}-day trial",
    )

    rp = getattr(user, "recruiter_profile", None)
    if rp:
        rp.tier = "pro"
        rp.subscription_status = "trialing"
        rp.subscription_end = now + timedelta(days=days)
        rp.current_plan_id = plan.id

    db.add(
        AuditLog(
            user_id=current_user.id,
            action="start_trial",
            target_id=str(user_id),
            details=f"Admin {get_user_email(current_user)} started {days}-day trial of {plan.name} for user #{user_id}",
            ip_address=request.client.host,
        )
    )
    db.commit()
    return {"message": f"Started {days}-day trial of {plan.name}"}


# ============================================
# S10 — Payment Proof Review (admin)
# ============================================


class ReviewProofRequest(BaseModel):
    notes: Optional[str] = None


@router.get("/payment-proofs")
def list_payment_proofs(
    page: int = 1,
    per_page: int = 30,
    proof_status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List manual payment proofs with optional proof_status filter."""
    check_permission(current_user, "manage_finance")
    try:
        query = (
            db.query(Transaction)
            .options(joinedload(Transaction.user))
            .filter(Transaction.proof_url.isnot(None))
        )
        if proof_status:
            query = query.filter(Transaction.proof_status == proof_status)

        result = paginate(query, page, per_page)
        return {
            "total": result["total"],
            "page": result["page"],
            "per_page": result["per_page"],
            "total_pages": result["total_pages"],
            "proofs": [
                {
                    "id": tx.id,
                    "user_id": tx.user_id,
                    "user_name": get_user_name(tx.user) if tx.user else "Unknown",
                    "user_email": get_user_email(tx.user) if tx.user else "Unknown",
                    "amount": tx.amount,
                    "currency": tx.currency,
                    "status": tx.status,
                    "proof_status": tx.proof_status,
                    "proof_url": tx.proof_url,
                    "proof_file_size": tx.proof_file_size,
                    "proof_file_type": tx.proof_file_type,
                    "proof_verified_at": tx.proof_verified_at,
                    "proof_verified_by": tx.proof_verified_by,
                    "proof_review_notes": tx.proof_review_notes,
                    "description": tx.description,
                    "created_at": tx.created_at,
                }
                for tx in result["items"]
            ],
        }
    except Exception as e:
        logger.error(f"Failed to fetch payment proofs: {e}", exc_info=True)
        return {
            "total": 0,
            "page": 1,
            "per_page": 30,
            "total_pages": 0,
            "proofs": [],
        }


@router.get("/payment-proofs/{tx_id}")
def get_payment_proof(
    tx_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get details for a single payment proof."""
    check_permission(current_user, "manage_finance")
    tx = db.query(Transaction).filter(Transaction.id == tx_id).first()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
    if not tx.proof_url:
        raise HTTPException(status_code=404, detail="No proof uploaded for this transaction")

    return {
        "id": tx.id,
        "user_id": tx.user_id,
        "user_name": get_user_name(tx.user) if tx.user else "Unknown",
        "user_email": get_user_email(tx.user) if tx.user else "Unknown",
        "amount": tx.amount,
        "currency": tx.currency,
        "status": tx.status,
        "proof_status": tx.proof_status,
        "proof_url": tx.proof_url,
        "proof_file_size": tx.proof_file_size,
        "proof_file_type": tx.proof_file_type,
        "proof_verified_at": tx.proof_verified_at,
        "proof_verified_by": tx.proof_verified_by,
        "proof_review_notes": tx.proof_review_notes,
        "description": tx.description,
        "created_at": tx.created_at,
    }


@router.get("/payment-proofs/{tx_id}/file")
def download_payment_proof(
    tx_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Serve the payment proof file for admin review."""
    check_permission(current_user, "manage_finance")
    tx = db.query(Transaction).filter(Transaction.id == tx_id).first()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
    if not tx.proof_url:
        raise HTTPException(status_code=404, detail="No proof uploaded for this transaction")

    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    file_path = os.path.join(base_dir, tx.proof_url)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Proof file not found on disk")

    filename = os.path.basename(file_path)
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type=tx.proof_file_type or "application/octet-stream",
    )


@router.post("/payment-proofs/{tx_id}/verify")
def verify_payment_proof(
    tx_id: int,
    payload: Optional[ReviewProofRequest] = None,
    request: Request = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark a payment proof as verified (does not approve the subscription)."""
    check_permission(current_user, "manage_finance")
    tx = db.query(Transaction).filter(Transaction.id == tx_id).with_for_update().first()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
    if not tx.proof_url:
        raise HTTPException(status_code=400, detail="No proof uploaded for this transaction")

    tx.proof_status = "verified"
    tx.proof_verified_at = datetime.now(UTC)
    tx.proof_verified_by = current_user.id
    if payload and payload.notes:
        tx.proof_review_notes = payload.notes

    db.add(
        AuditLog(
            user_id=current_user.id,
            action="verify_payment_proof",
            target_id=str(tx_id),
            details=(
                f"Admin {get_user_email(current_user)} verified payment proof "
                f"for tx #{tx_id} ({tx.description})"
            ),
            ip_address=request.client.host,
        )
    )
    db.commit()
    return {"message": "Payment proof verified"}


@router.post("/payment-proofs/{tx_id}/reject")
def reject_payment_proof(
    tx_id: int,
    payload: ReviewProofRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Reject a payment proof with a reason (company can re-upload)."""
    check_permission(current_user, "manage_finance")
    tx = db.query(Transaction).filter(Transaction.id == tx_id).with_for_update().first()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
    if not tx.proof_url:
        raise HTTPException(status_code=400, detail="No proof uploaded for this transaction")

    if not payload.notes or not payload.notes.strip():
        raise HTTPException(status_code=400, detail="Rejection reason is required")

    tx.proof_status = "rejected"
    tx.proof_review_notes = payload.notes.strip()
    tx.proof_verified_at = None
    tx.proof_verified_by = None

    db.add(
        AuditLog(
            user_id=current_user.id,
            action="reject_payment_proof",
            target_id=str(tx_id),
            details=(
                f"Admin {get_user_email(current_user)} rejected payment proof "
                f"for tx #{tx_id} ({tx.description}): {payload.notes.strip()}"
            ),
            ip_address=request.client.host,
        )
    )
    db.commit()

    user = db.query(User).filter(User.id == tx.user_id).first()
    if user:
        try:
            email_service.send_subscription_status_email(
                user, "Failed", reason=f"Payment proof rejected: {payload.notes.strip()}"
            )
        except Exception as email_e:
            logger.error(f"Failed to send proof rejection email for tx {tx_id}: {email_e}")

    return {"message": "Payment proof rejected. The company may re-upload."}
