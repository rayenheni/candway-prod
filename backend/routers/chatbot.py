import json
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.authz import get_chatbot_lead_for_recruiter
from backend.career_chatbot import CareerChatbot
from backend.database import AuditLog, ChatbotLead, Job, User, get_db
from backend.dependencies import get_current_user, get_optional_user, require_recruiter
from backend.logger import logger

router = APIRouter(prefix="/chatbot", tags=["chatbot"])


class ChatMessage(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    conversation_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])
    context: dict = Field(default_factory=dict)


class ChatResponse(BaseModel):
    reply: str
    actions: list[str] = Field(default_factory=list)
    suggested_jobs: list[dict] = Field(default_factory=list)
    stage: str = "exploring"
    captured: dict = Field(default_factory=dict)
    conversation_id: str = ""


class CaptureLeadRequest(BaseModel):
    conversation_id: str
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    role_interest: str | None = None
    experience_level: str | None = None
    skills: str | None = None
    source_job_id: int | None = None


class TransferRequest(BaseModel):
    message: str | None = None


CONVERSATION_RATE_LIMIT = {}


def check_rate_limit(conversation_id: str) -> bool:
    now = datetime.now(UTC)
    key = f"chatbot_rate:{conversation_id}"
    entry = CONVERSATION_RATE_LIMIT.get(key)
    if entry:
        if now - entry["reset_at"] > timedelta(hours=1):
            CONVERSATION_RATE_LIMIT[key] = {"count": 1, "reset_at": now}
            return True
        if entry["count"] >= 50:
            return False
        entry["count"] += 1
        return True
    CONVERSATION_RATE_LIMIT[key] = {"count": 1, "reset_at": now}
    return True


def _derive_company_id(
    db: Session, source_job_id: int | None = None, current_user: User | None = None
) -> int:
    """Derive company_id from user context or job. Raises ValueError if impossible."""
    if current_user:
        company_id = getattr(current_user, "_company_id", None)
        if company_id:
            return company_id
    if source_job_id:
        job = db.query(Job).filter(Job.id == source_job_id).first()
        if job:
            from backend.authz import _user_company_id

            cid = _user_company_id(db, job.recruiter_id)
            if cid:
                return cid
    raise ValueError(
        "Cannot create ChatbotLead: unable to resolve company_id from user or job context. "
        "A valid company context is required for tenant isolation."
    )


def _log_audit(
    user: User | None,
    action: str,
    target_id: str | None,
    details: str | None,
    request: Request,
    db: Session,
):
    if not user:
        return
    audit = AuditLog(
        user_id=user.id,
        company_id=getattr(user, "_company_id", None),
        action=action,
        target_id=target_id,
        details=details,
        ip_address=request.client.host if request.client else None,
    )
    db.add(audit)
    db.commit()


@router.post("/message")
async def send_message(
    req: ChatMessage,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
):
    try:
        if not check_rate_limit(req.conversation_id):
            return ChatResponse(
                reply="You've reached the message limit. Please try again later or contact us directly.",
                actions=[],
                suggested_jobs=[],
                stage="complete",
                conversation_id=req.conversation_id,
            )

        existing_lead = (
            db.query(ChatbotLead)
            .filter(ChatbotLead.conversation_id == req.conversation_id)
            .first()
        )

        history = []
        context = req.context or {}
        context["company_name"] = context.get("company_name") or "Candway"
        context["company_description"] = (
            context.get("company_description") or "AI-Powered Recruitment Platform"
        )
        context["faq"] = context.get("faq") or []

        if existing_lead and existing_lead.message_history:
            try:
                history = json.loads(existing_lead.message_history)
            except (json.JSONDecodeError, TypeError):
                history = []

        # Monetization: charge authenticated candidates 1 credit per AI turn.
        # Guests (no wallet) keep the existing conversation rate limit.
        credit_tx = None
        if current_user is not None:
            from backend.credit_service import consume_credits_or_402

            credit_tx = consume_credits_or_402(
                db,
                current_user,
                1,
                "career_chatbot",
                reference_type="conversation",
                reference_id=None,
            )

        result = await CareerChatbot.handle_message(req.message, history, context, db)

        captured = result.get("captured_info", {})
        if existing_lead:
            captured = CareerChatbot.capture_candidate_info(
                req.message,
                {
                    "name": existing_lead.name,
                    "email": existing_lead.email,
                    "phone": existing_lead.phone,
                    "role_interest": existing_lead.role_interest,
                    "experience_level": existing_lead.experience_level,
                },
            )
        else:
            captured = CareerChatbot.capture_candidate_info(req.message, {})

        history.append({"role": "user", "content": req.message})
        history.append({"role": "assistant", "content": result.get("reply", "")})
        history = history[-20:]

        should_save = result.get("should_save_lead", False)
        should_search = result.get("should_search_jobs", False)
        job_query = result.get("job_search_query", "")
        stage = result.get("conversation_stage", "exploring")

        suggested_jobs = []
        if should_search and job_query:
            suggested_jobs = await CareerChatbot.search_jobs(job_query, db)
        elif should_search:
            suggested_jobs = await CareerChatbot.search_jobs(req.message, db)

        job_id = context.get("job_id")
        if existing_lead:
            existing_lead.message_history = json.dumps(history)
            existing_lead.stage = stage
            if captured.get("name"):
                existing_lead.name = captured["name"]
            if captured.get("email"):
                existing_lead.email = captured["email"]
            if captured.get("phone"):
                existing_lead.phone = captured["phone"]
            if captured.get("role_interest"):
                existing_lead.role_interest = captured["role_interest"]
            if captured.get("experience_level"):
                existing_lead.experience_level = captured["experience_level"]
            if not existing_lead.company_id:
                existing_lead.company_id = _derive_company_id(db, job_id, current_user)
            db.commit()
        else:
            if captured.get("name") or captured.get("email") or should_save:
                company_id = _derive_company_id(db, job_id, current_user)
                existing_lead = ChatbotLead(
                    conversation_id=req.conversation_id,
                    company_id=company_id,
                    name=captured.get("name"),
                    email=captured.get("email"),
                    phone=captured.get("phone"),
                    role_interest=captured.get("role_interest"),
                    experience_level=captured.get("experience_level"),
                    message_history=json.dumps(history),
                    stage=stage,
                    source_job_id=job_id,
                )
                db.add(existing_lead)
                db.commit()

        actions = []
        if result.get("should_schedule"):
            actions.append("schedule")
        if result.get("should_transfer"):
            actions.append("talk_to_human")
        if suggested_jobs:
            actions.append("view_jobs")
        if captured.get("name") or captured.get("email"):
            actions.append("apply")

        quick_replies = result.get("suggested_quick_replies", [])

        return ChatResponse(
            reply=result.get("reply", ""),
            actions=actions + quick_replies,
            suggested_jobs=suggested_jobs,
            stage=stage,
            captured=captured,
            conversation_id=req.conversation_id,
        )

    except Exception as e:
        logger.error(f"Chatbot message error: {e}", exc_info=True)
        if credit_tx is not None:
            try:
                from backend.credit_service import rollback_credits

                rollback_credits(db, credit_tx)
            except Exception:
                pass
        return ChatResponse(
            reply="I'm sorry, something went wrong. Please try again.",
            actions=[],
            suggested_jobs=[],
            stage="exploring",
            conversation_id=req.conversation_id,
        )


@router.get("/jobs")
async def search_jobs(
    query: str = "",
    limit: int = 5,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
):
    if query:
        jobs = await CareerChatbot.search_jobs(query, db, limit)
    else:
        jobs_q = (
            db.query(Job)
            .filter(
                Job.is_active,
                Job.deleted_at.is_(None),
            )
            .order_by(Job.created_at.desc())
            .limit(limit)
            .all()
        )
        jobs = [
            {
                "id": j.id,
                "title": j.title,
                "company": j.company_name
                or (j.company.name if j.company else "Unknown"),
                "location": j.location or "Remote",
                "type": j.type,
                "salary_range": j.salary_range,
                "description": j.description[:300] if j.description else "",
                "required_skills": j.required_skills or "",
            }
            for j in jobs_q
        ]
    return {"jobs": jobs, "total": len(jobs)}


@router.post("/capture-lead")
async def capture_lead(
    req: CaptureLeadRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
):
    try:
        existing = (
            db.query(ChatbotLead)
            .filter(ChatbotLead.conversation_id == req.conversation_id)
            .first()
        )

        if existing:
            # Authorization: if lead has a company, user must belong to it
            if existing.company_id and current_user:
                get_chatbot_lead_for_recruiter(existing.id, current_user, db)
            if req.name:
                existing.name = req.name
            if req.email:
                existing.email = req.email
            if req.phone:
                existing.phone = req.phone
            if req.role_interest:
                existing.role_interest = req.role_interest
            if req.experience_level:
                existing.experience_level = req.experience_level
            if req.skills:
                existing.skills = req.skills
            if req.source_job_id:
                existing.source_job_id = req.source_job_id
            if not existing.company_id:
                existing.company_id = _derive_company_id(
                    db, req.source_job_id, current_user
                )
            existing.stage = "capturing"
            db.commit()
            db.refresh(existing)
            lead = existing
        else:
            company_id = _derive_company_id(db, req.source_job_id, current_user)
            lead = ChatbotLead(
                conversation_id=req.conversation_id,
                company_id=company_id,
                name=req.name,
                email=req.email,
                phone=req.phone,
                role_interest=req.role_interest,
                experience_level=req.experience_level,
                skills=req.skills,
                source_job_id=req.source_job_id,
                message_history="[]",
                stage="capturing",
            )
            db.add(lead)
            db.commit()
            db.refresh(lead)

        if lead.email or lead.name:
            try:
                recruiters = (
                    db.query(User)
                    .filter(
                        User.role == "recruiter",
                        User.deleted_at.is_(None),
                    )
                    .limit(5)
                    .all()
                )

                from backend.notifications import notify_user

                for recruiter in recruiters:
                    await notify_user(
                        user_id=str(recruiter.id),
                        message=f"New chatbot lead: {lead.name or 'Anonymous'} interested in {lead.role_interest or 'a role'}",
                        title="New Career Chat Lead",
                        level="info",
                        notification_type="lead_captured",
                        related_type="chatbot_lead",
                        related_id=lead.id,
                        db_session=db,
                    )
            except Exception as notify_err:
                logger.error(
                    f"Failed to notify recruiters about new lead: {notify_err}"
                )

        _log_audit(
            current_user,
            "lead_captured",
            str(lead.id),
            f"Captured lead: {lead.name}",
            request,
            db,
        )
        return {"success": True, "lead_id": lead.id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Capture lead error: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to capture lead")


@router.post("/transfer/{conversation_id}")
async def transfer_to_human(
    conversation_id: str,
    request: Request,
    req: TransferRequest = TransferRequest(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        lead = (
            db.query(ChatbotLead)
            .filter(ChatbotLead.conversation_id == conversation_id)
            .first()
        )

        if not lead:
            raise HTTPException(status_code=404, detail="Conversation not found")

        # Authorization: enforce company ownership
        if lead.company_id:
            get_chatbot_lead_for_recruiter(lead.id, current_user, db)

        lead.stage = "complete"

        history = []
        if lead.message_history:
            try:
                history = json.loads(lead.message_history)
            except (json.JSONDecodeError, TypeError):
                pass

        history.append({"role": "system", "content": "Transferred to human recruiter"})
        lead.message_history = json.dumps(history)
        db.commit()

        try:
            recruiters = (
                db.query(User)
                .filter(
                    User.role == "recruiter",
                    User.deleted_at.is_(None),
                )
                .limit(5)
                .all()
            )

            from backend.notifications import notify_user

            for recruiter in recruiters:
                extra_msg = f" Message: {req.message}" if req.message else ""
                await notify_user(
                    user_id=str(recruiter.id),
                    message=f"Chatbot transfer requested by {lead.name or 'Anonymous candidate'}. Role interest: {lead.role_interest or 'Unknown'}.{extra_msg}",
                    title="Chat Transfer Requested",
                    level="warning",
                    notification_type="chat_transfer",
                    related_type="chatbot_lead",
                    related_id=lead.id,
                    db_session=db,
                )
        except Exception as notify_err:
            logger.error(f"Failed to notify about transfer: {notify_err}")

        _log_audit(
            current_user,
            "lead_transferred",
            str(lead.id),
            "Transferred to human recruiter",
            request,
            db,
        )
        return {
            "success": True,
            "message": "A recruiter will reach out to you shortly.",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Transfer to human error: {e}")
        raise HTTPException(status_code=500, detail="Failed to process transfer")


@router.get("/leads")
async def get_leads(
    request: Request,
    stage: str = "",
    role: str = "",
    days: int = 30,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_recruiter),
):
    user_company_id = getattr(current_user, "_company_id", None)

    query = db.query(ChatbotLead)

    # Tenant isolation: filter by company
    if user_company_id:
        query = query.filter(ChatbotLead.company_id == user_company_id)

    cutoff = datetime.now(UTC) - timedelta(days=days)
    query = query.filter(ChatbotLead.created_at >= cutoff)

    if stage:
        query = query.filter(ChatbotLead.stage == stage)
    if role:
        query = query.filter(ChatbotLead.role_interest.ilike(f"%{role}%"))

    total = query.count()

    leads = (
        query.order_by(ChatbotLead.created_at.desc()).offset(offset).limit(limit).all()
    )

    result = []
    for lead in leads:
        history = []
        if lead.message_history:
            try:
                history = json.loads(lead.message_history)
            except (json.JSONDecodeError, TypeError):
                pass
        result.append(
            {
                "id": lead.id,
                "conversation_id": lead.conversation_id,
                "name": lead.name,
                "email": lead.email,
                "phone": lead.phone,
                "role_interest": lead.role_interest,
                "experience_level": lead.experience_level,
                "skills": lead.skills,
                "stage": lead.stage,
                "source_job_id": lead.source_job_id,
                "assigned_recruiter_id": lead.assigned_recruiter_id,
                "contacted_at": lead.contacted_at.isoformat()
                if lead.contacted_at
                else None,
                "message_history": history[-10:],
                "created_at": lead.created_at.isoformat() if lead.created_at else None,
                "updated_at": lead.updated_at.isoformat() if lead.updated_at else None,
            }
        )

    _log_audit(
        current_user,
        "leads_listed",
        None,
        f"Listed {total} leads (company={user_company_id}, stage={stage}, days={days})",
        request,
        db,
    )
    return {"leads": result, "total": total}


@router.post("/leads/{lead_id}/assign")
async def assign_lead(
    lead_id: int,
    recruiter_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_recruiter),
):
    lead = get_chatbot_lead_for_recruiter(lead_id, current_user, db)
    lead.assigned_recruiter_id = recruiter_id
    db.commit()

    _log_audit(
        current_user,
        "lead_assigned",
        str(lead_id),
        f"Assigned lead {lead_id} to recruiter {recruiter_id}",
        request,
        db,
    )
    return {"success": True}


@router.post("/leads/{lead_id}/contacted")
async def mark_lead_contacted(
    lead_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_recruiter),
):
    lead = get_chatbot_lead_for_recruiter(lead_id, current_user, db)
    lead.contacted_at = datetime.now(UTC)
    db.commit()

    _log_audit(
        current_user,
        "lead_contacted",
        str(lead_id),
        "Marked lead as contacted",
        request,
        db,
    )
    return {"success": True}
