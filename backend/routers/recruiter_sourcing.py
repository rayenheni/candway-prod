import json
from datetime import UTC, datetime
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.authz import get_job_for_recruiter
from backend.database import CompanyMember, SourcedCandidate, User
from backend.dependencies import get_db, require_recruiter
from backend.email_service import email_service
from backend.logger import logger
from backend.sourcing_agent import SourcingAgent

router = APIRouter(prefix="/recruiter/sourcing", tags=["Recruiter Sourcing"])


class BulkInviteRequest(BaseModel):
    candidate_ids: List[int]


class InviteRequest(BaseModel):
    subject: Optional[str] = None
    body: Optional[str] = None


@router.post("/source/{job_id}")
async def trigger_sourcing(
    job_id: int,
    background_tasks: BackgroundTasks,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    _job = get_job_for_recruiter(job_id, recruiter, db)

    background_tasks.add_task(SourcingAgent.source_for_job, job_id, recruiter.id, db)

    return {"status": "processing", "sourced_count": 0, "job_id": job_id}


@router.get("/results/{job_id}")
async def get_sourcing_results(
    job_id: int,
    source: Optional[str] = None,
    min_score: Optional[float] = None,
    page: int = 1,
    per_page: int = 20,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    job = get_job_for_recruiter(job_id, recruiter, db)

    query = db.query(SourcedCandidate).filter(
        SourcedCandidate.recruiter_id == recruiter.id,
        SourcedCandidate.job_id == job_id,
        not SourcedCandidate.is_hidden,
    )

    if source:
        query = query.filter(SourcedCandidate.source == source)
    if min_score is not None:
        query = query.filter(SourcedCandidate.match_score >= min_score)

    # M6 FIX: was returning all rows with no pagination
    per_page = max(1, min(per_page, 100))
    offset = (max(1, page) - 1) * per_page
    total = query.count()

    candidates = (
        query.order_by(SourcedCandidate.match_score.desc())
        .offset(offset)
        .limit(per_page)
        .all()
    )

    scores = [c.match_score for c in candidates if c.match_score is not None]
    avg_score = round(sum(scores) / len(scores), 1) if scores else 0
    sources_used = list(set(c.source for c in candidates if c.source))

    return {
        "candidates": [
            {
                "id": c.id,
                "source": c.source,
                "source_id": c.source_id,
                "name": c.name,
                "email": c.email,
                "headline": c.headline,
                "location": c.location,
                "profile_url": c.profile_url,
                "avatar_url": c.avatar_url,
                "skills": c.skills.split(", ") if c.skills else [],
                "bio": c.bio,
                "match_score": c.match_score,
                "match_data": json.loads(c.match_data) if c.match_data else {},
                "invited_at": c.invited_at.isoformat() if c.invited_at else None,
                "responded_at": c.responded_at.isoformat() if c.responded_at else None,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in candidates
        ],
        "meta": {
            "total_found": total,
            "page": page,
            "per_page": per_page,
            "pages": (total + per_page - 1) // per_page,
            "sources_used": sources_used,
            "avg_score": avg_score,
            "job_title": job.title,
        },
    }


@router.post("/candidates/{candidate_id}/invite")
async def invite_candidate(
    candidate_id: int,
    invite: Optional[InviteRequest] = None,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    candidate = (
        db.query(SourcedCandidate)
        .join(CompanyMember, CompanyMember.user_id == SourcedCandidate.recruiter_id)
        .filter(
            SourcedCandidate.id == candidate_id,
            CompanyMember.company_id == getattr(recruiter, "_company_id", None),
            CompanyMember.is_active,
        )
        .first()
    )
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    job = get_job_for_recruiter(candidate.job_id, recruiter, db)

    subject = (
        invite.subject if invite and invite.subject else f"Job Opportunity: {job.title}"
    )
    body = (
        invite.body
        if invite and invite.body
        else f"""
<p>Hello {candidate.name},</p>
<p>We found your profile on <strong>{candidate.source.title()}</strong> and were impressed by your background.</p>
<p>We are looking for a <strong>{job.title}</strong> at <strong>{job.company_name}</strong>. Your skills and experience seem like a great match.</p>
<p>Would you be interested in learning more? Please visit our careers page to apply.</p>
<p>Best regards,<br>{recruiter.name or recruiter.email}<br>{job.company_name}</p>
"""
    )

    # B1 FIX: use the candidate's actual email, not an empty string
    candidate_email = (candidate.email or "").strip()
    if not candidate_email:
        logger.warning(
            f"Sourced candidate {candidate.id} ({candidate.name}) has no email — skipping invite send"
        )
        # Still mark as invited so the recruiter sees the attempt
        candidate.invited_at = datetime.now(UTC)
        db.commit()
        return {
            "status": "invited_no_email",
            "candidate_id": candidate_id,
            "subject": subject,
        }

    try:
        email_service.send_email(
            to_email=candidate_email,
            subject=subject,
            body=body,
        )
        logger.info(
            f"Invite sent to {candidate.name} ({candidate_email}) for job {job.title}"
        )
    except Exception as e:
        logger.error(f"Failed to send invite email: {e}")

    candidate.invited_at = datetime.now(UTC)
    db.commit()

    return {"status": "invited", "candidate_id": candidate_id, "subject": subject}


@router.post("/candidates/bulk-invite")
async def bulk_invite_candidates(
    req: BulkInviteRequest,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    invited = []
    errors = []

    for cid in req.candidate_ids:
        candidate = (
            db.query(SourcedCandidate)
            .join(CompanyMember, CompanyMember.user_id == SourcedCandidate.recruiter_id)
            .filter(
                SourcedCandidate.id == cid,
                CompanyMember.company_id == getattr(recruiter, "_company_id", None),
                CompanyMember.is_active,
            )
            .first()
        )
        if not candidate:
            errors.append({"candidate_id": cid, "error": "Not found"})
            continue

        job = get_job_for_recruiter(candidate.job_id, recruiter, db)
        subject = f"Job Opportunity: {job.title if job else 'Position'}"

        # B1 FIX: use the candidate's actual email, skip if missing
        candidate_email = (candidate.email or "").strip()
        if not candidate_email:
            errors.append(
                {"candidate_id": cid, "error": "Candidate has no email address"}
            )
            continue

        try:
            email_service.send_email(
                to_email=candidate_email,
                subject=subject,
                body=f"<p>Hello {candidate.name},</p><p>We found your profile on {candidate.source.title()}.</p>",
            )
            candidate.invited_at = datetime.now(UTC)
            invited.append(cid)
        except Exception as e:
            errors.append({"candidate_id": cid, "error": str(e)})

    db.commit()

    return {
        "status": "completed",
        "invited_count": len(invited),
        "invited": invited,
        "errors": errors,
    }


@router.get("/stats")
async def get_sourcing_stats(
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    company_id = getattr(recruiter, "_company_id", None)
    total_sourced = (
        db.query(func.count(SourcedCandidate.id))
        .join(CompanyMember, CompanyMember.user_id == SourcedCandidate.recruiter_id)
        .filter(
            CompanyMember.company_id == company_id,
            CompanyMember.is_active,
            not SourcedCandidate.is_hidden,
        )
        .scalar()
    )

    total_invited = (
        db.query(func.count(SourcedCandidate.id))
        .join(CompanyMember, CompanyMember.user_id == SourcedCandidate.recruiter_id)
        .filter(
            CompanyMember.company_id == company_id,
            CompanyMember.is_active,
            SourcedCandidate.invited_at.isnot(None),
            not SourcedCandidate.is_hidden,
        )
        .scalar()
    )

    total_responded = (
        db.query(func.count(SourcedCandidate.id))
        .join(CompanyMember, CompanyMember.user_id == SourcedCandidate.recruiter_id)
        .filter(
            CompanyMember.company_id == company_id,
            CompanyMember.is_active,
            SourcedCandidate.responded_at.isnot(None),
            not SourcedCandidate.is_hidden,
        )
        .scalar()
    )

    by_source = (
        db.query(
            SourcedCandidate.source,
            func.count(SourcedCandidate.id),
        )
        .join(CompanyMember, CompanyMember.user_id == SourcedCandidate.recruiter_id)
        .filter(
            CompanyMember.company_id == company_id,
            CompanyMember.is_active,
            not SourcedCandidate.is_hidden,
        )
        .group_by(SourcedCandidate.source)
        .all()
    )

    return {
        "total_sourced": total_sourced,
        "total_invited": total_invited,
        "total_responded": total_responded,
        "response_rate": round(total_responded / total_invited * 100, 1)
        if total_invited > 0
        else 0,
        "by_source": {src: count for src, count in by_source},
    }
