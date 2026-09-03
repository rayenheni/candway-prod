import json
import logging
from datetime import UTC, datetime, timedelta
from typing import List, Optional, Tuple

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
)
from pydantic import BaseModel
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session, joinedload, selectinload, undefer

from backend.candidate_subscription_service import CandidateSubscriptionService
from backend.database import (
    Application,
    ConversationParticipant,
    EEOConsent,
    EvaluationSession,
    Interview,
    Job,
    Message,
    SavedJob,
    User,
)
from backend.dependencies import get_current_user, get_db, get_interview_access
from backend.entity_writer import sync_cv_document
from backend.enums import canonicalize_status
from backend.models.ats.types import ApplicationType
from backend.models.evaluation.profile import CandidateProfile
from backend.pdf_generator import generate_pdf_report
from backend.profile_helpers import (
    get_user_avatar_url,
    get_user_bio,
    get_user_company_name,
    get_user_email,
    get_user_github_url,
    get_user_headline,
    get_user_is_super_admin,
    get_user_linkedin_url,
    get_user_location,
    get_user_name,
    get_user_phone,
    get_user_portfolio_url,
    get_user_profile_views,
    get_user_profile_views_growth,
    get_user_skills,
)
from backend.scoring_service import ScoringService
from backend.services.application_service import ApplicationService

from .common import (
    normalize_interview_log_for_dashboard,
    safe_load_json,
)

router = APIRouter(tags=["candidate"])

logger = logging.getLogger(__name__)


class CVData(BaseModel):
    summary: str = ""
    skills: List[str] = []
    experience: List[dict] = []
    education: List[dict] = []
    projects: List[dict] = []
    languages: List[dict] = []
    certifications: List[dict] = []
    declared_role: Optional[str] = "General"
    location: Optional[str] = None
    phone: Optional[str] = None


def generate_anonymized_text(data: CVData) -> str:
    text = f"ROLE TARGET: {data.declared_role}\n\n"
    text += f"SUMMARY:\n{data.summary}\n\n"
    text += "SKILLS:\n" + ", ".join(data.skills) + "\n\n"
    text += "EXPERIENCE:\n"
    for exp in data.experience:
        text += f"- {exp.get('role', 'Role')} at {exp.get('company', 'Company')} ({exp.get('duration', '')})\n"
        text += f"  {exp.get('description', '')}\n"
    text += "\n"
    text += "EDUCATION:\n"
    for edu in data.education:
        text += f"- {edu.get('degree', 'Degree')} in {edu.get('field', 'Field')} at {edu.get('school', 'School')} ({edu.get('year', '')})\n"
    text += "\n"
    text += "PROJECTS:\n"
    for proj in data.projects:
        text += f"- {proj.get('name', 'Project')}: {proj.get('description', '')} (Tech: {proj.get('tech', '')})\n"
    return text


def _recruiter_has_application_access(
    application: Application, current_user: User
) -> bool:
    if not current_user or not application:
        return False
    if current_user.role in ["admin"] or get_user_is_super_admin(current_user):
        return True
    if application.assigned_to == current_user.id:
        return True
    if application.job and application.job.recruiter_id == current_user.id:
        return True
    if application.batch_job and application.batch_job.recruiter_id == current_user.id:
        return True
    return False


async def run_cv_analysis(
    app_id: int,
    text: str,
    role: str,
    db: Session,
    job_id: Optional[int] = None,
):
    from backend.ai import analyze_cv, extract_cv_details
    from backend.database import Application, Rubric
    from backend.notifications import notify_user
    from backend.services.rubric_match_service import (
        build_rubric_context,
        compute_rubric_skill_match,
        compute_rubric_weighted_cv_score,
    )

    # Job-specific apply: resolve the job's rubric (modern Job.rubric_id,
    # falling back to the legacy Rubric.job_id binding) and run the CV
    # extraction with that rubric's context so the analysis + score are
    # specific to this job. The CV score is then recruiter-visible before
    # any AI interview invite.
    rubric = None
    rubric_context = ""
    is_job_apply = job_id is not None
    if is_job_apply:
        job = db.query(Job).filter(Job.id == job_id).first()
        if job:
            rubric_id = job.rubric_id
            if rubric_id:
                rubric = (
                    db.query(Rubric)
                    .filter(
                        Rubric.id == rubric_id,
                        Rubric.company_id == job.company_id,
                        Rubric.is_active,
                    )
                    .first()
                )
            if rubric is None:
                rubric = (
                    db.query(Rubric)
                    .filter(
                        Rubric.job_id == job_id,
                        Rubric.company_id == job.company_id,
                        Rubric.is_active,
                    )
                    .first()
                )
            if rubric is not None:
                try:
                    rubric_context = build_rubric_context(rubric)
                except Exception as e:
                    logger.warning(
                        f"run_cv_analysis: failed to build rubric context for rubric {rubric.id}: {e}"
                    )
                    rubric_context = ""

    try:
        if rubric_context:
            result = await extract_cv_details(text, role, rubric_context)
        else:
            result = await analyze_cv(text, role)
        app = (
            db.query(Application)
            .options(
                selectinload(Application.cv_document),
            )
            .filter(Application.id == app_id)
            .first()
        )
        if app:
            _cv = app.cv_document
            _a = getattr(_cv, "analysis_json", None) or app.analysis_json
            existing_meta = {}
            if _a:
                try:
                    existing_meta = json.loads(_a)
                except Exception as e:
                    logger.error(f"Error parsing existing meta: {e}")
            builder_data = existing_meta.get("builder_data")
            result["builder_data"] = builder_data
            if rubric is not None and rubric_context:
                try:
                    match = compute_rubric_skill_match(text, rubric)
                    ai_semantic_score = result.get("score")
                    if ai_semantic_score is None or float(ai_semantic_score) <= 0:
                        ai_semantic_score = float(match["match_percentage"])
                        result["score"] = ai_semantic_score
                    # P0: deterministic rubric-weighted CV score. When the
                    # rubric is parseable, this becomes the recruiter-visible
                    # cv_score (per-skill weighted evidence), replacing the raw
                    # AI semantic score. On any parsing/scoring failure we fall
                    # back to the keyword-scan score and mark generic_fallback.
                    weighted = None
                    try:
                        weighted = compute_rubric_weighted_cv_score(
                            text, rubric, result.get("skills")
                        )
                    except Exception as w_err:
                        logger.warning(
                            f"run_cv_analysis: rubric-weighted CV scoring failed for app "
                            f"{app_id}: {w_err}"
                        )
                    if weighted is not None:
                        result["score"] = weighted["cv_score"]
                        result["scoring_method"] = weighted["scoring_method"]
                        result["cv_rubric_weighted"] = True
                        result["skill_scores"] = weighted["skill_scores"]
                        result["normalized_weights"] = weighted["normalized_weights"]
                        result["coverage_pct"] = weighted["coverage_pct"]
                        result["missing_skills"] = weighted["missing_skills"]
                        ai_semantic_score = float(weighted["cv_score"])
                    else:
                        result["scoring_method"] = "generic_fallback"
                        result["cv_rubric_weighted"] = False
                    result["rubric_match"] = {
                        "rubric_id": rubric.id,
                        "rubric_title": rubric.title or "Rubric",
                        "match_percentage": int(round(ai_semantic_score)),
                        "total_skills": match["total_skills"],
                        "matched_skills": match["matched_skills"],
                        "missing_skills": match["missing_skills"],
                    }
                except Exception as e:
                    logger.warning(
                        f"run_cv_analysis: rubric match computation failed for app {app_id}: {e}"
                    )
                    result["scoring_method"] = "generic_fallback"
                    result["cv_rubric_weighted"] = False
            sync_cv_document(
                db, app, analysis_json=result, detected_role=result.get("detected_role")
            )
            if result.get("score") is not None:
                score_val = float(result["score"])
                score_val = max(0.0, min(100.0, score_val))
                if result.get("cv_rubric_weighted"):
                    ScoringService.set_cv_rubric(
                        app,
                        db,
                        cv_score=score_val,
                        breakdown={
                            "cv_rubric_weighted": True,
                            "skill_scores": result.get("skill_scores"),
                            "normalized_weights": result.get("normalized_weights"),
                            "coverage_pct": result.get("coverage_pct"),
                            "missing_skills": result.get("missing_skills"),
                            "scoring_method": result.get(
                                "scoring_method", "deterministic_keyword_weighted"
                            ),
                            "detail_rows": [
                                {
                                    "criterion_name": name,
                                    "score": info.get("score", 0.0),
                                    "weight": info.get("normalized_weight"),
                                    "feedback": info.get("feedback"),
                                }
                                for name, info in (
                                    (result.get("skill_scores") or {}).items()
                                )
                            ],
                        },
                        computed_by="cv_analysis",
                    )
                else:
                    ScoringService.set_cv_only(
                        app, db, cv_score=score_val, computed_by="cv_analysis"
                    )
            if result.get("verdict"):
                ScoringService.set_verdict(
                    app, db, verdict=result["verdict"], computed_by="cv_analysis"
                )
            if app.rubric_id is None and rubric is not None:
                app.rubric_id = rubric.id
                logger.info(
                    f"Linked application {app.id} to rubric {rubric.id} after CV analysis"
                )
            # Job-specific applies move straight into recruiter review
            # ("screening"); the manual CV-builder path keeps "analyzed".
            # If the AI returned an error payload, keep the app out of
            # recruiter review instead of silently screening a failed analysis.
            if result.get("error"):
                app.status = "analysis_failed"
                app.analysis_error = str(result.get("error"))[:500]
            else:
                app.status = "screening" if is_job_apply else "analyzed"
            # Apply-time CV analysis is charged to the owning company's wallet
            # (recruiter pays; applying stays free for the candidate). Best-effort
            # in a background task: a company with no resolvable wallet/member is
            # simply not charged rather than blocking the candidate's application.
            if is_job_apply and not result.get("error"):
                try:
                    from backend.credit_service import consume_company_credits

                    fallback = None
                    if getattr(job, "recruiter_id", None):
                        fallback = (
                            db.query(User)
                            .filter(User.id == job.recruiter_id)
                            .first()
                        )
                    consume_company_credits(
                        db,
                        getattr(app, "company_id", None),
                        3,
                        "cv_analysis",
                        reference_type="application",
                        reference_id=app_id,
                        fallback_user=fallback,
                    )
                except Exception as charge_err:
                    logger.warning(
                        f"run_cv_analysis: company credit charge skipped for app "
                        f"{app_id}: {charge_err}"
                    )
            db.commit()
            await notify_user(
                str(app.user_id),
                "Your CV analysis is complete. You can now view your assessment.",
                title="Analysis Complete",
                level="success",
            )
            # Candidate AI-analysis usage is reserved by the candidate
            # CV-analysis route before the AI call. Do not increment the
            # monthly counter here, otherwise successful analyses can be
            # counted twice.
            db.commit()
    except Exception as e:
        logger.error(f"Background Analysis Failed: {e}")
        app = db.query(Application).filter(Application.id == app_id).first()
        if app:
            try:
                app.status = "analysis_failed"
                app.analysis_error = str(e)
                db.commit()
            except Exception as state_err:
                logger.error(
                    f"Failed to persist analysis failure state for app {app_id}: {state_err}"
                )
        try:
            if app:
                await notify_user(
                    str(app.user_id),
                    "There was an error analyzing your CV. Please try re-uploading.",
                    title="Analysis Failed",
                    level="error",
                )
        except Exception as notify_err:
            logger.error(
                f"CV analysis failure notification failed for app {app_id}: {notify_err}"
            )


@router.post("/applications")
def save_application(
    cv_data: CVData,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        if cv_data.phone and current_user.candidate_profile:
            current_user.candidate_profile.phone = cv_data.phone
        if cv_data.location and current_user.candidate_profile:
            current_user.candidate_profile.location = cv_data.location

        app = (
            db.query(Application)
            .options(
                selectinload(Application.cv_document),
                selectinload(Application.evaluation_sessions).selectinload(
                    EvaluationSession.evaluation_result
                ),
            )
            .filter(
                Application.user_id == current_user.id, Application.status == "applied"
            )
            .with_for_update()
            .order_by(Application.created_at.desc())
            .first()
        )

        if not any(
            (
                cv_data.summary and cv_data.summary.strip(),
                cv_data.skills,
                cv_data.experience,
                cv_data.education,
                cv_data.projects,
                cv_data.languages,
                cv_data.certifications,
            )
        ):
            raise HTTPException(
                status_code=400,
                detail="Please provide at least one section of your CV before saving this application.",
            )

        company_id = getattr(current_user, "_company_id", None)
        if not company_id:
            raise HTTPException(
                status_code=403, detail="Candidate company membership is required"
            )

        if not app:
            app = ApplicationService.create_application(
                db,
                company_id=company_id,
                application_type=ApplicationType.MANUAL,
                user_id=current_user.id,
                candidate_email=get_user_email(current_user),
                candidate_name=get_user_name(current_user),
                status="applied",
            )
        _cv = app.cv_document
        _er_sa = (
            app.evaluation_sessions[0].evaluation_result
            if app.evaluation_sessions and app.evaluation_sessions[0].evaluation_result
            else None
        )
        _sc = _er_sa
        _cv_text = getattr(_cv, "cv_text_anonymized", None) or app.cv_text_anonymized
        _cv_role = getattr(_cv, "declared_role", None) or app.declared_role
        _sc_score = _sc.final_score if _sc else None
        sync_cv_document(db, app, declared_role=cv_data.declared_role)
        app.full_name = get_user_name(current_user)
        app.email = get_user_email(current_user)
        app.phone = get_user_phone(current_user)
        sync_cv_document(db, app, cv_text_anonymized=generate_anonymized_text(cv_data))
        # CV Builder saves are not file uploads.
        # Do not consume the monthly CV upload quota here.
        existing_meta = {}
        if app.analysis_json:
            existing_meta = safe_load_json(app.analysis_json)
        existing_meta["builder_data"] = cv_data.model_dump()
        sync_cv_document(db, app, analysis_json=existing_meta)
        if not (ScoringService.get_canonical_score(app.id, db) or _sc_score):
            base_score = 10
            if len(cv_data.experience) > 0:
                base_score += 20
            if len(cv_data.education) > 0:
                base_score += 15
            if len(cv_data.skills) > 3:
                base_score += 15
            ScoringService.set_cv_only(
                app, db, cv_score=float(base_score), computed_by="cv_builder_init"
            )
        db.commit()
        db.refresh(app)
        from backend.trakin.core import safe_execute

        background_tasks.add_task(
            safe_execute,
            "AI_CV_Analysis",
            run_cv_analysis,
            app_id=app.id,
            text=_cv_text,
            role=_cv_role,
            db=db,
        )
        return {
            "id": app.id,
            "status": app.status,
            "message": "CV Saved Successfully",
            "eeo_url": f"/candidate/eeo-form?application_id={app.id}",
        }
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(
            f"save_application internal error (user={current_user.id}): {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred while saving your application. Please try again.",
        )


def _compute_talent_graph_data(analysis_data: dict, skills_dict: dict) -> dict:
    strengths = analysis_data.get("strengths", [])
    analysis_data.get("weaknesses", [])
    gaps = analysis_data.get("gaps", [])
    skill_metrics = analysis_data.get("skill_metrics") or skills_dict or {}

    clusters = {}
    categories = {
        "technical": [
            "python",
            "java",
            "javascript",
            "typescript",
            "react",
            "sql",
            "aws",
            "docker",
            "api",
            "backend",
            "frontend",
            "database",
            "cloud",
            "devops",
            "system design",
        ],
        "soft": [
            "communication",
            "leadership",
            "teamwork",
            "problem solving",
            "critical thinking",
            "adaptability",
            "creativity",
        ],
        "domain": [
            "machine learning",
            "data science",
            "product management",
            "finance",
            "marketing",
            "sales",
        ],
        "tools": ["git", "jira", "figma", "docker", "kubernetes", "jenkins", "ci/cd"],
    }
    for skill_name, val in (
        skill_metrics if isinstance(skill_metrics, dict) else {}
    ).items():
        skill_lower = skill_name.lower()
        assigned = False
        for cat, keywords in categories.items():
            if any(kw in skill_lower for kw in keywords):
                if cat not in clusters:
                    clusters[cat] = []
                clusters[cat].append(
                    {"name": skill_name, "score": min(100, int(val) if val else 50)}
                )
                assigned = True
                break
        if not assigned:
            if "core" not in clusters:
                clusters["core"] = []
            clusters["core"].append(
                {"name": skill_name, "score": min(100, int(val) if val else 50)}
            )

    weakness_zones = [
        s
        for s in (strengths if isinstance(strengths, list) else [])
        if isinstance(s, str) and len(s) < 60
    ]
    strength_zones = []
    for k, v in (skill_metrics if isinstance(skill_metrics, dict) else {}).items():
        try:
            if float(v) >= 70:
                strength_zones.append(k)
        except (ValueError, TypeError):
            pass

    relationships = []
    seen_pairs = set()
    for cat, items in clusters.items():
        names = [it["name"] for it in items][:4]
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                pair = tuple(sorted([names[i], names[j]]))
                if pair not in seen_pairs:
                    seen_pairs.add(pair)
                    relationships.append(
                        {
                            "source": pair[0],
                            "target": pair[1],
                            "value": 30,
                            "category": cat,
                        }
                    )
    relationships = relationships[:10]

    return {
        "clusters": clusters,
        "strength_zones": strength_zones[:8],
        "weakness_zones": weakness_zones[:8] or (gaps[:4] if gaps else []),
        "skill_relationships": relationships,
        "node_count": len(skill_metrics),
        "edge_count": len(relationships),
    }


def _compute_career_intelligence(
    analysis_data: dict, app, current_user, db=None
) -> dict:
    _cv = app.cv_document if app else None
    _er_ci = (
        app.evaluation_sessions[0].evaluation_result
        if app
        and app.evaluation_sessions
        and app.evaluation_sessions[0].evaluation_result
        else None
    )
    _sc = _er_ci
    declared_role = (
        getattr(_cv, "declared_role", None)
        or (app.declared_role if app else None)
        or "General"
    )
    score = _sc.final_score if _sc else None

    market_scores = {
        "software engineer": 92,
        "data scientist": 88,
        "product manager": 85,
        "devops": 90,
        "backend developer": 91,
        "frontend developer": 87,
        "full stack": 89,
        "machine learning": 93,
        "ai engineer": 94,
        "designer": 78,
        "marketing": 72,
        "sales": 70,
        "general": 75,
    }
    role_lower = declared_role.lower()
    market_score = 75
    for key, val in market_scores.items():
        if key in role_lower:
            market_score = val
            break

    base_salary = {"junior": 45000, "mid": 75000, "senior": 110000, "lead": 150000}
    seniority = "mid"
    if score >= 85:
        seniority = "senior"
    elif score >= 70:
        seniority = "mid"
    elif score >= 50:
        seniority = "junior"
    else:
        seniority = "junior"

    salary_min = int(base_salary.get(seniority, 75000) * (0.85 + (score / 500)))
    salary_max = int(base_salary.get(seniority, 75000) * (1.15 + (score / 400)))
    salary_currency = "USD"

    hiring_prob = min(95, max(5, int(score * 0.7 + market_score * 0.3)))

    return {
        "market_score": market_score,
        "market_demand": "Very High"
        if market_score >= 85
        else "High"
        if market_score >= 70
        else "Moderate"
        if market_score >= 50
        else "Low",
        "salary_estimation": {
            "min": salary_min,
            "max": salary_max,
            "currency": salary_currency,
        },
        "hiring_probability": hiring_prob,
        "seniority_level": seniority.capitalize(),
        "best_fitting_roles": [
            declared_role,
            f"Senior {declared_role}"
            if seniority != "senior"
            else f"Lead {declared_role}",
        ],
        "top_companies": top_companies_for_role(declared_role, db) if db else [],
        "skill_trends": {
            "rising": ["AI/ML", "Cloud Native", "System Design"],
            "declining": ["Legacy Systems", "Monolithic Architecture"],
        },
    }


def top_companies_for_role(declared_role: str, db=None) -> list:
    if not db:
        return []
    try:
        from backend.database import Job

        terms = [t for t in (declared_role or "").lower().split() if len(t) > 2]
        if not terms:
            return []
        q = db.query(Job).filter(Job.is_active == True)  # noqa: E712
        for t in terms[:2]:
            q = q.filter(Job.title.ilike(f"%{t}%"))
        rows = q.order_by(Job.created_at.desc()).limit(5).all()
        seen = []
        for j in rows:
            name = j.company_name or (j.company.name if j.company else None)
            if name and name not in seen:
                seen.append(name)
        return seen[:5]
    except Exception as e:
        logger.warning(f"Failed to resolve applicant companies: {e}")
        return []


def get_profile_checklist(user: User, app: Application) -> list:
    _ev_ses_prof = (
        app.evaluation_sessions[0] if app and app.evaluation_sessions else None
    )
    _iv_state_prof = getattr(_ev_ses_prof, "interview_state", None) or (
        app.interview_state if app else None
    )
    return [
        {
            "id": "cv",
            "label": "CV Uploaded",
            "completed": bool(app and app.cv_file_path),
        },
        {
            "id": "linkedin",
            "label": "LinkedIn Linked",
            "completed": bool(get_user_linkedin_url(user)),
        },
        {
            "id": "ai_interview",
            "label": "AI Interview",
            "completed": bool(app and _iv_state_prof == "completed"),
        },
        {
            "id": "skills",
            "label": "Skills Verified",
            "completed": bool(get_user_skills(user)),
        },
        {
            "id": "photo",
            "label": "Profile Photo",
            "completed": bool(get_user_avatar_url(user)),
        },
    ]


def calculate_profile_completion(user: User) -> int:
    fields = [
        get_user_name(user),
        get_user_email(user),
        get_user_phone(user),
        get_user_headline(user),
        get_user_bio(user),
        get_user_location(user),
        get_user_linkedin_url(user),
        get_user_github_url(user),
        get_user_portfolio_url(user),
        get_user_avatar_url(user),
        get_user_skills(user),
    ]
    filled = [f for f in fields if f]
    return int((len(filled) / len(fields)) * 100) if fields else 0


def get_upcoming_interviews(db: Session, user: User) -> list:
    user_email = user.email.strip().lower() if user.email else ""
    try:
        interviews = (
            db.query(Interview)
            .join(Application)
            .options(joinedload(Interview.application).joinedload(Application.job))
            .filter(
                or_(
                    Application.user_id == user.id,
                    func.lower(Application.email) == user_email,
                ),
                Interview.status == "scheduled",
            )
            .order_by(Interview.scheduled_time.asc())
            .limit(5)
            .all()
        )
    except Exception as e:
        logger.warning(f"Failed to load upcoming interviews for user {user.id}: {e}")
        return []

    result = []
    for i in interviews:
        try:
            title = (i.type or "Technical").capitalize() + " Interview"
            company = None
            if i.application and i.application.job and i.application.job.company_name:
                company = i.application.job.company_name
            elif (
                i.application
                and i.application.batch_job
                and i.application.batch_job.recruiter
            ):
                company = get_user_company_name(i.application.batch_job.recruiter)
            # Bug B-3: never fall back to a fabricated "AI Assessment"
            # company name. If the company is genuinely unknown, say so.
            company = company or "Company"
            sched = i.scheduled_time
            if sched:
                time_str = sched.strftime("%B %d, %Y - %I:%M %p")
                days_str = (
                    "In "
                    + str((sched - datetime.now(UTC).replace(tzinfo=None)).days)
                    + " days"
                )
            else:
                time_str = "To be scheduled"
                days_str = "TBD"
            logo = "https://ui-avatars.com/api/?name=" + company
            result.append(
                {
                    "id": i.id,
                    "title": title,
                    "company": company,
                    "time": time_str,
                    "days": days_str,
                    "logo": logo,
                }
            )
        except Exception as e:
            logger.warning(f"Failed to serialize upcoming interview: {e}")
            continue
    return result


def get_suggested_jobs(db: Session, declared_role: str) -> list:
    if not declared_role:
        return []

    role_lower = declared_role.lower()
    role_terms = set(role_lower.replace("-", " ").replace("/", " ").split())
    role_terms = {t for t in role_terms if len(t) > 2}

    all_active = (
        db.query(Job)
        .filter(Job.is_active)
        .order_by(Job.created_at.desc())
        .limit(30)
        .all()
    )

    scored = []
    for j in all_active:
        score = 0
        job_title_lower = (j.title or "").lower()
        job_desc_lower = (j.description or "").lower()

        for term in role_terms:
            if term in job_title_lower:
                score += 10
            if term in job_desc_lower:
                score += 3

        if score > 0:
            scored.append((score, j))

    scored.sort(key=lambda x: x[0], reverse=True)
    matched = [j for _, j in scored[:5]]

    if len(matched) < 5:
        seen = {j.id for j in matched}
        for j in all_active:
            if j.id not in seen:
                matched.append(j)
                if len(matched) >= 5:
                    break

    return [
        {
            "id": j.id,
            "title": j.title,
            "company": j.company_name
            or (j.company.name if j.company else "Unknown Company"),
            "location": j.location,
            "match": 95 if j in scored[:5] else 70,
            "logo": getattr(j, "logo_url", None)
            or ("https://ui-avatars.com/api/?name=" + (j.company_name or "C")),
            "salary_range": getattr(j, "salary_range", None),
            "work_type": getattr(j, "work_type", None),
        }
        for j in matched
    ]


def get_all_applications(db: Session, user: User) -> list:
    user_email = user.email.strip().lower() if user.email else ""
    try:
        apps = (
            db.query(Application)
            .options(
                joinedload(Application.job),
                selectinload(Application.cv_document),
            )
            .filter(
                or_(
                    Application.user_id == user.id,
                    func.lower(Application.email) == user_email,
                ),
                or_(
                    Application.job_id.isnot(None),
                    Application.batch_id.isnot(None),
                ),
            )
            .order_by(Application.created_at.desc())
            .limit(10)
            .all()
        )
    except Exception as e:
        logger.warning(f"Failed to load suggested jobs: {e}")
        return []
    result = []
    for a in apps:
        try:
            _cv_a = a.cv_document
            _cv_role_a = getattr(_cv_a, "declared_role", None) or a.declared_role
            if a.job:
                company = (
                    a.job.company_name
                    or (a.job.company.name if a.job.company else None)
                    or "Job Application"
                )
            elif a.batch_id:
                company = "Recruiter Campaign"
            else:
                company = "Direct Upload"
            logo = None
            if a.job:
                logo = getattr(a.job, "logo_url", None)
            if not logo:
                logo = "https://ui-avatars.com/api/?name=" + company
            result.append(
                {
                    "id": a.id,
                    "title": _cv_role_a or "Untitled Role",
                    "company": company,
                    "status": (a.status or "applied").lower().replace(" ", "_"),
                    "created_at": a.created_at.isoformat() if a.created_at else None,
                    "date": a.created_at.strftime("%B %d, %Y")
                    if a.created_at
                    else "N/A",
                    "logo": logo,
                }
            )
        except Exception:
            continue
    return result


def _build_ai_activity_feed(app, current_user) -> list:
    events = []
    now = datetime.now(UTC)
    _cv = app.cv_document if app else None
    _er_af = (
        app.evaluation_sessions[0].evaluation_result
        if app
        and app.evaluation_sessions
        and app.evaluation_sessions[0].evaluation_result
        else None
    )
    _sc = _er_af
    _iv = app.evaluation_sessions[0] if app and app.evaluation_sessions else None
    _a = getattr(_cv, "analysis_json", None) or (app.analysis_json if app else None)
    _sc_score = _sc.final_score if _sc else None
    _iv_state = getattr(_iv, "interview_state", None) or (
        app.interview_state if app else None
    )

    try:
        if app and _a:
            score = _sc_score
            ts = app.updated_at or app.created_at
            events.append(
                {
                    "type": "profile_analyzed",
                    "icon": "fa-brain",
                    "color": "purple",
                    "title": "Profile Analyzed",
                    "text": f"AI completed analysis with {score}/100 score",
                    "description": f"AI completed analysis with {score}/100 score",
                    "timestamp": ts.isoformat() if ts else now.isoformat(),
                }
            )

        if app and _sc_score:
            ts = app.updated_at or app.created_at
            events.append(
                {
                    "type": "score_updated",
                    "icon": "fa-chart-line",
                    "color": "cyan",
                    "title": "AI Score Updated",
                    "text": f"Overall score updated to {_sc_score}/100",
                    "description": f"Overall score updated to {_sc_score}/100",
                    "timestamp": ts.isoformat() if ts else now.isoformat(),
                }
            )

        if app and _iv_state == "completed":
            ts = app.updated_at or app.created_at
            events.append(
                {
                    "type": "interview_feedback",
                    "icon": "fa-comments",
                    "color": "emerald",
                    "title": "Interview Feedback Generated",
                    "text": "AI analyzed your interview performance",
                    "description": "AI analyzed your interview performance",
                    "timestamp": ts.isoformat() if ts else now.isoformat(),
                }
            )
    except Exception:
        pass

    if current_user and getattr(current_user, "profile_views", 0) > 0:
        events.append(
            {
                "type": "profile_viewed",
                "icon": "fa-eye",
                "color": "amber",
                "title": "Recruiters Viewed Profile",
                "text": f"{getattr(current_user, 'profile_views', 0)} recruiters viewed your profile",
                "description": f"{getattr(current_user, 'profile_views', 0)} recruiters viewed your profile",
                "timestamp": now.isoformat(),
            }
        )

    try:
        events.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    except Exception:
        pass
    return events[:10]


def _normalize_skill_dicts(skills):
    """Normalize mixed skill shapes (str / dict / JSON string) to {name, level} dicts."""
    out = []
    for s in skills or []:
        if isinstance(s, str):
            if s.strip():
                out.append({"name": s.strip(), "level": 80})
        elif isinstance(s, dict):
            name = s.get("name") or s.get("skill")
            if name:
                level = s.get("level")
                if level is None and isinstance(s.get("confidence"), (int, float)):
                    level = int(s.get("confidence") * 100)
                out.append(
                    {
                        "name": str(name),
                        "level": int(level) if isinstance(level, (int, float)) else 80,
                    }
                )
    return out


def _resolve_dashboard_skills(current_user, profile):
    """Return (skill_names, skill_metrics) for the dashboard.

    Priority: builder_data.skills -> candidate_profiles.skills column ->
    analysis-derived skills. Always returns normalized string names so the
    dashboard renders cleanly regardless of storage shape.
    """
    profile_skills = []
    if profile is not None and getattr(profile, "builder_data", None):
        try:
            builder = safe_load_json(profile.builder_data) or {}
        except Exception:
            builder = {}
        profile_skills = builder.get("skills") or []
    if not profile_skills and profile is not None and profile.skills:
        try:
            parsed = (
                safe_load_json(profile.skills)
                if isinstance(profile.skills, str)
                else profile.skills
            )
        except Exception:
            parsed = None
        profile_skills = parsed or []
    if not profile_skills and current_user is not None:
        raw = get_user_skills(current_user) or ""
        if raw:
            try:
                parsed = safe_load_json(raw) if isinstance(raw, str) else raw
            except Exception:
                parsed = [s.strip() for s in str(raw).split(",") if s.strip()]
            profile_skills = parsed or []

    normalized = _normalize_skill_dicts(profile_skills)
    names = [s["name"] for s in normalized]
    metrics = {s["name"]: s["level"] for s in normalized}
    return names, metrics


def _resolve_dashboard_achievements(current_user, db, score=0):
    """Return achievements for the dashboard, seeding the catalog on first call.

    Achievements are auto-unlocked based on real profile data:
    - skill-master / polyglot: skill levels from profile skills
    - profile-star: profile completion >= 100
    - first-application / top-candidate: application count / AI score
    """
    from backend.models.achievement import Achievement, seed_achievements_for_user

    try:
        seed_achievements_for_user(current_user.id, db)
    except Exception:
        pass

    profile = (
        db.query(CandidateProfile)
        .filter(CandidateProfile.user_id == current_user.id)
        .first()
    )
    _, skill_metrics = _resolve_dashboard_skills(current_user, profile)
    applications_count = (
        db.query(Application).filter(Application.user_id == current_user.id).count()
    )
    try:
        completion = calculate_profile_completion(current_user)
    except Exception:
        completion = 0

    max_skill = max(skill_metrics.values()) if skill_metrics else 0
    num_skills = len(skill_metrics)

    unlock_rules = {
        "first-application": applications_count > 0,
        "top-candidate": score >= 95,
        "skill-master": max_skill >= 90,
        "polyglot": num_skills >= 5,
        "profile-star": completion >= 100,
    }

    achs = db.query(Achievement).filter(Achievement.user_id == current_user.id).all()
    changed = False
    result = []
    for a in achs or []:
        should_unlock = unlock_rules.get(a.slug, False)
        if should_unlock and not a.unlocked:
            a.unlocked = True
            a.progress_current = a.progress_max
            changed = True
        result.append({"slug": a.slug, "name": a.name, "unlocked": a.unlocked})
    if changed:
        try:
            db.commit()
        except Exception:
            db.rollback()
    return result


def _resolve_dashboard_profile_score(current_user, profile):
    """Resolve dashboard score from builder_data (cv-review score) when no
    Application/EvaluationResult exists. Mirrors profile._resolve_profile_score."""
    if profile is not None and getattr(profile, "builder_data", None):
        try:
            builder = safe_load_json(profile.builder_data) or {}
        except Exception:
            builder = {}
        builder_score = builder.get("score") or builder.get("professional_score")
        if builder_score is not None:
            try:
                return int(float(builder_score)), builder.get("verdict")
            except (ValueError, TypeError):
                pass
        grade_score = builder.get("overall_grade")
        if grade_score:
            mapped = {"A": 90, "B": 80, "C": 70, "D": 60, "F": 50}.get(
                str(grade_score).strip().upper()[0:1], None
            )
            if mapped is not None:
                return mapped, builder.get("verdict")
        skills = builder.get("skills") or []
        if skills:
            levels = []
            for s in skills:
                if isinstance(s, dict) and s.get("level"):
                    levels.append(float(s["level"]))
                elif isinstance(s, dict) and s.get("name"):
                    levels.append(70.0)
            if levels:
                return int(sum(levels) / len(levels)), None
    return 0, None


def _is_candidate_onboarding_completed(current_user: User, db: Session) -> bool:
    """Return True only when the candidate has completed the core onboarding data."""

    profile = (
        db.query(CandidateProfile)
        .filter(CandidateProfile.user_id == current_user.id)
        .first()
    )

    if not profile:
        return False

    has_identity = any(
        bool(getattr(profile, field, None))
        for field in (
            "name",
            "headline",
            "location",
        )
    )

    has_skills = bool(profile.skills)

    has_preferences = any(
        bool(getattr(profile, field, None))
        for field in (
            "work_preference",
            "availability",
            "salary_expectation_min",
            "salary_expectation_max",
            "relocation_willing",
        )
    )

    # CV/application data can also complete the candidate's setup.
    has_cv_or_application = (
        db.query(Application)
        .filter(Application.user_id == current_user.id)
        .first()
        is not None
    )

    return bool(
        (has_identity and has_skills and has_preferences)
        or has_cv_or_application
    )


def _get_my_application_summary_impl(current_user: User, db: Session):
    logger.debug(
        f"Dashboard: User {current_user.id} ({current_user.email}) requesting dashboard"
    )
    user_email = current_user.email.strip().lower() if current_user.email else ""
    app = (
        db.query(Application)
        .options(
            selectinload(Application.cv_document),
            selectinload(Application.evaluation_sessions).selectinload(
                EvaluationSession.evaluation_result
            ),
            undefer(Application.recruiter_notes),
        )
        .filter(
            or_(
                Application.user_id == current_user.id,
                and_(
                    Application.user_id.is_(None),
                    func.lower(Application.email) == user_email,
                ),
            )
        )
        .order_by(Application.created_at.desc())
        .first()
    )

    if not app:
        profile = (
            db.query(CandidateProfile)
            .filter(CandidateProfile.user_id == current_user.id)
            .first()
        )
        _profile_score, _profile_verdict = _resolve_dashboard_profile_score(
            current_user, profile
        )
        skills_list, skill_metrics = _resolve_dashboard_skills(current_user, profile)
        achs = _resolve_dashboard_achievements(current_user, db, score=_profile_score)
        onboarding_completed = _is_candidate_onboarding_completed(
            current_user, db
        )
        return {
            "status": "ok",
            "score": _profile_score,
            "overall_score": _profile_score,
            "verdict": _profile_verdict
            or ("High Potential" if _profile_score >= 70 else "Developing"),
            "analysis": {},
            "skill_metrics": skill_metrics,
            "name": get_user_name(current_user),
            "email": get_user_email(current_user),
            "avatar_url": get_user_avatar_url(current_user),
            "profile_views": getattr(profile, "profile_views", 0) if profile else 0,
            "profile_views_growth": getattr(profile, "profile_views_growth", 12.0)
            if profile
            else 12.0,
            "applications_count": 0,
            "interviews_count": 0,
            "messages_count": 0,
            "saved_jobs_count": 0,
            "profile_completion": 30 if skills_list else 15,
            "onboarding_completed": onboarding_completed,
            "upcoming_interviews": [],
            "suggested_jobs": [],
            "applications": [],
            "checklist": [],
            "achievements": achs,
            "skills": skills_list,
            "declared_role": "General",
        }
    _cv = app.cv_document
    _ev_ses = app.evaluation_sessions[0] if app.evaluation_sessions else None
    _er_ms = (
        _ev_ses.evaluation_result if _ev_ses and _ev_ses.evaluation_result else None
    )
    _sc = _er_ms
    _ev = _ev_ses
    _iv_state = getattr(_ev_ses, "interview_state", None) or app.interview_state
    _iv_log = getattr(_ev_ses, "interview_log", None) or app.interview_log
    from backend.interview_turns import load_turns

    _iv_qa = load_turns(db, app)
    _sc_score = _sc.final_score if _sc else None
    _cv_role = getattr(_cv, "declared_role", None) or app.declared_role
    _cv_analysis = getattr(_cv, "analysis_json", None) or app.analysis_json
    _sc_verdict = ScoringService.get_canonical_verdict(app, db) if db else None
    _ev_reasoning = getattr(_ev_ses, "score_reasoning", None) or getattr(
        app, "score_reasoning", None
    )

    analysis_data = {}
    if _cv_analysis:
        analysis_data = safe_load_json(_cv_analysis)

    try:
        interview_log = normalize_interview_log_for_dashboard(_iv_log, _iv_qa)
    except Exception:
        interview_log = []

    skill_metrics = (
        analysis_data.get("skill_metrics") or analysis_data.get("skills") or {}
    )

    score = _sc_score or 0
    ai_confidence = analysis_data.get(
        "ai_confidence", analysis_data.get("confidence", 0.85)
    )
    if isinstance(ai_confidence, float) and ai_confidence <= 1.0:
        ai_confidence = ai_confidence * 100
    ai_confidence = min(99, max(50, int(ai_confidence)))

    strengths_analysis = analysis_data.get("strengths", [])
    weaknesses_analysis = analysis_data.get("weaknesses", []) or analysis_data.get(
        "gaps", []
    )

    employability_forecast = {
        "current_readiness": score,
        "projected_3_months": min(100, score + 12),
        "projected_6_months": min(100, score + 22),
        "improvement_needed": max(0, 100 - score),
        "estimated_time_to_hire_ready": f"{max(1, int((100 - score) / 8))} months",
    }

    rec_priority = (
        "critical"
        if score < 50
        else "high"
        if score < 70
        else "medium"
        if score < 85
        else "low"
    )

    try:
        talent_graph = _compute_talent_graph_data(analysis_data, skill_metrics)
    except Exception:
        talent_graph = {}

    try:
        career_intel = _compute_career_intelligence(
            analysis_data, app, current_user, db
        )
    except Exception:
        career_intel = {
            "market_score": 75,
            "market_demand": "Moderate",
            "hiring_probability": 50,
            "salary_estimation": {"min": 40000, "max": 75000, "currency": "USD"},
        }

    try:
        ai_activity = _build_ai_activity_feed(app, current_user)
    except Exception:
        ai_activity = []

    try:
        recruiter_name = app.assignee.name if (app.assignee) else "AI Recruitment Team"
        recruiter_role = "Hiring Manager" if app.assignee else "Intelligence System"
        recruiter_avatar = (
            f"https://ui-avatars.com/api/?name={app.assignee.name.replace(' ', '+')}&background=7C3AED&color=fff"
            if app.assignee
            else "https://ui-avatars.com/api/?name=AI&background=7C3AED&color=fff"
        )
    except Exception:
        recruiter_name = "AI Recruitment Team"
        recruiter_role = "Intelligence System"
        recruiter_avatar = (
            "https://ui-avatars.com/api/?name=AI&background=7C3AED&color=fff"
        )

    try:
        created_at_str = (
            app.created_at.isoformat()
            if app.created_at
            else datetime.now(UTC).isoformat()
        )
        last_analyzed_str = (
            app.updated_at.isoformat() if app.updated_at else created_at_str
        )
    except Exception:
        created_at_str = datetime.now(UTC).isoformat()
        last_analyzed_str = created_at_str

    try:
        applications_count = (
            db.query(Application)
            .filter(
                or_(
                    Application.user_id == current_user.id,
                    func.lower(Application.email) == user_email,
                ),
                or_(
                    Application.job_id.isnot(None),
                    Application.batch_id.isnot(None),
                ),
            )
            .count()
        )
    except Exception:
        applications_count = 0

    try:
        interviews_count = (
            db.query(EvaluationSession)
            .join(Application, Application.id == EvaluationSession.application_id)
            .filter(
                or_(
                    Application.user_id == current_user.id,
                    func.lower(Application.email) == user_email,
                )
            )
            .count()
        )
    except Exception:
        interviews_count = 0

    try:
        messages_count = (
            db.query(Message)
            .filter(
                Message.conversation_id.in_(
                    db.query(ConversationParticipant.conversation_id).filter(
                        ConversationParticipant.user_id == current_user.id,
                        ConversationParticipant.left_at.is_(None),
                    )
                ),
                Message.sender_id != current_user.id,
            )
            .count()
        )
    except Exception:
        messages_count = 0

    try:
        saved_jobs_count = (
            db.query(SavedJob).filter(SavedJob.user_id == current_user.id).count()
        )
    except Exception:
        saved_jobs_count = 0

    try:
        profile_completion = calculate_profile_completion(current_user)
    except Exception:
        profile_completion = 0

    try:
        upcoming_interviews = get_upcoming_interviews(db, current_user)
    except Exception:
        upcoming_interviews = []

    try:
        suggested_jobs = get_suggested_jobs(db, _cv_role)
    except Exception:
        suggested_jobs = []

    try:
        applications = get_all_applications(db, current_user)
    except Exception:
        applications = []

    try:
        checklist = get_profile_checklist(current_user, app)
    except Exception:
        checklist = []

    profile_for_skills = (
        db.query(CandidateProfile)
        .filter(CandidateProfile.user_id == current_user.id)
        .first()
    )
    dash_skill_names, dash_skill_metrics = _resolve_dashboard_skills(
        current_user, profile_for_skills
    )
    if not dash_skill_names:
        dash_skill_names = [
            s["name"] for s in _normalize_skill_dicts(analysis_data.get("skills") or [])
        ]
    if not dash_skill_metrics:
        dash_skill_metrics = skill_metrics

    onboarding_completed = _is_candidate_onboarding_completed(
        current_user, db
    )

    return {
        "id": app.id,
        "status": canonicalize_status(app.status),
        # CANDIDATE DASHBOARD SCORE CONTRACT:
        # This is a candidate-level CV/profile score, NOT the final score
        # of the latest job application/interview.
        "score": (
            _sc.cv_score
            if _sc is not None and _sc.cv_score is not None
            else None
        ),
        "overall_score": (
            _sc.cv_score
            if _sc is not None and _sc.cv_score is not None
            else None
        ),
        "verdict": (
            "High Potential"
            if (
                _sc is not None
                and _sc.cv_score is not None
                and _sc.cv_score >= 70
            )
            else "Developing"
        ),
        "fraud_score": _sc.fraud_score if _sc else 0,
        "score_reasoning": _ev_reasoning or getattr(app, "recruiter_notes", None),
        "analysis": analysis_data,
        "skill_metrics": dash_skill_metrics,
        "intelligence": {
            "market_score": career_intel["market_score"],
            "ai_confidence": ai_confidence / 100,
            "market_demand": career_intel["market_demand"],
            "hiring_probability": career_intel["hiring_probability"],
            "employability_forecast": employability_forecast,
            "strengths_analysis": strengths_analysis,
            "weaknesses_analysis": weaknesses_analysis,
            "recommendation_priority": rec_priority,
            "salary_prediction": career_intel["salary_estimation"],
            "top_skill_pct": max(dash_skill_metrics.values())
            if (isinstance(dash_skill_metrics, dict) and len(dash_skill_metrics) > 0)
            else 0,
            "top_role_pct": score,
            "recruiter_name": recruiter_name,
            "recruiter_role": recruiter_role,
            "recruiter_avatar": recruiter_avatar,
        },
        "talent_graph": talent_graph,
        "career_intelligence": career_intel,
        "ai_activity": ai_activity,
        "interview_log": interview_log,
        "interview_state": _iv_state or "not_started",
        "interview_progress": app.interview_progress or 0,
        "email": app.email,
        "declared_role": _cv_role,
        "name": get_user_name(current_user),
        "profile_views": get_user_profile_views(current_user),
        "profile_views_growth": get_user_profile_views_growth(current_user),
        "created_at": created_at_str,
        "last_analyzed": last_analyzed_str,
        "avatar_url": getattr(current_user, "avatar_url", None),
        "applications_count": applications_count,
        "interviews_count": interviews_count,
        "messages_count": messages_count,
        "saved_jobs_count": saved_jobs_count,
        "profile_completion": profile_completion,
        "onboarding_completed": onboarding_completed,
        "upcoming_interviews": upcoming_interviews,
        "suggested_jobs": suggested_jobs,
        "applications": applications,
        "checklist": checklist,
        "achievements": _resolve_dashboard_achievements(current_user, db, score=score),
        "skills": dash_skill_names,
    }


@router.get("/applications/me")
@router.get("/dashboard")
def get_my_application_summary(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    try:
        return _get_my_application_summary_impl(current_user, db)
    except Exception as e:
        logger.error(f"Dashboard error for user {current_user.id}: {e}", exc_info=True)
        return {
            "status": "error",
            "score": 0,
            "overall_score": 0,
            "analysis": {},
            "skill_metrics": {},
            "intelligence": {
                "market_score": 75,
                "ai_confidence": 0.85,
                "market_demand": "Moderate",
                "hiring_probability": 50,
                "employability_forecast": {
                    "current_readiness": 0,
                    "projected_3_months": 12,
                    "projected_6_months": 22,
                    "improvement_needed": 100,
                    "estimated_time_to_hire_ready": "12 months",
                },
                "strengths_analysis": [],
                "weaknesses_analysis": [],
                "recommendation_priority": "critical",
                "salary_prediction": {"min": 40000, "max": 75000, "currency": "USD"},
                "top_skill_pct": 0,
                "top_role_pct": 0,
                "recruiter_name": "AI Recruitment Team",
                "recruiter_role": "Intelligence System",
                "recruiter_avatar": "https://ui-avatars.com/api/?name=AI&background=7C3AED&color=fff",
            },
            "talent_graph": {},
            "career_intelligence": {},
            "ai_activity": [],
            "interview_log": [],
            "interview_state": "not_started",
            "interview_progress": 0,
            "email": get_user_email(current_user),
            "declared_role": "General",
            "name": get_user_name(current_user),
            "profile_views": get_user_profile_views(current_user),
            "profile_views_growth": get_user_profile_views_growth(current_user),
            "created_at": datetime.now(UTC).isoformat(),
            "last_analyzed": datetime.now(UTC).isoformat(),
            "avatar_url": getattr(current_user, "avatar_url", None),
            "applications_count": 0,
            "interviews_count": 0,
            "messages_count": 0,
            "saved_jobs_count": 0,
            "profile_completion": 0,
            "upcoming_interviews": [],
            "suggested_jobs": [],
            "applications": [],
            "checklist": [],
        }


@router.get("/current-application")
def get_current_application(
    type: Optional[str] = None,
    db: Session = Depends(get_db),
    auth: Tuple[Optional[User], Application] = Depends(get_interview_access),
):
    current_user, app = auth

    if not app and current_user:
        query = (
            db.query(Application)
            .options(
                selectinload(Application.cv_document),
                selectinload(Application.evaluation_sessions).selectinload(
                    EvaluationSession.evaluation_result
                ),
            )
            .filter(Application.user_id == current_user.id)
        )
        if type == "audit":
            query = query.filter(
                Application.job_id.is_(None), Application.batch_id.is_(None)
            )
        elif type == "job":
            query = query.filter(
                (Application.job_id.isnot(None)) | (Application.batch_id.isnot(None))
            )
        app = query.order_by(Application.created_at.desc()).first()
    if not app:
        return {"status": "none"}
    _cv_cur = app.cv_document
    _ev_ses = app.evaluation_sessions[0] if app.evaluation_sessions else None
    _er_cur = (
        _ev_ses.evaluation_result if _ev_ses and _ev_ses.evaluation_result else None
    )
    _sc_cur = _er_cur
    _cv_role_cur = getattr(_cv_cur, "declared_role", None) or app.declared_role
    _sc_score_cur = _sc_cur.final_score if _sc_cur else None
    _iv_log_cur = getattr(_ev_ses, "interview_log", None) or app.interview_log
    _iv_state_cur = getattr(_ev_ses, "interview_state", None) or app.interview_state
    _cv_analysis_cur = getattr(_cv_cur, "analysis_json", None) or app.analysis_json
    job_title = _cv_role_cur or "General Assessment"
    company_name = "Pro Dashboard"
    if app.job:
        job_title = app.job.title
        company_name = app.job.company_name
    elif app.batch_job:
        job_title = app.batch_job.target_role or app.batch_job.title
        company_name = (
            get_user_company_name(app.batch_job.recruiter)
            if app.batch_job.recruiter
            else "Partner Employer"
        )

    return {
        "id": app.id,
        "status": canonicalize_status(app.status),
        "score": _sc_score_cur,
        "overall_score": _sc_score_cur,
        "declared_role": _cv_role_cur,
        "job_title": job_title,
        "company_name": company_name,
        "is_audit": app.job_id is None and app.batch_id is None,
        "interview_log": _iv_log_cur,
        "interview_state": _iv_state_cur or "not_started",
        "interview_progress": app.interview_progress or 0,
        "interview_last_saved": app.interview_last_saved.isoformat()
        if app.interview_last_saved
        else None,
        "analysis_json": _cv_analysis_cur,
        "cv_score": _sc_cur.cv_score if _sc_cur else None,
        "created_at": app.created_at.isoformat(),
    }


@router.get("/applications/{app_id}")
def get_application_by_id(
    app_id: int,
    db: Session = Depends(get_db),
    auth: Tuple[Optional[User], Application] = Depends(get_interview_access),
):
    current_user, app = auth

    if not app:
        app = (
            db.query(Application)
            .options(
                selectinload(Application.cv_document),
                selectinload(Application.evaluation_sessions).selectinload(
                    EvaluationSession.evaluation_result
                ),
            )
            .filter(Application.id == app_id)
            .first()
        )
        if not app:
            raise HTTPException(status_code=404, detail="Application not found")

        is_owner = current_user and app.user_id == current_user.id
        is_admin = current_user and current_user.role == "admin"
        recruiter_access = (
            current_user
            and current_user.role == "recruiter"
            and _recruiter_has_application_access(app, current_user)
        )

        if not (is_owner or is_admin or recruiter_access):
            raise HTTPException(status_code=403, detail="Access denied")

    _cv_id = app.cv_document
    _ev_ses_id = app.evaluation_sessions[0] if app.evaluation_sessions else None
    _er_id = (
        _ev_ses_id.evaluation_result
        if _ev_ses_id and _ev_ses_id.evaluation_result
        else None
    )
    _sc_id = _er_id
    _cv_role_id = getattr(_cv_id, "declared_role", None) or app.declared_role
    _sc_score_id = _sc_id.final_score if _sc_id else None
    _iv_log_id = getattr(_ev_ses_id, "interview_log", None) or app.interview_log
    _iv_state_id = getattr(_ev_ses_id, "interview_state", None) or app.interview_state
    _cv_analysis_id = getattr(_cv_id, "analysis_json", None) or app.analysis_json

    if app.invited_at:
        expiry_limit = app.invited_at + timedelta(days=7)
        if (
            datetime.now(UTC).replace(tzinfo=None) > expiry_limit
            and app.status == "invited"
        ):
            raise HTTPException(
                status_code=403,
                detail="This interview invitation has expired (7-day limit).",
            )
    job_title = _cv_role_id or "General Assessment"
    company_name = "Pro Dashboard"
    if app.job:
        job_title = app.job.title
        company_name = app.job.company_name
    elif app.batch_job:
        job_title = app.batch_job.target_role or app.batch_job.title
        if app.batch_job and app.batch_job.recruiter:
            company_name = get_user_company_name(app.batch_job.recruiter)
        else:
            company_name = "Partner Employer"

    eeo = db.query(EEOConsent).filter(EEOConsent.application_id == app.id).first()

    return {
        "id": app.id,
        "status": canonicalize_status(app.status),
        "score": _sc_score_id,
        "overall_score": _sc_score_id,
        "declared_role": _cv_role_id,
        "job_title": job_title,
        "company_name": company_name,
        "is_audit": app.job_id is None and app.batch_id is None,
        "job_id": app.job_id,
        "batch_id": app.batch_id,
        "interview_log": _iv_log_id,
        "interview_state": _iv_state_id or "not_started",
        "interview_progress": app.interview_progress or 0,
        "interview_time_left": app.interview_time_left or 1800,
        "interview_last_saved": app.interview_last_saved.isoformat()
        if app.interview_last_saved
        else None,
        "analysis_json": _cv_analysis_id,
        "cv_score": _sc_id.cv_score if _sc_id else None,
        "email": app.email,
        "created_at": app.created_at.isoformat(),
        "eeo_submitted": eeo is not None,
    }


@router.get("/applications/me/history")
def get_application_history(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    from backend.database import BatchJob

    logger.info(f"[HISTORY] Fetching applications for user {current_user.id}")
    user_email = current_user.email.strip().lower() if current_user.email else ""
    apps = (
        db.query(Application)
        .options(
            joinedload(Application.job),
            joinedload(Application.batch_job).joinedload(BatchJob.recruiter),
            selectinload(Application.cv_document),
            selectinload(Application.evaluation_sessions).selectinload(
                EvaluationSession.evaluation_result
            ),
        )
        .filter(
            or_(
                Application.user_id == current_user.id,
                and_(
                    Application.user_id.is_(None),
                    func.lower(Application.email) == user_email,
                ),
            )
        )
        .order_by(Application.created_at.desc())
        .limit(50)
        .all()
    )
    logger.info(f"[HISTORY] Found {len(apps)} applications")
    results = []
    for app in apps:
        _cv_hist = app.cv_document
        _er_hist = (
            app.evaluation_sessions[0].evaluation_result
            if app.evaluation_sessions and app.evaluation_sessions[0].evaluation_result
            else None
        )
        _sc_hist = _er_hist
        _cv_role_hist = getattr(_cv_hist, "declared_role", None) or app.declared_role
        _sc_score_hist = _sc_hist.final_score if _sc_hist else None
        _cv_analysis_hist = (
            getattr(_cv_hist, "analysis_json", None) or app.analysis_json
        )
        job_title = _cv_role_hist or "General Application"
        company = "Candway AI"
        if app.job:
            job_title = app.job.title or job_title
            company = app.job.company_name or company
        elif app.batch_job:
            job_title = app.batch_job.target_role or app.batch_job.title or job_title
            company = "Campaign Invite"

        analysis = {}
        if _cv_analysis_hist:
            try:
                analysis = json.loads(_cv_analysis_hist)
            except Exception as e:
                logger.error(
                    f"Error parsing analysis JSON for user {current_user.id}: {e}"
                )
                analysis = {"weaknesses": [], "strengths": []}
        weaknesses = analysis.get("weaknesses", [])
        score_reasoning = analysis.get("score_reasoning", "Analysis complete")
        verdict = (
            _sc_hist.verdict
            if _sc_hist and _sc_hist.verdict
            else (_sc_hist.score_breakdown or {}).get("verdict")
            if _sc_hist and _sc_hist.score_breakdown
            else analysis.get("verdict", "Pending Review")
        )

        results.append(
            {
                "id": app.id,
                "status": canonicalize_status(app.status),
                "score": _sc_score_hist or 0,
                "date": app.created_at.isoformat() if app.created_at else "",
                "role": job_title,
                "company": company,
                "verdict": verdict,
                "score_reasoning": score_reasoning,
                "analysis": {"weaknesses": weaknesses},
            }
        )
    logger.info(f"[HISTORY] Returning {len(results)} results")
    return results


@router.get("/applications/{app_id}/pdf")
def download_pdf_report(
    app_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from fastapi.responses import Response

    application = (
        db.query(Application)
        .options(
            selectinload(Application.cv_document),
        )
        .filter(Application.id == app_id)
        .first()
    )
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    if application.user_id != current_user.id and current_user.role != "recruiter":
        raise HTTPException(status_code=403, detail="Not authorized")
    if application.user_id == current_user.id and current_user.role != "recruiter":
        CandidateSubscriptionService.check_pdf_download_limit(current_user, db)
        from backend.credit_service import consume_credits_or_402

        credit_tx_pdf = consume_credits_or_402(
            db,
            current_user,
            1,
            "pdf_report",
            reference_type="application",
            reference_id=app_id,
        )
    _cv_pdf = application.cv_document
    _cv_analysis_pdf = (
        getattr(_cv_pdf, "analysis_json", None) or application.analysis_json
    )
    _cv_role_pdf = getattr(_cv_pdf, "declared_role", None) or application.declared_role
    analysis_data = {}
    if _cv_analysis_pdf:
        try:
            analysis_data = json.loads(_cv_analysis_pdf)
        except Exception as e:
            logger.error(f"Error parsing analysis JSON for app {app_id}: {e}")
    if application.user_id != current_user.id and not _recruiter_has_application_access(
        application, current_user
    ):
        raise HTTPException(status_code=403, detail="Not authorized")
    analysis_data["role"] = _cv_role_pdf or "Technical Interview"
    analysis_data["candidate_name"] = application.full_name
    try:
        pdf_bytes = generate_pdf_report(analysis_data)
    except Exception as e:
        logger.error(f"PDF generation failed for app {app_id}: {e}")
        if application.user_id == current_user.id and current_user.role != "recruiter":
            try:
                from backend.credit_service import rollback_credits

                rollback_credits(db, credit_tx_pdf)
            except Exception:
                pass
        raise HTTPException(
            status_code=500,
            detail="Could not generate the PDF report at this time.",
        )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="report_{app_id}.pdf"'},
    )


@router.get("/applications/{app_id}/audit")
def get_application_audit(
    app_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    app = (
        db.query(Application)
        .options(
            selectinload(Application.cv_document),
            selectinload(Application.evaluation_sessions).selectinload(
                EvaluationSession.evaluation_result
            ),
        )
        .filter(Application.id == app_id, Application.user_id == current_user.id)
        .first()
    )
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    _cv_audit = app.cv_document
    _er_audit = (
        app.evaluation_sessions[0].evaluation_result
        if app.evaluation_sessions and app.evaluation_sessions[0].evaluation_result
        else None
    )
    _sc_audit = _er_audit
    _cv_analysis_audit = getattr(_cv_audit, "analysis_json", None) or app.analysis_json
    _sc_score_audit = _sc_audit.final_score if _sc_audit else None
    analysis = {}
    try:
        if _cv_analysis_audit:
            analysis = json.loads(_cv_analysis_audit)
    except Exception as e:
        logger.error(f"Error parsing analysis for audit: {e}")
    return {
        "overall_score": _sc_score_audit,
        "cv_score": _sc_audit.cv_score if _sc_audit else None,
        "factors": [
            {
                "name": "Skill Match",
                "value": analysis.get("match_score", 0),
                "description": "How well your profile matches the role requirements.",
            },
            {
                "name": "Experience Level",
                "value": 85
                if "Senior" in str(analysis.get("experience_level", ""))
                else 60,
                "description": "Assessment of your years of experience vs expectations.",
            },
            {
                "name": "Interview Performance",
                "value": _sc_score_audit,
                "description": "Real-time evaluation of your technical answers.",
            },
        ],
        "strengths": analysis.get("strengths", []),
        "weaknesses": analysis.get("missing_skills", [])
        or analysis.get("weaknesses", []),
        "reasoning": analysis.get(
            "summary", "Analysis completed by Candway AI Engine."
        ),
    }


@router.post("/applications/{app_id}/withdraw")
def withdraw_application(
    app_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Candidate-initiated withdrawal of a job application.

    Bug H-2: the applications tracker only removed the row from local React
    state — no API call was made, so the backend kept the application active
    and the recruiter never learned the candidate had withdrawn.
    """
    app = (
        db.query(Application)
        .filter(
            Application.id == app_id,
            or_(
                Application.user_id == current_user.id,
                func.lower(Application.email)
                == (get_user_email(current_user) or "").lower(),
            ),
        )
        .first()
    )
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    if app.status == "withdrawn":
        return {"message": "Application already withdrawn", "status": "withdrawn"}

    app.status = "withdrawn"
    db.commit()

    # Best-effort notification to the job's recruiter so the pipeline reflects
    # the withdrawal promptly.
    try:
        from backend.email_service import email_service

        job_title = (
            app.job.title
            if app.job
            else (app.batch_job.title if app.batch_job else "a role")
        )
        recruiter_email = None
        if app.job and app.job.recruiter:
            recruiter_email = app.job.recruiter.email
        elif app.batch_job and app.batch_job.recruiter:
            recruiter_email = app.batch_job.recruiter.email
        if recruiter_email:
            email_service.send_email(
                to_email=recruiter_email,
                subject=f"Application Withdrawn: {job_title}",
                body=(
                    f"<p><strong>{get_user_name(current_user) or 'A candidate'}</strong> has "
                    f"withdrawn their application for <strong>{job_title}</strong>.</p>"
                ),
            )
    except Exception as notify_err:
        logger.warning(f"Withdraw notification failed for app {app_id}: {notify_err}")

    logger.info(f"Application {app_id} withdrawn by candidate {current_user.id}")
    return {
        "message": "Application withdrawn successfully",
        "status": "withdrawn",
        "application_id": app.id,
    }
