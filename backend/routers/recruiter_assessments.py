import json
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.assessment_service import AssessmentService
from backend.authz import get_application_for_recruiter, get_job_for_recruiter
from backend.database import (
    Assessment,
    AssessmentInvitation,
    CompanyMember,
    User,
)
from backend.dependencies import get_db, require_recruiter
from backend.logger import logger

router = APIRouter(prefix="/recruiter/assessments", tags=["Recruiter Assessments"])


class CreateAssessmentRequest(BaseModel):
    job_id: int
    provider: str
    test_name: str
    difficulty: str = "medium"
    duration_minutes: int = 60
    skills: List[str] = []


class InviteCandidateRequest(BaseModel):
    application_id: int
    send_email: bool = True


class BulkInviteRequest(BaseModel):
    application_ids: List[int]
    send_email: bool = True


@router.post("/create")
async def create_assessment(
    req: CreateAssessmentRequest,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    _job = get_job_for_recruiter(req.job_id, recruiter, db)

    try:
        result = await AssessmentService.create_assessment(
            provider=req.provider,
            job_id=req.job_id,
            recruiter_id=recruiter.id,
            test_name=req.test_name,
            difficulty=req.difficulty,
            duration_minutes=req.duration_minutes,
            skills=req.skills,
            db=db,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Create assessment failed: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to create assessment: {str(e)}"
        )


@router.get("")
def list_assessments(
    job_id: Optional[int] = None,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    company_id = getattr(recruiter, "_company_id", None)
    query = (
        db.query(Assessment)
        .join(CompanyMember, CompanyMember.user_id == Assessment.recruiter_id)
        .filter(CompanyMember.company_id == company_id, CompanyMember.is_active)
    )
    if job_id:
        query = query.filter(Assessment.job_id == job_id)
    assessments = query.order_by(Assessment.created_at.desc()).all()

    result = []
    for a in assessments:
        total_invites = (
            db.query(func.count(AssessmentInvitation.id))
            .filter(AssessmentInvitation.assessment_id == a.id)
            .scalar()
            or 0
        )
        completed_invites = (
            db.query(func.count(AssessmentInvitation.id))
            .filter(
                AssessmentInvitation.assessment_id == a.id,
                AssessmentInvitation.status == "completed",
            )
            .scalar()
            or 0
        )
        avg_score = (
            db.query(func.avg(AssessmentInvitation.score))
            .filter(
                AssessmentInvitation.assessment_id == a.id,
                AssessmentInvitation.score.isnot(None),
            )
            .scalar()
        )

        result.append(
            {
                "id": a.id,
                "job_id": a.job_id,
                "provider": a.provider,
                "test_name": a.test_name,
                "difficulty": a.difficulty,
                "duration_minutes": a.duration_minutes,
                "skills": json.loads(a.skills) if a.skills else [],
                "status": a.status,
                "total_invited": total_invites,
                "completed_count": completed_invites,
                "avg_score": round(float(avg_score), 1) if avg_score else None,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
        )

    return result


@router.get("/{assessment_id}")
def get_assessment(
    assessment_id: int,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    assessment = (
        db.query(Assessment)
        .join(CompanyMember, CompanyMember.user_id == Assessment.recruiter_id)
        .filter(
            Assessment.id == assessment_id,
            CompanyMember.company_id == getattr(recruiter, "_company_id", None),
            CompanyMember.is_active,
        )
        .first()
    )
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    invitations = (
        db.query(AssessmentInvitation)
        .filter(AssessmentInvitation.assessment_id == assessment.id)
        .order_by(AssessmentInvitation.invited_at.desc())
        .all()
    )

    invite_list = []
    for inv in invitations:
        app = get_application_for_recruiter(inv.application_id, recruiter, db)
        invite_list.append(
            {
                "id": inv.id,
                "application_id": inv.application_id,
                "candidate_name": app.full_name if app else "Unknown",
                "candidate_email": app.email if app else "",
                "status": inv.status,
                "score": inv.score,
                "max_score": inv.max_score,
                "skills_breakdown": json.loads(inv.skills_breakdown)
                if inv.skills_breakdown
                else None,
                "duration_seconds": inv.duration_seconds,
                "plagiarism_flag": inv.plagiarism_flag,
                "invited_at": inv.invited_at.isoformat() if inv.invited_at else None,
                "completed_at": inv.completed_at.isoformat()
                if inv.completed_at
                else None,
                "invite_url": inv.invite_url,
            }
        )

    job = get_job_for_recruiter(assessment.job_id, recruiter, db)

    return {
        "id": assessment.id,
        "job_id": assessment.job_id,
        "job_title": job.title if job else None,
        "provider": assessment.provider,
        "provider_test_id": assessment.provider_test_id,
        "test_name": assessment.test_name,
        "difficulty": assessment.difficulty,
        "duration_minutes": assessment.duration_minutes,
        "skills": json.loads(assessment.skills) if assessment.skills else [],
        "status": assessment.status,
        "created_at": assessment.created_at.isoformat()
        if assessment.created_at
        else None,
        "invitations": invite_list,
        "total_invited": len(invite_list),
        "completed_count": sum(1 for i in invite_list if i["status"] == "completed"),
    }


@router.post("/{assessment_id}/invite/{application_id}")
async def invite_candidate(
    assessment_id: int,
    application_id: int,
    req: InviteCandidateRequest = None,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    assessment = (
        db.query(Assessment)
        .join(CompanyMember, CompanyMember.user_id == Assessment.recruiter_id)
        .filter(
            Assessment.id == assessment_id,
            CompanyMember.company_id == getattr(recruiter, "_company_id", None),
            CompanyMember.is_active,
        )
        .first()
    )
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    if assessment.status != "active":
        raise HTTPException(status_code=400, detail="Assessment is not active")

    app = get_application_for_recruiter(application_id, recruiter, db)

    existing = (
        db.query(AssessmentInvitation)
        .filter(
            AssessmentInvitation.assessment_id == assessment_id,
            AssessmentInvitation.application_id == application_id,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=400, detail="Candidate already invited to this assessment"
        )

    send_email = req.send_email if req else True

    try:
        result = await AssessmentService.invite_candidate(
            provider=assessment.provider,
            test_id=assessment.provider_test_id,
            application_id=application_id,
            candidate_email=app.email,
            candidate_name=app.full_name,
            send_email=send_email,
            db=db,
        )
        return result
    except Exception as e:
        logger.error(f"Invite failed: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to invite candidate: {str(e)}"
        )


@router.post("/{assessment_id}/bulk-invite")
async def bulk_invite(
    assessment_id: int,
    req: BulkInviteRequest,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    assessment = (
        db.query(Assessment)
        .join(CompanyMember, CompanyMember.user_id == Assessment.recruiter_id)
        .filter(
            Assessment.id == assessment_id,
            CompanyMember.company_id == getattr(recruiter, "_company_id", None),
            CompanyMember.is_active,
        )
        .first()
    )
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    if assessment.status != "active":
        raise HTTPException(status_code=400, detail="Assessment is not active")

    results = []
    errors = []

    for app_id in req.application_ids:
        app = get_application_for_recruiter(app_id, recruiter, db)

        existing = (
            db.query(AssessmentInvitation)
            .filter(
                AssessmentInvitation.assessment_id == assessment_id,
                AssessmentInvitation.application_id == app_id,
            )
            .first()
        )
        if existing:
            errors.append({"application_id": app_id, "error": "Already invited"})
            continue

        try:
            result = await AssessmentService.invite_candidate(
                provider=assessment.provider,
                test_id=assessment.provider_test_id,
                application_id=app_id,
                candidate_email=app.email,
                candidate_name=app.full_name,
                send_email=req.send_email,
                db=db,
            )
            results.append(result)
        except Exception as e:
            errors.append({"application_id": app_id, "error": str(e)})

    return {
        "successful": len(results),
        "failed": len(errors),
        "results": results,
        "errors": errors,
    }


@router.get("/{assessment_id}/results")
def get_assessment_results(
    assessment_id: int,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    assessment = (
        db.query(Assessment)
        .join(CompanyMember, CompanyMember.user_id == Assessment.recruiter_id)
        .filter(
            Assessment.id == assessment_id,
            CompanyMember.company_id == getattr(recruiter, "_company_id", None),
            CompanyMember.is_active,
        )
        .first()
    )
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    invitations = (
        db.query(AssessmentInvitation)
        .filter(
            AssessmentInvitation.assessment_id == assessment.id,
            AssessmentInvitation.status == "completed",
        )
        .order_by(AssessmentInvitation.completed_at.desc())
        .all()
    )

    results = []
    for inv in invitations:
        app = get_application_for_recruiter(inv.application_id, recruiter, db)
        results.append(
            {
                "invitation_id": inv.id,
                "application_id": inv.application_id,
                "candidate_name": app.full_name if app else "Unknown",
                "candidate_email": app.email if app else "",
                "score": inv.score,
                "max_score": inv.max_score,
                "percentage": round((inv.score / inv.max_score * 100), 1)
                if inv.score and inv.max_score
                else None,
                "skills_breakdown": json.loads(inv.skills_breakdown)
                if inv.skills_breakdown
                else None,
                "duration_seconds": inv.duration_seconds,
                "plagiarism_flag": inv.plagiarism_flag,
                "completed_at": inv.completed_at.isoformat()
                if inv.completed_at
                else None,
            }
        )

    return {
        "assessment_id": assessment.id,
        "test_name": assessment.test_name,
        "results": results,
        "total_completed": len(results),
    }


@router.get("/{assessment_id}/candidate/{application_id}/result")
def get_candidate_result(
    assessment_id: int,
    application_id: int,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    assessment = (
        db.query(Assessment)
        .join(CompanyMember, CompanyMember.user_id == Assessment.recruiter_id)
        .filter(
            Assessment.id == assessment_id,
            CompanyMember.company_id == getattr(recruiter, "_company_id", None),
            CompanyMember.is_active,
        )
        .first()
    )
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    invitation = (
        db.query(AssessmentInvitation)
        .filter(
            AssessmentInvitation.assessment_id == assessment_id,
            AssessmentInvitation.application_id == application_id,
        )
        .first()
    )
    if not invitation:
        raise HTTPException(status_code=404, detail="Invitation not found")

    app = get_application_for_recruiter(application_id, recruiter, db)

    return {
        "invitation_id": invitation.id,
        "application_id": invitation.application_id,
        "candidate_name": app.full_name if app else "Unknown",
        "candidate_email": app.email if app else "",
        "status": invitation.status,
        "score": invitation.score,
        "max_score": invitation.max_score,
        "percentage": round((invitation.score / invitation.max_score * 100), 1)
        if invitation.score and invitation.max_score
        else None,
        "skills_breakdown": json.loads(invitation.skills_breakdown)
        if invitation.skills_breakdown
        else None,
        "duration_seconds": invitation.duration_seconds,
        "plagiarism_flag": invitation.plagiarism_flag,
        "invited_at": invitation.invited_at.isoformat()
        if invitation.invited_at
        else None,
        "completed_at": invitation.completed_at.isoformat()
        if invitation.completed_at
        else None,
        "invite_url": invitation.invite_url,
    }


@router.get("/available-tests")
def get_available_tests(
    provider: str,
    recruiter: User = Depends(require_recruiter),
):
    from backend.config import get_settings

    settings = get_settings()
    api_key = ""
    if provider == "hackerrank":
        api_key = settings.hackerrank_api_key or ""
    elif provider == "codility":
        api_key = settings.codility_api_key or ""

    if not api_key:
        raise HTTPException(
            status_code=400, detail=f"API key not configured for {provider}"
        )

    try:
        tests = AssessmentService.get_available_tests(provider, api_key)
        return {"provider": provider, "tests": tests}
    except Exception as e:
        logger.error(f"Failed to list tests: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{assessment_id}/close")
def close_assessment(
    assessment_id: int,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    assessment = (
        db.query(Assessment)
        .join(CompanyMember, CompanyMember.user_id == Assessment.recruiter_id)
        .filter(
            Assessment.id == assessment_id,
            CompanyMember.company_id == getattr(recruiter, "_company_id", None),
            CompanyMember.is_active,
        )
        .first()
    )
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    assessment.status = "closed"
    db.commit()
    return {"message": "Assessment closed", "id": assessment.id}


@router.post("/{assessment_id}/reopen")
def reopen_assessment(
    assessment_id: int,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    assessment = (
        db.query(Assessment)
        .join(CompanyMember, CompanyMember.user_id == Assessment.recruiter_id)
        .filter(
            Assessment.id == assessment_id,
            CompanyMember.company_id == getattr(recruiter, "_company_id", None),
            CompanyMember.is_active,
        )
        .first()
    )
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    assessment.status = "active"
    db.commit()
    return {"message": "Assessment reopened", "id": assessment.id}
