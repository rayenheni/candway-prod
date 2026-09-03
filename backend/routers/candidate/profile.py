import json
import logging
import os
import uuid
from datetime import UTC, datetime

from fastapi import (
    APIRouter,
    Body,
    Depends,
    File,
    HTTPException,
    UploadFile,
)
from sqlalchemy.orm import Session, selectinload

from backend.database import (
    Application,
    AuditLog,
    CandidateProfile,
    EvaluationSession,
    Job,
    ProfileVisit,
    User,
)
from backend.dependencies import get_current_user, get_db
from backend.profile_helpers import (
    get_user_availability,
    get_user_avatar_url,
    get_user_bio,
    get_user_email,
    get_user_github_url,
    get_user_headline,
    get_user_languages,
    get_user_linkedin_url,
    get_user_location,
    get_user_name,
    get_user_phone,
    get_user_portfolio_url,
    get_user_relocation_willing,
    get_user_salary_expectation_max,
    get_user_salary_expectation_min,
    get_user_skills,
    get_user_tier,
    get_user_work_preference,
)

from .applications import get_my_application_summary
from .common import _check_api_rate_limit, safe_load_json

router = APIRouter(tags=["candidate"])

logger = logging.getLogger(__name__)


@router.get("/me")
def get_candidate_me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "name": get_user_name(current_user),
        "email": get_user_email(current_user),
        "role": current_user.role,
        "phone": get_user_phone(current_user) or None,
        "location": get_user_location(current_user) or None,
        "headline": get_user_headline(current_user) or None,
        "bio": get_user_bio(current_user) or None,
        "linkedin_url": get_user_linkedin_url(current_user) or None,
        "github_url": get_user_github_url(current_user) or None,
        "portfolio_url": get_user_portfolio_url(current_user) or None,
        "avatar_url": get_user_avatar_url(current_user) or None,
        "skills": get_user_skills(current_user),
        "tier": get_user_tier(current_user) or "free",
        "last_active": datetime.now(UTC).isoformat(),
    }


@router.get("/profile/synthesis")
async def get_candidate_synthesis(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    app = (
        db.query(Application)
        .filter(Application.user_id == current_user.id)
        .order_by(Application.created_at.desc())
        .first()
    )
    if not app:
        return {"synthesis": None, "status": "no_data"}
    if app.analysis_json:
        data = safe_load_json(app.analysis_json)
        summary = data.get("summary") or data.get("professional_synthesis")
        if not summary and "builder_data" in data:
            summary = data["builder_data"].get("summary")
        if summary:
            return {
                "synthesis": summary,
                "key_strengths": data.get("key_strengths", []),
                "market_position": data.get("market_position", "Competitive"),
                "potential": data.get("potential", "High"),
                "generated_at": app.created_at.isoformat(),
            }

    _er_syn = (
        app.evaluation_sessions[0].evaluation_result
        if app.evaluation_sessions and app.evaluation_sessions[0].evaluation_result
        else None
    )
    score = (_er_syn.final_score if _er_syn else None) or 0
    return {
        "synthesis": f"{get_user_name(current_user)} is a {app.declared_role or 'professional'} with a technical score of {score}.",
        "market_position": "Job Ready",
        "potential": "High",
        "status": "partial",
    }


@router.get("/profile-data")
def get_candidate_profile_data(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    summary = get_my_application_summary(current_user, db)
    salary_min = get_user_salary_expectation_min(current_user)
    salary_max = get_user_salary_expectation_max(current_user)
    return {
        "success": True,
        "data": {
            **summary,
            "name": get_user_name(current_user),
            "phone": get_user_phone(current_user),
            "headline": get_user_headline(current_user),
            "location": get_user_location(current_user),
            "avatar_url": get_user_avatar_url(current_user),
            "bio": get_user_bio(current_user),
            "email": get_user_email(current_user),
            "skills": get_user_skills(current_user),
            "availability": get_user_availability(current_user)
            or "Available Immediately",
            "work_preference": get_user_work_preference(current_user)
            or "Remote / Hybrid",
            "salary_expectation_min": salary_min,
            "salary_expectation_max": salary_max,
            "expected_salary": f"{salary_min} - {salary_max}"
            if salary_min and salary_max
            else "Negotiable",
            "links": {
                "linkedin": get_user_linkedin_url(current_user),
                "github": get_user_github_url(current_user),
                "portfolio": get_user_portfolio_url(current_user),
            },
        },
    }


@router.get("/profile/comprehensive", response_model=dict)
def get_comprehensive_profile(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    app = (
        db.query(Application)
        .filter(Application.user_id == current_user.id)
        .order_by(Application.created_at.desc())
        .first()
    )
    analysis_data = {}
    if app and app.analysis_json:
        try:
            analysis_data = (
                json.loads(app.analysis_json)
                if isinstance(app.analysis_json, str)
                else app.analysis_json
            )
        except Exception:
            pass

    profile_builder = {}
    profile = getattr(current_user, "candidate_profile", None)
    if profile and profile.builder_data:
        try:
            profile_builder = safe_load_json(profile.builder_data) or {}
        except Exception:
            profile_builder = {}

    builder = profile_builder
    if not builder:
        builder = analysis_data.get("builder_data", {}) or profile_builder
    if "experience" in builder:
        experience = builder.get("experience") or []
    else:
        experience = analysis_data.get("experience", [])
    if "education" in builder:
        education = builder.get("education") or []
    else:
        education = analysis_data.get("education", [])
    advanced = analysis_data.get("advanced_analysis", {})
    if not experience and advanced.get("experience_timeline"):
        experience = [
            {
                "title": e.get("title") or e.get("role"),
                "company": e.get("company") or e.get("organization"),
                "duration": e.get("duration") or e.get("period"),
                "description": e.get("description") or e.get("achievements"),
            }
            for e in advanced.get("experience_timeline", [])
        ]
    skills = builder.get("skills", [])
    if not skills and analysis_data.get("skills"):
        skills = analysis_data.get("skills", [])
    if not skills and advanced.get("skills"):
        skills = [
            {"name": s.get("name"), "level": int((s.get("confidence", 0.5)) * 100)}
            for s in advanced.get("skills", [])
        ]
    if profile and profile.skills:
        try:
            profile_skills = (
                safe_load_json(profile.skills)
                if isinstance(profile.skills, str)
                else profile.skills
            )
            if profile_skills:
                skills = profile_skills
        except Exception:
            pass
    skills = _normalize_skills(skills)
    apps = (
        db.query(Application)
        .options(
            selectinload(Application.evaluation_sessions).selectinload(
                EvaluationSession.evaluation_result
            )
        )
        .filter(Application.user_id == current_user.id)
        .all()
    )
    badges = []
    interview_scores = []

    # Candidate profile score is CV/profile based.
    # Application final_score belongs to a specific job/interview and
    # must never become the candidate's global profile score.
    cv_scores = []

    for a in apps:
        _er_a = (
            a.evaluation_sessions[0].evaluation_result
            if a.evaluation_sessions and a.evaluation_sessions[0].evaluation_result
            else None
        )

        if _er_a:
            if _er_a.cv_score is not None:
                cv_scores.append(float(_er_a.cv_score))

            if _er_a.final_score is not None:
                interview_scores.append(float(_er_a.final_score))

    # Use the best available CV score as the candidate-level profile score.
    # This is independent from interview/application final scores.
    profile_score = max(cv_scores) if cv_scores else None

    scores = interview_scores

    if scores:
        badges.append(
            {
                "id": "first_steps",
                "name": "First Steps",
                "icon": "fa-shoe-prints",
                "description": "Completed your first AI interview",
                "color": "slate",
            }
        )
        if any(s >= 60 for s in scores):
            badges.append(
                {
                    "id": "rising_star",
                    "name": "Rising Star",
                    "icon": "fa-star",
                    "description": "Scored 60+ in an AI interview",
                    "color": "blue",
                }
            )
        if any(s >= 80 for s in scores):
            badges.append(
                {
                    "id": "expert",
                    "name": "Expert Performer",
                    "icon": "fa-award",
                    "description": "Scored 80+ in an AI interview",
                    "color": "purple",
                }
            )
        if len(scores) >= 10:
            badges.append(
                {
                    "id": "interview_pro",
                    "name": "Interview Pro",
                    "icon": "fa-microphone",
                    "description": f"Completed {len(scores)} AI interviews",
                    "color": "emerald",
                }
            )
    synthesis = analysis_data.get("summary") or analysis_data.get(
        "professional_synthesis"
    )
    if not synthesis and builder:
        synthesis = builder.get("summary")
    if not synthesis and profile and profile.bio:
        synthesis = profile.bio
    # CANONICAL CANDIDATE PROFILE SCORE:
    # A candidate profile is global and is NOT tied to one interview.
    # Therefore it must show the candidate's CV score, never an
    # application/interview final_score.
    _er_app = (
        app.evaluation_sessions[0].evaluation_result
        if app
        and app.evaluation_sessions
        and app.evaluation_sessions[0].evaluation_result
        else None
    )

    _profile_cv_score = (
        float(_er_app.cv_score)
        if _er_app is not None and _er_app.cv_score is not None
        else None
    )

    # Fallback to the CV analysis score when no EvaluationResult CV score exists.
    if _profile_cv_score is None:
        raw_analysis_score = analysis_data.get("score")
        try:
            _profile_cv_score = float(raw_analysis_score)
        except (TypeError, ValueError):
            _profile_cv_score = None

    _profile_score = (
        int(round(_profile_cv_score))
        if _profile_cv_score is not None
        else 0
    )

    _profile_verdict = (
        getattr(_er_app, "verdict", None)
        if _er_app is not None
        else None
    )
    return {
        "id": current_user.id,
        "name": get_user_name(current_user),
        "email": get_user_email(current_user),
        "phone": get_user_phone(current_user) or None,
        "location": get_user_location(current_user) or None,
        "headline": get_user_headline(current_user) or None,
        "bio": get_user_bio(current_user) or None,
        "avatar": get_user_avatar_url(current_user) or None,
        "linkedin_url": get_user_linkedin_url(current_user) or None,
        "github_url": get_user_github_url(current_user) or None,
        "portfolio_url": get_user_portfolio_url(current_user) or None,
        "skills": get_user_skills(current_user) or None,
        "tier": get_user_tier(current_user) or "free",
        "application": {
            "id": app.id if app else None,
            "status": app.status if app else None,
            # PROFILE SCORE = CV SCORE ONLY.
            # final_score belongs to an individual application/interview.
            "score": _profile_score,
            "verdict": _profile_verdict
            or (
                _er_app.verdict
                if _er_app and _er_app.verdict
                else (
                    (_er_app.score_breakdown or {}).get("verdict")
                    if _er_app and _er_app.score_breakdown
                    else None
                )
            ),
            "created_at": app.created_at.isoformat()
            if app and app.created_at
            else None,
        },
        "analysis": {
            "experience": experience,
            "education": education,
            "skills": skills,
            "summary": synthesis,
            "detected_role": analysis_data.get("detected_role"),
            "seniority_level": analysis_data.get("seniority_level"),
            "skill_metrics": analysis_data.get("skill_metrics")
            or analysis_data.get("skills")
            or {},
            "strengths": analysis_data.get("strengths", []),
            "weaknesses": analysis_data.get("weaknesses", []),
            "languages": analysis_data.get("languages", ["English", "French"]),
        },
        "badges": badges,
        "availability": get_user_availability(current_user) or "Available Immediately",
        "work_preference": get_user_work_preference(current_user)
        or "Full-time, Remote or Hybrid",
        "salary_min": get_user_salary_expectation_min(current_user) or 4000,
        "salary_max": get_user_salary_expectation_max(current_user) or 8000,
        "relocation_willing": get_user_relocation_willing(current_user),
        "currency": "TND",
    }


def _resolve_profile_score(_er_app, app, analysis_data, profile):
    """Resolve the candidate-level professional/CV score.

    IMPORTANT SCORE CONTRACT:
      - Profile score = CV/profile score.
      - Application final_score = job/application-specific interview result.
      - Never use final_score as the candidate's global profile score.

    Priority:
      1. EvaluationResult.cv_score
      2. analysis_json CV score
      3. cv_review numeric score stored in profile builder data
      4. overall_grade converted to 0-100
      5. average skill level as last resort
    """

    # 1. Canonical CV score from EvaluationResult.
    if _er_app is not None and getattr(_er_app, "cv_score", None) is not None:
        return int(round(float(_er_app.cv_score))), None

    # 2. CV analysis score.
    for key in ("cv_score", "score"):
        value = analysis_data.get(key)
        if isinstance(value, (int, float)):
            return int(round(float(value))), None

    # 3. CV builder/review score.
    builder_data = {}
    if profile is not None:
        raw_builder = getattr(profile, "builder_data", None)
        if raw_builder:
            try:
                builder_data = (
                    safe_load_json(raw_builder)
                    if isinstance(raw_builder, str)
                    else raw_builder
                ) or {}
            except Exception:
                builder_data = {}

    cv_review = builder_data.get("cv_review") or builder_data.get("cvReview") or {}

    if isinstance(cv_review, dict):
        for key in ("score", "cv_score", "numeric_score"):
            value = cv_review.get(key)
            if isinstance(value, (int, float)):
                return int(round(float(value))), None

        grade = cv_review.get("overall_grade")
        if isinstance(grade, str):
            grade_map = {
                "A+": 95,
                "A": 90,
                "A-": 87,
                "B+": 85,
                "B": 80,
                "B-": 77,
                "C+": 75,
                "C": 70,
                "C-": 67,
                "D": 60,
                "F": 40,
            }
            normalized = grade.strip().upper()
            if normalized in grade_map:
                return grade_map[normalized], None

    # 4. Skill-level fallback.
    skills = builder_data.get("skills") or analysis_data.get("skills") or []
    levels = []

    if isinstance(skills, list):
        for skill in skills:
            if not isinstance(skill, dict):
                continue
            level = skill.get("level")
            if isinstance(level, (int, float)):
                levels.append(float(level))

    if levels:
        return int(round(sum(levels) / len(levels))), None

    # No candidate-level score available yet.
    return None, None

@router.get("/profile/{user_id}")
def get_public_profile(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    logger.info(
        f"Profile access: user_id={current_user.id}, target_user_id={user_id}, role={current_user.role}"
    )

    if current_user.id != user_id:
        if current_user.role != "recruiter":
            raise HTTPException(
                status_code=403,
                detail="Permission denied. Only recruiters can view profiles.",
            )

        from backend.database import BatchJob

        has_link = (
            db.query(Application)
            .outerjoin(Job)
            .outerjoin(BatchJob)
            .filter(
                Application.user_id == user_id,
                (
                    (Job.recruiter_id == current_user.id)
                    | (BatchJob.recruiter_id == current_user.id)
                ),
            )
            .first()
        )

        if not has_link:
            logger.warning(
                f"SECURITY: Unauthorized profile access - user {current_user.id} tried to access candidate {user_id}"
            )
            raise HTTPException(
                status_code=403,
                detail="Access denied. You can only view profiles of candidates who applied to your jobs or campaigns.",
            )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    app = (
        db.query(Application)
        .filter(Application.user_id == user_id)
        .order_by(Application.created_at.desc())
        .first()
    )
    cv_data = {}
    if app and app.analysis_json:
        full_data = safe_load_json(app.analysis_json)
        cv_data = full_data.get("builder_data", {})

    is_owner = current_user.id == user_id
    is_pro = (
        is_owner or current_user.role == "admin" or get_user_tier(current_user) == "pro"
    )

    return {
        "id": user.id,
        "name": get_user_name(user),
        "headline": get_user_headline(user),
        "location": get_user_location(user),
        "bio": get_user_bio(user),
        "email": get_user_email(user) if is_pro else "hidden@candway.com",
        "phone": (get_user_phone(user) if is_pro else "+* ** *** ***")
        if get_user_phone(user)
        else None,
        "links": {
            "linkedin": get_user_linkedin_url(user),
            "github": get_user_github_url(user),
            "portfolio": get_user_portfolio_url(user),
        },
        "cv": cv_data,
        "is_locked": not is_pro,
    }


@router.post("/profile/{user_id}/view")
def increment_profile_view(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "recruiter":
        return {"status": "skipped", "reason": "non_recruiter_view"}

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    profile = getattr(user, "candidate_profile", None)
    new_count = ((profile.profile_views if profile else 0) or 0) + 1
    if profile:
        profile.profile_views = new_count

    visit = ProfileVisit(candidate_id=user_id, visitor_id=current_user.id)
    db.add(visit)

    db.commit()
    return {"status": "success", "new_total": new_count}


@router.get("/profile-visitors")
def get_profile_visitors(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    if current_user.role != "candidate":
        raise HTTPException(status_code=403, detail="Only candidates can access this.")

    visitors = (
        db.query(ProfileVisit)
        .filter(ProfileVisit.candidate_id == current_user.id)
        .order_by(ProfileVisit.created_at.desc())
        .limit(50)
        .all()
    )

    result = []
    seen_users = set()
    for v in visitors:
        if v.visitor_id in seen_users:
            continue
        seen_users.add(v.visitor_id)

        result.append(
            {
                "id": v.visitor.id,
                "name": get_user_name(v.visitor) or "Anonymous Recruiter",
                "company": getattr(
                    getattr(v.visitor, "recruiter_profile", None), "company_name", None
                )
                or "Unknown Company",
                "avatar": getattr(
                    getattr(v.visitor, "recruiter_profile", None),
                    "company_logo_url",
                    None,
                ),
                "visited_at": v.created_at.isoformat(),
            }
        )

    return result


def _parse_skills_json(raw):
    if not raw:
        return []
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str) and raw.startswith("[") and raw.endswith("]"):
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            pass
    return raw


def _normalize_skills(raw_skills):
    """Normalize mixed skill shapes (str / dict / JSON string) to [{name, level}]."""
    if raw_skills is None:
        return []
    if isinstance(raw_skills, str):
        try:
            parsed = json.loads(raw_skills)
        except (json.JSONDecodeError, TypeError):
            parsed = [s.strip() for s in raw_skills.split(",") if s.strip()]
        return _normalize_skills(parsed)
    if not isinstance(raw_skills, list):
        return []
    normalized = []
    for s in raw_skills:
        if isinstance(s, str):
            if s.strip():
                normalized.append({"name": s.strip(), "level": 70})
        elif isinstance(s, dict):
            name = s.get("name") or s.get("skill")
            if name:
                level = s.get("level")
                if level is None and isinstance(s.get("confidence"), (int, float)):
                    level = int(s.get("confidence") * 100)
                normalized.append(
                    {
                        "name": str(name),
                        "level": level if isinstance(level, int) else 70,
                    }
                )
    return normalized


@router.put("/profile")
async def update_profile(
    data: dict = Body(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    is_allowed, retry_after = await _check_api_rate_limit(
        identifier=f"profile_update_{current_user.id}",
        max_requests=10,
        window_seconds=3600,
    )
    if not is_allowed:
        raise HTTPException(
            status_code=429,
            detail=f"Too many profile updates. Please wait {retry_after} seconds.",
        )

    # CandidateProfile is the canonical candidate profile record.
    # Existing users may predate this model, so create it lazily.
    profile = (
        db.query(CandidateProfile)
        .filter(CandidateProfile.user_id == current_user.id)
        .first()
    )

    if not profile:
        profile = CandidateProfile(
            user_id=current_user.id,
            company_id=None,
        )
        db.add(profile)
        db.flush()

    allowed_fields = [
        "name",
        "headline",
        "location",
        "bio",
        "phone",
        "linkedin_url",
        "github_url",
        "portfolio_url",
        "skills",
        "languages",
        "availability",
        "work_preference",
        "salary_expectation_min",
        "salary_expectation_max",
        "relocation_willing",
    ]
    profile_write_fields = {
        "name",
        "headline",
        "bio",
        "phone",
        "skills",
        "location",
        "languages",
        "availability",
        "work_preference",
        "salary_expectation_min",
        "salary_expectation_max",
        "relocation_willing",
    }
    updated_fields = []
    for field, value in data.items():
        if field in allowed_fields:
            profile_value = value
            if field == "skills":
                if isinstance(value, list):
                    if value and all(isinstance(s, dict) for s in value):
                        profile_value = json.dumps(_normalize_skills(value))
                    else:
                        profile_value = json.dumps(
                            [str(s).strip() for s in value if str(s).strip()]
                        )
                elif isinstance(value, str):
                    parts = [s.strip() for s in value.split(",") if s.strip()]
                    profile_value = json.dumps(parts) if parts else "[]"
                setattr(current_user, field, profile_value)
            else:
                setattr(current_user, field, value)
            if field in profile_write_fields:
                setattr(profile, field, profile_value)
            updated_fields.append(field)

    if profile and profile.builder_data and ("skills" in data or "summary" in data):
        try:
            builder_data = safe_load_json(profile.builder_data) or {}
        except Exception:
            builder_data = {}
        dirty = False
        if "skills" in data and "skills" in builder_data:
            existing_names = set()
            for s in builder_data["skills"]:
                if isinstance(s, dict) and s.get("name"):
                    existing_names.add(str(s["name"]))
                elif isinstance(s, str):
                    existing_names.add(s)
            new_names = set()
            for s in _normalize_skills(data["skills"]):
                new_names.add(s["name"])
            if existing_names != new_names:
                builder_data["skills"] = _normalize_skills(data["skills"])
                dirty = True
        if "summary" in data and data["summary"]:
            builder_data["summary"] = data["summary"]
            dirty = True
        if dirty:
            profile.builder_data = json.dumps(builder_data)
    audit = AuditLog(
        user_id=current_user.id,
        action="profile_update",
        target_id=str(current_user.id),
        details=f"Updated fields: {', '.join(updated_fields)}",
        ip_address="system",
    )
    db.add(audit)
    db.commit()
    db.refresh(current_user)
    return {
        "message": "Profile updated successfully",
        "user": {
            "name": get_user_name(current_user),
            "headline": get_user_headline(current_user),
            "location": get_user_location(current_user),
            "avatar": get_user_avatar_url(current_user),
            "skills": _parse_skills_json(get_user_skills(current_user)),
        },
    }


@router.get("/profile")
def get_profile(current_user: User = Depends(get_current_user)):
    return {
        "name": get_user_name(current_user),
        "email": get_user_email(current_user),
        "phone": get_user_phone(current_user),
        "headline": get_user_headline(current_user),
        "location": get_user_location(current_user) or None,
        "bio": get_user_bio(current_user),
        "avatar": get_user_avatar_url(current_user) or None,
        "skills": _parse_skills_json(get_user_skills(current_user)),
        "languages": get_user_languages(current_user) or None,
        "availability": get_user_availability(current_user) or None,
        "work_preference": get_user_work_preference(current_user) or None,
        "salary_expectation_min": get_user_salary_expectation_min(current_user) or None,
        "salary_expectation_max": get_user_salary_expectation_max(current_user) or None,
        "relocation_willing": get_user_relocation_willing(current_user),
        "links": {
            "linkedin": get_user_linkedin_url(current_user) or None,
            "github": get_user_github_url(current_user) or None,
            "portfolio": get_user_portfolio_url(current_user) or None,
        },
    }


@router.post("/avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Invalid image file")

    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(
            status_code=400, detail="File too large. Maximum 5MB allowed."
        )

    try:
        from backend.file_security import scan_for_malware
        from backend.security import secure_filename

        safe_filename = secure_filename(file.filename)
        is_safe, scan_result = scan_for_malware(content, safe_filename)
        if not is_safe:
            logger.warning(
                f" MALWARE DETECTED in avatar upload by user {current_user.id}: {scan_result}"
            )
            raise HTTPException(
                status_code=400, detail="File contains potentially malicious content"
            )
    except ImportError:
        pass

    UPLOAD_DIR = "uploads/avatars"
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    ext = file.filename.split(".")[-1] if "." in file.filename else "jpg"
    filename = f"{current_user.id}_{uuid.uuid4().hex[:8]}.{ext}"
    file_path = os.path.join(UPLOAD_DIR, filename)
    with open(file_path, "wb") as buffer:
        buffer.write(content)

    avatar_url = f"/uploads/avatars/{filename}"
    profile = getattr(current_user, "candidate_profile", None)
    if profile:
        profile.avatar_url = avatar_url
    db.commit()
    return {"url": avatar_url}
