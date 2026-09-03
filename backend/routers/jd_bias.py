from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.bias_detection_jd import JDBiasDetector
from backend.database import Job, User
from backend.dependencies import get_db, require_recruiter
from backend.logger import logger
from backend.simple_rate_limiter import SimpleRateLimiter
from backend.tenant import get_current_company_id

router = APIRouter(prefix="/jd", tags=["JD Bias Detection"])

jd_rate_limiter = SimpleRateLimiter()


class AnalyzeRequest(BaseModel):
    title: str
    description: str
    skills: Optional[List[str]] = None


class RewriteRequest(BaseModel):
    title: str
    description: str
    style: str = "neutral"


@router.post("/analyze")
async def analyze_jd(
    request: Request,
    body: AnalyzeRequest,
    recruiter: User = Depends(require_recruiter),
):
    _company_id = get_current_company_id(recruiter)
    client_ip = request.client.host if request.client else "unknown"
    allowed, retry_after = jd_rate_limiter.is_allowed(
        f"jd_analyze:{client_ip}", max_requests=20, window_seconds=3600
    )
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Try again in {retry_after} seconds.",
        )

    if not body.description.strip():
        raise HTTPException(status_code=400, detail="Description cannot be empty")

    try:
        result = await JDBiasDetector.analyze_jd(
            body.title, body.description, body.skills
        )
        return result
    except Exception as e:
        logger.error(f"[JD Bias] Analysis error: {e}")
        raise HTTPException(
            status_code=500, detail="Analysis failed. Please try again."
        )


@router.post("/analyze/{job_id}")
async def analyze_existing_jd(
    job_id: int,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    company_id = get_current_company_id(recruiter)
    job = db.query(Job).filter(Job.id == job_id, Job.company_id == company_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    try:
        skills = []
        if job.required_skills:
            skills = [s.strip() for s in job.required_skills.split(",") if s.strip()]
        result = await JDBiasDetector.analyze_jd(
            job.title or "", job.description or "", skills
        )
        result["job_id"] = job.id
        result["job_title"] = job.title
        return result
    except Exception as e:
        logger.error(f"[JD Bias] Analysis error for job {job_id}: {e}")
        raise HTTPException(
            status_code=500, detail="Analysis failed. Please try again."
        )


@router.post("/rewrite")
async def rewrite_jd(
    body: RewriteRequest,
    recruiter: User = Depends(require_recruiter),
):
    if not body.description.strip():
        raise HTTPException(status_code=400, detail="Description cannot be empty")

    if body.style not in ("neutral", "warm", "professional", "innovative"):
        raise HTTPException(status_code=400, detail=f"Invalid style: {body.style}")

    try:
        flags = JDBiasDetector.rule_based_scan(body.description)
        result = await JDBiasDetector.generate_inclusive_rewrite(
            body.description, flags, body.style
        )
        return result
    except Exception as e:
        logger.error(f"[JD Bias] Rewrite error: {e}")
        raise HTTPException(status_code=500, detail="Rewrite failed. Please try again.")


@router.get("/word-lists")
async def get_word_lists(recruiter: User = Depends(require_recruiter)):
    return JDBiasDetector.get_word_lists()
