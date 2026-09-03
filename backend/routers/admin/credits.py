"""Admin credit wallet endpoints (Monetization S6).

manage_finance-gated: list wallets, inspect a wallet + its immutable
ledger, grant credits (top-up / promo / enterprise contract), and apply
signed adjustments (+/-). All mutations write a CreditTransaction ledger
row (idempotency-keyed) and an AuditLog entry.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from backend.credit_service import adjust_credits, get_or_create_wallet, grant_credits
from backend.database import AuditLog, CreditTransaction, CreditWallet, User
from backend.dependencies import get_current_user, get_db
from backend.logger import logger
from backend.profile_helpers import get_user_email, get_user_name, get_user_tier
from backend.routers.admin.common import check_permission, paginate

router = APIRouter(tags=["admin"])


class CreditGrantRequest(BaseModel):
    credits: int
    provider: Optional[str] = "admin"  # admin|promo|manual
    provider_ref: Optional[str] = None  # invoice number / promo code
    note: Optional[str] = None


class CreditAdjustRequest(BaseModel):
    amount: int  # signed: + grants, - removes
    note: Optional[str] = None


def _wallet_view(db: Session, wallet: CreditWallet, user: User | None) -> dict:
    recent = (
        db.query(CreditTransaction)
        .filter(CreditTransaction.wallet_id == wallet.id)
        .order_by(CreditTransaction.id.desc())
        .limit(10)
        .all()
    )
    return {
        "id": wallet.id,
        "user_id": wallet.user_id,
        "user_name": get_user_name(user) if user else "Unknown",
        "user_email": get_user_email(user) if user else "Unknown",
        "tier": get_user_tier(user) if user else "free",
        "balance": float(wallet.balance or 0),
        "currency": wallet.currency,
        "is_active": wallet.is_active,
        "recent_transactions": [
            {
                "id": t.id,
                "type": t.type,
                "amount": float(t.amount),
                "resource": t.resource,
                "note": t.note,
                "status": t.status,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in recent
        ],
    }


@router.get("/credits")
def list_credit_wallets(
    q: str = "",
    page: int = 1,
    per_page: int = 30,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all credit wallets with balances, user info, and recent activity."""
    check_permission(current_user, "manage_finance")
    query = (
        db.query(CreditWallet)
        .options(joinedload(CreditWallet.user))
        .filter(CreditWallet.is_active)
    )
    if q:
        like = f"%{q.strip()}%"
        query = query.join(CreditWallet.user).filter(
            or_(
                User.email.ilike(like),
                User.name.ilike(like),
            )
        )
    result = paginate(query, page, per_page)
    items = []
    for wallet in result["items"]:
        try:
            items.append(_wallet_view(db, wallet, wallet.user))
        except Exception as e:
            logger.warning(
                f"list_credit_wallets failed to render wallet {wallet.id}: {e}"
            )
    return {
        "total": result["total"],
        "page": result["page"],
        "per_page": result["per_page"],
        "total_pages": result["total_pages"],
        "wallets": items,
    }


@router.get("/credits/{user_id}")
def get_credit_wallet(
    user_id: int,
    page: int = 1,
    per_page: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Wallet detail + paginated immutable ledger history."""
    check_permission(current_user, "manage_finance")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    wallet = get_or_create_wallet(db, user)
    tx_query = (
        db.query(CreditTransaction)
        .filter(CreditTransaction.wallet_id == wallet.id)
        .order_by(CreditTransaction.id.desc())
    )
    result = paginate(tx_query, page, per_page)
    return {
        "wallet": _wallet_view(db, wallet, user),
        "total": result["total"],
        "page": result["page"],
        "per_page": result["per_page"],
        "total_pages": result["total_pages"],
        "transactions": [
            {
                "id": t.id,
                "type": t.type,
                "amount": float(t.amount),
                "resource": t.resource,
                "reference_type": t.reference_type,
                "reference_id": t.reference_id,
                "actor_type": t.actor_type,
                "actor_id": t.actor_id,
                "provider": t.provider,
                "provider_ref": t.provider_ref,
                "idempotency_key": t.idempotency_key,
                "status": t.status,
                "note": t.note,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in result["items"]
        ],
    }


@router.post("/credits/{user_id}/grant")
def grant_user_credits(
    user_id: int,
    req: CreditGrantRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Grant credits: manual top-up, promo, or enterprise contract."""
    check_permission(current_user, "manage_finance")
    if req.credits <= 0:
        raise HTTPException(status_code=400, detail="credits must be positive")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if req.provider not in ("admin", "promo", "manual"):
        raise HTTPException(
            status_code=400, detail="provider must be one of: admin, promo, manual"
        )

    tx_type = (
        "promo"
        if req.provider == "promo"
        else ("topup" if req.provider == "manual" else "grant")
    )
    try:
        tx = grant_credits(
            db,
            user,
            req.credits,
            provider=req.provider,
            provider_ref=req.provider_ref,
            note=req.note,
            tx_type=tx_type,
            actor_type="admin",
            actor_id=current_user.id,
        )
    except Exception as e:
        logger.error(
            f"grant_user_credits failed for user {user_id}: {e}", exc_info=True
        )
        raise HTTPException(status_code=500, detail="Failed to grant credits")

    db.add(
        AuditLog(
            user_id=current_user.id,
            action="grant_credits",
            target_id=str(user_id),
            details=(
                f"Admin {get_user_email(current_user)} granted {req.credits} credits "
                f"({tx_type}/{req.provider}) to user #{user_id} — ledger tx #{tx.id}"
            ),
        )
    )
    db.commit()
    return {
        "message": "Credits granted",
        "user_id": user_id,
        "granted": req.credits,
        "balance": float(get_or_create_wallet(db, user).balance),
        "type": tx_type,
        "ledger_id": tx.id,
    }


@router.post("/credits/{user_id}/adjust")
def adjust_user_credits(
    user_id: int,
    req: CreditAdjustRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Apply a signed adjustment: + amount adds credits, - amount removes."""
    check_permission(current_user, "manage_finance")
    if req.amount == 0:
        raise HTTPException(status_code=400, detail="amount must be non-zero")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        tx = adjust_credits(
            db,
            user,
            req.amount,
            note=req.note,
            admin_user_id=current_user.id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(
            f"adjust_user_credits failed for user {user_id}: {e}", exc_info=True
        )
        raise HTTPException(status_code=500, detail="Failed to adjust credits")

    db.add(
        AuditLog(
            user_id=current_user.id,
            action="adjust_credits",
            target_id=str(user_id),
            details=(
                f"Admin {get_user_email(current_user)} adjusted credits by "
                f"{req.amount} for user #{user_id} — ledger tx #{tx.id}"
            ),
        )
    )
    db.commit()
    return {
        "message": "Credits adjusted",
        "user_id": user_id,
        "amount": req.amount,
        "balance": float(get_or_create_wallet(db, user).balance),
        "ledger_id": tx.id,
    }
