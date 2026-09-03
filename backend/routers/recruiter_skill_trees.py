"""
Skill Tree Management API — /api/v1/recruiter/skill-trees
---------------------------------------------------------
Provides a reusable Skill Tree Management system.
Skill trees can be created standalone (reusable in library) or linked to jobs.
"""

import json
from datetime import UTC, datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.authz import get_rubric_for_recruiter
from backend.database import Application, BatchJob, EvaluationResult, EvaluationSession, Job, Rubric, User
from backend.dependencies import get_db, require_recruiter
from backend.logger import logger
from backend.tenant import get_current_company_id

router = APIRouter(prefix="/recruiter/skill-trees", tags=["Recruiter Skill Trees"])


def _utcnow():
    return datetime.now(UTC).replace(tzinfo=None)


def _parse_criteria(rubric) -> list:
    """Parse rubric.criteria_json (TEXT/JSON string) into categories list."""
    raw = rubric.criteria_json
    if not raw:
        return []
    # criteria_json may already be a dict (if set programmatically) or a JSON string
    if isinstance(raw, (dict, list)):
        return raw.get("categories", []) if isinstance(raw, dict) else raw
    try:
        data = json.loads(raw)
        return data.get("categories", []) if isinstance(data, dict) else data
    except (json.JSONDecodeError, TypeError):
        return []


def _dump_criteria(categories: list, extra: dict = None) -> str:
    """Serialize categories + optional extra fields to JSON string for criteria_json."""
    data = extra or {}
    data["categories"] = categories
    return json.dumps(data)


def _safe_float(value, default: float = 1.0) -> float:
    """Coerce a weight value to a non-negative float (default 1.0)."""
    try:
        val = float(value)
    except (TypeError, ValueError):
        val = default
    return val if val >= 0 else default


def _normalize_categories(categories: list) -> list:
    """Normalize incoming category dicts into the rubric criteria_json shape.

    Accepts both flat shapes ({name, skills:[{name, level, weight, required}]})
    and already-nested shapes ({name, weight, subcategories:[{name, weight, skills}]}).
    Weights are preserved (default 1.0), never hardcoded.
    """
    result = []
    for c in categories or []:
        if not isinstance(c, dict) or not c.get("name"):
            continue

        raw_skills = c.get("skills")
        if isinstance(raw_skills, list):
            # Flat shape — wrap into a single "Skills" subcategory.
            skills = []
            for s in raw_skills:
                if not isinstance(s, dict) or not s.get("name"):
                    continue
                skills.append(
                    {
                        "name": s.get("name", ""),
                        "weight": _safe_float(s.get("weight", 1.0)),
                        "is_required": bool(s.get("required", s.get("is_required", False))),
                        "keywords": s.get("keywords", []) or [],
                        "level": s.get("level", "intermediate"),
                    }
                )
            result.append(
                {
                    "name": c.get("name"),
                    "weight": _safe_float(c.get("weight", 1.0)),
                    "subcategories": [
                        {
                            "name": "Skills",
                            "weight": _safe_float(c.get("subcategory_weight", 1.0)),
                            "skills": skills,
                        }
                    ],
                }
            )
        else:
            # Already nested (from existing rubrics or the wizard).
            subs = []
            for sub in c.get("subcategories", []) or []:
                if not isinstance(sub, dict):
                    continue
                sub_skills = []
                for s in sub.get("skills", []) or []:
                    if not isinstance(s, dict) or not s.get("name"):
                        continue
                    sub_skills.append(
                        {
                            "name": s.get("name", ""),
                            "weight": _safe_float(s.get("weight", 1.0)),
                            "is_required": bool(s.get("is_required", s.get("required", False))),
                            "keywords": s.get("keywords", []) or [],
                            "level": s.get("level", "intermediate"),
                        }
                    )
                subs.append(
                    {
                        "name": sub.get("name", "Skills"),
                        "weight": _safe_float(sub.get("weight", 1.0)),
                        "skills": sub_skills,
                    }
                )
            if not subs:
                subs = [
                    {
                        "name": "Skills",
                        "weight": _safe_float(c.get("subcategory_weight", 1.0)),
                        "skills": [],
                    }
                ]
            result.append(
                {
                    "name": c.get("name"),
                    "weight": _safe_float(c.get("weight", 1.0)),
                    "subcategories": subs,
                }
            )
    return result


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class StandaloneSkillTreeCreate(BaseModel):
    name: str
    category_id: Optional[int] = None
    industry: Optional[str] = None
    seniority: Optional[str] = "mid"
    description: Optional[str] = None
    categories: List[dict] = []
    skill_count: Optional[int] = 0


class SkillTreeCreate(BaseModel):
    job_id: int
    title: Optional[str] = None
    description: Optional[str] = None
    categories: Optional[List[int]] = []
    rubric: Optional[dict] = None
    seniority: Optional[str] = "mid"


class SkillTreeUpdate(BaseModel):
    rubric: dict
    seniority: Optional[str] = "mid"


class SkillTreePatch(BaseModel):
    title: Optional[str] = None
    name: Optional[str] = None
    seniority: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class SkillTreeDuplicate(BaseModel):
    new_name: Optional[str] = None
    job_id: Optional[int] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _format_skill_tree(rubric, job: Job = None, campaign_count: int = 0) -> dict:
    """Serialise a Rubric row for the list/detail response."""
    cats = _parse_criteria(rubric)

    skill_count = sum(
        len(sub.get("skills", []))
        for cat in cats
        for sub in cat.get("subcategories", [])
    )

    category_names = [c.get("name") for c in cats if c.get("name")]

    return {
        "id": rubric.id,
        "job_id": rubric.job_id,
        "job_name": rubric.title or (job.title if job else f"Skill Tree #{rubric.id}"),
        "category_name": category_names[0] if category_names else None,
        "categories": category_names,
        "version": rubric.version,
        "seniority": rubric.complexity or "mid",
        "skill_count": skill_count,
        "category_count": len(cats),
        "published": bool(rubric.is_active),
        "campaign_count": campaign_count,
        "created_at": rubric.created_at.isoformat() if rubric.created_at else None,
    }


def _fallback_generated_rubric(title: str) -> list:
    """Deterministic fallback rubric used when the AI call fails or is skipped."""
    label = title.strip() or "Role"
    return [
        {
            "name": "Technical Skills",
            "weight": 50,
            "subcategories": [
                {
                    "name": "Skills",
                    "weight": 1.0,
                    "skills": [
                        {
                            "name": f"{label} Core Expertise",
                            "weight": 40,
                            "is_required": True,
                            "keywords": [],
                            "level": "advanced",
                        },
                        {
                            "name": "Tools & Methodologies",
                            "weight": 30,
                            "is_required": False,
                            "keywords": [],
                            "level": "intermediate",
                        },
                        {
                            "name": "Problem Solving",
                            "weight": 30,
                            "is_required": False,
                            "keywords": [],
                            "level": "advanced",
                        },
                    ],
                }
            ],
        },
        {
            "name": "Soft Skills",
            "weight": 30,
            "subcategories": [
                {
                    "name": "Skills",
                    "weight": 1.0,
                    "skills": [
                        {
                            "name": "Communication",
                            "weight": 40,
                            "is_required": True,
                            "keywords": [],
                            "level": "intermediate",
                        },
                        {
                            "name": "Collaboration",
                            "weight": 30,
                            "is_required": False,
                            "keywords": [],
                            "level": "intermediate",
                        },
                        {
                            "name": "Adaptability",
                            "weight": 30,
                            "is_required": False,
                            "keywords": [],
                            "level": "intermediate",
                        },
                    ],
                }
            ],
        },
        {
            "name": "Experience & Impact",
            "weight": 20,
            "subcategories": [
                {
                    "name": "Skills",
                    "weight": 1.0,
                    "skills": [
                        {
                            "name": "Delivering Results",
                            "weight": 50,
                            "is_required": True,
                            "keywords": [],
                            "level": "advanced",
                        },
                        {
                            "name": "Leadership",
                            "weight": 50,
                            "is_required": False,
                            "keywords": [],
                            "level": "intermediate",
                        },
                    ],
                }
            ],
        },
    ]


def _owned_job(job_id: int, company_id: int, recruiter: User, db: Session) -> Job:
    job = db.query(Job).filter(Job.id == job_id, Job.company_id == company_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("")
def list_skill_trees(
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
    company_id: int = Depends(get_current_company_id),
):
    """Return all skill trees (standalone + job-linked) for this recruiter."""
    rubrics = (
        db.query(Rubric)
        .filter(Rubric.company_id == company_id, Rubric.is_active)
        .order_by(Rubric.created_at.desc())
        .all()
    )

    job_ids = list({r.job_id for r in rubrics if r.job_id})
    job_map = {}
    if job_ids:
        for j in db.query(Job).filter(Job.id.in_(job_ids)).all():
            job_map[j.id] = j

    campaign_counts = (
        dict(
            db.query(BatchJob.rubric_id, func.count(BatchJob.id))
            .filter(BatchJob.rubric_id.in_([r.id for r in rubrics]))
            .group_by(BatchJob.rubric_id)
            .all()
        )
        if rubrics
        else {}
    )

    return {
        "skill_trees": [
            _format_skill_tree(r, job_map.get(r.job_id), campaign_counts.get(r.id, 0))
            for r in rubrics
        ]
    }


@router.post("/standalone", status_code=status.HTTP_201_CREATED)
def create_standalone_skill_tree(
    data: StandaloneSkillTreeCreate,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
    company_id: int = Depends(get_current_company_id),
):
    """Create a reusable standalone skill tree (not tied to a job)."""
    categories = _normalize_categories(data.categories)

    criteria_json = _dump_criteria(categories)

    new_rubric = Rubric(
        job_id=None,
        company_id=company_id,
        version=1,
        title=data.name,
        complexity=data.seniority or "mid",
        description=data.description,
        criteria_json=criteria_json,
        is_active=True,
        created_by=recruiter.id,
        created_at=_utcnow(),
    )
    db.add(new_rubric)
    db.commit()
    db.refresh(new_rubric)

    logger.info(
        f"Standalone skill tree created: id={new_rubric.id} name={data.name} "
        f"by recruiter={recruiter.id}"
    )

    return {
        "success": True,
        "id": new_rubric.id,
        "version": new_rubric.version,
        "skill_tree": _format_skill_tree(new_rubric),
    }


@router.post("/ai/generate")
async def ai_generate_skill_tree(
    data: dict,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    """AI-generate a full rubric (categories + skills + levels + weights) from a role title."""
    title = str(data.get("title", "")).strip()[:200]
    description = str(data.get("description", "")).strip()[:1000]

    from backend.ai.llm import call_groq_cascade
    from backend.credit_service import consume_credits_or_402, rollback_credits

    _fallback = _fallback_generated_rubric(title)

    if not title:
        return {"success": True, "source": "fallback", "categories": _fallback}

    credit_tx = None
    try:
        prompt = (
            f"Create an evaluation rubric for the role: {title!r}."
            + (f" Context: {description!r}." if description else "")
            + (
                " Return JSON with key 'categories' — an array of 2-4 category objects. "
                "Each category has 'name' (str), 'weight' (int, 1-100, all categories should roughly sum to 100), "
                "and 'skills' — an array of 3-8 skill objects, each with 'name' (str), "
                "'level' (one of beginner/intermediate/advanced/expert), "
                "'required' (bool), 'weight' (int 1-100)."
            )
        )
        credit_tx = consume_credits_or_402(
            db, recruiter, 1, "skill_tree_generate", reference_type="skill_tree_generate"
        )
        res = await call_groq_cascade(
            [{"role": "user", "content": prompt}], json_mode=True
        )
        categories = res.get("categories", [])
        if isinstance(categories, list) and categories:
            return {
                "success": True,
                "source": "ai",
                "categories": _normalize_categories(categories),
            }
    except HTTPException:
        raise
    except Exception as e:
        if credit_tx is not None:
            try:
                rollback_credits(db, credit_tx)
            except Exception:
                pass
        logger.warning(f"AI skill-tree generate fallback: {e}")

    return {"success": True, "source": "fallback", "categories": _fallback}


@router.post("", status_code=status.HTTP_201_CREATED)
def create_skill_tree(
    data: SkillTreeCreate,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
    company_id: int = Depends(get_current_company_id),
):
    """Create and publish a skill tree linked to a job."""
    job = _owned_job(data.job_id, company_id, recruiter, db)

    rubric_data = data.rubric or {}
    categories = _normalize_categories(rubric_data.get("categories", []))

    criteria_json = _dump_criteria(
        categories,
        {
            "job_id": data.job_id,
            "seniority": data.seniority or "mid",
        },
    )

    existing = (
        db.query(Rubric)
        .filter(
            Rubric.job_id == data.job_id,
            Rubric.company_id == company_id,
            Rubric.is_active,
        )
        .all()
    )
    next_version = 1
    if existing:
        next_version = max(r.version for r in existing) + 1
        for r in existing:
            r.is_active = False

    new_rubric = Rubric(
        job_id=data.job_id,
        company_id=company_id,
        version=next_version,
        title=data.title or job.title,
        complexity=data.seniority or "mid",
        criteria_json=criteria_json,
        is_active=True,
        created_by=recruiter.id,
        created_at=_utcnow(),
    )
    db.add(new_rubric)
    job.rubric_id = new_rubric.id
    db.commit()
    db.refresh(new_rubric)

    logger.info(
        f"Skill tree created: job={data.job_id} version={next_version} "
        f"by recruiter={recruiter.id}"
    )

    return {
        "success": True,
        "id": new_rubric.id,
        "job_id": new_rubric.job_id,
        "version": new_rubric.version,
        "skill_tree": _format_skill_tree(new_rubric, job),
    }


@router.post("/{tree_id}/duplicate", status_code=status.HTTP_201_CREATED)
def duplicate_skill_tree(
    tree_id: int,
    data: SkillTreeDuplicate = None,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
    company_id: int = Depends(get_current_company_id),
):
    """Duplicate a skill tree, creating a new copy."""
    original = get_rubric_for_recruiter(tree_id, recruiter, db)

    new_name = (
        data.new_name
        if data and data.new_name
        else (original.title or f"Copy of #{original.id}")
    )
    new_title = f"{new_name} (Copy)" if original.job_id else new_name

    new_rubric = Rubric(
        job_id=data.job_id if data and data.job_id else original.job_id,
        company_id=company_id,
        version=1,
        title=new_title,
        complexity=original.complexity or "mid",
        criteria_json=original.criteria_json,
        is_active=True,
        created_by=recruiter.id,
        created_at=_utcnow(),
    )
    db.add(new_rubric)
    db.commit()
    db.refresh(new_rubric)

    return {
        "success": True,
        "id": new_rubric.id,
        "version": new_rubric.version,
        "skill_tree": _format_skill_tree(new_rubric),
    }


@router.get("/{tree_id}")
def get_skill_tree(
    tree_id: int,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
    company_id: int = Depends(get_current_company_id),
):
    """Return a single skill tree by its Rubric ID."""
    rubric = get_rubric_for_recruiter(tree_id, recruiter, db)

    job = None
    if rubric.job_id:
        job = (
            db.query(Job)
            .filter(Job.id == rubric.job_id, Job.company_id == company_id)
            .first()
        )

    cats = _parse_criteria(rubric)
    rubric_data = {
        "categories": cats,
    }

    return {
        **_format_skill_tree(rubric, job),
        "rubric_json": rubric_data,
        "criteria_json": rubric.criteria_json,
    }


@router.get("/{tree_id}/detail")
def get_skill_tree_detail(
    tree_id: int,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
    company_id: int = Depends(get_current_company_id),
):
    """Full rubric detail: structure, linked jobs, campaigns, and evaluated candidates."""
    rubric = get_rubric_for_recruiter(tree_id, recruiter, db)

    job = None
    if rubric.job_id:
        job = (
            db.query(Job)
            .filter(Job.id == rubric.job_id, Job.company_id == company_id)
            .first()
        )

    cats = _parse_criteria(rubric)

    # Jobs directly linked to this rubric (job.rubric_id) + jobs tied via campaigns.
    linked_job_ids = set()
    linked_jobs = []
    direct_jobs = (
        db.query(Job)
        .filter(Job.company_id == company_id, Job.rubric_id == rubric.id)
        .all()
    )
    for j in direct_jobs:
        linked_job_ids.add(j.id)
        linked_jobs.append(
            {
                "id": j.id,
                "title": j.title or f"Job #{j.id}",
                "location": j.location,
                "type": j.type,
                "status": "active" if j.is_active else "draft",
                "link_type": "direct",
            }
        )

    campaigns = (
        db.query(BatchJob)
        .filter(BatchJob.company_id == company_id, BatchJob.rubric_id == rubric.id)
        .all()
    )
    for bj in campaigns:
        if bj.job_id and bj.job_id not in linked_job_ids:
            j = (
                db.query(Job)
                .filter(Job.id == bj.job_id, Job.company_id == company_id)
                .first()
            )
            if j:
                linked_job_ids.add(j.id)
                linked_jobs.append(
                    {
                        "id": j.id,
                        "title": j.title or f"Job #{j.id}",
                        "location": j.location,
                        "type": j.type,
                        "status": "active" if j.is_active else "draft",
                        "link_type": f"campaign:{bj.id}",
                    }
                )

    # Candidates evaluated against this rubric.
    evaluated_candidates = []
    results = (
        db.query(EvaluationResult, EvaluationSession, Application)
        .join(EvaluationSession, EvaluationSession.id == EvaluationResult.evaluation_session_id)
        .join(Application, Application.id == EvaluationSession.application_id)
        .filter(
            EvaluationResult.rubric_id == rubric.id,
            EvaluationResult.company_id == company_id,
        )
        .all()
    )
    for result, session, app in results:
        evaluated_candidates.append(
            {
                "application_id": app.id,
                "candidate_name": app.full_name or app.email or "Unknown",
                "email": app.email,
                "job_title": app.job_id and linked_jobs and next(
                    (lj["title"] for lj in linked_jobs if lj["id"] == app.job_id),
                    None,
                ) or None,
                "final_score": result.final_score,
                "rubric_score": result.rubric_score,
                "rubric_version": result.rubric_version,
                "cv_score": result.cv_score,
                "status": app.status,
                "evaluated_at": (
                    result.created_at.isoformat() if result.created_at else None
                ),
            }
        )

    return {
        **_format_skill_tree(rubric, job),
        "rubric_json": {"categories": cats},
        "criteria_json": rubric.criteria_json,
        "description": rubric.description,
        "linked_jobs": linked_jobs,
        "campaign_count": len(campaigns),
        "evaluated_candidates": evaluated_candidates,
        "evaluated_count": len(evaluated_candidates),
    }


@router.put("/{tree_id}")
def update_skill_tree(
    tree_id: int,
    data: SkillTreeUpdate,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
    company_id: int = Depends(get_current_company_id),
):
    """Replace rubric JSON for an existing skill tree (new version)."""
    old_rubric = get_rubric_for_recruiter(tree_id, recruiter, db)

    old_rubric.is_active = False

    rubric_data = data.rubric
    categories = _normalize_categories(rubric_data.get("categories", []))
    criteria_json = _dump_criteria(
        categories,
        {
            "job_id": old_rubric.job_id,
            "seniority": data.seniority or old_rubric.complexity or "mid",
        },
    )

    new_rubric = Rubric(
        job_id=old_rubric.job_id,
        company_id=company_id,
        version=old_rubric.version + 1,
        title=old_rubric.title,
        complexity=data.seniority or old_rubric.complexity or "mid",
        criteria_json=criteria_json,
        is_active=True,
        created_by=recruiter.id,
        created_at=_utcnow(),
    )
    db.add(new_rubric)
    db.commit()
    db.refresh(new_rubric)

    # Re-point job + campaign rubric links from the old version to the new one
    # so edits never orphan a job/campaign that referenced the previous version.
    if old_rubric.id != new_rubric.id:
        db.query(Job).filter(
            Job.company_id == company_id,
            Job.rubric_id == old_rubric.id,
        ).update({Job.rubric_id: new_rubric.id}, synchronize_session=False)
        db.query(BatchJob).filter(
            BatchJob.company_id == company_id,
            BatchJob.rubric_id == old_rubric.id,
        ).update({BatchJob.rubric_id: new_rubric.id}, synchronize_session=False)
        db.commit()

    return {
        "success": True,
        "id": new_rubric.id,
        "version": new_rubric.version,
        "skill_tree": _format_skill_tree(new_rubric),
    }


@router.patch("/{tree_id}")
def patch_skill_tree(
    tree_id: int,
    data: SkillTreePatch,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
    company_id: int = Depends(get_current_company_id),
):
    """Partially update a skill tree (rename, change seniority/description)."""
    rubric = get_rubric_for_recruiter(tree_id, recruiter, db)

    if data.title is not None:
        rubric.title = data.title
    if data.name is not None:
        rubric.title = data.name
    if data.seniority is not None:
        rubric.complexity = data.seniority
    if data.description is not None:
        rubric.description = data.description
    if data.is_active is not None:
        rubric.is_active = data.is_active

    rubric.updated_at = _utcnow()
    db.commit()
    db.refresh(rubric)

    logger.info(f"Skill tree patched: id={tree_id} by recruiter={recruiter.id}")
    return {
        "success": True,
        "id": rubric.id,
        "skill_tree": _format_skill_tree(rubric),
    }


@router.delete("/{tree_id}", status_code=status.HTTP_200_OK)
def delete_skill_tree(
    tree_id: int,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
    company_id: int = Depends(get_current_company_id),
):
    """Soft-delete a skill tree by marking is_active=False."""
    rubric = get_rubric_for_recruiter(tree_id, recruiter, db)

    rubric.is_active = False
    db.commit()

    logger.info(f"Skill tree archived: id={tree_id} by recruiter={recruiter.id}")
    return {"success": True, "id": tree_id}
