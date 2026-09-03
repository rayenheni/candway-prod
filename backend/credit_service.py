"""Credit wallet service — universal AI credit ledger.

Monetization S2: get/create wallet, atomic consume (optimistic lock +
row-lock), rollback, grant. All movements go through CreditTransaction
(immutable ledger) with unique idempotency_key to prevent double-charge.
"""

from typing import Optional

from sqlalchemy import update
from sqlalchemy.orm import Session

from backend.database import (
    CompanyMember,
    CreditTransaction,
    CreditWallet,
    UsageEvent,
    User,
    CompanyMember   
)

from backend.models import SystemConfig


def _resolve_wallet_company_id(db: Session, user: User) -> Optional[int]:
    for attr in ("_company_id", "company_id"):
        value = getattr(user, attr, None)
        if value:
            return value

    return (
        db.query(CompanyMember.company_id)
        .filter(CompanyMember.user_id == user.id)
        .scalar()
    )
# ---------------------------------------------------------------------------
# ADMIN-CONTROLLED AI PRICING
# ---------------------------------------------------------------------------
# Global gating toggle + per-resource credit costs are stored in SystemConfig
# so the platform admin can control monetization live without redeploys.
#   - "ai_credit_gating_enabled" = "true"/"false" (master switch)
#   - "ai_credit_cost_<resource>" = integer credit price (falls back to the
#     caller's default when unset)


def is_credit_gating_enabled(db: Session) -> bool:
    """Master switch for AI credit charging (SystemConfig, default ON)."""
    cfg = db.query(SystemConfig).filter(SystemConfig.key == "ai_credit_gating_enabled").first()
    if cfg is None or cfg.value is None:
        return True
    return str(cfg.value).strip().lower() not in ("false", "0", "off", "no")


def get_configured_credit_cost(db: Session, resource: str, default: int) -> int:
    """Admin-configured credit price for a resource, falling back to ``default``.

    A configured value of 0 means the feature is free. Negative/invalid
    config values are ignored and the caller's default is used.
    """
    cfg = (
        db.query(SystemConfig)
        .filter(SystemConfig.key == f"ai_credit_cost_{resource}")
        .first()
    )
    if cfg is None or cfg.value is None:
        return default
    try:
        cost = int(float(str(cfg.value).strip()))
    except (TypeError, ValueError):
        return default
    if cost < 0:
        return default
    return cost


def effective_credit_cost(db: Session, resource: str, default: int) -> int:
    """Resolve the final credit cost honoring admin gating + pricing.

    Returns 0 when gating is disabled (feature free) and the configured
    per-resource price otherwise.
    """
    if not is_credit_gating_enabled(db):
        return 0
    return get_configured_credit_cost(db, resource, default)


def get_all_credit_pricing(db: Session) -> dict:
    """Return the full admin-visible pricing map (config overrides + defaults)."""
    defaults = {
        "cv_analysis": 3,
        "interview_question_gen": 5,
        "ai_interview_evaluation": 5,
        "pdf_report": 1,
        "ai_invitation": 1,
        "score_comparison": 1,
        "debrief_summary": 1,
        "translation": 1,
        "career_chatbot": 1,
        "wizard_suggest": 1,
        "skill_tree_generate": 1,
        "ai_search": 2,
        "career_roadmap": 4,
        "copilot_chat": 1,
        "jd_writer": 2,
    }
    return {
        resource: get_configured_credit_cost(db, resource, default)
        for resource, default in defaults.items()
    }


def get_or_create_wallet(db: Session, user: User) -> CreditWallet:
    """Fetch the user's wallet, creating a 0-balance wallet if missing."""
    wallet = db.query(CreditWallet).filter(CreditWallet.user_id == user.id).first()
    if wallet:
        return wallet

    wallet = CreditWallet(
        user_id=user.id,
        company_id=_resolve_wallet_company_id(db, user),
        balance=0,
        version=0,
        currency="CRED",
    )
    db.add(wallet)
    db.commit()
    db.refresh(wallet)
    return wallet



def consume_credits(
    db: Session,
    user: User,
    credits: int,
    resource: str,
    reference_type: Optional[str] = None,
    reference_id: Optional[int] = None,
) -> CreditTransaction:
    """Atomically reserve credits from the wallet.

    Optimistic lock via UPDATE ... WHERE balance >= n AND version = v.
    Raises ValueError on insufficient funds. Idempotent per (resource, ref).
    Admin users bypass the wallet entirely.
    """
    # Admin-controlled pricing: honor the global gating switch + per-resource
    # credit cost from SystemConfig. A 0 cost (free feature or gating off)
    # returns a no-op transaction so callers behave as if fully granted.
    credits = effective_credit_cost(db, resource, credits)
    if credits <= 0:
        return CreditTransaction(
            id=0,
            wallet_id=0,
            user_id=user.id,
            amount=0,
            type="consume",
            resource=resource,
            reference_type=reference_type,
            reference_id=reference_id,
            actor_type="system",
            provider="free",
            idempotency_key=f"free:{resource}:{reference_id or user.id}",
            status="succeeded",
        )

    if getattr(user, "role", "") == "admin":
        return CreditTransaction(
            id=0,
            wallet_id=0,
            user_id=user.id,
            amount=-credits,
            type="consume",
            resource=resource,
            reference_type=reference_type,
            reference_id=reference_id,
            actor_type="admin",
            actor_id=user.id,
            provider="admin",
            idempotency_key=f"consume:{resource}:{reference_id or user.id}",
            status="succeeded",
        )

    wallet = get_or_create_wallet(db, user)

    idem = f"consume:{resource}"
    if reference_id is not None:
        idem += f":{reference_id}"
    else:
        # No stable reference → one unique idempotency key per request so
        # sequential calls both consume. Retry-dedup only applies when a
        # stable reference (e.g. application id) is supplied.
        import uuid

        idem += f":{uuid.uuid4()}"

    existing = (
        db.query(CreditTransaction)
        .filter(CreditTransaction.idempotency_key == idem)
        .first()
    )
    if existing:
        return existing

    result = db.execute(
        update(CreditWallet)
        .where(
            CreditWallet.user_id == user.id,
            CreditWallet.balance >= credits,
            CreditWallet.version == wallet.version,
        )
        .values(
            balance=CreditWallet.balance - credits,
            version=CreditWallet.version + 1,
        )
    )
    if result.rowcount == 0:
        db.rollback()
        raise ValueError(
            f"Insufficient credits: need {credits}, have {float(wallet.balance or 0)}"
        )

    tx = CreditTransaction(
        wallet_id=wallet.id,
        user_id=user.id,
        company_id=wallet.company_id,
        amount=-credits,
        type="consume",
        resource=resource,
        reference_type=reference_type,
        reference_id=reference_id,
        actor_type="user",
        actor_id=user.id,
        provider="system",
        idempotency_key=idem,
        status="succeeded",
    )
    db.add(tx)
    db.commit()
    db.refresh(tx)
    return tx


def rollback_credits(db: Session, tx: CreditTransaction) -> None:
    """Restore credits consumed by a failed operation (compensating rollback)."""
    if not tx or tx.status == "reversed" or getattr(tx, "id", 0) == 0:
        return
    tx.status = "reversed"
    db.execute(
        update(CreditWallet)
        .where(CreditWallet.user_id == tx.user_id)
        .values(balance=CreditWallet.balance + abs(tx.amount))
    )
    db.add(
        CreditTransaction(
            wallet_id=tx.wallet_id,
            user_id=tx.user_id,
            company_id=tx.company_id,
            amount=abs(tx.amount),
            type="rollback",
            resource=tx.resource,
            reference_type=tx.reference_type,
            reference_id=tx.reference_id,
            actor_type="system",
            provider="system",
            idempotency_key=f"rollback:{tx.idempotency_key}",
            status="succeeded",
        )
    )
    db.commit()


def consume_credits_or_402(
    db: Session,
    user: User,
    credits: int,
    resource: str,
    reference_type: Optional[str] = None,
    reference_id: Optional[int] = None,
) -> CreditTransaction:
    """Like consume_credits but raises FastAPI 402 with the standard shape.

    For inline call sites (endpoints where a dependency gate is awkward,
    e.g. behind cache short-circuits). Returns the ledger transaction so
    callers can rollback_credits on downstream AI failure.
    """
    from fastapi import HTTPException, status

    try:
        return consume_credits(
            db,
            user,
            credits,
            resource,
            reference_type=reference_type,
            reference_id=reference_id,
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "error": "insufficient_credits",
                "message": f"This feature costs {credits} credit(s) and you don't have enough.",
                "cost": credits,
                "upgrade_url": "/subscription",
            },
        )


def grant_credits(
    db: Session,
    user: User,
    credits: int,
    provider: str = "system",
    provider_ref: Optional[str] = None,
    note: Optional[str] = None,
    tx_type: str = "grant",
    actor_type: Optional[str] = None,
    actor_id: Optional[int] = None,
) -> CreditTransaction:
    """Grant credits (monthly allocation, top-up approval, promo, admin)."""
    wallet = get_or_create_wallet(db, user)
    idem = f"{tx_type}:{provider}:{provider_ref or user.id}:{credits}:{note or ''}"

    existing = (
        db.query(CreditTransaction)
        .filter(CreditTransaction.idempotency_key == idem)
        .first()
    )
    if existing:
        return existing

    wallet.balance = (wallet.balance or 0) + credits
    tx = CreditTransaction(
        wallet_id=wallet.id,
        user_id=user.id,
        company_id=wallet.company_id,
        amount=credits,
        type=tx_type,
        provider=provider,
        provider_ref=provider_ref,
        actor_type=actor_type or ("system" if provider == "system" else "admin"),
        actor_id=actor_id,
        idempotency_key=idem,
        status="succeeded",
        note=note,
    )
    db.add(tx)
    db.commit()
    db.refresh(tx)
    return tx


def adjust_credits(
    db: Session,
    user: User,
    amount: int,
    note: Optional[str] = None,
    admin_user_id: Optional[int] = None,
) -> CreditTransaction:
    """Apply a signed adjustment (+ grants, - removes) to the wallet.

    Negative adjustments can never drive the balance below zero. Writes
    an immutable 'adjustment' ledger row with admin attribution.
    """
    wallet = get_or_create_wallet(db, user)
    import uuid

    idem = f"adjustment:{uuid.uuid4()}"
    if amount >= 0:
        wallet.balance = (wallet.balance or 0) + amount
    else:
        removal = abs(amount)
        current = wallet.balance or 0
        if current < removal:
            raise ValueError(
                f"Cannot remove {removal} credits: balance is only {current}"
            )
        wallet.balance = current - removal

    tx = CreditTransaction(
        wallet_id=wallet.id,
        user_id=user.id,
        company_id=wallet.company_id,
        amount=amount,
        type="adjustment",
        actor_type="admin",
        actor_id=admin_user_id,
        provider="admin",
        idempotency_key=idem,
        status="succeeded",
        note=note,
    )
    db.add(tx)
    db.commit()
    db.refresh(tx)
    return tx


def record_usage_event(
    db: Session,
    user_id: Optional[int],
    company_id: Optional[int],
    resource: str,
    credits: int = 0,
    cost_usd: Optional[float] = None,
    model: Optional[str] = None,
    reference_type: Optional[str] = None,
    reference_id: Optional[int] = None,
    metadata_json: Optional[str] = None,
) -> UsageEvent:
    """Append an immutable metering row for analytics dashboards."""
    event = UsageEvent(
        user_id=user_id,
        company_id=company_id,
        resource=resource,
        credits=credits,
        cost_usd=cost_usd,
        model=model,
        reference_type=reference_type,
        reference_id=reference_id,
        metadata_json=metadata_json,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def resolve_company_billing_user(
    db: Session, company_id: Optional[int]
) -> Optional[User]:
    """Resolve a user whose wallet represents a company's AI spend.

    Prefers an active company owner, falling back to any active member.
    Standalone recruiters (company_id None) have no company wallet — their
    own wallet is used via the normal user-scoped path. Returns None when
    the company has no resolvable active member.
    """
    if not company_id:
        return None
    owner = (
        db.query(CompanyMember)
        .filter(
            CompanyMember.company_id == company_id,
            CompanyMember.is_active.is_(True),
            CompanyMember.role == "owner",
        )
        .order_by(CompanyMember.joined_at.asc(), CompanyMember.id.asc())
        .first()
    )
    member = owner or (
        db.query(CompanyMember)
        .filter(
            CompanyMember.company_id == company_id,
            CompanyMember.is_active.is_(True),
        )
        .order_by(CompanyMember.id.asc())
        .first()
    )
    if member is None:
        return None
    return db.query(User).filter(User.id == member.user_id).first()


def get_user_credit_balance(db: Session, user: User) -> float:
    """Current wallet balance for a user (0.0 when no wallet exists)."""
    wallet = (
        db.query(CreditWallet).filter(CreditWallet.user_id == user.id).first()
    )
    return float(wallet.balance or 0) if wallet else 0.0


def transfer_company_credits(
    db: Session,
    company_id: int,
    target_user: User,
    credits: int,
    note: Optional[str] = None,
    admin_user_id: Optional[int] = None,
) -> dict:
    """Transfer credits from a company's pool to a target user's wallet.

    The company pool lives on the billing owner's user-scoped wallet
    (see resolve_company_billing_user). The transfer debits the pool and
    credits the target in a single transaction with idempotent ledger keys
    (``transfer:{company_id}:{target}:{credits}:{note}``) so a retried
    request can never double-move credits. Raises ValueError when the pool
    has insufficient balance or no billing owner is resolvable.
    """
    if credits <= 0:
        raise ValueError("credits must be positive")
    source_user = resolve_company_billing_user(db, company_id)
    if source_user is None:
        raise ValueError("No company billing owner is available to draw credits from")
    source_wallet = get_or_create_wallet(db, source_user)
    target_wallet = get_or_create_wallet(db, target_user)

    idem_base = f"transfer:{company_id}:{target_user.id}:{credits}:{note or ''}"
    existing = (
        db.query(CreditTransaction)
        .filter(CreditTransaction.idempotency_key == f"{idem_base}:in")
        .first()
    )
    if existing:
        return {
            "source_user_id": source_user.id,
            "target_user_id": target_user.id,
            "credits": credits,
            "source_balance": float(source_wallet.balance or 0),
            "target_balance": float(target_wallet.balance or 0),
            "duplicate": True,
        }

    source_balance = float(source_wallet.balance or 0)
    if source_balance < credits:
        raise ValueError(
            f"Insufficient company credits: need {credits}, have {source_balance}"
        )

    source_wallet.balance = source_balance - credits
    target_wallet.balance = (target_wallet.balance or 0) + credits
    db.add(
        CreditTransaction(
            wallet_id=source_wallet.id,
            user_id=source_user.id,
            company_id=source_wallet.company_id,
            amount=-credits,
            type="adjustment",
            actor_type="admin",
            actor_id=admin_user_id,
            provider="org",
            provider_ref=f"transfer-out-{company_id}-{target_user.id}",
            idempotency_key=f"{idem_base}:out",
            status="succeeded",
            note=note or f"Transfer to user {target_user.id}",
        )
    )
    db.add(
        CreditTransaction(
            wallet_id=target_wallet.id,
            user_id=target_user.id,
            company_id=target_wallet.company_id,
            amount=credits,
            type="grant",
            actor_type="admin",
            actor_id=admin_user_id,
            provider="org",
            provider_ref=f"transfer-in-{company_id}-{target_user.id}",
            idempotency_key=f"{idem_base}:in",
            status="succeeded",
            note=note or f"Company credit transfer ({company_id})",
        )
    )
    db.commit()
    db.refresh(source_wallet)
    db.refresh(target_wallet)
    return {
        "source_user_id": source_user.id,
        "target_user_id": target_user.id,
        "credits": credits,
        "source_balance": float(source_wallet.balance or 0),
        "target_balance": float(target_wallet.balance or 0),
        "duplicate": False,
    }


def consume_company_credits(
    db: Session,
    company_id: Optional[int],
    credits: int,
    resource: str,
    reference_type: Optional[str] = None,
    reference_id: Optional[int] = None,
    fallback_user: Optional[User] = None,
) -> Optional[CreditTransaction]:
    """Consume credits from a company's wallet (owner user's wallet).

    Wallets are user-scoped; charging a company means debiting its billing
    owner's wallet. Falls back to ``fallback_user`` when the company has no
    active member (e.g. a standalone recruiter). Returns None (no charge)
    when neither a company user nor a fallback user is resolvable.
    """
    user = resolve_company_billing_user(db, company_id) or fallback_user
    if user is None:
        return None
    try:
        tx = consume_credits(
            db,
            user,
            credits,
            resource,
            reference_type=reference_type,
            reference_id=reference_id,
        )
    except ValueError:
        return None
    # Meter the company's AI usage so the financial dashboard's feature-usage
    # breakdown includes company-scoped spend. Recorded even when the consume
    # was a free no-op (gating off / price 0) so feature usage stays accurate.
    try:
        record_usage_event(
            db,
            user_id=user.id,
            company_id=company_id,
            resource=resource,
            credits=int(abs(getattr(tx, "amount", 0) or 0)),
            reference_type=reference_type,
            reference_id=reference_id,
        )
    except Exception:
        pass
    return tx
