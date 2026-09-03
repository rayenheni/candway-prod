"""
Offer Management API Endpoints (ATS 2.0)
Handles offer letters, templates, and e-signatures
"""

import os
from datetime import UTC, date, datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import and_
from sqlalchemy.orm import Session

from backend.authz import get_application_for_recruiter, get_offer_for_recruiter
from backend.config import get_settings
from backend.database import Application, Offer, OfferTemplate, User
from backend.dependencies import (
    get_db,
    require_candidate,
    require_recruiter,
)
from backend.email_utils import send_email
from backend.esign_service import create_esign_envelope, get_esign_status
from backend.logger import logger
from backend.optimistic_lock import retry_stale
from backend.tenant import get_current_company_id

router = APIRouter(prefix="/recruiter/offers", tags=["Offer Management"])


def _utcnow():
    return datetime.now(UTC).replace(tzinfo=None)


# ============================================
# SCHEMAS
# ============================================


class OfferTemplateCreate(BaseModel):
    name: str
    subject: str
    body: str  # HTML with placeholders


class OfferCreate(BaseModel):
    application_id: int
    position: str
    salary: str
    start_date: Optional[date] = None
    template_id: Optional[int] = None
    custom_subject: Optional[str] = None
    custom_body: Optional[str] = None
    expires_in_days: int = 7


class OfferResponse(BaseModel):
    id: int
    application_id: int
    candidate_name: str
    candidate_email: str
    position: str
    salary: str
    start_date: Optional[date]
    status: str
    expires_at: Optional[datetime]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


def replace_placeholders(template: str, data: dict) -> str:
    """Replace placeholders in template with actual data"""
    for key, value in data.items():
        placeholder = f"{{{{{key}}}}}"
        template = template.replace(placeholder, str(value))
    return template


# ============================================
# OFFER TEMPLATE ENDPOINTS
# ============================================


@router.post("/templates", status_code=status.HTTP_201_CREATED)
def create_offer_template(
    data: OfferTemplateCreate,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
    company_id: int = Depends(get_current_company_id),
):
    """Create a new offer letter template"""
    template = OfferTemplate(
        recruiter_id=recruiter.id,
        company_id=company_id,
        name=data.name,
        subject=data.subject,
        body=data.body,
    )
    db.add(template)
    db.commit()
    db.refresh(template)

    logger.info(f"Offer template created by {recruiter.email}")

    return {"success": True, "template_id": template.id}


@router.get("/templates")
def get_offer_templates(
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
    company_id: int = Depends(get_current_company_id),
):
    """Get all offer templates for the recruiter"""
    templates = (
        db.query(OfferTemplate)
        .filter(
            and_(
                OfferTemplate.company_id == company_id,
                OfferTemplate.is_active,
            )
        )
        .all()
    )

    return [
        {
            "id": t.id,
            "name": t.name,
            "subject": t.subject,
            "body": t.body,
            "created_at": t.created_at,
        }
        for t in templates
    ]


@router.delete("/templates/{template_id}")
def delete_offer_template(
    template_id: int,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
    company_id: int = Depends(get_current_company_id),
):
    """Delete (deactivate) an offer template"""
    template = (
        db.query(OfferTemplate)
        .filter(
            and_(
                OfferTemplate.id == template_id,
                OfferTemplate.company_id == company_id,
            )
        )
        .first()
    )

    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    template.is_active = False
    db.commit()

    return {"success": True}


# ============================================
# OFFER ENDPOINTS
# ============================================


@router.post("/send", status_code=status.HTTP_201_CREATED)
@retry_stale()
async def send_offer(
    data: OfferCreate,
    background_tasks: BackgroundTasks,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
    company_id: int = Depends(get_current_company_id),
):
    """Send a job offer to a candidate with e-signature"""
    app = get_application_for_recruiter(data.application_id, recruiter, db)

    subject = data.custom_subject
    body = data.custom_body

    if data.template_id:
        template = (
            db.query(OfferTemplate)
            .filter(
                and_(
                    OfferTemplate.id == data.template_id,
                    OfferTemplate.company_id == company_id,
                )
            )
            .first()
        )

        if template:
            subject = template.subject
            body = template.body

    placeholder_data = {
        "candidate_name": app.full_name,
        "position": data.position,
        "salary": data.salary,
        "start_date": data.start_date.strftime("%B %d, %Y")
        if data.start_date
        else "TBD",
        "company_name": app.job.company_name if app.job else "Our Company",
    }

    subject = replace_placeholders(subject, placeholder_data)
    body = replace_placeholders(body, placeholder_data)

    esign_result = await create_esign_envelope(
        offer_data={
            "position": data.position,
            "salary": data.salary,
            "start_date": data.start_date.strftime("%Y-%m-%d")
            if data.start_date
            else None,
            "body": body,
        },
        candidate_email=app.email,
        candidate_name=app.full_name,
        recruiter_email=recruiter.email,
    )

    offer = Offer(
        application_id=data.application_id,
        company_id=company_id,
        created_by=recruiter.id,
        position=data.position,
        salary=data.salary,
        start_date=data.start_date,
        subject=subject,
        body=body,
        signature_request_id=esign_result.get("envelope_id"),
        expires_at=_utcnow() + timedelta(days=data.expires_in_days),
    )
    db.add(offer)
    db.flush()

    app.status = "offer"

    db.commit()
    db.refresh(offer)

    background_tasks.add_task(
        send_offer_email,
        offer.id,
        app.email,
        app.full_name,
        subject,
        body,
        esign_result.get("signing_url"),
    )

    try:
        import asyncio

        from backend.webhook_dispatcher import dispatch_webhook

        asyncio.create_task(
            dispatch_webhook(
                "offer_sent",
                {
                    "offer_id": offer.id,
                    "application_id": app.id,
                    "candidate_name": app.full_name,
                    "position": data.position,
                    "salary": data.salary,
                    "sent_by": recruiter.email,
                },
                getattr(recruiter, "_company_id", None),
            )
        )
    except Exception as e:
        logger.warning(f"Failed to dispatch offer webhook: {e}")

    logger.info(f"Offer sent by {recruiter.email} to application {data.application_id}")

    return {
        "success": True,
        "offer_id": offer.id,
        "esign": {
            "envelope_id": esign_result.get("envelope_id"),
            "signing_url": esign_result.get("signing_url"),
            "status": esign_result.get("status"),
        },
    }


@router.get("/list", response_model=List[OfferResponse])
def get_offers(
    status_filter: Optional[str] = None,
    page: int = 1,
    per_page: int = 25,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
    company_id: int = Depends(get_current_company_id),
):
    """Get all offers for the recruiter with pagination."""
    # M6 FIX: was hardcoded limit=50 with no pagination support
    per_page = max(1, min(per_page, 100))  # clamp 1-100
    offset = (max(1, page) - 1) * per_page

    query = (
        db.query(Offer).join(Application).filter(Application.company_id == company_id)
    )

    if status_filter:
        query = query.filter(Offer.status == status_filter)

    total = query.count()
    offers = (
        query.order_by(Offer.created_at.desc()).offset(offset).limit(per_page).all()
    )

    return {
        "offers": [format_offer_response(o, db) for o in offers],
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "pages": (total + per_page - 1) // per_page,
        },
    }


@router.get("/{offer_id}")
def get_offer_details(
    offer_id: int,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    """Get detailed information about an offer"""
    offer = get_offer_for_recruiter(offer_id, recruiter, db)

    return {
        **format_offer_response(offer, db),
        "subject": offer.subject,
        "body": offer.body,
        "candidate_response": offer.candidate_response,
        "responded_at": offer.responded_at,
        "signed_at": offer.signed_at,
    }


@router.put("/{offer_id}/withdraw")
@retry_stale()
def withdraw_offer(
    offer_id: int,
    reason: Optional[str] = None,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    """Withdraw an offer"""
    offer = get_offer_for_recruiter(offer_id, recruiter, db)
    app = get_application_for_recruiter(offer.application_id, recruiter, db)

    offer.status = "withdrawn"
    db.commit()

    # Send withdrawal email
    if reason:
        subject = "Offer Update"
        body = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2>Offer Update</h2>
            <p>Dear {app.full_name},</p>
            <p>We regret to inform you that the offer for the position of <strong>{offer.position}</strong> has been withdrawn.</p>
            {f"<p><strong>Reason:</strong> {reason}</p>" if reason else ""}
            <p>Thank you for your time and interest.</p>
        </div>
        """
        send_email(app.email, subject, body)

    logger.info(f"Offer {offer_id} withdrawn by {recruiter.email}")

    return {"success": True}


@router.post("/{offer_id}/resend")
def resend_offer(
    offer_id: int,
    background_tasks: BackgroundTasks,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    """Resend an offer email"""
    offer = get_offer_for_recruiter(offer_id, recruiter, db)
    app = get_application_for_recruiter(offer.application_id, recruiter, db)

    # Send offer email in background
    background_tasks.add_task(
        send_offer_email,
        offer.id,
        app.email,
        app.full_name,
        offer.subject,
        offer.body,
        db,
    )

    logger.info(f"Offer {offer_id} resent by {recruiter.email}")

    return {"success": True}


# ============================================
# CANDIDATE RESPONSE ENDPOINTS (Authenticated)
# ============================================


@router.post("/respond/{offer_id}")
@retry_stale()
def respond_to_offer(
    offer_id: int,
    accept: bool,
    response_message: Optional[str] = None,
    candidate: User = Depends(require_candidate),
    db: Session = Depends(get_db),
):
    """Candidate responds to an offer (accept/decline)"""
    offer = db.query(Offer).filter(Offer.id == offer_id).first()
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")
    app = offer.application

    # Verify the candidate owns this application
    if not app.owner or app.owner.id != candidate.id:
        raise HTTPException(status_code=404, detail="Application not found")

    # Check that the offer belongs to this candidate
    candidate_email = candidate.email or ""
    app_email = app.email or ""
    if app_email.lower() != candidate_email.lower() and app.user_id != candidate.id:
        # Also check if candidate owns the application directly
        if not app.owner or app.owner.id != candidate.id:
            raise HTTPException(status_code=403, detail="This offer is not for you")

    # Check if offer is still valid
    if offer.status != "pending":
        raise HTTPException(status_code=400, detail="Offer is no longer available")

    if offer.expires_at and offer.expires_at < _utcnow():
        offer.status = "expired"
        db.commit()
        raise HTTPException(status_code=400, detail="Offer has expired")

    # Update offer
    offer.status = "accepted" if accept else "declined"
    offer.candidate_response = response_message
    offer.responded_at = _utcnow()

    # Update application status
    if accept:
        app.status = "hired"
        offer.signed_at = _utcnow()
    else:
        app.status = "offer_declined"

    db.commit()

    # Notify recruiter
    recruiter = db.query(User).filter(User.id == offer.created_by).first()
    if recruiter and recruiter.email:
        status_text = "accepted" if accept else "declined"
        settings = get_settings()
        offers_url = f"{settings.frontend_url}/recruiter/offers"
        subject = f"Offer {status_text.title()}: {app.full_name}"
        body = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2>Offer {status_text.title()}</h2>
            <p><strong>{app.full_name}</strong> has {status_text} your offer for the position of <strong>{offer.position}</strong>.</p>
            {f"<p><strong>Message:</strong> {response_message}</p>" if response_message else ""}
            <a href="{offers_url}" style="display: inline-block; background: #4f46e5; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; margin: 20px 0;">
                View Offer Details
            </a>
        </div>
        """
        send_email(recruiter.email, subject, body)

    try:
        import asyncio

        from backend.webhook_dispatcher import dispatch_webhook

        asyncio.create_task(
            dispatch_webhook(
                "offer_responded",
                {
                    "offer_id": offer.id,
                    "application_id": app.id,
                    "candidate_name": app.full_name,
                    "position": offer.position,
                    "status": offer.status,
                    "response_message": response_message,
                },
                app.company_id,
            )
        )
    except Exception as e:
        logger.warning(f"Failed to dispatch offer response webhook: {e}")

    logger.info(f"Offer {offer_id} responded by candidate {candidate.email}")

    return {"success": True, "status": offer.status}


@router.get("/candidate/{offer_id}")
def get_candidate_offer_details(
    offer_id: int,
    candidate: User = Depends(require_candidate),
    db: Session = Depends(get_db),
):
    """Candidate views offer details"""
    offer = db.query(Offer).filter(Offer.id == offer_id).first()
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")
    app = offer.application
    if not app or app.user_id != candidate.id:
        raise HTTPException(status_code=404, detail="Offer not found")
    return {
        "id": offer.id,
        "status": offer.status,
        "subject": offer.subject,
        "body": offer.body,
        "salary": offer.salary,
        "start_date": str(offer.start_date) if offer.start_date else None,
        "expires_at": str(offer.expires_at) if offer.expires_at else None,
        "responded_at": str(offer.responded_at) if offer.responded_at else None,
        "signed_at": str(offer.signed_at) if offer.signed_at else None,
        "job_title": app.job.title if app.job else None,
        "company_name": app.job.company_name if app.job else None,
    }


# ============================================
# E-SIGNATURE ENDPOINTS
# ============================================


@router.post("/{offer_id}/esign-status")
async def check_esign_status(
    offer_id: int,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    """Check the e-signature status of an offer"""
    offer = get_offer_for_recruiter(offer_id, recruiter, db)

    if not offer.signature_request_id:
        raise HTTPException(status_code=400, detail="No e-signature request found")

    status = await get_esign_status(offer.signature_request_id)

    return {
        "offer_id": offer.id,
        "envelope_id": offer.signature_request_id,
        "esign_status": status.get("status"),
        "signed": status.get("signed", False) or offer.signed_at is not None,
    }


@router.get("/{offer_id}/signing-url")
async def get_signing_url(
    offer_id: int,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    """Get the e-signature signing URL for an offer"""
    offer = get_offer_for_recruiter(offer_id, recruiter, db)

    app = get_application_for_recruiter(offer.application_id, recruiter, db)

    if not offer.signature_request_id:
        esign_result = await create_esign_envelope(
            offer_data={
                "position": offer.position,
                "salary": offer.salary,
                "start_date": offer.start_date.strftime("%Y-%m-%d")
                if offer.start_date
                else None,
                "body": offer.body,
            },
            candidate_email=app.email,
            candidate_name=app.full_name,
            recruiter_email=recruiter.email,
        )
        offer.signature_request_id = esign_result.get("envelope_id")
        db.commit()
        return {
            "signing_url": esign_result.get("signing_url"),
            "envelope_id": esign_result.get("envelope_id"),
        }

    return {
        "signing_url": f"{get_settings().frontend_url}/candidate/esign-view?envelope_id={offer.signature_request_id}",
        "envelope_id": offer.signature_request_id,
    }


@router.post("/docusign-webhook")
async def docusign_webhook(request: Request, db: Session = Depends(get_db)):
    """Receive DocuSign Connect completion events"""
    # S2 FIX: verify the HMAC signature sent by DocuSign so random POST
    # requests cannot mark offers as signed.
    import hashlib
    import hmac

    settings = get_settings()
    docusign_hmac_key = getattr(settings, "docusign_hmac_key", None) or os.environ.get(
        "DOCUSIGN_HMAC_KEY", ""
    )

    if docusign_hmac_key:
        raw_body = await request.body()
        # DocuSign sends the signature in X-DocuSign-Signature-1
        incoming_sig = request.headers.get("X-DocuSign-Signature-1", "")
        if not incoming_sig:
            logger.warning("DocuSign webhook missing signature header — rejected")
            return {"status": "ignored"}

        expected = hmac.new(
            docusign_hmac_key.encode("utf-8"),
            raw_body,
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected, incoming_sig):
            logger.warning("DocuSign webhook signature mismatch — rejected")
            return {"status": "ignored"}

        try:
            payload = __import__("json").loads(raw_body)
        except Exception:
            payload = {}
    else:
        logger.error(
            "DOCUSIGN_HMAC_KEY not set. Rejecting unauthenticated DocuSign webhook."
        )
        return {"status": "ignored"}

    try:
        envelope_id = None

        if isinstance(payload, dict):
            envelope_id = payload.get("envelopeId") or payload.get("envelope_id")

        if not envelope_id:
            logger.warning("DocuSign webhook received without envelope_id")
            return {"status": "ignored"}

        offer = (
            db.query(Offer).filter(Offer.signature_request_id == envelope_id).first()
        )
        if not offer:
            logger.warning(f"No offer found for DocuSign envelope {envelope_id}")
            return {"status": "ignored"}

        offer.status = "accepted"
        offer.signed_at = _utcnow()

        app = offer.application
        if app:
            app.status = "hired"

        db.commit()
        logger.info(
            f"Offer {offer.id} signed via DocuSign webhook (envelope {envelope_id})"
        )

        return {"status": "ok"}
    except Exception as e:
        logger.error(f"DocuSign webhook processing error: {e}")
        return {"status": "error", "detail": "Webhook processing failed"}


# ============================================
# HELPER FUNCTIONS
# ============================================


def format_offer_response(offer: Offer, db: Session) -> dict:
    """Format offer for API response"""
    app = offer.application

    return {
        "id": offer.id,
        "application_id": offer.application_id,
        "candidate_name": app.full_name,
        "candidate_email": app.email,
        "position": offer.position,
        "salary": offer.salary,
        "start_date": offer.start_date,
        "status": offer.status,
        "expires_at": offer.expires_at,
        "created_at": offer.created_at,
    }


def send_offer_email(
    offer_id: int,
    candidate_email: str,
    candidate_name: str,
    subject: str,
    body: str,
    signing_url: str = None,
):
    """Send offer email to candidate with e-signature link"""
    try:
        settings = get_settings()

        sign_button = ""
        if signing_url:
            sign_button = f"""
            <div style="text-align: center; margin: 30px 0;">
                <a href="{signing_url}" style="display: inline-block; background: #4f46e5; color: white; padding: 15px 30px; text-decoration: none; border-radius: 6px; font-weight: bold; font-size: 16px;">
                    Review & Sign Offer Electronically
                </a>
            </div>
            """

        email_body = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            {body}

            {sign_button}

            <div style="text-align: center; margin: 20px 0;">
                <a href="{settings.frontend_url}/candidate/offers/{offer_id}/accept" style="display: inline-block; background: #10b981; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; margin: 0 8px; font-weight: bold;">
                    Accept Offer
                </a>
                <a href="{settings.frontend_url}/candidate/offers/{offer_id}/decline" style="display: inline-block; background: #ef4444; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; margin: 0 8px; font-weight: bold;">
                    Decline Offer
                </a>
            </div>

            <p style="color: #6b7280; font-size: 12px; text-align: center; margin-top: 30px;">
                This offer expires in 7 days. Please sign or respond by clicking one of the options above.
            </p>
        </div>
        """

        send_email(candidate_email, subject, email_body)
        logger.info(f"Offer email sent to {candidate_email}")
    except Exception as e:
        logger.error(f"Failed to send offer email: {e}")
