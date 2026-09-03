"""
Shared ownership-check utilities for the Candway API.

Every function returns 404 (not 403) on failure so that an attacker
cannot distinguish "resource does not exist" from "resource exists
but you do not own it".  Admin role bypasses all ownership checks.

Chatbot lead functions return 403 Forbidden per security requirements
to prevent IDOR and cross-company access.
"""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.database import (
    Application,
    BatchJob,
    ChatbotLead,
    CompanyMember,
    Conversation,
    ConversationParticipant,
    Interview,
    InterviewScorecard,
    Job,
    Offer,
    Rubric,
    User,
)


def _assert_tenant(resource, company_id, name="resource"):
    """Lazy import to break circular: tenant.py → deps.py → authz.py → tenant.py"""
    from backend.tenant import assert_tenant_match as _m

    _m(resource, company_id, name)


# ── helpers ──────────────────────────────────────────────────────


def _user_company_id(
    db: Session,
    user_id: int,
) -> int | None:
    membership = (
        db.query(CompanyMember.company_id)
        .filter(
            CompanyMember.user_id == user_id,
            CompanyMember.is_active,
        )
        .first()
    )
    return membership.company_id if membership else None


def _company_id_for_user(
    recruiter: User,
    db: Session,
) -> int | None:
    return getattr(recruiter, "_company_id", None) or _user_company_id(db, recruiter.id)


def _has_active_company_membership(
    recruiter: User,
    company_id: int,
    db: Session,
) -> bool:
    if not company_id:
        return False
    current_company_id = _company_id_for_user(recruiter, db)
    if current_company_id != company_id:
        return False
    membership = (
        db.query(CompanyMember)
        .filter(
            CompanyMember.user_id == recruiter.id,
            CompanyMember.company_id == company_id,
            CompanyMember.is_active,
        )
        .first()
    )
    return membership is not None


def _recruiter_owns_application(
    recruiter: User,
    app: Application,
    db: Session,
) -> bool:
    """Return True if recruiter is in the application's company tenant.
    Super-admins bypass the membership check (docstring: "Admin role
    bypasses all ownership checks")."""
    from backend.profile_helpers import get_user_is_super_admin

    if get_user_is_super_admin(recruiter):
        return True
    if not _has_active_company_membership(recruiter, app.company_id, db):
        return False
    return True


# ── public helpers ────────────────────────────────────────────────


def get_application_for_candidate(
    app_id: int,
    user: User,
    db: Session,
) -> Application:
    """Candidate can only access own applications.  404 on miss."""
    app = (
        db.query(Application)
        .filter(Application.id == app_id, Application.user_id == user.id)
        .first()
    )
    if not app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return app


def get_application_for_recruiter(
    app_id: int,
    recruiter: User,
    db: Session,
) -> Application:
    """Recruiter must own the job/batch or be assigned.  404 on miss."""
    app = db.query(Application).filter(Application.id == app_id).first()
    if not app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if not _recruiter_owns_application(recruiter, app, db):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return app


def get_job_for_recruiter(
    job_id: int,
    recruiter: User,
    db: Session,
) -> Job:
    """Recruiter/admin must belong to the job owner's company. 404 on miss."""
    from backend.profile_helpers import get_user_is_super_admin

    if get_user_is_super_admin(recruiter):
        job = db.query(Job).filter(Job.id == job_id).first()
    else:
        company_id = _company_id_for_user(recruiter, db)
        if company_id is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
        job = (
            db.query(Job).filter(Job.id == job_id, Job.company_id == company_id).first()
        )
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return job


def get_batch_for_recruiter(
    batch_id: int,
    recruiter: User,
    db: Session,
) -> BatchJob:
    """Recruiter/admin must belong to the batch owner's company. 404 on miss."""
    company_id = _company_id_for_user(recruiter, db)
    if company_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    batch = (
        db.query(BatchJob)
        .filter(BatchJob.id == batch_id, BatchJob.company_id == company_id)
        .first()
    )
    _assert_tenant(batch, company_id, "BatchJob")
    return batch


def get_offer_for_recruiter(
    offer_id: int,
    recruiter: User,
    db: Session,
) -> Offer:
    """Recruiter must own the offer via application ownership. 404 on miss."""
    company_id = _company_id_for_user(recruiter, db)
    if company_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    offer = (
        db.query(Offer)
        .filter(Offer.id == offer_id, Offer.company_id == company_id)
        .first()
    )
    _assert_tenant(offer, company_id, "Offer")
    return offer


def get_conversation_for_user(
    conv_id: int,
    user: User,
    db: Session,
) -> Conversation:
    """User must be a participant.  404 on miss."""
    conv = (
        db.query(Conversation)
        .join(ConversationParticipant)
        .filter(
            Conversation.id == conv_id,
            ConversationParticipant.user_id == user.id,
        )
        .first()
    )
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return conv


def get_rubric_for_recruiter(
    rubric_id: int,
    recruiter: User,
    db: Session,
) -> Rubric:
    """Recruiter must belong to the rubric creator's company.  404 on miss."""
    company_id = _company_id_for_user(recruiter, db)
    if company_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    rubric = (
        db.query(Rubric)
        .filter(Rubric.id == rubric_id, Rubric.company_id == company_id)
        .first()
    )
    _assert_tenant(rubric, company_id, "Rubric")
    return rubric


def get_rubric_access_for_recruiter(
    job_id: int,
    recruiter: User,
    db: Session,
) -> Job:
    """Recruiter must own the job to access its rubric.  404 on miss."""
    return get_job_for_recruiter(job_id, recruiter, db)


def get_scorecard_for_recruiter(
    scorecard_id: int,
    recruiter: User,
    db: Session,
) -> InterviewScorecard:
    """Recruiter must own the scorecard or it must be a system template.  404 on miss."""
    sc = (
        db.query(InterviewScorecard)
        .filter(InterviewScorecard.id == scorecard_id)
        .first()
    )
    if not sc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if sc.is_system:
        return sc
    company_id = _company_id_for_user(recruiter, db)
    _assert_tenant(sc, company_id, "InterviewScorecard")
    return sc


def get_interview_for_recruiter(
    interview_id: int,
    recruiter: User,
    db: Session,
) -> Interview:
    """Recruiter must own the interview's application.  404 on miss."""
    company_id = _company_id_for_user(recruiter, db)
    if company_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    interview = (
        db.query(Interview)
        .filter(Interview.id == interview_id, Interview.company_id == company_id)
        .first()
    )
    _assert_tenant(interview, company_id, "Interview")
    return interview


# ── Chatbot Lead Authorization ────────────────────────────────────


def get_chatbot_lead_for_recruiter(
    lead_id: int,
    user: User,
    db: Session,
) -> ChatbotLead:
    """Enforce tenant isolation for chatbot leads.

    Returns the lead on success.
    Raises 404 if not found or if tenant mismatch (prevents IDOR/enumeration).
    Raises 403 if super admin without explicit permission.
    """
    lead = db.query(ChatbotLead).filter(ChatbotLead.id == lead_id).first()
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead not found",
        )

    # Super admin: explicit permission required
    from backend.profile_helpers import get_user_is_super_admin

    if get_user_is_super_admin(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin access requires explicit permission. Use admin impersonation.",
        )

    # Admin / Recruiter: own company only → 404 on mismatch
    user_company = _company_id_for_user(user, db)
    if not user_company or lead.company_id != user_company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead not found",
        )

    return lead
