"""Saved-jobs endpoints for candidates.

Bug B-24: the ``/candidate/saved-jobs`` page existed and the
``SavedJob`` model was defined, but no API endpoints were wired
up. Candidates clicking the heart icon on a job in the job feed
got nothing; the saved-jobs page itself was hardcoded mock data.

This module adds the missing GET / POST / DELETE surface. The
router is registered under the ``/candidate`` prefix by
``backend.routers.candidate.__init__``.
"""

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from backend.database import Job, SavedJob, User
from backend.dependencies import get_current_user, get_db
from backend.profile_helpers import get_user_company_name

router = APIRouter(tags=["candidate"])
logger = logging.getLogger(__name__)


class SavedJobOut(BaseModel):
    id: int
    job_id: int
    job_title: str | None = None
    company_name: str | None = None
    location: str | None = None
    job_type: str | None = None
    salary_range: str | None = None
    match_score: float | None = None
    created_at: str | None = None


@router.get("/saved-jobs", response_model=dict)
def list_saved_jobs(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(SavedJob)
        .options(joinedload(SavedJob.job).joinedload(Job.recruiter))
        .filter(SavedJob.user_id == current_user.id)
        .order_by(SavedJob.created_at.desc())
        .all()
    )
    items: List[SavedJobOut] = []
    for row in rows:
        job = row.job
        if job is None:
            continue
        company = None
        try:
            company = get_user_company_name(job.recruiter) if job.recruiter else None
        except Exception:
            company = None
        items.append(
            SavedJobOut(
                id=row.id,
                job_id=job.id,
                job_title=job.title,
                company_name=company,
                location=job.location,
                job_type=job.job_type,
                salary_range=(
                    f"{job.salary_min}-{job.salary_max} {job.salary_currency}"
                    if job.salary_min
                    else None
                ),
                match_score=None,
                created_at=row.created_at.isoformat() if row.created_at else None,
            )
        )
    return {"saved_jobs": [item.dict() for item in items], "count": len(items)}


class SaveJobRequest(BaseModel):
    job_id: int


@router.post("/saved-jobs")
def save_job(
    payload: SaveJobRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    job = db.query(Job).filter(Job.id == payload.job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    existing = (
        db.query(SavedJob)
        .filter(
            SavedJob.user_id == current_user.id,
            SavedJob.job_id == payload.job_id,
        )
        .first()
    )
    if existing:
        return {"message": "Job already saved", "saved_job_id": existing.id}

    row = SavedJob(user_id=current_user.id, job_id=payload.job_id)
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # Race: another tab saved the same job. Return that one.
        existing = (
            db.query(SavedJob)
            .filter(
                SavedJob.user_id == current_user.id,
                SavedJob.job_id == payload.job_id,
            )
            .first()
        )
        if existing:
            return {"message": "Job already saved", "saved_job_id": existing.id}
        raise
    return {"message": "Job saved", "saved_job_id": row.id}


@router.delete("/saved-jobs/{saved_job_id}")
def remove_saved_job(
    saved_job_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = (
        db.query(SavedJob)
        .filter(
            SavedJob.id == saved_job_id,
            SavedJob.user_id == current_user.id,
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Saved job not found")
    db.delete(row)
    db.commit()
    return {"message": "Saved job removed"}
