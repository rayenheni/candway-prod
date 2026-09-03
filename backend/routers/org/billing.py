"""Organization portal — company-level subscription, billing and KYB.

All endpoints are tenant-scoped to the org admin's company and gated by
`require_org_admin`. The company (not the individual recruiter) is the
billing entity: an org admin purchases a recruiter plan with a seat count,
uploads a manual bank proof, and admin approval activates the company plan
and sets the recruiter seat limit (``Company.max_users``).

Company-scoped finance rows (Transaction / Invoice / Subscription) ALWAYS
set ``company_id`` explicitly — the schema is tenant-strict (NOT NULL).
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import (
    AuditLog,
    Company,
    CompanyMember,
    Invoice,
    PlanVersion,
    Subscription,
    SubscriptionHistory,
    SubscriptionPlan,
    Transaction,
    User,
)
from backend.dependencies import get_db, require_org_admin
from backend.logger import logger
from backend.profile_helpers import get_user_email

router = APIRouter(prefix="/org/billing", tags=["org"])

STAMP_DUTY = 1.000
TVA_RATE = 0.19
COMPANY_SUB_MARKER = "Company subscription"


class OrgBillingSummary(BaseModel):
    company_id: int
    company_name: str
    plan: Optional[dict]
    subscription_status: str
    seats: dict
    pending_transaction: Optional[dict]
    billing_email: Optional[str]
    billing_address: Optional[str]
    tax_id: Optional[str]
    kyb_status: Optional[str]


class OrgSubscribeRequest(BaseModel):
    plan_id: int
    billing_cycle: str = "monthly"  # monthly|yearly


class OrgKybSubmit(BaseModel):
    billing_email: str
    billing_address: Optional[str] = None
    tax_id: Optional[str] = None


def _get_company(db: Session, company_id: int) -> Company:
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


def _kyb_documents(company: Company) -> list:
    """Parse the company's stored KYB document list (JSON text column)."""
    if not company.kyb_documents:
        return []
    try:
        docs = json.loads(company.kyb_documents)
        return docs if isinstance(docs, list) else []
    except (ValueError, TypeError):
        return []


def _company_tx_payload(tx: Transaction) -> dict:
    return {
        "id": tx.id,
        "amount": tx.amount,
        "amount_ht": tx.amount_ht,
        "tva_amount": tx.tva_amount,
        "stamp_duty": tx.stamp_duty,
        "amount_ttc": tx.amount_ttc,
        "currency": tx.currency,
        "status": tx.status,
        "description": tx.description,
        "proof_url": tx.proof_url,
        "created_at": tx.created_at.isoformat() if tx.created_at else None,
    }


def _invoice_payload(inv: Invoice) -> dict:
    return {
        "id": inv.id,
        "invoice_number": inv.invoice_number,
        "amount_ht": inv.amount_ht,
        "tva_rate": inv.tva_rate,
        "tva_amount": inv.tva_amount,
        "stamp_duty": inv.stamp_duty,
        "total_ttc": inv.total_ttc,
        "status": inv.status,
        "client_name": inv.client_name,
        "created_at": inv.created_at.isoformat() if inv.created_at else None,
        "transaction_id": inv.transaction_id,
    }


def _current_company_subscription(
    db: Session, company_id: int
) -> Optional[Subscription]:
    return (
        db.query(Subscription)
        .filter(Subscription.company_id == company_id)
        .order_by(Subscription.id.desc())
        .first()
    )


def _get_company_plan(db: Session, company: Company) -> Optional[SubscriptionPlan]:
    if company.plan_id:
        return (
            db.query(SubscriptionPlan)
            .filter(SubscriptionPlan.id == company.plan_id)
            .first()
        )
    sub = _current_company_subscription(db, company.id)
    if sub:
        return (
            db.query(SubscriptionPlan)
            .filter(SubscriptionPlan.id == sub.plan_id)
            .first()
        )
    return None


def _count_active_recruiters(db: Session, company_id: int) -> int:
    return (
        db.query(CompanyMember)
        .filter(
            CompanyMember.company_id == company_id,
            CompanyMember.role == "recruiter",
            CompanyMember.is_active == True,  # noqa: E712
        )
        .count()
    )


def _seats_payload(db: Session, company: Company) -> dict:
    used = _count_active_recruiters(db, company.id)
    limit = company.max_users or 0
    return {
        "limit": limit,
        "used": used,
        "available": max(0, limit - used),
    }


@router.get("/plans")
def list_company_plans(
    current_user: User = Depends(require_org_admin),
    db: Session = Depends(get_db),
):
    """Recruiter team plans a company can purchase (seats-based)."""
    plans = (
        db.query(SubscriptionPlan)
        .filter(
            SubscriptionPlan.target_audience == "recruiter",
            SubscriptionPlan.is_active == True,  # noqa: E712
        )
        .order_by(SubscriptionPlan.price_monthly.asc())
        .all()
    )
    return [
        {
            "id": p.id,
            "name": p.name,
            "slug": p.slug,
            "price_monthly": p.price_monthly,
            "price_yearly": p.price_yearly,
            "currency": p.currency,
            "job_limit": p.job_limit,
            "cv_limit": p.cv_limit,
            "ai_interview_limit": p.ai_interview_limit,
            "team_seat_limit": p.team_seat_limit,
            "credits_monthly": p.credits_monthly,
        }
        for p in plans
    ]


@router.get("/summary")
def billing_summary(
    current_user: User = Depends(require_org_admin),
    db: Session = Depends(get_db),
):
    """Company billing snapshot: plan, seats, pending tx, KYB status."""
    company_id = current_user._company_id
    company = _get_company(db, company_id)
    plan = _get_company_plan(db, company)

    sub = _current_company_subscription(db, company_id)
    pending_tx = (
        db.query(Transaction)
        .filter(
            Transaction.company_id == company_id,
            Transaction.status == "pending",
            Transaction.description.like(f"{COMPANY_SUB_MARKER}%"),
        )
        .order_by(Transaction.id.desc())
        .first()
    )

    from backend.credit_service import (
        get_user_credit_balance,
        resolve_company_billing_user,
    )

    pool_user = resolve_company_billing_user(db, company_id)
    company_credit_balance = (
        get_user_credit_balance(db, pool_user) if pool_user else 0.0
    )

    return {
        "company_id": company.id,
        "company_name": company.name,
        "plan": {
            "id": plan.id,
            "name": plan.name,
            "slug": plan.slug,
            "price_monthly": plan.price_monthly,
            "price_yearly": plan.price_yearly,
            "team_seat_limit": plan.team_seat_limit,
        }
        if plan
        else None,
        "subscription_status": sub.status if sub else "none",
        "seats": _seats_payload(db, company),
        "company_credit_balance": company_credit_balance,
        "pending_transaction": _company_tx_payload(pending_tx) if pending_tx else None,
        "billing_email": company.billing_email,
        "billing_address": company.billing_address,
        "tax_id": company.tax_id,
        "kyb_status": company.kyb_status,
        "kyb_documents": _kyb_documents(company),
    }


@router.post("/subscribe")
def subscribe_company(
    data: OrgSubscribeRequest,
    request: Request,
    current_user: User = Depends(require_org_admin),
    db: Session = Depends(get_db),
):
    """Start a company subscription purchase.

    Creates a company-scoped pending Transaction + a pending Subscription
    row (owned by the org admin). Admin approval later activates the plan
    and raises the company's seat limit.
    """
    company_id = current_user._company_id
    company = _get_company(db, company_id)

    if data.billing_cycle not in ("monthly", "yearly"):
        raise HTTPException(
            status_code=400, detail="billing_cycle must be monthly or yearly"
        )

    plan = (
        db.query(SubscriptionPlan).filter(SubscriptionPlan.id == data.plan_id).first()
    )
    if not plan or not plan.is_active:
        raise HTTPException(status_code=404, detail="Plan not found")

    if plan.target_audience != "recruiter":
        raise HTTPException(
            status_code=400, detail="Invalid plan for company subscription"
        )

    price = plan.price_yearly if data.billing_cycle == "yearly" else plan.price_monthly
    if not price or price <= 0:
        raise HTTPException(status_code=400, detail="Plan has no price")

    existing = (
        db.query(Transaction)
        .filter(
            Transaction.company_id == company_id,
            Transaction.status == "pending",
            Transaction.description.like(f"{COMPANY_SUB_MARKER}%"),
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=400, detail="A pending company subscription already exists"
        )

    active = _current_company_subscription(db, company_id)
    if active and active.status in ("active", "trialing", "past_due"):
        raise HTTPException(
            status_code=409,
            detail=(
                "Your company already has an active subscription. "
                "Cancel it before purchasing a new one."
            ),
        )

    stamp_duty = STAMP_DUTY
    amount_ttc = float(price)
    if amount_ttc > stamp_duty:
        amount_ht = (amount_ttc - stamp_duty) / (1 + TVA_RATE)
        tva_amount = amount_ht * TVA_RATE
    else:
        amount_ht = 0.0
        tva_amount = 0.0

    tx = Transaction(
        user_id=current_user.id,
        company_id=company_id,
        amount=amount_ttc,
        currency="TND",
        status="pending",
        description=f"{COMPANY_SUB_MARKER} to {plan.name} ({data.billing_cycle})",
        amount_ht=round(amount_ht, 3),
        tva_amount=round(tva_amount, 3),
        stamp_duty=stamp_duty,
        amount_ttc=amount_ttc,
    )
    db.add(tx)
    db.flush()

    plan_version = (
        db.query(PlanVersion)
        .filter(PlanVersion.plan_id == plan.id)
        .order_by(PlanVersion.version.desc())
        .first()
    )

    sub = Subscription(
        user_id=current_user.id,
        company_id=company_id,
        plan_id=plan.id,
        plan_version_id=plan_version.id if plan_version else None,
        target_audience="recruiter",
        status="pending",
        billing_cycle=data.billing_cycle,
        notes=f"Company subscription for {company.name}",
    )
    db.add(sub)
    db.flush()

    db.add(
        AuditLog(
            user_id=current_user.id,
            company_id=company_id,
            action="org_subscribe",
            target_id=str(tx.id),
            details=(
                f"Org admin {get_user_email(current_user)} started company subscription "
                f"tx #{tx.id} for plan {plan.name} ({data.billing_cycle}) — awaiting proof"
            ),
            ip_address=request.client.host,
        )
    )
    db.commit()
    return {
        "message": "Subscription purchase created. Upload your bank proof to complete the payment.",
        "transaction_id": tx.id,
        "amount_ttc": amount_ttc,
    }


@router.post("/receipt/{tx_id}")
async def upload_company_receipt(
    tx_id: int,
    request: Request,
    file: UploadFile = File(...),
    current_user: User = Depends(require_org_admin),
    db: Session = Depends(get_db),
):
    """Attach a manual bank transfer proof to the company's pending purchase."""
    company_id = current_user._company_id
    tx = (
        db.query(Transaction)
        .filter(Transaction.id == tx_id, Transaction.company_id == company_id)
        .first()
    )
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
    if tx.status != "pending":
        raise HTTPException(status_code=409, detail="Transaction is not pending")

    ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}
    ALLOWED_MIME_TYPES = {"image/png", "image/jpeg", "application/pdf"}
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400, detail="Only PDF, PNG, and JPG files are allowed"
        )
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=400, detail="Invalid file type")

    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 5MB)")

    from backend.file_security import scan_for_malware, validate_file_content
    from backend.security import secure_filename

    is_valid, err_msg = validate_file_content(
        content, file_ext.lstrip("."), 5 * 1024 * 1024
    )
    if not is_valid:
        raise HTTPException(status_code=400, detail=err_msg)
    is_safe, scan_result = scan_for_malware(content, file.filename)
    if not is_safe:
        raise HTTPException(status_code=400, detail=scan_result)

    safe_name = secure_filename(file.filename)
    file_ext = os.path.splitext(safe_name)[1].lower()
    timestamp = datetime.now(UTC).replace(tzinfo=None).strftime("%Y%m%d%H%M%S")
    filename = f"company_receipt_{company_id}_{tx.id}_{timestamp}{file_ext}"
    upload_dir = "uploads/company_receipts"
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, filename)
    with open(file_path, "wb") as buffer:
        buffer.write(content)

    tx.proof_url = f"{upload_dir}/{filename}"
    tx.proof_status = "uploaded"
    tx.proof_file_size = len(content)
    tx.proof_file_type = file.content_type
    db.add(
        AuditLog(
            user_id=current_user.id,
            company_id=company_id,
            action="org_receipt_upload",
            target_id=str(tx.id),
            details=f"Org admin {get_user_email(current_user)} uploaded bank proof for tx #{tx.id}",
            ip_address=request.client.host,
        )
    )
    db.commit()
    return {
        "message": "Receipt uploaded. The company subscription is pending admin approval.",
        "transaction_id": tx.id,
    }


@router.get("/transactions")
def company_transactions(
    current_user: User = Depends(require_org_admin),
    db: Session = Depends(get_db),
):
    company_id = current_user._company_id
    txs = (
        db.query(Transaction)
        .filter(
            Transaction.company_id == company_id,
            Transaction.description.like(f"{COMPANY_SUB_MARKER}%"),
        )
        .order_by(Transaction.id.desc())
        .limit(50)
        .all()
    )
    return {"transactions": [_company_tx_payload(t) for t in txs]}


@router.get("/invoices")
def company_invoices(
    current_user: User = Depends(require_org_admin),
    db: Session = Depends(get_db),
):
    company_id = current_user._company_id
    invoices = (
        db.query(Invoice)
        .filter(Invoice.company_id == company_id)
        .order_by(Invoice.id.desc())
        .limit(50)
        .all()
    )
    return {"invoices": [_invoice_payload(i) for i in invoices]}


@router.get("/invoices/{invoice_id}/download")
def download_company_invoice(
    invoice_id: int,
    current_user: User = Depends(require_org_admin),
    db: Session = Depends(get_db),
):
    company_id = current_user._company_id
    invoice = (
        db.query(Invoice)
        .filter(Invoice.id == invoice_id, Invoice.company_id == company_id)
        .first()
    )
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    from backend.pdf_generator import generate_invoice_pdf

    pdf_data = {
        "invoice_number": invoice.invoice_number,
        "date": invoice.created_at.strftime("%Y-%m-%d")
        if invoice.created_at
        else "N/A",
        "client_name": invoice.client_name or "Valued Client",
        "client_mf": invoice.client_mf or "N/A",
        "client_address": invoice.client_address or "N/A",
        "amount_ht": invoice.amount_ht or 0.0,
        "tva_rate": invoice.tva_rate or 19.0,
        "tva_amount": invoice.tva_amount or 0.0,
        "stamp_duty": invoice.stamp_duty or 1.0,
        "total_ttc": invoice.total_ttc or 0.0,
        "status": invoice.status or "paid",
        "transaction_id": invoice.transaction_id or "N/A",
        "description": "Candway Talent Intelligence Platform - Company Plan",
    }
    pdf_bytes = generate_invoice_pdf(pdf_data)

    from fastapi.responses import Response

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=Invoice_{invoice.invoice_number}.pdf"
        },
    )


@router.get("/kyb")
def get_company_kyb(
    current_user: User = Depends(require_org_admin),
    db: Session = Depends(get_db),
):
    company = _get_company(db, current_user._company_id)
    return {
        "company_id": company.id,
        "company_name": company.name,
        "billing_email": company.billing_email,
        "billing_address": company.billing_address,
        "tax_id": company.tax_id,
        "kyb_status": company.kyb_status,
        "kyb_documents": _kyb_documents(company),
    }


@router.post("/kyb")
def submit_company_kyb(
    data: OrgKybSubmit,
    request: Request,
    current_user: User = Depends(require_org_admin),
    db: Session = Depends(get_db),
):
    """Submit company billing/KYB details for verification."""
    company = _get_company(db, current_user._company_id)
    email = (data.billing_email or "").strip().lower()
    if not email:
        raise HTTPException(status_code=400, detail="billing_email is required")
    company.billing_email = email
    company.billing_address = (data.billing_address or "").strip() or None
    company.tax_id = (data.tax_id or "").strip() or None
    company.kyb_status = "pending"
    db.add(
        AuditLog(
            user_id=current_user.id,
            company_id=company.id,
            action="org_kyb_submit",
            target_id=str(company.id),
            details=f"Org admin {get_user_email(current_user)} submitted KYB for {company.name}",
            ip_address=request.client.host,
        )
    )
    db.commit()
    return {
        "message": "KYB details submitted for verification.",
        "kyb_status": company.kyb_status,
    }


@router.post("/kyb/documents")
async def upload_kyb_documents(
    request: Request,
    files: List[UploadFile] = File(...),
    current_user: User = Depends(require_org_admin),
    db: Session = Depends(get_db),
):
    """Attach KYB proof documents (MF / registre de commerce) for admin review."""
    company = _get_company(db, current_user._company_id)

    ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}
    ALLOWED_MIME_TYPES = {"image/png", "image/jpeg", "application/pdf"}
    MAX_DOCS = 6
    if not files or len(files) > MAX_DOCS:
        raise HTTPException(
            status_code=400,
            detail=f"Provide between 1 and {MAX_DOCS} documents",
        )

    from backend.file_security import scan_for_malware, validate_file_content
    from backend.security import secure_filename

    upload_dir = "uploads/company_kyb"
    os.makedirs(upload_dir, exist_ok=True)

    saved = []
    for file in files:
        file_ext = os.path.splitext(file.filename or "")[1].lower()
        if file_ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Only PDF, PNG, and JPG files are allowed: {file.filename}",
            )
        if file.content_type not in ALLOWED_MIME_TYPES:
            raise HTTPException(
                status_code=400, detail=f"Invalid file type: {file.filename}"
            )

        content = await file.read()
        if len(content) > 5 * 1024 * 1024:
            raise HTTPException(
                status_code=400, detail=f"File too large (max 5MB): {file.filename}"
            )

        is_valid, err_msg = validate_file_content(
            content, file_ext.lstrip("."), 5 * 1024 * 1024
        )
        if not is_valid:
            raise HTTPException(status_code=400, detail=err_msg)
        is_safe, scan_result = scan_for_malware(content, file.filename)
        if not is_safe:
            raise HTTPException(status_code=400, detail=scan_result)

        safe_name = secure_filename(file.filename or "document")
        timestamp = datetime.now(UTC).replace(tzinfo=None).strftime("%Y%m%d%H%M%S")
        filename = f"kyb_{company.id}_{timestamp}_{len(saved)}{os.path.splitext(safe_name)[1].lower()}"
        file_path = os.path.join(upload_dir, filename)
        with open(file_path, "wb") as buffer:
            buffer.write(content)
        saved.append({"name": safe_name, "url": f"{upload_dir}/{filename}"})

    existing = _kyb_documents(company)
    existing.extend(saved)
    company.kyb_documents = json.dumps(existing)
    if company.kyb_status != "approved":
        company.kyb_status = "pending"

    db.add(
        AuditLog(
            user_id=current_user.id,
            company_id=company.id,
            action="org_kyb_documents",
            target_id=str(company.id),
            details=(
                f"Org admin {get_user_email(current_user)} uploaded {len(saved)} "
                f"KYB document(s) for {company.name}"
            ),
            ip_address=request.client.host,
        )
    )
    db.commit()
    return {
        "message": "KYB documents uploaded for verification.",
        "kyb_status": company.kyb_status,
        "documents": existing,
    }


@router.post("/cancel")
def cancel_company_subscription(
    request: Request,
    current_user: User = Depends(require_org_admin),
    db: Session = Depends(get_db),
):
    """Cancel the company's active subscription (at period end)."""
    company_id = current_user._company_id
    _company = _get_company(db, company_id)
    sub = _current_company_subscription(db, company_id)
    if not sub or sub.status not in ("active", "trialing", "pending", "past_due"):
        raise HTTPException(
            status_code=409, detail="No active company subscription to cancel"
        )

    sub.cancel_at_period_end = True
    db.add(
        AuditLog(
            user_id=current_user.id,
            company_id=company_id,
            action="org_cancel_subscription",
            target_id=str(sub.id),
            details=f"Org admin {get_user_email(current_user)} canceled company subscription #{sub.id}",
            ip_address=request.client.host,
        )
    )
    db.commit()
    return {
        "message": "Company subscription will cancel at the end of the current period."
    }


# =============================================================================
# Admin approval helpers (imported by backend/routers/admin/subscriptions.py)
# =============================================================================


def create_company_invoice(db: Session, company: Company, tx: Transaction) -> Invoice:
    """Create a company-scoped Invoice from an approved company transaction.

    Uses the company's own billing/KYB details as the client (B2B) instead
    of the org admin's personal details.
    """
    year = datetime.now(UTC).year
    last_invoice = (
        db.query(Invoice)
        .filter(Invoice.invoice_number.like(f"INV-{year}-%"))
        .order_by(Invoice.id.desc())
        .with_for_update()
        .first()
    )
    if last_invoice:
        try:
            last_seq = int(last_invoice.invoice_number.split("-")[-1])
            new_seq = last_seq + 1
        except (ValueError, IndexError):
            new_seq = 1
    else:
        new_seq = 1
    invoice_number = f"INV-{year}-{new_seq:04d}"

    invoice = Invoice(
        invoice_number=invoice_number,
        user_id=tx.user_id,
        company_id=company.id,
        transaction_id=tx.id,
        amount_ht=tx.amount_ht or 0.0,
        tva_rate=19.0,
        tva_amount=tx.tva_amount or 0.0,
        stamp_duty=tx.stamp_duty or 1.0,
        total_ttc=tx.amount_ttc or (tx.amount or 0.0),
        client_name=company.name,
        client_mf=company.tax_id or None,
        client_address=company.billing_address or "N/A",
        status="paid",
    )
    db.add(invoice)
    db.flush()
    return invoice


def approve_company_subscription(
    db: Session,
    tx: Transaction,
    admin_user_id: int,
) -> dict:
    """Activate a company subscription after a successful payment.

    Sets the company's plan, raises the recruiter seat limit to the plan's
    team_seat_limit, activates the pending Subscription row, generates the
    B2B invoice and logs an audit + history row. Returns a payload dict.
    """
    company = db.query(Company).filter(Company.id == tx.company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    sub = _current_company_subscription(db, company.id)
    if not sub or sub.status != "pending":
        raise HTTPException(
            status_code=409, detail="No pending company subscription to approve"
        )

    # A company must only ever have one active subscription. Deactivate any
    # other active/trialing/past_due rows before activating the new one.
    for other in (
        db.query(Subscription)
        .filter(
            Subscription.company_id == company.id,
            Subscription.id != sub.id,
            Subscription.status.in_(("active", "trialing", "past_due")),
        )
        .all()
    ):
        other.status = "canceled"
        other.canceled_at = datetime.now(UTC).replace(tzinfo=None, microsecond=0)
        db.add(
            SubscriptionHistory(
                subscription_id=other.id,
                user_id=other.user_id,
                company_id=company.id,
                action="canceled",
                to_plan_id=other.plan_id,
                admin_user_id=admin_user_id,
                notes="Superseded by a newly approved company subscription",
            )
        )

    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == sub.plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    now = datetime.now(UTC).replace(tzinfo=None, microsecond=0)
    period_end = (
        now + timedelta(days=365)
        if sub.billing_cycle == "yearly"
        else now + timedelta(days=30)
    )

    sub.status = "active"
    sub.started_at = now
    sub.current_period_start = now
    sub.current_period_end = period_end
    sub.cancel_at_period_end = False
    sub.canceled_at = None
    sub.last_payment_transaction_id = tx.id

    company.plan_id = plan.id
    company.subscription_status = "active"
    company.tier = plan.slug or company.tier
    if plan.team_seat_limit and plan.team_seat_limit > 0:
        company.max_users = plan.team_seat_limit

    db.add(
        SubscriptionHistory(
            subscription_id=sub.id,
            user_id=sub.user_id,
            company_id=company.id,
            action="activated",
            to_plan_id=plan.id,
            amount_paid=tx.amount_ttc or tx.amount,
            transaction_id=tx.id,
            admin_user_id=admin_user_id,
            notes="Company subscription approved by admin",
        )
    )
    db.add(
        AuditLog(
            user_id=admin_user_id,
            company_id=company.id,
            action="approve_company_subscription",
            target_id=str(tx.id),
            details=(
                f"Admin approved company subscription tx #{tx.id} "
                f"for company #{company.id} plan {plan.name} — seats set to {company.max_users}"
            ),
        )
    )
    db.flush()

    invoice = None
    try:
        invoice = create_company_invoice(db, company, tx)
    except Exception as e:
        logger.error(f"Failed to create company invoice for tx {tx.id}: {e}")

    # Grant the plan's monthly credit allocation immediately (the daily
    # 01:00 cron grants at period_start; doing it here gives the company
    # its credits right after approval instead of up to ~24h later).
    # The provider_ref mirrors the cron exactly, so the cron's idempotency
    # key collides and it will not double-grant.
    if plan.credits_monthly:
        from backend.credit_service import grant_credits, resolve_company_billing_user

        billing_user = resolve_company_billing_user(db, company.id)
        if billing_user is None:
            billing_user = db.query(User).filter(User.id == sub.user_id).first()
        if billing_user:
            try:
                grant_credits(
                    db,
                    billing_user,
                    plan.credits_monthly,
                    provider="system",
                    provider_ref=f"sub-{sub.id}-period-{sub.current_period_start.isoformat()}",
                    note=f"Monthly credit allocation for {plan.slug}",
                    tx_type="grant",
                )
            except Exception as ge:
                logger.error(
                    f"approve_company_subscription credit grant failed "
                    f"for sub {sub.id}: {ge}"
                )

    return {
        "message": "Company subscription approved",
        "company_id": company.id,
        "plan": plan.slug,
        "seats": company.max_users,
        "invoice_id": invoice.id if invoice else None,
    }
