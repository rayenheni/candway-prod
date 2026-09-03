import json
import re
from typing import Optional

import bleach
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.ai.llm import call_groq_cascade
from backend.authz import get_job_for_recruiter
from backend.credit_service import consume_credits_or_402, rollback_credits
from backend.database import (
    Category,
    CompanyMember,
    Job,
    JobAIConfig,
    JobEvaluationFramework,
    JobPipelineStage,
    JobRoleOverview,
    JobScreeningQuestion,
    JobSkill,
    Rubric,
)
from backend.dependencies import get_db, require_recruiter
from backend.job_wizard_schemas import (
    Step1BasicInfo,
    Step2RoleOutcomes,
    Step3SkillTree,
    Step4EvaluationConfig,
    Step5ScreeningPipeline,
    Step6ReviewPublish,
    SuggestionResult,
    WizardProgress,
)
from backend.logger import logger
from backend.subscription_service import SubscriptionService
from backend.tenant import get_current_company_id

router = APIRouter(prefix="/recruiter/jobs/wizard", tags=["Recruiter Job Wizard"])


# ── Public helpers for the wizard ──────────────────────────────


@router.get("/categories")
def list_wizard_categories(
    recruiter=Depends(require_recruiter),
    db: Session = Depends(get_db),
    company_id: int = Depends(get_current_company_id),
):
    """Return job categories from the existing categories table (type='job')."""
    categories = (
        db.query(Category).filter(Category.type == "job").order_by(Category.name).all()
    )
    return [{"id": c.id, "name": c.name, "description": None} for c in categories]


@router.get("/recruiters")
def list_wizard_recruiters(
    recruiter=Depends(require_recruiter),
    db: Session = Depends(get_db),
    company_id: int = Depends(get_current_company_id),
):
    """Return recruiters in the company for the hiring-manager dropdown."""
    members = (
        db.query(CompanyMember)
        .filter(
            CompanyMember.company_id == company_id,
            CompanyMember.is_active,
        )
        .all()
    )
    from backend.profile_helpers import get_user_name

    result = []
    for m in members:
        name = get_user_name(m.user) if m.user else None
        result.append(
            {
                "id": m.user_id,
                "name": name or "Unknown",
                "email": getattr(m.user, "email", ""),
            }
        )
    return result


_PROMPT_INJECTION_RE = re.compile(
    r"(ignore\s+previous|disregard\s+instructions?|system\s*prompt|you\s+are\s+now)",
    re.IGNORECASE,
)


def _sanitize_for_prompt(value: str, max_len: int = 200) -> str:
    cleaned = bleach.clean(value, tags=[], strip=True).strip()
    cleaned = cleaned[:max_len]
    if _PROMPT_INJECTION_RE.search(cleaned):
        raise HTTPException(
            status_code=400,
            detail="Invalid characters or content detected in input.",
        )
    return cleaned


def _compute_progress(db: Session, job: Job) -> WizardProgress:
    steps = []
    if job.title:
        steps.append(1)
    if db.query(JobRoleOverview).filter(JobRoleOverview.job_id == job.id).first():
        steps.append(2)
    has_inline_skills = bool(
        db.query(JobSkill).filter(JobSkill.job_id == job.id).first()
    )
    if has_inline_skills:
        steps.append(3)
    has_eval_framework = bool(
        db.query(JobEvaluationFramework)
        .filter(JobEvaluationFramework.job_id == job.id)
        .first()
    )
    if has_eval_framework:
        steps.append(4)
    # A linked library rubric satisfies the Rubric Evaluation step
    # (its skills + categories live in the `rubrics` row, not inline JobSkill/
    # JobEvaluationFramework rows), so treat steps 3 & 4 as complete.
    if job.rubric_id:
        steps.append(3)
        steps.append(4)
    has_screening = (
        db.query(JobScreeningQuestion)
        .filter(JobScreeningQuestion.job_id == job.id)
        .first()
    )
    has_pipeline = (
        db.query(JobPipelineStage).filter(JobPipelineStage.job_id == job.id).first()
    )
    if has_screening or has_pipeline:
        steps.append(5)
    current = len(steps) + 1 if steps else 1
    if current > 6:
        current = 6
    return WizardProgress(
        job_id=job.id,
        current_step=current,
        completed_steps=steps,
        is_published=bool(job.is_active),
    )


# ── Start ──────────────────────────────────────────────────────


@router.post("/start", response_model=WizardProgress)
def start_wizard(
    req: Step1BasicInfo,
    recruiter=Depends(require_recruiter),
    db: Session = Depends(get_db),
    company_id: int = Depends(get_current_company_id),
):
    company_name = getattr(recruiter, "company_name", "") or ""
    membership = (
        db.query(CompanyMember)
        .filter(
            CompanyMember.user_id == recruiter.id,
            CompanyMember.company_id == company_id,
            CompanyMember.is_active,
        )
        .first()
    )
    if membership and membership.company:
        company_name = membership.company.name

    salary_range = None
    if req.salary_min is not None and req.salary_max is not None:
        salary_range = (
            f"{req.salary_min}–{req.salary_max} {req.salary_currency or 'USD'}"
        )
    elif req.salary_min is not None:
        salary_range = f"From {req.salary_min} {req.salary_currency or 'USD'}"
    elif req.salary_max is not None:
        salary_range = f"Up to {req.salary_max} {req.salary_currency or 'USD'}"

    job = Job(
        recruiter_id=recruiter.id,
        company_id=company_id,
        title=req.title,
        company_name=company_name,
        location=req.location or "",
        type=req.employment_type,
        salary_range=salary_range,
        category_id=req.category_id,
        is_active=False,
    )
    db.add(job)

    # Consume one job slot when the wizard creates the job.
    # The remaining wizard steps only modify this existing job.
    if not SubscriptionService.record_usage(
        recruiter, "create_job", db, commit=False
    ):
        db.rollback()
        raise HTTPException(
            status_code=403,
            detail="Job slot limit reached for your current plan.",
        )

    db.commit()
    db.refresh(job)
    return _compute_progress(db, job)


# ── Step 1 – Basic Information ────────────────────────────────


@router.patch("/{job_id}/step1", response_model=WizardProgress)
def save_step1(
    job_id: int,
    req: Step1BasicInfo,
    recruiter=Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    job = get_job_for_recruiter(job_id, recruiter, db)
    if job.is_active:
        raise HTTPException(status_code=400, detail="Cannot modify a published job")

    salary_range = None
    if req.salary_min is not None and req.salary_max is not None:
        salary_range = (
            f"{req.salary_min}–{req.salary_max} {req.salary_currency or 'USD'}"
        )
    elif req.salary_min is not None:
        salary_range = f"From {req.salary_min} {req.salary_currency or 'USD'}"
    elif req.salary_max is not None:
        salary_range = f"Up to {req.salary_max} {req.salary_currency or 'USD'}"

    job.title = req.title
    job.location = req.location or ""
    job.type = req.employment_type
    job.salary_range = salary_range
    job.category_id = req.category_id
    db.commit()
    db.refresh(job)
    return _compute_progress(db, job)


# ── Step 2 – Role & Outcomes ──────────────────────────────────


@router.patch("/{job_id}/step2", response_model=WizardProgress)
def save_step2(
    job_id: int,
    req: Step2RoleOutcomes,
    recruiter=Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    job = get_job_for_recruiter(job_id, recruiter, db)
    if job.is_active:
        raise HTTPException(status_code=400, detail="Cannot modify a published job")

    db.query(JobRoleOverview).filter(JobRoleOverview.job_id == job.id).delete()
    for item in req.items:
        db.add(
            JobRoleOverview(
                company_id=job.company_id,
                job_id=job.id,
                question_key=item.question_key,
                question=item.question,
                answer=item.answer,
            )
        )
    db.commit()
    return _compute_progress(db, job)


# ── Step 3 – Choose or Create Skill Tree ──────────────────────


@router.patch("/{job_id}/step3", response_model=WizardProgress)
def save_step3(
    job_id: int,
    req: Step3SkillTree,
    recruiter=Depends(require_recruiter),
    db: Session = Depends(get_db),
    company_id: int = Depends(get_current_company_id),
):
    job = get_job_for_recruiter(job_id, recruiter, db)
    if job.is_active:
        raise HTTPException(status_code=400, detail="Cannot modify a published job")

    db.query(JobSkill).filter(JobSkill.job_id == job.id).delete()
    for idx, skill in enumerate(req.skills):
        db.add(
            JobSkill(
                company_id=job.company_id,
                job_id=job.id,
                skill_name=skill.skill_name,
                required_level=skill.required_level,
                weight=skill.weight,
                is_mandatory=skill.is_mandatory,
                notes=skill.notes,
                sort_order=skill.sort_order or idx,
            )
        )
    # Link rubric if skill_tree_id provided
    if req.skill_tree_id:
        rubric = (
            db.query(Rubric)
            .filter(
                Rubric.id == req.skill_tree_id,
                Rubric.is_active,
                (Rubric.company_id == company_id) | (Rubric.company_id.is_(None)),
            )
            .first()
        )
        if rubric:
            job.rubric_id = rubric.id
        else:
            logger.warning(
                f"Skill tree {req.skill_tree_id} not found/accessible, skipping rubric link"
            )
    db.commit()
    return _compute_progress(db, job)


# ── Step 4 – Evaluation Configuration ─────────────────────────


@router.patch("/{job_id}/step4", response_model=WizardProgress)
def save_step4(
    job_id: int,
    req: Step4EvaluationConfig,
    recruiter=Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    job = get_job_for_recruiter(job_id, recruiter, db)
    if job.is_active:
        raise HTTPException(status_code=400, detail="Cannot modify a published job")

    existing_ef = (
        db.query(JobEvaluationFramework)
        .filter(JobEvaluationFramework.job_id == job.id)
        .first()
    )
    categories_data = [
        {
            "name": cat.name,
            "weight": cat.weight,
            "sort_order": cat.sort_order,
        }
        for cat in req.categories
    ]
    if existing_ef:
        existing_ef.categories = categories_data
    else:
        db.add(
            JobEvaluationFramework(
                company_id=job.company_id,
                job_id=job.id,
                categories=categories_data,
            )
        )

    if req.ai_config:
        # duration_minutes and total_questions belong to Job, not JobAIConfig.
        # Keep them in the wizard schema because they are job-level settings,
        # but never pass them into the JobAIConfig SQLAlchemy model.
        ai_config_data = req.ai_config.model_dump(
            exclude_none=True,
            exclude={"duration_minutes", "total_questions"},
        )

        existing_ac = db.query(JobAIConfig).filter(JobAIConfig.job_id == job.id).first()
        if existing_ac:
            for field, value in ai_config_data.items():
                setattr(existing_ac, field, value)
        else:
            db.add(
                JobAIConfig(
                    job_id=job.id,
                    company_id=job.company_id,
                    **ai_config_data,
                )
            )
        if req.ai_config.custom_instructions:
            job.interview_instructions = req.ai_config.custom_instructions
        if req.ai_config.duration_minutes is not None:
            job.duration_minutes = req.ai_config.duration_minutes
            job.time_limit_seconds = req.ai_config.duration_minutes * 60
        if req.ai_config.total_questions is not None:
            job.total_questions = req.ai_config.total_questions
    db.commit()
    return _compute_progress(db, job)


# ── Step 5 – Screening & Pipeline ─────────────────────────────


@router.patch("/{job_id}/step5", response_model=WizardProgress)
def save_step5(
    job_id: int,
    req: Step5ScreeningPipeline,
    recruiter=Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    job = get_job_for_recruiter(job_id, recruiter, db)
    if job.is_active:
        raise HTTPException(status_code=400, detail="Cannot modify a published job")

    db.query(JobScreeningQuestion).filter(
        JobScreeningQuestion.job_id == job.id
    ).delete()
    db.query(JobPipelineStage).filter(JobPipelineStage.job_id == job.id).delete()

    for idx, q in enumerate(req.screening_questions):
        db.add(
            JobScreeningQuestion(
                company_id=job.company_id,
                job_id=job.id,
                question=q.question,
                type=q.type,
                options=q.options,
                is_required=q.is_required,
                sort_order=q.sort_order or idx,
            )
        )
    for idx, stage in enumerate(req.pipeline_stages):
        db.add(
            JobPipelineStage(
                company_id=job.company_id,
                job_id=job.id,
                name=stage.name,
                slug=stage.slug,
                sort_order=stage.sort_order or idx,
                color=stage.color,
                icon=stage.icon,
            )
        )
    db.commit()
    return _compute_progress(db, job)


# ── Publish ────────────────────────────────────────────────────


@router.post("/{job_id}/publish", response_model=WizardProgress)
def publish_job(
    job_id: int,
    req: Optional[Step6ReviewPublish] = None,
    recruiter=Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    job = get_job_for_recruiter(job_id, recruiter, db)
    if job.is_active:
        raise HTTPException(status_code=400, detail="Job is already published")

    progress = _compute_progress(db, job)
    completed = set(progress.completed_steps)
    missing = [s for s in range(1, 6) if s not in completed]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot publish: steps {missing} not completed",
        )

    # Job quota is consumed exactly once when the wizard creates the
    # draft job in /start. Publishing only activates that existing job.
    job.is_active = True
    # ── Auto-populate required_skills ──────────────────────────
    # 1) Inline JobSkill rows (built via Step 3 flat editor)
    inline_skills = [
        s.skill_name
        for s in db.query(JobSkill)
        .filter(JobSkill.job_id == job.id)
        .order_by(JobSkill.sort_order)
        .all()
        if s.skill_name
    ]
    # 2) Fallback: extract skill names from the linked rubric's criteria_json
    if not inline_skills and job.rubric_id:
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
                for cat in cats:
                    for sk in cat.get("skills", []):
                        name = sk.get("name")
                        if name:
                            inline_skills.append(name)
                    for sub in cat.get("subcategories", []):
                        for sk in sub.get("skills", []):
                            name = sk.get("name")
                            if name:
                                inline_skills.append(name)
            except (json.JSONDecodeError, TypeError, AttributeError):
                pass
    job.required_skills = ", ".join(inline_skills)

    # ── Auto-populate description from Role & Outcomes ─────────
    if not job.description:
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
                job.description = "\n\n".join(sections)

    db.commit()
    db.refresh(job)
    return _compute_progress(db, job)


# ── Get full wizard state ──────────────────────────────────────


@router.get("/{job_id}", response_model=dict)
def get_wizard_state(
    job_id: int,
    recruiter=Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    job = get_job_for_recruiter(job_id, recruiter, db)
    progress = _compute_progress(db, job)

    data = {
        "job": {
            "id": job.id,
            "title": job.title,
            "location": job.location,
            "employment_type": job.type,
            "salary_range": job.salary_range,
            "company_name": job.company_name,
            "category_id": job.category_id,
            "rubric_id": job.rubric_id,
            "is_active": job.is_active,
            "created_at": job.created_at.isoformat() if job.created_at else None,
        },
        "progress": progress.model_dump(),
    }

    role_overviews = (
        db.query(JobRoleOverview)
        .filter(JobRoleOverview.job_id == job.id)
        .order_by(JobRoleOverview.question_key)
        .all()
    )
    if role_overviews:
        data["role_overviews"] = [
            {
                "id": r.id,
                "question_key": r.question_key,
                "question": r.question,
                "answer": r.answer,
            }
            for r in role_overviews
        ]

    skills = (
        db.query(JobSkill)
        .filter(JobSkill.job_id == job.id)
        .order_by(JobSkill.sort_order)
        .all()
    )
    if skills:
        data["skills"] = [
            {
                "id": s.id,
                "skill_name": s.skill_name,
                "required_level": s.required_level,
                "weight": s.weight,
                "is_mandatory": s.is_mandatory,
                "notes": s.notes,
                "sort_order": s.sort_order,
            }
            for s in skills
        ]

    eval_framework = (
        db.query(JobEvaluationFramework)
        .filter(JobEvaluationFramework.job_id == job.id)
        .first()
    )
    if eval_framework:
        data["evaluation_framework"] = {
            "id": eval_framework.id,
            "categories": eval_framework.categories,
        }

    ai_config = db.query(JobAIConfig).filter(JobAIConfig.job_id == job.id).first()
    if ai_config:
        data["ai_config"] = {
            "ai_scoring_enabled": ai_config.ai_scoring_enabled,
            "minimum_recommended_score": ai_config.minimum_recommended_score,
            "auto_shortlist_threshold": ai_config.auto_shortlist_threshold,
            "auto_reject_threshold": ai_config.auto_reject_threshold,
            "explain_ai_decisions": ai_config.explain_ai_decisions,
            "evidence_based_scoring": ai_config.evidence_based_scoring,
            "ignore_missing_cv": ai_config.ignore_missing_cv,
            "prioritize_verified_skills": ai_config.prioritize_verified_skills,
            "custom_instructions": ai_config.custom_instructions,
        }

    screening = (
        db.query(JobScreeningQuestion)
        .filter(JobScreeningQuestion.job_id == job.id)
        .order_by(JobScreeningQuestion.sort_order)
        .all()
    )
    if screening:
        data["screening_questions"] = [
            {
                "id": q.id,
                "question": q.question,
                "type": q.type,
                "options": q.options,
                "is_required": q.is_required,
                "sort_order": q.sort_order,
            }
            for q in screening
        ]

    pipeline = (
        db.query(JobPipelineStage)
        .filter(JobPipelineStage.job_id == job.id)
        .order_by(JobPipelineStage.sort_order)
        .all()
    )
    if pipeline:
        data["pipeline_stages"] = [
            {
                "id": s.id,
                "name": s.name,
                "slug": s.slug,
                "sort_order": s.sort_order,
                "color": s.color,
                "icon": s.icon,
            }
            for s in pipeline
        ]

    return data


# ── Delete draft ───────────────────────────────────────────────


@router.delete("/{job_id}")
def delete_draft(
    job_id: int,
    recruiter=Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    from datetime import UTC, datetime

    job = get_job_for_recruiter(job_id, recruiter, db)
    job.is_active = False
    job.deleted_at = datetime.now(UTC)
    db.commit()
    return {"message": "Draft deleted"}


# ═══════════════════════════════════════════════════════════════
# AI Suggestion Endpoints  (mock/default data with AI fallback)
# ═══════════════════════════════════════════════════════════════


@router.post("/ai/suggest-skills", response_model=SuggestionResult)
async def ai_suggest_skills(
    body: dict,
    recruiter=Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    title = _sanitize_for_prompt(body.get("title", ""))
    credit_tx = None
    try:
        prompt = (
            f"Suggest 8-12 relevant skills for a '{title}' role. "
            "Return a JSON object with key 'skills' containing an array of skill-name strings."
        )
        credit_tx = consume_credits_or_402(
            db, recruiter, 1, "wizard_suggest", reference_type="wizard_suggest"
        )
        res = await call_groq_cascade(
            [{"role": "user", "content": prompt}], json_mode=True
        )
        suggestions = res.get("skills", [])
        if suggestions:
            return SuggestionResult(suggestions=suggestions[:20], source="ai")
    except HTTPException:
        raise
    except Exception as e:
        if credit_tx is not None:
            try:
                rollback_credits(db, credit_tx)
            except Exception:
                pass
        logger.warning(f"AI suggest-skills fallback: {e}")

    return SuggestionResult(
        suggestions=[
            "Communication",
            "Problem Solving",
            "Teamwork",
            "Leadership",
            "Project Management",
            "Technical Writing",
            "Data Analysis",
            "Critical Thinking",
            "Adaptability",
            "Customer Focus",
        ],
        source="fallback",
    )


@router.post("/ai/suggest-weights", response_model=SuggestionResult)
async def ai_suggest_weights(
    body: dict,
    recruiter=Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    skills = body.get("skills", [])
    if not skills:
        return SuggestionResult(
            suggestions=[
                {"skill": s, "weight": round(100 / max(len(skills), 1))} for s in skills
            ],
            source="fallback",
        )
    credit_tx = None
    try:
        safe_skills = [_sanitize_for_prompt(s, 100) for s in skills]
        prompt = (
            f"Distribute 100 weight points across these skills: {', '.join(safe_skills)}. "
            "Return JSON with key 'weights' — an array of {'skill': str, 'weight': int} objects. "
            "All weights must sum to 100."
        )
        credit_tx = consume_credits_or_402(
            db, recruiter, 1, "wizard_suggest", reference_type="wizard_suggest"
        )
        res = await call_groq_cascade(
            [{"role": "user", "content": prompt}], json_mode=True
        )
        suggestions = res.get("weights", [])
        if suggestions and sum(s.get("weight", 0) for s in suggestions) == 100:
            return SuggestionResult(suggestions=suggestions, source="ai")
    except HTTPException:
        raise
    except Exception as e:
        if credit_tx is not None:
            try:
                rollback_credits(db, credit_tx)
            except Exception:
                pass
        logger.warning(f"AI suggest-weights fallback: {e}")

    equal = round(100 / max(len(skills), 1))
    remainder = 100 - equal * len(skills)
    suggestions = []
    for i, skill in enumerate(skills):
        w = equal + (remainder if i == 0 else 0)
        suggestions.append({"skill": skill, "weight": w})
    return SuggestionResult(suggestions=suggestions, source="fallback")


@router.post("/ai/generate-summary", response_model=SuggestionResult)
async def ai_generate_summary(
    body: dict,
    recruiter=Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    items = body.get("items", [])
    role_summary = (
        "A dynamic professional responsible for driving key outcomes in their domain."
    )
    if not items:
        return SuggestionResult(suggestions=[role_summary], source="fallback")

    credit_tx = None
    try:
        qa_lines = "\n".join(
            f"Q: {_sanitize_for_prompt(i.get('question', ''), 150)} "
            f"A: {_sanitize_for_prompt(i.get('answer', ''), 300)}"
            for i in items
            if i.get("answer")
        )
        if not qa_lines:
            return SuggestionResult(suggestions=[role_summary], source="fallback")

        prompt = (
            f"Based on these Q&A items, generate a concise 2-3 sentence role summary:\n{qa_lines}\n"
            "Return JSON with key 'summary' containing the summary string."
        )
        credit_tx = consume_credits_or_402(
            db, recruiter, 1, "wizard_suggest", reference_type="wizard_suggest"
        )
        res = await call_groq_cascade(
            [{"role": "user", "content": prompt}], json_mode=True
        )
        summary = res.get("summary", "")
        if summary:
            return SuggestionResult(suggestions=[summary], source="ai")
    except HTTPException:
        raise
    except Exception as e:
        if credit_tx is not None:
            try:
                rollback_credits(db, credit_tx)
            except Exception:
                pass
        logger.warning(f"AI generate-summary fallback: {e}")

    return SuggestionResult(suggestions=[role_summary], source="fallback")


@router.post("/ai/suggest-categories", response_model=SuggestionResult)
async def ai_suggest_categories(
    body: dict,
    recruiter=Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    skills = body.get("skills", [])
    if not skills:
        return SuggestionResult(
            suggestions=[
                {"name": "Technical Skills", "weight": 40, "sort_order": 0},
                {"name": "Soft Skills", "weight": 30, "sort_order": 1},
                {"name": "Experience & Impact", "weight": 30, "sort_order": 2},
            ],
            source="fallback",
        )

    credit_tx = None
    try:
        safe_skills = [_sanitize_for_prompt(s, 100) for s in skills]
        prompt = (
            f"Group these skills into 2-4 evaluation categories and assign weights summing to 100: "
            f"{', '.join(safe_skills)}. "
            "Return JSON with key 'categories' — array of {'name': str, 'weight': int, 'sort_order': int}."
        )
        credit_tx = consume_credits_or_402(
            db, recruiter, 1, "wizard_suggest", reference_type="wizard_suggest"
        )
        res = await call_groq_cascade(
            [{"role": "user", "content": prompt}], json_mode=True
        )
        suggestions = res.get("categories", [])
        if suggestions and sum(s.get("weight", 0) for s in suggestions) == 100:
            return SuggestionResult(suggestions=suggestions, source="ai")
    except HTTPException:
        raise
    except Exception as e:
        if credit_tx is not None:
            try:
                rollback_credits(db, credit_tx)
            except Exception:
                pass
        logger.warning(f"AI suggest-categories fallback: {e}")

    return SuggestionResult(
        suggestions=[
            {"name": "Technical Skills", "weight": 40, "sort_order": 0},
            {"name": "Soft Skills", "weight": 30, "sort_order": 1},
            {"name": "Experience & Impact", "weight": 30, "sort_order": 2},
        ],
        source="fallback",
    )


@router.post("/ai/suggest-pipeline", response_model=SuggestionResult)
async def ai_suggest_pipeline(
    body: dict,
    recruiter=Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    job_type = body.get("employment_type", "full-time")
    _ = _sanitize_for_prompt(str(job_type), 50)

    defaults = [
        {
            "name": "Applied",
            "slug": "applied",
            "sort_order": 0,
            "color": "#6366f1",
            "icon": "file-text",
        },
        {
            "name": "Screening",
            "slug": "screening",
            "sort_order": 1,
            "color": "#f59e0b",
            "icon": "search",
        },
        {
            "name": "Interview",
            "slug": "interview",
            "sort_order": 2,
            "color": "#3b82f6",
            "icon": "users",
        },
        {
            "name": "Offer",
            "slug": "offer",
            "sort_order": 3,
            "color": "#10b981",
            "icon": "check-circle",
        },
        {
            "name": "Hired",
            "slug": "hired",
            "sort_order": 4,
            "color": "#059669",
            "icon": "user-check",
        },
    ]

    credit_tx = None
    try:
        prompt = (
            f"Suggest a hiring pipeline for a {job_type} role with 4-6 stages. "
            "Return JSON with key 'stages' — array of {'name': str, 'slug': str, 'sort_order': int, "
            "'color': str (hex), 'icon': str}."
        )
        credit_tx = consume_credits_or_402(
            db, recruiter, 1, "wizard_suggest", reference_type="wizard_suggest"
        )
        res = await call_groq_cascade(
            [{"role": "user", "content": prompt}], json_mode=True
        )
        suggestions = res.get("stages", [])
        if suggestions and len(suggestions) >= 3:
            return SuggestionResult(suggestions=suggestions, source="ai")
    except HTTPException:
        raise
    except Exception as e:
        if credit_tx is not None:
            try:
                rollback_credits(db, credit_tx)
            except Exception:
                pass
        logger.warning(f"AI suggest-pipeline fallback: {e}")

    return SuggestionResult(suggestions=defaults, source="fallback")


@router.post("/ai/suggest-questions", response_model=SuggestionResult)
async def ai_suggest_questions(
    body: dict,
    recruiter=Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    skills = body.get("skills", [])
    if not skills:
        return SuggestionResult(
            suggestions=[
                {
                    "question": "Describe a challenging project you led.",
                    "type": "behavioral",
                    "sort_order": 0,
                },
                {
                    "question": "What relevant experience do you bring?",
                    "type": "general",
                    "sort_order": 1,
                },
            ],
            source="fallback",
        )

    credit_tx = None
    try:
        safe_skills = [_sanitize_for_prompt(s, 100) for s in skills]
        prompt = (
            f"Generate 3-5 screening questions for a role requiring these skills: "
            f"{', '.join(safe_skills)}. "
            "Return JSON with key 'questions' — array of {'question': str, 'type': str (technical|behavioral|general), "
            "'sort_order': int}."
        )
        credit_tx = consume_credits_or_402(
            db, recruiter, 1, "wizard_suggest", reference_type="wizard_suggest"
        )
        res = await call_groq_cascade(
            [{"role": "user", "content": prompt}], json_mode=True
        )
        suggestions = res.get("questions", [])
        if suggestions:
            return SuggestionResult(suggestions=suggestions, source="ai")
    except HTTPException:
        raise
    except Exception as e:
        if credit_tx is not None:
            try:
                rollback_credits(db, credit_tx)
            except Exception:
                pass
        logger.warning(f"AI suggest-questions fallback: {e}")

    return SuggestionResult(
        suggestions=[
            {
                "question": f"Describe your experience with {skills[0]}.",
                "type": "technical",
                "sort_order": 0,
            },
            {
                "question": "Tell us about a time you solved a complex problem.",
                "type": "behavioral",
                "sort_order": 1,
            },
            {
                "question": "Why are you interested in this role?",
                "type": "general",
                "sort_order": 2,
            },
        ],
        source="fallback",
    )


@router.post("/ai/suggest-salary", response_model=SuggestionResult)
async def ai_suggest_salary(
    body: dict,
    recruiter=Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    title = _sanitize_for_prompt(body.get("title", ""), 150)
    location = _sanitize_for_prompt(body.get("location", ""), 100)

    defaults = [
        {
            "source": "market",
            "min": 60000,
            "max": 90000,
            "currency": "USD",
            "label": "Market Range (Entry–Mid)",
        },
        {
            "source": "market",
            "min": 90000,
            "max": 140000,
            "currency": "USD",
            "label": "Market Range (Mid–Senior)",
        },
    ]

    if not title:
        return SuggestionResult(suggestions=defaults, source="fallback")

    credit_tx = None
    try:
        prompt = (
            f"Suggest a salary range for '{title}' in '{location}'. "
            "Return JSON with key 'ranges' — array of {'source': str, 'min': int, 'max': int, "
            "'currency': str, 'label': str}."
        )
        credit_tx = consume_credits_or_402(
            db, recruiter, 1, "wizard_suggest", reference_type="wizard_suggest"
        )
        res = await call_groq_cascade(
            [{"role": "user", "content": prompt}], json_mode=True
        )
        suggestions = res.get("ranges", [])
        if suggestions:
            return SuggestionResult(suggestions=suggestions, source="ai")
    except HTTPException:
        raise
    except Exception as e:
        if credit_tx is not None:
            try:
                rollback_credits(db, credit_tx)
            except Exception:
                pass
        logger.warning(f"AI suggest-salary fallback: {e}")

    return SuggestionResult(suggestions=defaults, source="fallback")


@router.post("/ai/detect-gaps", response_model=SuggestionResult)
async def ai_detect_gaps(
    body: dict,
    recruiter=Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    try:
        current_state = body.get("current_state", {})
        completed = set(current_state.get("completed_steps", []))

        gaps = []
        if 1 not in completed:
            gaps.append(
                {"step": 1, "field": "title", "message": "Job title is required"}
            )
        if 2 not in completed:
            gaps.append(
                {
                    "step": 2,
                    "field": "role_overviews",
                    "message": "Role overview Q&A is missing",
                }
            )
        if 3 not in completed:
            gaps.append(
                {
                    "step": 3,
                    "field": "skills",
                    "message": "At least one skill is required",
                }
            )
        if 4 not in completed:
            gaps.append(
                {
                    "step": 4,
                    "field": "evaluation_config",
                    "message": "Evaluation categories not configured",
                }
            )
        if 5 not in completed:
            gaps.append(
                {
                    "step": 5,
                    "field": "pipeline",
                    "message": "Pipeline stages not defined",
                }
            )

        title = _sanitize_for_prompt(current_state.get("title", ""), 200)

        if title and gaps:
            prompt = (
                f"For a '{title}' job creation wizard, the user has completed steps {completed}. "
                f"Remaining gaps: {', '.join(g['message'] for g in gaps)}. "
                "Suggest what to focus on next. Return JSON with key 'advice' — a short string."
            )
            try:
                credit_tx = consume_credits_or_402(
                    db, recruiter, 1, "wizard_suggest", reference_type="wizard_suggest"
                )
                res = await call_groq_cascade(
                    [{"role": "user", "content": prompt}], json_mode=True
                )
                advice = res.get("advice", "")
                if advice:
                    gaps.append({"step": 0, "field": "advice", "message": advice})
            except HTTPException:
                raise
            except Exception:
                try:
                    rollback_credits(db, credit_tx)
                except Exception:
                    pass

        if gaps:
            return SuggestionResult(
                suggestions=gaps,
                source="ai"
                if len(gaps) > len([g for g in gaps if g.get("step") == 0])
                else "fallback",
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"AI detect-gaps fallback: {e}")

    return SuggestionResult(suggestions=[], source="fallback")
