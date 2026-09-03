import csv
import io
import json
import re
from datetime import UTC, datetime, timedelta
from typing import List, Optional

import bleach
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, field_validator
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, selectinload

from backend.ai.llm import call_groq_cascade
from backend.authz import get_job_for_recruiter, get_rubric_for_recruiter
from backend.auto_job_creator import AutoJobCreator
from backend.bias_detection_jd import JDBiasDetector
from backend.database import (
    Application,
    CompanyMember,
    EvaluationResult,
    EvaluationSession,
    Job,
    JobPipelineStage,
    Rubric,
    User,
)
from backend.pdf_generator import PDFReport
from backend.dependencies import (
    get_db,
    get_pagination_meta,
    paginate,
    require_credits,
    require_recruiter,
)
from backend.logger import logger
from backend.optimistic_lock import retry_stale
from backend.profile_helpers import get_user_company_name
from backend.repository.metrics_repository import MetricsRepository
from backend.schemas import AutoJobCreateRequest, JobCreate
from backend.subscription_service import SubscriptionService

router = APIRouter(prefix="/recruiter", tags=["Recruiter Jobs"])

# S3 FIX: strip any HTML/control chars from recruiter-supplied strings
# before they reach the LLM prompt. We allow only printable ASCII/Unicode
# text — no angle brackets, no backticks, no system-prompt-like patterns.
_PROMPT_INJECTION_RE = re.compile(
    r"(ignore\s+previous|disregard\s+instructions?|system\s*prompt|you\s+are\s+now)",
    re.IGNORECASE,
)


def _sanitize_for_prompt(value: str, max_len: int = 200) -> str:
    """Strip HTML, truncate, and reject obvious prompt-injection attempts."""
    cleaned = bleach.clean(value, tags=[], strip=True).strip()
    cleaned = cleaned[:max_len]
    if _PROMPT_INJECTION_RE.search(cleaned):
        raise HTTPException(
            status_code=400,
            detail="Invalid characters or content detected in input.",
        )
    return cleaned


class JobGenRequest(BaseModel):
    title: str
    skills: List[str]

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("title cannot be empty")
        return v.strip()[:200]

    @field_validator("skills")
    @classmethod
    def validate_skills(cls, v: List[str]) -> List[str]:
        return [s.strip()[:100] for s in v if s.strip()][:20]  # max 20 skills


class JobUpdate(BaseModel):
    title: Optional[str] = None
    company_name: Optional[str] = None
    location: Optional[str] = None
    salary_range: Optional[str] = None
    type: Optional[str] = None
    description: Optional[str] = None
    required_skills: Optional[List[str]] = None
    interview_instructions: Optional[str] = None
    total_questions: Optional[int] = None
    time_limit_seconds: Optional[int] = None
    duration_minutes: Optional[int] = None
    category_id: Optional[int] = None


@router.post("/generate-job")
async def generate_job_description(
    req: JobGenRequest,
    recruiter: User = Depends(require_recruiter),
    _credit_tx: object = Depends(require_credits("jd_writer", credits=2)),
):
    # S3 FIX: sanitize inputs before building the prompt
    safe_title = _sanitize_for_prompt(req.title)
    safe_skills = [_sanitize_for_prompt(s, max_len=100) for s in req.skills]

    prompt = f"""
    You are an expert HR Specialist. Write a compelling, professional Job Description for:
    Role: {safe_title}
    Skills: {", ".join(safe_skills)}
    Format nicely with clear sections.
    Structure:
    1. **About the Role**: 2 sentences hook.
    2. **Key Responsibilities**: 3-4 bullet points.
    3. **Requirements**: 3-4 bullet points matching the skills.
    4. **Why Join Us**: 1 inspiring sentence.
    Return strictly JSON: {{ "description": "The full formatted text..." }}
    """
    try:
        res = await call_groq_cascade(
            [{"role": "user", "content": prompt}], json_mode=True
        )
        return res
    except Exception as e:
        logger.error(f"Job Gen Error: {e}")
        return {
            "description": f"We are looking for a skilled {safe_title} proficient in {', '.join(safe_skills)}.\n\nResponsibilities:\n- Lead projects\n- Collaborate with team\n\nRequirements:\n- Experience with listed skills."
        }


@router.post("/jobs/auto-create")
async def auto_create_job(
    req: AutoJobCreateRequest,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    creator = AutoJobCreator(db, recruiter)

    try:
        result = await creator.run(
            title=req.title,
            skills=req.skills,
            seniority=req.seniority,
            company=req.company,
            location=req.location,
            type_=req.type,
            description_override=req.description_override,
        )
        return result
    except ValueError as exc:
        if str(exc) == "Job slot limit reached for your current plan.":
            raise HTTPException(
                status_code=403,
                detail=str(exc),
            ) from exc
        raise


@router.patch("/jobs/{job_id}/category")
@retry_stale()
def update_job_category(
    job_id: int,
    body: dict,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    job = get_job_for_recruiter(job_id, recruiter, db)
    if job.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Job not found")
    category_id = body.get("category_id")
    if category_id is not None:
        from backend.database import Category

        cat = db.query(Category).filter(Category.id == category_id).first()
        if not cat:
            raise HTTPException(status_code=400, detail="Category not found")
    job.category_id = category_id
    db.commit()
    return {"success": True, "category_id": job.category_id}


@router.get("/jobs/my")
def get_my_jobs(
    page: int = 1,
    per_page: int = 20,
    search: Optional[str] = None,
    type: Optional[str] = None,
    location: Optional[str] = None,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    company_id = getattr(recruiter, "_company_id", None)
    if company_id:
        query = (
            db.query(Job)
            .join(CompanyMember, CompanyMember.user_id == Job.recruiter_id)
            .filter(
                Job.deleted_at.is_(None),
                CompanyMember.company_id == company_id,
                CompanyMember.is_active,
            )
        )
    else:
        query = db.query(Job).filter(
            Job.deleted_at.is_(None),
            Job.recruiter_id == recruiter.id,
        )
    # Apply Filters
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(Job.title.ilike(search_term), Job.description.ilike(search_term))
        )
    if type and type != "All Types":
        query = query.filter(Job.type == type)

    if location and location != "All Locations":
        if location == "Remote":
            query = query.filter(Job.location.ilike("%Remote%"))
        elif location == "On-site":
            query = query.filter(Job.location.notilike("%Remote%"))
        else:
            loc_term = f"%{location.strip()}%"
            query = query.filter(Job.location.ilike(loc_term))

    # Get total count for pagination
    total_count = query.count()
    # Get paginated jobs
    # Re-apply ordering
    query = query.order_by(Job.created_at.desc())
    jobs = paginate(query, page, per_page).all()
    # Batch fetch applicant counts to prevent N+1
    job_ids = [j.id for j in jobs]
    app_counts = (
        MetricsRepository(db).get_job_applicant_counts(job_ids) if job_ids else {}
    )

    results = []
    for job in jobs:
        bias_flags = JDBiasDetector.rule_based_scan(job.description or "")
        llm_fallback = {
            "gender_inclusivity_score": 70,
            "age_inclusivity_score": 70,
            "requirement_fairness_score": 70,
            "confidence_balance_score": 70,
            "accessibility_score": 70,
            "overall_inclusivity_score": 70,
        }
        bias_scores = JDBiasDetector.compute_score(bias_flags, llm_fallback)
        category_name = job.category_rel.name if job.category_rel else None
        job_dict = {
            "id": job.id,
            "title": job.title,
            "company": job.company_name,
            "location": job.location,
            "salary_range": job.salary_range,
            "type": job.type,
            "description": job.description,
            "required_skills": job.required_skills,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "is_active": job.is_active,
            "status": "published" if job.is_active else "draft",
            "views": job.views,
            "applicant_count": app_counts.get(job.id, 0),
            "bias_score": bias_scores["overall_score"],
            "bias_grade": bias_scores["grade"],
            "category_id": job.category_id,
            "category_name": category_name,
        }
        results.append(job_dict)
    # Return with pagination metadata
    return {
        "items": results,
        "pagination": get_pagination_meta(total_count, page, per_page),
    }


@router.get("/jobs/{job_id}")
@retry_stale()
def get_job_detail(
    job_id: int,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    job = get_job_for_recruiter(job_id, recruiter, db)
    if job.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Job not found")
    category_name = job.category_rel.name if job.category_rel else None
    app_counts = MetricsRepository(db).get_job_applicant_counts([job.id])

    # ── Resolve required_skills (string → list) ────────────────
    required_skills_raw = job.required_skills
    # Fallback: extract from linked rubric if empty
    if not required_skills_raw and job.rubric_id:
        rubric = (
            db.query(Rubric)
            .filter(
                Rubric.id == job.rubric_id,
                Rubric.company_id == job.company_id,
                Rubric.is_active,
            )
            .first()
        )
        if rubric and rubric.criteria_json:
            try:
                raw = rubric.criteria_json
                cats = json.loads(raw).get("categories", []) if isinstance(raw, str) else (
                    raw.get("categories", []) if isinstance(raw, dict) else raw
                )
                names = []
                for cat in cats:
                    for sk in cat.get("skills", []):
                        if sk.get("name"):
                            names.append(sk["name"])
                    for sub in cat.get("subcategories", []):
                        for sk in sub.get("skills", []):
                            if sk.get("name"):
                                names.append(sk["name"])
                if names:
                    required_skills_raw = ", ".join(names)
            except Exception:
                pass

    # ── Resolve description from Role & Outcomes fallback ──────
    description = job.description
    if not description:
        from backend.database import JobRoleOverview
        role_overviews = (
            db.query(JobRoleOverview)
            .filter(JobRoleOverview.job_id == job.id)
            .order_by(JobRoleOverview.question_key)
            .all()
        )
        if role_overviews:
            sections = []
            for rv in role_overviews:
                if rv.answer and rv.answer.strip():
                    sections.append(f"<h3>{rv.question}</h3>\n<p>{rv.answer}</p>")
            if sections:
                description = "\n\n".join(sections)

    return {
        "id": job.id,
        "title": job.title,
        "company": job.company_name,
        "location": job.location,
        "salary_range": job.salary_range,
        "type": job.type,
        "description": description,
        "required_skills": required_skills_raw,
        "interview_instructions": job.interview_instructions,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "is_active": job.is_active,
        "status": "published" if job.is_active else "draft",
        "views": job.views,
        "applicant_count": app_counts.get(job.id, 0),
        "category_id": job.category_id,
        "category_name": category_name,
    }


@router.patch("/jobs/{job_id}")
@retry_stale()
def update_job(
    job_id: int,
    payload: JobUpdate,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    job = get_job_for_recruiter(job_id, recruiter, db)
    if job.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Job not found")
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        if value is not None:
            setattr(job, field, value)
    db.commit()
    db.refresh(job)
    category_name = job.category_rel.name if job.category_rel else None
    app_counts = MetricsRepository(db).get_job_applicant_counts([job.id])
    return {
        "id": job.id,
        "title": job.title,
        "company": job.company_name,
        "location": job.location,
        "salary_range": job.salary_range,
        "type": job.type,
        "description": job.description,
        "required_skills": job.required_skills,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "is_active": job.is_active,
        "views": job.views,
        "applicant_count": app_counts.get(job.id, 0),
        "category_id": job.category_id,
        "category_name": category_name,
    }


@router.post("/jobs/{job_id}/publish")
@retry_stale()
def publish_job(
    job_id: int,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    job = get_job_for_recruiter(job_id, recruiter, db)
    if job.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Job not found")
    job.is_active = True
    db.commit()
    return {"message": "Job published", "id": job.id, "is_active": True}


@router.post("/jobs/{job_id}/close")
@retry_stale()
def close_job(
    job_id: int,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    job = get_job_for_recruiter(job_id, recruiter, db)
    if job.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Job not found")
    job.is_active = False
    db.commit()
    return {"message": "Job closed", "id": job.id, "is_active": False}


@router.get("/jobs/{job_id}/analytics")
def get_job_analytics(
    job_id: int,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    job = get_job_for_recruiter(job_id, recruiter, db)
    company_id = getattr(recruiter, "_company_id", None)
    metrics = MetricsRepository(db)
    app_counts = metrics.get_job_applicant_counts([job.id])
    return {
        "job_id": job.id,
        "views": job.views,
        "applicant_count": app_counts.get(job.id, 0),
        "is_active": job.is_active,
    }


@router.post("/jobs")
@retry_stale()
def create_job(
    job: JobCreate,
    background_tasks: BackgroundTasks,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    company_name = job.company_name or get_user_company_name(recruiter)
    if not company_name:
        raise HTTPException(
            status_code=400,
            detail="Company Name is required. Please update your profile settings or provide it for this job.",
        )

    # Check for duplicate within 24 hours
    company_id = getattr(recruiter, "_company_id", None)
    if company_id:
        existing = (
            db.query(Job)
            .join(CompanyMember, CompanyMember.user_id == Job.recruiter_id)
            .filter(
                CompanyMember.company_id == company_id,
                CompanyMember.is_active,
                Job.title == job.title,
                Job.created_at >= datetime.now(UTC) - timedelta(hours=24),
            )
            .first()
        )
    else:
        existing = (
            db.query(Job)
            .filter(
                Job.recruiter_id == recruiter.id,
                Job.title == job.title,
                Job.created_at >= datetime.now(UTC) - timedelta(hours=24),
            )
            .first()
        )

    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Duplicate detected: You already posted a job with this title today (Job ID: {existing.id})",
        )


    new_job = Job(
        recruiter_id=recruiter.id,
        company_id=company_id,
        title=job.title,
        company_name=company_name,
        location=job.location,
        salary_range=job.salary_range,
        type=job.type,
        description=job.description,
        required_skills=", ".join(job.required_skills),
        interview_instructions=job.interview_instructions or None,
        total_questions=job.total_questions,
        time_limit_seconds=job.time_limit_seconds,
        duration_minutes=job.duration_minutes,
        category_id=job.category_id,
    )
    db.add(new_job)

    if not SubscriptionService.record_usage(
        recruiter, "create_job", db, commit=False
    ):
        db.rollback()
        raise HTTPException(
            status_code=403,
            detail="Job slot limit reached for your current plan.",
        )

    db.commit()
    db.refresh(new_job)

    # Link skill tree if provided
    if job.skill_tree_id:
        try:
            rubric = get_rubric_for_recruiter(job.skill_tree_id, recruiter, db)
            new_job.rubric_id = rubric.id
            db.commit()
            db.refresh(new_job)
            logger.info(f"Linked skill tree {rubric.id} to job {new_job.id}")
        except HTTPException:
            logger.warning(
                f"Skill tree {job.skill_tree_id} not found/accessible, skipping link"
            )

    if new_job.required_skills:
        skills_list = [
            s.strip() for s in new_job.required_skills.split(",") if s.strip()
        ]
        if skills_list:
            import json

            from backend.database import Rubric

            draft_rubric = {
                "version": 1,
                "seniority": "mid",
                "categories": [
                    {
                        "name": "Technical Skills",
                        "description": f"Core technical skills for {new_job.title}",
                        "weight": 1.0,
                        "subcategories": [
                            {
                                "name": "Required Skills",
                                "description": "Skills required for this role",
                                "weight": 1.0,
                                "skills": [
                                    {
                                        "name": skill,
                                        "description": f"Proficiency in {skill}",
                                        "weight": 1.0,
                                        "keywords": [skill.lower()],
                                        "levels": {
                                            "junior": [
                                                {
                                                    "score_threshold": 30,
                                                    "description": f"Basic knowledge of {skill}",
                                                    "keywords": [
                                                        f"basic {skill.lower()}",
                                                        f"fundamental {skill.lower()}",
                                                    ],
                                                    "sort_order": 1,
                                                },
                                                {
                                                    "score_threshold": 60,
                                                    "description": f"Working proficiency in {skill}",
                                                    "keywords": [
                                                        f"{skill.lower()} experience",
                                                        f"worked with {skill.lower()}",
                                                    ],
                                                    "sort_order": 2,
                                                },
                                                {
                                                    "score_threshold": 90,
                                                    "description": f"Expert in {skill}",
                                                    "keywords": [
                                                        f"expert {skill.lower()}",
                                                        f"advanced {skill.lower()}",
                                                    ],
                                                    "sort_order": 3,
                                                },
                                            ],
                                            "mid": [
                                                {
                                                    "score_threshold": 30,
                                                    "description": f"Basic knowledge of {skill}",
                                                    "keywords": [
                                                        f"basic {skill.lower()}",
                                                        f"fundamental {skill.lower()}",
                                                    ],
                                                    "sort_order": 1,
                                                },
                                                {
                                                    "score_threshold": 60,
                                                    "description": f"Working proficiency in {skill}",
                                                    "keywords": [
                                                        f"{skill.lower()} experience",
                                                        f"worked with {skill.lower()}",
                                                    ],
                                                    "sort_order": 2,
                                                },
                                                {
                                                    "score_threshold": 90,
                                                    "description": f"Expert in {skill}",
                                                    "keywords": [
                                                        f"expert {skill.lower()}",
                                                        f"advanced {skill.lower()}",
                                                    ],
                                                    "sort_order": 3,
                                                },
                                            ],
                                            "senior": [
                                                {
                                                    "score_threshold": 30,
                                                    "description": f"Basic knowledge of {skill}",
                                                    "keywords": [
                                                        f"basic {skill.lower()}",
                                                        f"fundamental {skill.lower()}",
                                                    ],
                                                    "sort_order": 1,
                                                },
                                                {
                                                    "score_threshold": 60,
                                                    "description": f"Working proficiency in {skill}",
                                                    "keywords": [
                                                        f"{skill.lower()} experience",
                                                        f"worked with {skill.lower()}",
                                                    ],
                                                    "sort_order": 2,
                                                },
                                                {
                                                    "score_threshold": 90,
                                                    "description": f"Expert in {skill}",
                                                    "keywords": [
                                                        f"expert {skill.lower()}",
                                                        f"advanced {skill.lower()}",
                                                    ],
                                                    "sort_order": 3,
                                                },
                                            ],
                                        },
                                        "is_required": True,
                                    }
                                    for skill in skills_list
                                ],
                            }
                        ],
                    }
                ],
            }
            draft = Rubric(
                job_id=new_job.id,
                company_id=company_id,
                version=0,
                is_active=0,
                created_by=recruiter.id,
                title=f"{new_job.title} — Auto-generated",
                criteria_json=json.dumps(draft_rubric),
            )
            db.add(draft)
            db.commit()
            logger.info(
                f"Auto-created draft rubric for job {new_job.id} with {len(skills_list)} skills"
            )

    from backend.routers.recruiter_reengagement import _run_analysis

    background_tasks.add_task(_run_analysis, new_job, recruiter.id)

    return new_job


@router.post("/jobs/{job_id}/clone")
@retry_stale()
def clone_job(
    job_id: int,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    job = get_job_for_recruiter(job_id, recruiter, db)


    new_job = Job(
        recruiter_id=recruiter.id,
        company_id=job.company_id,
        title=f"{job.title} (Copy)",
        company_name=job.company_name,
        location=job.location,
        salary_range=job.salary_range,
        type=job.type,
        description=job.description,
        required_skills=job.required_skills,
        interview_instructions=job.interview_instructions,
        category_id=job.category_id,
        is_active=True,
        views=0,
    )
    db.add(new_job)

    if not SubscriptionService.record_usage(
        recruiter, "create_job", db, commit=False
    ):
        db.rollback()
        raise HTTPException(
            status_code=403,
            detail="Job slot limit reached for your current plan.",
        )

    db.commit()
    db.refresh(new_job)

    return {
        "id": new_job.id,
        "title": new_job.title,
        "company": new_job.company_name,
        "location": new_job.location,
        "type": new_job.type,
        "description": new_job.description,
        "required_skills": new_job.required_skills,
        "created_at": new_job.created_at,
        "is_active": new_job.is_active,
        "views": new_job.views,
    }


@router.get("/jobs/{job_id}/pipeline-stages")
def get_job_pipeline_stages(
    job_id: int,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    job = get_job_for_recruiter(job_id, recruiter, db)
    stages = (
        db.query(JobPipelineStage)
        .filter(JobPipelineStage.job_id == job.id)
        .order_by(JobPipelineStage.sort_order)
        .all()
    )
    if not stages:
        return [
            {"name": "Applied", "slug": "applied", "color": "#64748b", "sort_order": 0},
            {
                "name": "Screening",
                "slug": "screening",
                "color": "#0ea5e9",
                "sort_order": 1,
            },
            {
                "name": "Interview",
                "slug": "interviewing",
                "color": "#8b5cf6",
                "sort_order": 2,
            },
            {
                "name": "Shortlisted",
                "slug": "shortlisted",
                "color": "#f59e0b",
                "sort_order": 3,
            },
            {"name": "Offer", "slug": "offer", "color": "#f97316", "sort_order": 4},
            {"name": "Hired", "slug": "hired", "color": "#10b981", "sort_order": 5},
        ]
    return [
        {"name": s.name, "slug": s.slug, "color": s.color, "sort_order": s.sort_order}
        for s in stages
    ]


@router.delete("/jobs/{job_id}")
@retry_stale()
def delete_job(
    job_id: int,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    job = get_job_for_recruiter(job_id, recruiter, db)
    # SOFT DELETE FIX
    job.is_active = False
    job.deleted_at = datetime.now(UTC)
    # Free up usage slot
    SubscriptionService.decrement_usage(recruiter, "create_job", db)
    db.commit()
    return {"message": "Job archived"}


# ── Job Report ──────────────────────────────────────────────

_FUNNEL_APPLIED = ["applied", "imported", "pending", "new", "invited"]
_FUNNEL_SCREENING = ["screening", "screened", "shortlisted", "analyzed", "analyzing", "analysis_failed"]
_FUNNEL_INTERVIEW = ["interviewing", "interview", "completed", "active"]
_FUNNEL_OFFER = ["offer", "offered", "offer_declined"]
_FUNNEL_HIRED = ["hired"]
_FUNNEL_REJECTED = ["rejected", "failed"]


def _build_job_report(db: Session, job: Job) -> dict:
    """Build a job-level recruitment report scoped to the given tenant job."""
    apps_q = (
        db.query(Application)
        .options(
            selectinload(Application.evaluation_sessions).selectinload(
                EvaluationSession.evaluation_result
            )
        )
        .filter(
            Application.job_id == job.id,
            Application.company_id == job.company_id,
            Application.deleted_at.is_(None),
        )
    )
    apps = apps_q.all()
    total = len(apps)

    status_counts: dict[str, int] = {}
    source_counts: dict[str, int] = {}
    avg_cv_values: list[float] = []
    avg_interview_values: list[float] = []
    for a in apps:
        status = a.status or "pending"
        status_counts[status] = status_counts.get(status, 0) + 1
        src = a.source or "Direct"
        source_counts[src] = source_counts.get(src, 0) + 1
        try:
            es = a.evaluation_sessions
            if es and es[0] and es[0].evaluation_result:
                er = es[0].evaluation_result
                if er.cv_score is not None:
                    avg_cv_values.append(float(er.cv_score))
                if er.final_score is not None:
                    avg_interview_values.append(float(er.final_score))
        except Exception:
            continue

    funnel = [
        {
            "stage": "Applied",
            "slug": "applied",
            "count": sum(status_counts.get(s, 0) for s in _FUNNEL_APPLIED),
        },
        {
            "stage": "Screening",
            "slug": "screening",
            "count": sum(status_counts.get(s, 0) for s in _FUNNEL_SCREENING),
        },
        {
            "stage": "Interview",
            "slug": "interviewing",
            "count": sum(status_counts.get(s, 0) for s in _FUNNEL_INTERVIEW),
        },
        {
            "stage": "Offer",
            "slug": "offer",
            "count": sum(status_counts.get(s, 0) for s in _FUNNEL_OFFER),
        },
        {
            "stage": "Hired",
            "slug": "hired",
            "count": sum(status_counts.get(s, 0) for s in _FUNNEL_HIRED),
        },
        {
            "stage": "Rejected",
            "slug": "rejected",
            "count": sum(status_counts.get(s, 0) for s in _FUNNEL_REJECTED),
        },
    ]
    for stage in funnel:
        stage["conversion"] = (
            round(stage["count"] / total * 100, 1) if total else 0
        )

    recent = []
    for a in sorted(apps, key=lambda x: x.created_at or datetime.min, reverse=True)[:10]:
        score = None
        try:
            es = a.evaluation_sessions
            if es and es[0] and es[0].evaluation_result:
                score = es[0].evaluation_result.final_score
        except Exception:
            score = None
        recent.append(
            {
                "id": a.id,
                "full_name": a.full_name or (a.email or "Candidate"),
                "email": a.email or "",
                "status": a.status,
                "score": score,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
        )

    return {
        "job": {
            "id": job.id,
            "title": job.title,
            "company": job.company_name,
            "location": job.location,
            "type": job.type,
            "status": "published" if job.is_active else "draft",
            "views": job.views,
            "created_at": job.created_at.isoformat() if job.created_at else None,
        },
        "summary": {
            "total_applicants": total,
            "views": job.views,
            "applicants_by_status": status_counts,
            "avg_cv_score": round(sum(avg_cv_values) / len(avg_cv_values), 1)
            if avg_cv_values
            else None,
            "avg_interview_score": round(
                sum(avg_interview_values) / len(avg_interview_values), 1
            )
            if avg_interview_values
            else None,
        },
        "funnel": funnel,
        "sources": source_counts,
        "recent_applicants": recent,
    }


@router.get("/jobs/{job_id}/report")
def get_job_report(
    job_id: int,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    job = get_job_for_recruiter(job_id, recruiter, db)
    if job.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Job not found")
    return _build_job_report(db, job)


@router.get("/jobs/{job_id}/report/export")
def export_job_report(
    job_id: int,
    format: str = Query("csv", pattern="^(csv|pdf)$"),
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    job = get_job_for_recruiter(job_id, recruiter, db)
    if job.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Job not found")
    report = _build_job_report(db, job)
    filename = f"job-{job.id}-report"

    if format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Job Report", job.title])
        writer.writerow(["Company", job.company_name or ""])
        writer.writerow(["Location", job.location or ""])
        writer.writerow(["Status", "published" if job.is_active else "draft"])
        writer.writerow(["Views", job.views])
        writer.writerow(
            ["Total Applicants", report["summary"]["total_applicants"]]
        )
        writer.writerow(
            [
                "Avg CV Score",
                report["summary"]["avg_cv_score"]
                if report["summary"]["avg_cv_score"] is not None
                else "N/A",
            ]
        )
        writer.writerow(
            [
                "Avg Interview Score",
                report["summary"]["avg_interview_score"]
                if report["summary"]["avg_interview_score"] is not None
                else "N/A",
            ]
        )
        writer.writerow([])
        writer.writerow(["Stage", "Count", "Conversion %"])
        for stage in report["funnel"]:
            writer.writerow(
                [stage["stage"], stage["count"], stage["conversion"]]
            )
        writer.writerow([])
        writer.writerow(["Source", "Count"])
        for src, count in report["sources"].items():
            writer.writerow([src, count])
        writer.writerow([])
        writer.writerow(["Applicant", "Email", "Status", "Score", "Applied At"])
        for app in report["recent_applicants"]:
            writer.writerow(
                [
                    app["full_name"],
                    app["email"],
                    app["status"],
                    app["score"] if app["score"] is not None else "N/A",
                    app["created_at"] or "",
                ]
            )
        return StreamingResponse(
            io.StringIO(output.getvalue()),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename={filename}.csv"
            },
        )

    pdf = PDFReport()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, f"Job Report: {job.title}", ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(
        0,
        7,
        f"{job.company_name or ''} | {job.location or 'Location N/A'} | "
        f"{'Published' if job.is_active else 'Draft'}",
        ln=True,
    )
    pdf.ln(5)

    summary = report["summary"]
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 9, "Summary", ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 7, f"Total Applicants: {summary['total_applicants']}", ln=True)
    pdf.cell(0, 7, f"Views: {summary['views']}", ln=True)
    pdf.cell(
        0,
        7,
        "Avg CV Score: "
        + (str(summary["avg_cv_score"]) if summary["avg_cv_score"] is not None else "N/A"),
        ln=True,
    )
    pdf.cell(
        0,
        7,
        "Avg Interview Score: "
        + (
            str(summary["avg_interview_score"])
            if summary["avg_interview_score"] is not None
            else "N/A"
        ),
        ln=True,
    )
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 9, "Pipeline", ln=True)
    pdf.set_font("Helvetica", "", 10)
    for stage in report["funnel"]:
        pdf.cell(
            0,
            7,
            f"  {stage['stage']}: {stage['count']} ({stage['conversion']}%)",
            ln=True,
        )
    pdf.ln(4)

    if report["sources"]:
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 9, "Sources", ln=True)
        pdf.set_font("Helvetica", "", 10)
        for src, count in report["sources"].items():
            pdf.cell(0, 7, f"  {src}: {count}", ln=True)
        pdf.ln(4)

    if report["recent_applicants"]:
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 9, "Recent Applicants", ln=True)
        pdf.set_font("Helvetica", "", 9)
        for app in report["recent_applicants"]:
            pdf.cell(
                0,
                6,
                f"  {app['full_name']} — {app['status']}"
                + (f" (score {app['score']})" if app["score"] is not None else ""),
                ln=True,
            )

    return StreamingResponse(
        io.BytesIO(bytes(pdf.output(dest="S"), "latin-1")),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename={filename}.pdf"
        },
    )
