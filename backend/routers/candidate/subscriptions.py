import logging
import os
from datetime import UTC, datetime
from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
)
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.candidate_subscription_service import CandidateSubscriptionService
from backend.database import (
    CompanyMember,
    Invoice,
    SubscriptionPlan,
    SupportTicket,
    SystemConfig,
    Transaction,
    User,
)
from backend.dependencies import get_current_user, get_db
from backend.profile_helpers import (
    get_user_email,
    get_user_name,
    get_user_subscription_status,
    get_user_tier,
)

router = APIRouter(tags=["candidate"])

logger = logging.getLogger(__name__)


class ManualUpgradeRequest(BaseModel):
    plan_id: int
    notes: Optional[str] = None


class UpgradeRequest(BaseModel):
    plan_id: int
    message: Optional[str] = "I would like to upgrade my plan."


@router.get("/subscription/usage")
def get_subscription_usage_consolidated(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    if current_user.role != "candidate":
        return {
            "plan_name": "N/A",
            "plan_slug": "n/a",
            "cv_uploads": {"used": 0, "limit": 0, "unlimited": False},
            "ai_analyses": {"used": 0, "limit": 0, "unlimited": False},
            "pdf_downloads": {"used": 0, "limit": 0, "unlimited": False},
            "reset_date": None,
            "tier": get_user_tier(current_user) or "free",
            "subscription_status": get_user_subscription_status(current_user),
        }
    stats = CandidateSubscriptionService.get_usage_stats(current_user, db)
    stats["tier"] = get_user_tier(current_user) or "free"
    stats["subscription_status"] = get_user_subscription_status(current_user)
    return stats


@router.get("/plans")
def list_candidate_plans(db: Session = Depends(get_db)):
    plans = (
        db.query(SubscriptionPlan)
        .filter(
            SubscriptionPlan.target_audience == "candidate",
            SubscriptionPlan.is_active,
        )
        .order_by(SubscriptionPlan.price_monthly.asc())
        .all()
    )
    return plans


@router.post("/upgrade")
def request_upgrade(
    req: UpgradeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != "candidate":
        raise HTTPException(status_code=403, detail="Only candidates can request upgrades from this endpoint")

    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == req.plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Selected plan not found")

    # Resolve the candidate's tenant from their active company membership.
    # User does not expose company_id as a SQLAlchemy field; tenant context
    # is represented by CompanyMember and optionally cached on _company_id.
    company_id = getattr(current_user, "_company_id", None)

    if company_id is not None:
        membership = (
            db.query(CompanyMember)
            .filter(
                CompanyMember.user_id == current_user.id,
                CompanyMember.company_id == company_id,
                CompanyMember.is_active.is_(True),
            )
            .first()
        )
        if membership is None:
            company_id = None

    if company_id is None:
        membership = (
            db.query(CompanyMember)
            .filter(
                CompanyMember.user_id == current_user.id,
                CompanyMember.is_active.is_(True),
            )
            .order_by(CompanyMember.id.asc())
            .first()
        )
        if membership:
            company_id = membership.company_id

    if company_id is None:
        raise HTTPException(
            status_code=400,
            detail="Candidate is not associated with an active company",
        )

    existing = (
        db.query(SupportTicket)
        .filter(
            SupportTicket.user_id == current_user.id,
            SupportTicket.category == "upgrade",
            SupportTicket.status == "open",
        )
        .first()
    )
    if existing:
        return {
            "message": "You already have a pending upgrade request. Our team will contact you soon.",
            "status": "pending",
        }
    ticket = SupportTicket(
        company_id=company_id,
        user_id=current_user.id,
        subject=f"UPGRADE REQUEST: {plan.name}",
        category="upgrade",
        priority="high",
        description=f"Candidate {get_user_name(current_user)} ({get_user_email(current_user)}) wants to upgrade to {plan.name}.\n\nMessage: {req.message}",
        status="open",
    )
    db.add(ticket)
    db.commit()
    return {
        "message": "Upgrade request submitted successfully. Our team will contact you for payment verification.",
        "status": "success",
    }


@router.get("/payment-config")
def get_payment_config(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    settings = (
        db.query(SystemConfig)
        .filter(
            SystemConfig.key.in_(
                [
                    "bank_name",
                    "bank_account_name",
                    "bank_account_number",
                    "bank_iban",
                    "payment_instructions",
                ]
            )
        )
        .all()
    )
    config = {s.key: s.value for s in settings}
    return config


@router.post("/upgrade/manual")
async def request_manual_upgrade(
    request: Request,
    plan_id: int = Form(...),
    notes: Optional[str] = Form(None),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

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
    filename = f"receipt_{current_user.id}_{timestamp}{file_ext}"
    upload_dir = "uploads/receipts"
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, filename)
    with open(file_path, "wb") as buffer:
        buffer.write(content)
    from backend.database import Transaction

    existing_tx = (
        db.query(Transaction)
        .filter(Transaction.user_id == current_user.id, Transaction.status == "pending")
        .first()
    )
    if existing_tx:
        raise HTTPException(
            status_code=400, detail="You already have a pending upgrade request."
        )

    stamp_duty = 1.000
    tva_rate = 0.19
    amount_ttc = float(plan.price_monthly)
    if amount_ttc > stamp_duty:
        amount_ht = (amount_ttc - stamp_duty) / (1 + tva_rate)
        tva_amount = amount_ht * tva_rate
    else:
        amount_ht = 0.0
        tva_amount = 0.0
    tx = Transaction(
        user_id=current_user.id,
        amount=amount_ttc,
        currency="TND",
        status="pending",
        description=f"Manual Upgrade to {plan.name}",
        proof_url=f"{upload_dir}/{filename}",
        proof_status="uploaded",
        proof_file_size=len(content),
        proof_file_type=file.content_type,
        amount_ht=round(amount_ht, 3),
        tva_amount=round(tva_amount, 3),
        stamp_duty=stamp_duty,
        amount_ttc=amount_ttc,
    )
    db.add(tx)
    cp = getattr(current_user, "candidate_profile", None)
    if cp:
        cp.subscription_status = "pending_approval"
        cp.subscription_plan = plan.slug
    db.commit()
    return {
        "message": "Receipt uploaded. upgrade pending approval.",
        "status": "pending_approval",
    }


@router.get("/invoices/{tx_id}/download")
def download_candidate_invoice(
    tx_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tx = db.query(Transaction).filter(Transaction.id == tx_id).first()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
    if tx.user_id != current_user.id:
        raise HTTPException(
            status_code=403, detail="Not authorized to access this invoice"
        )
    invoice = db.query(Invoice).filter(Invoice.transaction_id == tx.id).first()
    if not invoice:
        # Bug H-6: previously this fabricated a "MockInvoice" from the
        # transaction and served it as a real invoice. Only a paid
        # transaction has a legally valid invoice, so create a real
        # persisted Invoice row (or refuse the download) instead.
        if tx.status != "succeeded":
            raise HTTPException(
                status_code=404,
                detail="Invoice is not available until the payment has been approved.",
            )
        from backend.routers.admin.invoices import _create_invoice_internal

        if not tx.amount and not (tx.amount_ht or 0):
            raise HTTPException(
                status_code=404, detail="This transaction has no invoicable amount."
            )

        invoice = _create_invoice_internal(
            db,
            user_id=current_user.id,
            amount=tx.amount or 0,
            transaction_id=tx.id,
            is_ttc=True,
            company_id=tx.company_id,
        )
        if not invoice:
            raise HTTPException(
                status_code=404,
                detail="Could not generate an invoice for this transaction.",
            )

    from backend.pdf_generator import generate_invoice_pdf

    pdf_path = generate_invoice_pdf(invoice)
    from fastapi.responses import FileResponse

    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=f"Invoice-{invoice.invoice_number}.pdf",
    )
