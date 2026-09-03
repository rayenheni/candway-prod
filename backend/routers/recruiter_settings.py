import os
from datetime import UTC, datetime
from typing import List, Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    Response,
    UploadFile,
)
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from backend.database import (
    Company,
    CompanyMember,
    EmailTemplate,
    Invoice,
    SubscriptionPlan,
    SystemConfig,
    Transaction,
    User,
)
from backend.dependencies import (
    get_db,
    require_recruiter,
)
from backend.logger import logger
from backend.models.evaluation.profile import RecruiterProfile
from backend.pdf_generator import generate_invoice_pdf
from backend.profile_helpers import (
    get_user_usage_ai_interviews,
    get_user_usage_cvs,
    get_user_usage_jobs,
)
from backend.schemas import InvoiceResponse, RecruiterSettingsUpdate
from backend.schemas import SubscriptionPlan as SubscriptionPlanSchema
from backend.tenant import get_current_company_id

router = APIRouter(prefix="/recruiter", tags=["Recruiter Settings"])

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


def _utcnow():
    return datetime.now(UTC).replace(tzinfo=None)


def _is_company_managed(db: Session, recruiter: User) -> bool:
    """True when the recruiter is a member of a company.

    Company-managed recruiters only see their usage and limits — the company
    (org admin) owns subscriptions, billing and financial documents.
    """
    membership = (
        db.query(CompanyMember)
        .filter(
            CompanyMember.user_id == recruiter.id,
            CompanyMember.is_active == True,  # noqa: E712
        )
        .first()
    )
    return membership is not None


def _assert_not_company_managed(db: Session, recruiter: User) -> None:
    """403 when the recruiter's subscription is managed by their company."""
    if _is_company_managed(db, recruiter):
        raise HTTPException(
            status_code=403,
            detail=(
                "Your subscription and billing are managed by your company. "
                "Contact your company admin or use the Company workspace."
            ),
        )


# --- SCHEMAS ---
class TestEmailRequest(BaseModel):
    email: Optional[str] = None


class EmailTemplateCreate(BaseModel):
    name: str
    subject: str
    body_html: str
    is_default: bool = False


class EmailTemplateResponse(EmailTemplateCreate):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# --- SETTINGS ENDPOINTS ---


@router.get("/settings")
def get_recruiter_settings(recruiter: User = Depends(require_recruiter)):
    profile = getattr(recruiter, "recruiter_profile", None)
    return {
        "company_name": profile.company_name if profile else "",
        "company_description": profile.company_description if profile else "",
        "company_logo_url": profile.company_logo_url if profile else "",
        "smtp_host": profile.smtp_host if profile else "",
        "smtp_port": profile.smtp_port if profile else None,
        "smtp_user": profile.smtp_user if profile else "",
        "smtp_password_set": bool(profile.smtp_password) if profile else False,
    }


@router.post("/settings")
def update_recruiter_settings(
    settings_update: RecruiterSettingsUpdate,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    profile = getattr(recruiter, "recruiter_profile", None)
    if not profile:
        profile = RecruiterProfile(user_id=recruiter.id)
        db.add(profile)
        db.flush()
    for key, value in settings_update.model_dump(exclude_unset=True).items():
        setattr(profile, key, value)
    db.commit()
    return {"message": "Settings updated"}


@router.post("/company-logo")
async def upload_company_logo(
    request: Request,
    file: UploadFile = File(...),
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    if not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=400, detail="Invalid file type. Only image files are allowed."
        )

    # FIX ISSUE-06: enforce 5MB max size before writing to disk
    MAX_SIZE = 5 * 1024 * 1024  # 5MB
    content = await file.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(
            status_code=400, detail="Logo file too large. Maximum allowed size is 5MB."
        )

    from backend.file_security import scan_for_malware, validate_file_content
    from backend.security import secure_filename

    safe_name = secure_filename(file.filename)
    file_ext = safe_name.split(".")[-1].lower()
    is_valid, err_msg = validate_file_content(content, file_ext, 5 * 1024 * 1024)
    if not is_valid:
        raise HTTPException(status_code=400, detail=err_msg)
    is_safe, scan_result = scan_for_malware(content, file.filename)
    if not is_safe:
        raise HTTPException(status_code=400, detail=scan_result)

    filename = f"company_{recruiter.id}_{int(_utcnow().timestamp())}.{file_ext}"
    file_path = os.path.join(UPLOAD_DIR, filename)

    with open(file_path, "wb") as buffer:
        buffer.write(content)

    base_url = str(request.base_url).rstrip("/")
    logo_url = f"{base_url}/uploads/{filename}"
    from backend.models.evaluation.profile import RecruiterProfile

    profile = (
        db.query(RecruiterProfile)
        .filter(RecruiterProfile.user_id == recruiter.id)
        .first()
    )
    if profile:
        profile.company_logo_url = logo_url

    # Company logo is company-owned: mirror it onto the tenant record so it
    # appears on the public job board (and any company-scoped surface).
    company_id = getattr(recruiter, "_company_id", None)
    if company_id:
        from backend.models.foundation.company import Company

        company = db.query(Company).filter(Company.id == company_id).first()
        if company:
            company.logo_url = logo_url
    db.commit()
    return {"message": "Logo updated", "company_logo_url": logo_url}


@router.post("/email/test")
def send_test_email(
    payload: TestEmailRequest, recruiter: User = Depends(require_recruiter)
):
    profile = getattr(recruiter, "recruiter_profile", None)
    smtp_host = profile.smtp_host if profile else None
    smtp_port = profile.smtp_port if profile else None
    smtp_user = profile.smtp_user if profile else None
    smtp_password = profile.smtp_password if profile else None
    target_email = payload.email or recruiter.email
    if not all([smtp_host, smtp_port, smtp_user, smtp_password]):
        raise HTTPException(status_code=400, detail="Incomplete SMTP settings")

    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    try:
        msg = MIMEMultipart()
        msg["From"] = smtp_user
        msg["To"] = target_email
        msg["Subject"] = "Candway SMTP Test"
        body = f"SMTP Configured Correctly!\nHost: {smtp_host}"
        msg.attach(MIMEText(body, "plain"))

        server = smtplib.SMTP(smtp_host, smtp_port)
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.sendmail(smtp_user, target_email, msg.as_string())
        server.quit()
        return {"message": f"Test email sent to {target_email}"}
    except Exception as e:
        logger.error(f"SMTP test failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=400,
            detail="SMTP configuration test failed. Verify your SMTP settings.",
        )


# --- TEMPLATE ENDPOINTS ---


@router.get("/templates", response_model=List[EmailTemplateResponse])
def get_templates(
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
    company_id: int = Depends(get_current_company_id),
):
    return db.query(EmailTemplate).filter(EmailTemplate.company_id == company_id).all()


@router.post("/templates", response_model=EmailTemplateResponse)
def create_template(
    template: EmailTemplateCreate,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
    company_id: int = Depends(get_current_company_id),
):
    if template.is_default:
        db.query(EmailTemplate).filter(
            EmailTemplate.company_id == company_id, EmailTemplate.is_default
        ).update({"is_default": False})

    from backend.security import sanitize_content

    safe_body = sanitize_content(template.body_html)
    new_tpl = EmailTemplate(
        recruiter_id=recruiter.id,
        company_id=company_id,
        name=template.name,
        subject=template.subject,
        body_html=safe_body,
        is_default=template.is_default,
    )
    db.add(new_tpl)
    db.commit()
    db.refresh(new_tpl)
    return new_tpl


@router.put("/templates/{template_id}")
def update_template(
    template_id: int,
    template: EmailTemplateCreate,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
    company_id: int = Depends(get_current_company_id),
):
    tpl = (
        db.query(EmailTemplate)
        .filter(EmailTemplate.id == template_id, EmailTemplate.company_id == company_id)
        .first()
    )
    if not tpl:
        raise HTTPException(status_code=404, detail="Template not found")

    if template.is_default:
        db.query(EmailTemplate).filter(
            EmailTemplate.company_id == company_id, EmailTemplate.is_default
        ).update({"is_default": False})

    from backend.security import sanitize_content

    tpl.name, tpl.subject, tpl.body_html, tpl.is_default = (
        template.name,
        template.subject,
        sanitize_content(template.body_html),
        template.is_default,
    )
    db.commit()
    return {"message": "Template updated"}


@router.delete("/templates/{template_id}")
def delete_template(
    template_id: int,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
    company_id: int = Depends(get_current_company_id),
):
    db.query(EmailTemplate).filter(
        EmailTemplate.id == template_id, EmailTemplate.company_id == company_id
    ).delete()
    db.commit()
    return {"message": "Template deleted"}


@router.post("/templates/seed")
def seed_templates(
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
    company_id: int = Depends(get_current_company_id),
):
    if (
        db.query(EmailTemplate).filter(EmailTemplate.company_id == company_id).count()
        > 0
    ):
        return {"message": "Templates already exist"}

    default_templates = [
        {
            "name": "Professional Invitation",
            "subject": "Interview Invitation - {{job_title}}",
            "body_html": "<p>Dear <strong>{{candidate_name}}</strong>, please <a href='{{INTERVIEW_LINK}}'>click here</a> for your interview.</p>",
            "is_default": True,
        }
    ]
    for t in default_templates:
        db.add(EmailTemplate(recruiter_id=recruiter.id, company_id=company_id, **t))
    db.commit()
    return {"message": "Templates seeded"}


# --- SUBSCRIPTION ENDPOINTS ---


@router.post("/subscription/upgrade")
async def upgrade_subscription(
    plan: str = Form(...),
    proof_file: UploadFile = File(None),
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
    company_id: int = Depends(get_current_company_id),
):
    _assert_not_company_managed(db, recruiter)
    # Rate limiting: limit to 2 upgrade attempts per 5 minutes to prevent spam
    from backend.redis_rate_limiter import check_rate_limit as check_upgrade_rate_limit

    is_allowed, rate_metadata = await check_upgrade_rate_limit(
        f"upgrade_req_{recruiter.id}", max_requests=2, window_seconds=300
    )
    retry_after = rate_metadata.get("retry_after", 0)
    if not is_allowed:
        raise HTTPException(
            status_code=429,
            detail=f"Too many upgrade requests. Please wait {retry_after} seconds before trying again.",
        )

    # SECURE: Validate plan strictly from database - never trust client input directly
    db_plan = (
        db.query(SubscriptionPlan)
        .filter(SubscriptionPlan.slug == plan, SubscriptionPlan.is_active)
        .first()
    )
    if not db_plan:
        raise HTTPException(status_code=400, detail="Invalid or inactive plan")

    # Additional security: Only allow upgrade from 'free' plan, never downgrade or lateral move
    # unless explicitly approved by admin
    upgrade_profile = getattr(recruiter, "recruiter_profile", None)
    current_plan = getattr(upgrade_profile, "subscription_plan", None) or "free"
    current_status = getattr(upgrade_profile, "subscription_status", None) or ""
    if current_plan != "free" and current_status == "active":
        if db_plan.slug == "free":
            # Downgrade - allowed but flagged
            logger.info(f"User {recruiter.id} initiated downgrade to free tier")
        elif db_plan.slug != current_plan:
            # Lateral move between paid plans - requires admin approval
            logger.info(
                f"User {recruiter.id} changing from {current_plan} to {db_plan.slug}"
            )

    proof_path = None
    if proof_file:
        # Security Validation
        ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".pdf"}
        ext = os.path.splitext(proof_file.filename)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail="Invalid file type. Only PNG, JPG, or PDF allowed.",
            )

        # Check size (5MB limit)
        content = await proof_file.read()
        if len(content) > 5 * 1024 * 1024:
            raise HTTPException(
                status_code=400, detail="File too large. Maximum size is 5MB."
            )

        if proof_file.content_type not in {
            "image/png",
            "image/jpeg",
            "application/pdf",
        }:
            raise HTTPException(status_code=400, detail="Invalid content type")

        from backend.file_security import scan_for_malware, validate_file_content

        is_valid, err_msg = validate_file_content(
            content, ext.lstrip("."), 5 * 1024 * 1024
        )
        if not is_valid:
            raise HTTPException(status_code=400, detail=err_msg)
        is_safe, scan_result = scan_for_malware(content, proof_file.filename)
        if not is_safe:
            raise HTTPException(status_code=400, detail=scan_result)

        # Sanitize filename
        from backend.security import secure_filename

        safe_filename = secure_filename(proof_file.filename)

        proof_dir = os.path.join(UPLOAD_DIR, "payment_proofs")
        os.makedirs(proof_dir, exist_ok=True)
        proof_path = os.path.join(proof_dir, f"{recruiter.id}_{safe_filename}")

        with open(proof_path, "wb") as f:
            f.write(content)

        # The URL in the DB should be relative to the server root
        # e.g. "uploads/payment_proofs/filename.png"
        proof_url = f"uploads/payment_proofs/{recruiter.id}_{safe_filename}"
    else:
        proof_url = None
    from backend.models.evaluation.profile import RecruiterProfile

    rp = (
        db.query(RecruiterProfile)
        .filter(RecruiterProfile.user_id == recruiter.id)
        .first()
    )
    if rp:
        rp.subscription_status = "pending_approval"
        rp.subscription_plan = plan  # This is the slug
    recruiter.payment_proof_path = proof_url

    # Create a Transaction record for Admin visibility
    new_tx = Transaction(
        user_id=recruiter.id,
        company_id=company_id,
        amount=db_plan.price_monthly,
        currency=db_plan.currency,
        status="Pending",
        description=f"Subscription Upgrade: {db_plan.name}",
        proof_url=proof_url,
        proof_status="uploaded",
        proof_file_size=len(content),
        proof_file_type=proof_file.content_type,
    )
    db.add(new_tx)
    db.commit()
    return {
        "message": "Upgrade request submitted",
        "status": "pending_approval",
        "transaction_id": new_tx.id,
    }


@router.get("/subscription/plans", response_model=List[SubscriptionPlanSchema])
def get_available_plans(
    db: Session = Depends(get_db), recruiter: User = Depends(require_recruiter)
):
    """Returns all active plans relevant to recruiters (browsing allowed even
    when the recruiter's billing is managed by their company)."""
    return (
        db.query(SubscriptionPlan)
        .filter(
            SubscriptionPlan.is_active,
            SubscriptionPlan.target_audience == "recruiter",
        )
        .all()
    )


@router.get("/subscription/payment-config")
def get_recruiter_payment_config(
    recruiter: User = Depends(require_recruiter), db: Session = Depends(get_db)
):
    """Return the manual bank-transfer payment instructions (from SystemConfig).

    The config is shared platform-wide (same for candidate + recruiter flows)
    and must be set by an admin under System settings. An empty dict means no
    payment instructions have been configured yet.
    """
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
    return {s.key: s.value for s in settings}


@router.get("/subscription/status")
def get_subscription_status(
    recruiter: User = Depends(require_recruiter), db: Session = Depends(get_db)
):
    profile = getattr(recruiter, "recruiter_profile", None)
    sub_plan = profile.subscription_plan if profile else None
    tier = profile.tier if profile else None
    sub_status = profile.subscription_status if profile else None
    sub_end = profile.subscription_end if profile else None

    # Company-managed recruiters: the company owns the subscription. Surface
    # the company's plan (name/tier/limits/expiry) instead of the recruiter's
    # own profile, which is always free for company members.
    membership = (
        db.query(CompanyMember)
        .filter(
            CompanyMember.user_id == recruiter.id,
            CompanyMember.is_active == True,  # noqa: E712
        )
        .first()
    )
    if membership:
        company_ = db.query(Company).filter(Company.id == membership.company_id).first()
        company_plan = None
        if company_ and company_.plan_id:
            company_plan = (
                db.query(SubscriptionPlan)
                .filter(SubscriptionPlan.id == company_.plan_id)
                .first()
            )
        if company_plan:
            tier = company_plan.slug or tier
            sub_plan = company_plan.slug
            sub_status = (
                company_.subscription_status or sub_status or "active"
            )
        elif company_:
            sub_status = company_.subscription_status or sub_status or "active"

    # Company subscription expiry (authoritative period end), when company-managed.
    if membership:
        from backend.database import Subscription

        company_sub = (
            db.query(Subscription)
            .filter(Subscription.company_id == membership.company_id)
            .order_by(Subscription.id.desc())
            .first()
        )
        if company_sub and company_sub.current_period_end:
            sub_end = company_sub.current_period_end
        if company_sub and company_sub.status:
            sub_status = company_sub.status

    # Latest rejection context (S10): surface reason + timestamp so the
    # billing page can explain why a manual payment was rejected.
    rejection_reason = None
    rejected_at = None
    if sub_status == "rejected" or sub_status == "Failed":
        last_tx = (
            db.query(Transaction)
            .filter(Transaction.user_id == recruiter.id)
            .order_by(Transaction.id.desc())
            .first()
        )
        if last_tx:
            rejection_reason = last_tx.rejection_reason
            rejected_at = last_tx.rejected_at

    # Query plan directly instead of using relationship to avoid schema issues
    plan = None
    if sub_plan:
        plan = (
            db.query(SubscriptionPlan).filter(SubscriptionPlan.slug == sub_plan).first()
        )

    # Default limits if no plan found
    limits = {
        "job_limit": plan.job_limit if plan else 5,
        "cv_limit": plan.cv_limit if plan else 50,
        "ai_interview_limit": plan.ai_interview_limit if plan else 10,
        "team_seat_limit": plan.team_seat_limit if plan else 1,
    }

    # Credit wallet balance (S10e) — the recruiter's own wallet (their quota).
    credit_balance = 0
    try:
        from backend.credit_service import get_or_create_wallet

        credit_balance = float(get_or_create_wallet(db, recruiter).balance or 0)
    except Exception as e:
        logger.warning(
            f"get_subscription_status credit wallet lookup failed for user {recruiter.id}: {e}"
        )

    # Admin-controlled AI credit pricing so recruiters know the cost of each
    # AI feature before triggering it (prices live in SystemConfig).
    from backend.credit_service import get_all_credit_pricing

    credit_pricing = get_all_credit_pricing(db)

    # Company credit pool (product decision: companies own billing/subscription;
    # recruiters see their quota). For company-managed recruiters the quota they
    # spend comes from the company's billing owner wallet.
    company_credit_balance = None
    company_name = None
    membership = (
        db.query(CompanyMember)
        .filter(
            CompanyMember.user_id == recruiter.id,
            CompanyMember.is_active == True,  # noqa: E712
        )
        .first()
    )
    if membership:
        from backend.credit_service import get_or_create_wallet, resolve_company_billing_user

        company_ = db.query(Company).filter(Company.id == membership.company_id).first()
        company_name = company_.name if company_ else None
        billing_user = resolve_company_billing_user(db, membership.company_id)
        if billing_user:
            try:
                company_credit_balance = float(
                    get_or_create_wallet(db, billing_user).balance or 0
                )
            except Exception as e:
                logger.warning(
                    f"get_subscription_status company wallet lookup failed for user {recruiter.id}: {e}"
                )

    return {
        "tier": tier or "free",
        "status": sub_status or "active",
        "managed_by_company": _is_company_managed(db, recruiter),
        "rejection_reason": rejection_reason,
        "rejected_at": rejected_at.isoformat() if rejected_at else None,
        "credit_balance": credit_balance,
        "company_credit_balance": company_credit_balance,
        "company_name": company_name,
        "credit_pricing": credit_pricing,
        "plan_name": plan.name
        if plan
        else (sub_plan if sub_plan != "free" else "Free Tier"),
        "plan_slug": plan.slug if plan else (sub_plan or "free-recruiter"),
        "expiry": sub_end.strftime("%Y-%m-%d") if sub_end else None,
        "usage": {
            "jobs": get_user_usage_jobs(recruiter),
            "cvs": get_user_usage_cvs(recruiter),
            "ai_interviews": get_user_usage_ai_interviews(recruiter),
        },
        "limits": limits,
    }


@router.get("/subscription/invoices", response_model=List[InvoiceResponse])
def get_recruiter_invoices(
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
    company_id: int = Depends(get_current_company_id),
):
    _assert_not_company_managed(db, recruiter)
    from backend.database import Invoice

    return (
        db.query(Invoice)
        .filter(Invoice.company_id == company_id)
        .order_by(Invoice.created_at.desc())
        .all()
    )


@router.get("/subscription/invoices/{invoice_id}/download")
def download_recruiter_invoice(
    invoice_id: int,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
    company_id: int = Depends(get_current_company_id),
):
    _assert_not_company_managed(db, recruiter)
    invoice = (
        db.query(Invoice)
        .filter(Invoice.id == invoice_id, Invoice.company_id == company_id)
        .first()
    )
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    # Prepare data for PDF
    pdf_data = {
        "invoice_number": invoice.invoice_number,
        "date": invoice.created_at.strftime("%Y-%m-%d"),
        "client_name": invoice.client_name,
        "client_mf": invoice.client_mf,
        "client_address": invoice.client_address,
        "amount_ht": invoice.amount_ht,
        "tva_rate": invoice.tva_rate,
        "tva_amount": invoice.tva_amount,
        "stamp_duty": invoice.stamp_duty,
        "total_ttc": invoice.total_ttc,
        "status": invoice.status,
        "transaction_id": invoice.transaction_id or "N/A",
    }

    pdf_bytes = generate_invoice_pdf(pdf_data)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=Invoice_{invoice.invoice_number}.pdf"
        },
    )
