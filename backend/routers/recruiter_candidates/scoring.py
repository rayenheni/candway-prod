import hashlib
import json
import re
from datetime import UTC, datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload, undefer

from backend.ai import generate_score_comparison
from backend.authz import (
    get_application_for_recruiter,
    get_batch_for_recruiter,
    get_job_for_recruiter,
)
from backend.database import (
    Application,
    BatchJob,
    CompanyMember,
    EvaluationResult,
    EvaluationSession,
    Job,
    RubricScoringDetail,
    User,
)
from backend.dependencies import get_db, require_recruiter
from backend.entity_writer import sync_cv_document
from backend.logger import logger
from backend.profile_helpers import (
    get_user_company_name,
    get_user_email,
    get_user_name,
    get_user_tier,
)
from backend.repository.metrics_repository import MetricsRepository
from backend.scoring_engine import ScoringEngine
from backend.scoring_service import ScoringService
from backend.services.feature_service import has_feature
from backend.subscription_service import SubscriptionService

router = APIRouter(tags=["Recruiter Candidates"])


class BulkIdRequest(BaseModel):
    app_ids: List[int]


class CompareRequest(BaseModel):
    job_id: Optional[int] = None
    batch_id: Optional[int] = None
    ids: List[int]


def extract_interview_highlights(
    interview_log: str, max_count: int = 3, app_score: int = 0
) -> List[dict]:
    """
    Extract meaningful Q&A pairs from interview log with quality scoring.

    Args:
        interview_log: JSON string of interview conversation
        max_count: Maximum number of highlights to extract
        app_score: Application score for context

    Returns:
        List of highlight dictionaries with question, answer, feedback
    """
    highlights = []

    if not interview_log:
        return highlights

    try:
        if isinstance(interview_log, str):
            log_data = json.loads(interview_log)
        else:
            log_data = interview_log

        if not isinstance(log_data, list) or not log_data:
            return highlights

        # Extract Q&A pairs with quality scoring
        qa_pairs = []

        for i in range(len(log_data) - 1):
            msg = log_data[i]
            response = log_data[i + 1]

            # Check for valid Q&A pattern: AI Question (assistant) -> Candidate Answer (user/human)
            if not (
                msg.get("role") in ["assistant", "ai"]
                and response.get("role") in ["user", "human"]
            ):
                continue

            q_text = (msg.get("content") or "").strip()
            a_text = (response.get("content") or "").strip()

            # Skip empty exchanges
            if not q_text or not a_text:
                continue

            # Calculate quality score
            quality = (
                min(len(q_text) / 50, 2.0)  # Longer questions (max +2)
                + min(len(a_text) / 200, 3.0)  # Longer answers (max +3)
            )

            # Bonus for technical keywords
            tech_keywords = [
                "algorithm",
                "database",
                "API",
                "architecture",
                "optimization",
                "design",
                "system",
                "code",
            ]
            for keyword in tech_keywords:
                if (
                    keyword.lower() in q_text.lower()
                    or keyword.lower() in a_text.lower()
                ):
                    quality += 1.0
                    break  # Only count once per pair

            qa_pairs.append({"q": q_text, "a": a_text, "quality": quality})

        # Sort by quality and take top N
        qa_pairs.sort(key=lambda x: x["quality"], reverse=True)

        for qa in qa_pairs[:max_count]:
            # Intelligent truncation
            def truncate_smart(text, max_len=150):
                if len(text) <= max_len:
                    return text
                truncated = text[:max_len]
                last_space = truncated.rfind(" ")
                if last_space > max_len * 0.7:
                    return truncated[:last_space] + "..."
                return truncated + "..."

            # Context-aware feedback
            if app_score > 75:
                feedback = "Response demonstrates strong technical depth and clear communication"
            elif app_score > 60:
                feedback = "Solid understanding with good practical application"
            else:
                feedback = "Shows foundational knowledge with room for improvement"

            highlights.append(
                {
                    "question": truncate_smart(qa["q"], 150),
                    "answer": truncate_smart(qa["a"], 200),
                    "feedback": feedback,
                }
            )

        return highlights

    except Exception as err:
        logger.warning(f"Error extracting interview highlights: {err}")
        return []


def _parse_competencies(app: Application, db: Session) -> dict:
    """Parse structured Q&A for competency scores"""
    competencies = {}
    try:
        from backend.interview_turns import load_turns

        qa_data = load_turns(db, app)
        if isinstance(qa_data, list):
            scores = [q.get("score", 0) for q in qa_data if isinstance(q, dict)]
            if scores:
                avg = sum(scores) / len(scores)
                competencies = {
                    "technical": min(100, int(avg + (10 if avg > 50 else 0))),
                    "communication": min(100, int(avg + (5 if avg > 50 else -5))),
                    "problem_solving": min(100, int(avg + (8 if avg > 50 else -2))),
                    "adaptability": min(100, int(avg + (3 if avg > 50 else -3))),
                    "confidence": min(100, int(avg + (15 if avg > 50 else -10))),
                }
    except Exception as e:
        logger.error(f"Error parsing competencies for app {app.id}: {e}")
    return competencies


def _build_application_data_for_scoring(
    app: Application, db: Session, is_pro: bool
) -> dict:
    """Build application data dict for scoring engine"""
    _cv_scoring = app.cv_document
    _iv_scoring = app.evaluation_sessions[0] if app.evaluation_sessions else None
    _sc_sessions_scoring = app.evaluation_sessions or []
    _sc_scoring = (
        _sc_sessions_scoring[0].evaluation_result
        if _sc_sessions_scoring and _sc_sessions_scoring[0].evaluation_result
        else None
    )
    _sc_cv_scoring = _sc_scoring.cv_score if _sc_scoring else None
    _sc_final_scoring = _sc_scoring.final_score if _sc_scoring else None
    _cv_role_scoring = getattr(_cv_scoring, "declared_role", None) or getattr(
        app, "declared_role", None
    )
    _iv_questions_scoring = getattr(
        _iv_scoring, "interview_questions", None
    ) or getattr(app, "interview_questions", None)
    _cv_analysis_scoring = getattr(_cv_scoring, "analysis_json", None) or getattr(
        app, "analysis_json", None
    )

    # Parse analysis
    analysis = {}
    strengths = []
    weaknesses = []
    skills_list = []
    skill_metrics = {}
    experience_years = 0
    location = "Not specified"

    if _cv_analysis_scoring:
        try:
            analysis = (
                _cv_analysis_scoring
                if isinstance(_cv_analysis_scoring, dict)
                else (json.loads(_cv_analysis_scoring) if _cv_analysis_scoring else {})
            )
            strengths = analysis.get("strengths", [])
            weaknesses = analysis.get("weaknesses", []) or analysis.get(
                "areas_for_improvement", []
            )

            skill_metrics = analysis.get("skill_metrics", {})
            if skill_metrics:
                skills_list = list(skill_metrics.keys())
            elif analysis.get("skills"):
                skills_list = analysis.get("skills", [])

            experience_years = analysis.get("experience_years", 0) or 0
            location = (
                analysis.get("location", "Not specified")
                or analysis.get("city", "Not specified")
                or "Not specified"
            )
        except Exception as e:
            logger.error(f"Error parsing analysis for app {app.id}: {e}")

    # Get competencies
    competencies = _parse_competencies(app, db)

    # Get user for name
    user = (
        db.query(User).filter(User.id == app.user_id).first() if app.user_id else None
    )

    real_name = app.full_name or (get_user_name(user) if user else "Unknown")

    # Strip common AI-generated prefixes
    if real_name.startswith("Name: "):
        real_name = real_name.replace("Name: ", "", 1)

    full_name = real_name
    if not is_pro:
        # Mask name for non-pro recruiters
        parts = real_name.split()
        if parts:
            full_name = f"{parts[0][0]}. Candidate"
        else:
            full_name = "Candidate"

    # Build owner info
    owner = None
    if user:
        owner = {"name": get_user_name(user), "email": get_user_email(user)}

    # Determine role
    role = _cv_role_scoring
    if not role or role.lower() == "candidate":
        if app.job_id:
            role = db.query(Job.title).filter(Job.id == app.job_id).scalar()
        elif app.batch_id:
            role = db.query(BatchJob.title).filter(BatchJob.id == app.batch_id).scalar()

    if not role:
        # Try to extract from analysis if still empty
        role = analysis.get("role")

    if not role or role.lower() == "candidate":
        role = "Not specified"

    # Get interview questions count
    total_questions = 15
    if _iv_questions_scoring:
        try:
            questions_data = json.loads(_iv_questions_scoring)
            if isinstance(questions_data, list):
                total_questions = len(questions_data)
        except (json.JSONDecodeError, TypeError, ValueError):
            pass

    return {
        "id": app.id,
        "name": full_name,
        "full_name": full_name,
        "email": app.email if is_pro else "hidden@candway.com",
        "role": role or "Candidate",
        "cv_score": _sc_cv_scoring or 0,
        "overall_score": _sc_final_scoring or 0,
        "status": app.status,
        "skills": skills_list[:10],
        "skill_metrics": skill_metrics,
        "strengths": strengths[:5],
        "weaknesses": weaknesses[:5],
        "experience_years": experience_years,
        "location": location,
        "summary": analysis.get("summary", "No analysis available"),
        "created_at": app.created_at.strftime("%Y-%m-%d") if app.created_at else None,
        "proctoring_violations": getattr(_iv_scoring, "proctoring_violations", None),
        "interview_progress": app.interview_progress or 0,
        "interview_total": total_questions,
        "interview_questions": _iv_questions_scoring,
        "competencies": competencies,
        "job_id": app.job_id,
        "batch_id": app.batch_id,
        "owner": owner,
    }


def _build_legacy_response(candidates: list, is_pro: bool) -> dict:
    """Build legacy response format for backward compatibility"""

    legacy_candidates = []
    for c in candidates:
        legacy_candidates.append(
            {
                "id": c.get("id"),
                "name": c.get("name"),
                "role": c.get("role"),
                "cv_score": c.get("cv_score"),
                "interview_score": c.get("interview_score"),
                "overall_score": c.get("final_score"),
                "skills": c.get("skills", []),
                "experience_years": c.get("experience_years", 0),
                "location": c.get("location", "Not specified"),
                "created_at": c.get("created_at"),
                "status": c.get("status"),
                "trust_score": c.get("trust_score", 100),
            }
        )

    return {"candidates": legacy_candidates}


def _get_all_candidate_interviews_impl(
    app_id: int, recruiter: User, db: Session
) -> dict:
    app = get_application_for_recruiter(app_id, recruiter, db)
    _cv_impl = app.cv_document
    _iv_impl = app.evaluation_sessions[0] if app.evaluation_sessions else None
    _es_list_impl = app.evaluation_sessions or []
    _sc_impl = (
        _es_list_impl[0].evaluation_result
        if _es_list_impl and _es_list_impl[0].evaluation_result
        else None
    )
    _sc_score_impl = _sc_impl.final_score if _sc_impl else None
    _cv_role_impl = getattr(_cv_impl, "declared_role", None) or getattr(
        app, "declared_role", None
    )
    _iv_log_impl = getattr(_iv_impl, "interview_log", None) or getattr(
        app, "interview_log", None
    )
    _cv_analysis_impl = getattr(_cv_impl, "analysis_json", None) or getattr(
        app, "analysis_json", None
    )

    is_pro = (
        get_user_tier(recruiter) in ("pro", "pro_plus", "enterprise")
        or recruiter.role == "admin"
    )
    real_name = app.full_name or "Unknown"
    candidate_name = (
        real_name
        if is_pro
        else (
            real_name.split()[0][0] + ". Candidate"
            if real_name.split()
            else "Candidate"
        )
    )

    if not app.user_id:
        return {"interviews": [], "candidate_name": candidate_name}

    # Get all job/batch IDs belonging to this recruiter's company
    company_id = getattr(recruiter, "_company_id", None)
    recruiter_job_ids = [
        j.id
        for j in db.query(Job.id)
        .join(CompanyMember, CompanyMember.user_id == Job.recruiter_id)
        .filter(CompanyMember.company_id == company_id, CompanyMember.is_active)
        .all()
    ]
    recruiter_batch_ids = [
        b.id
        for b in db.query(BatchJob.id)
        .join(CompanyMember, CompanyMember.user_id == BatchJob.recruiter_id)
        .filter(CompanyMember.company_id == company_id, CompanyMember.is_active)
        .all()
    ]

    # Build filter conditions dynamically
    conditions = [
        Application.user_id == app.user_id,
        Application.company_id == app.company_id,
    ]
    or_conditions = []
    if recruiter_job_ids:
        or_conditions.append(Application.job_id.in_(recruiter_job_ids))
    if recruiter_batch_ids:
        or_conditions.append(Application.batch_id.in_(recruiter_batch_ids))
    if or_conditions:
        conditions.append(or_(*or_conditions))

    all_apps = (
        db.query(Application)
        .options(
            selectinload(Application.cv_document),
            selectinload(Application.evaluation_sessions)
            .selectinload(EvaluationSession.evaluation_result)
            .selectinload(EvaluationResult.rubric_scoring_details),
            selectinload(Application.job).selectinload(Job.recruiter),
            selectinload(Application.batch_job).selectinload(BatchJob.recruiter),
        )
        .filter(*conditions)
        .order_by(Application.created_at.desc())
        .all()
    )

    interviews = []
    for a in all_apps:
        _a_cv = a.cv_document
        _a_iv = a.evaluation_sessions[0] if a.evaluation_sessions else None
        _as_list = a.evaluation_sessions or []
        _a_sc = (
            _as_list[0].evaluation_result
            if _as_list and _as_list[0].evaluation_result
            else None
        )
        _a_role = getattr(_a_cv, "declared_role", None) or getattr(
            a, "declared_role", None
        )
        _a_sc_score = _a_sc.final_score if _a_sc else None
        _a_analysis = getattr(_a_cv, "analysis_json", None) or getattr(
            a, "analysis_json", None
        )
        _a_log = getattr(_a_iv, "interview_log", None) or getattr(
            a, "interview_log", None
        )
        from backend.interview_turns import load_turns

        _a_qa = load_turns(db, a)
        _a_sc_cv = _a_sc.cv_score if _a_sc else None
        rubric_summary = _a_sc
        breakdown_data = {}
        if rubric_summary:
            bd = rubric_summary.score_breakdown or {}
            if isinstance(bd, str):
                bd = json.loads(bd) if bd else {}
            breakdown_data = bd if isinstance(bd, dict) else {}
        rubric_gaps = list(breakdown_data.get("gaps", [])) if breakdown_data else []
        rubric_categories = (
            list(breakdown_data.get("category_scores", [])) if breakdown_data else []
        )
        rubric_skill_scores = (
            breakdown_data.get("skill_scores", {}) if breakdown_data else {}
        )
        # Apply recruiter score overrides
        skill_overrides = (
            breakdown_data.get("overrides", {})
            if isinstance(breakdown_data, dict)
            else {}
        )
        if skill_overrides and isinstance(skill_overrides, dict):
            for skill_name, override in skill_overrides.items():
                if skill_name in rubric_skill_scores:
                    rubric_skill_scores[skill_name]["final_score"] = override[
                        "new_score"
                    ]
                    rubric_skill_scores[skill_name]["overridden"] = True
                else:
                    rubric_skill_scores[skill_name] = {
                        "final_score": override["new_score"],
                        "is_required": False,
                        "overridden": True,
                    }
        rubric_evidence = []
        rubric_evidence_rows = (
            rubric_summary.rubric_scoring_details if rubric_summary else []
        )
        for idx, row in enumerate(rubric_evidence_rows, 1):
            override = skill_overrides.get(row.criterion_name)
            evidence_score = override["new_score"] if override else row.score
            rubric_evidence.append(
                {
                    "skill_name": row.criterion_name,
                    "turn_number": idx,
                    "matched_keywords": [],
                    "missing_competencies": [],
                    "explanation": row.feedback,
                    "final_score": evidence_score,
                    "overridden": bool(override),
                }
            )
        # Get role/title
        role = _a_role
        if not role:
            if a.job_id:
                role = db.query(Job.title).filter(Job.id == a.job_id).scalar()
            elif a.batch_id:
                role = (
                    db.query(BatchJob.title).filter(BatchJob.id == a.batch_id).scalar()
                )

        # Parse analysis
        analysis = {}
        if _a_analysis:
            try:
                analysis = (
                    _a_analysis
                    if isinstance(_a_analysis, dict)
                    else (json.loads(_a_analysis) if _a_analysis else {})
                )
            except (json.JSONDecodeError, TypeError, ValueError):
                pass

        # Parse interview log for question data
        questions_data = []
        score_timeline = []
        try:
            if _a_log:
                log_data = json.loads(_a_log) if isinstance(_a_log, str) else _a_log
                if isinstance(log_data, list):
                    q_num = 0
                    prev_timestamp = 0
                    for item in log_data:
                        if isinstance(item, dict) and item.get("role") in (
                            "assistant",
                            "ai",
                        ):
                            q_num += 1
                            score = item.get("score", 0)
                            q_timestamp = item.get("timestamp", 0)
                            response_time = 0
                            if prev_timestamp and q_timestamp:
                                response_time = round(q_timestamp - prev_timestamp, 1)
                            questions_data.append(
                                {
                                    "number": q_num,
                                    "question": (item.get("content") or "")[:200],
                                    "answer": "",
                                    "score": score,
                                    "feedback": item.get("feedback", ""),
                                    "reasoning": item.get("reasoning", ""),
                                    "type": item.get("type", "general"),
                                    "difficulty": item.get("difficulty", "medium"),
                                    "status": "answered" if score > 0 else "pending",
                                    "response_time": response_time,
                                    "question_timestamp": q_timestamp,
                                    "answer_timestamp": "",
                                }
                            )
                            score_timeline.append({"q": f"Q{q_num}", "score": score})
                            prev_timestamp = q_timestamp
                        elif (
                            isinstance(item, dict)
                            and item.get("role") in ("user", "human")
                            and questions_data
                        ):
                            questions_data[-1]["answer"] = (item.get("content") or "")[
                                :300
                            ]
                            questions_data[-1]["answer_timestamp"] = item.get(
                                "timestamp", ""
                            )
                            if questions_data[-1].get(
                                "question_timestamp"
                            ) and item.get("timestamp"):
                                rt = round(
                                    item.get("timestamp", 0)
                                    - questions_data[-1].get("question_timestamp", 0),
                                    1,
                                )
                                if rt > 0:
                                    questions_data[-1]["response_time"] = rt
        except (json.JSONDecodeError, TypeError, ValueError):
            pass

        # Parse structured Q&A if available
        if not questions_data and _a_qa:
            try:
                qa_data = json.loads(_a_qa) if isinstance(_a_qa, str) else _a_qa
                if isinstance(qa_data, list):
                    for i, q in enumerate(qa_data):
                        if isinstance(q, dict):
                            score = q.get("score", 0)
                            questions_data.append(
                                {
                                    "number": i + 1,
                                    "question": (q.get("question") or "")[:200],
                                    "answer": (q.get("answer") or "")[:300],
                                    "score": score,
                                    "feedback": q.get("feedback", ""),
                                    "reasoning": q.get("reasoning", ""),
                                    "type": q.get("type", "general"),
                                    "difficulty": q.get("difficulty", "medium"),
                                    "status": "answered" if score > 0 else "pending",
                                    "response_time": q.get("response_time_seconds", 0),
                                    "question_timestamp": q.get(
                                        "question_timestamp", 0
                                    ),
                                    "answer_timestamp": q.get("answer_timestamp", ""),
                                }
                            )
                            score_timeline.append({"q": f"Q{i + 1}", "score": score})
            except (json.JSONDecodeError, TypeError, ValueError):
                pass

        # Determine interview state (entity first, then fallback)
        interview_state = "pending"
        entity_state = getattr(_a_iv, "interview_state", None)
        if entity_state:
            interview_state = entity_state
        else:
            app_status = a.status or "applied"
            _has_log = bool(_a_log) and _a_log != "[]"
            if app_status in ("completed", "hired", "offer"):
                interview_state = "completed"
            elif app_status in ("interviewing", "screening"):
                interview_state = "completed" if _has_log else "in-progress"
            elif app_status == "rejected":
                interview_state = "completed"
            elif (_a_sc_score or 0) > 0 and _a_analysis:
                interview_state = "completed"
            elif _has_log:
                interview_state = "in-progress"

        # Calculate duration
        duration = "--"
        if _a_log:
            try:
                log_data = json.loads(_a_log) if isinstance(_a_log, str) else _a_log
                if isinstance(log_data, list) and len(log_data) > 1:
                    first_ts = log_data[0].get("timestamp", 0)
                    last_ts = log_data[-1].get("timestamp", 0)
                    if first_ts and last_ts:
                        mins = int((last_ts - first_ts) / 60)
                        duration = f"{mins} min"
            except (json.JSONDecodeError, TypeError, ValueError):
                pass

        # Performance overview — rubric-driven when rubric exists
        is_rubric_driven = bool(rubric_categories)
        performance_overview = []
        if is_rubric_driven:
            for cat in rubric_categories:
                if isinstance(cat, dict):
                    cname = cat.get("name") or ""
                    cscore = cat.get("score") or 0
                    cscore_rounded = round(float(cscore))
                    label = (
                        "Excellent"
                        if cscore_rounded >= 80
                        else "Good"
                        if cscore_rounded >= 60
                        else "Fair"
                    )
                    performance_overview.append(
                        {
                            "label": str(cname)[:60],
                            "score": cscore_rounded,
                            "label_score": label,
                        }
                    )
        else:
            try:
                if _a_qa:
                    qa_data = json.loads(_a_qa) if isinstance(_a_qa, str) else _a_qa
                    if isinstance(qa_data, list):
                        scores = [
                            q.get("score", 0) for q in qa_data if isinstance(q, dict)
                        ]
                        if scores:
                            avg = sum(scores) / len(scores)
                            fabricated = {
                                "Technical": min(100, avg + 10),
                                "Communication": min(100, avg + 5),
                                "Problem Solving": min(100, avg + 8),
                                "Adaptability": min(100, avg + 3),
                                "Confidence": min(100, avg + 15),
                            }
                            for flabel, fscore in fabricated.items():
                                label = (
                                    "Excellent"
                                    if fscore >= 80
                                    else "Good"
                                    if fscore >= 60
                                    else "Fair"
                                )
                                performance_overview.append(
                                    {
                                        "label": flabel,
                                        "score": round(fscore),
                                        "label_score": label,
                                    }
                                )
            except (json.JSONDecodeError, TypeError, ValueError):
                pass

        # Highlights
        highlights = {}
        if questions_data:
            answered = [q for q in questions_data if q["score"] > 0]
            if answered:
                best = max(answered, key=lambda x: x["score"])
                worst = min(answered, key=lambda x: x["score"])
                highlights = {
                    "best_moment": {
                        "question": best["question"][:100],
                        "topic": best.get("type", "general"),
                        "score": best["score"],
                    },
                    "worst_moment": {
                        "question": worst["question"][:100],
                        "topic": worst.get("type", "general"),
                        "score": worst["score"],
                    },
                }

        score = _a_sc_score or 0
        score_label = (
            "Exceptional"
            if score >= 85
            else "Strong"
            if score >= 70
            else "Competent"
            if score >= 55
            else "Developing"
            if score >= 40
            else "Needs Improvement"
        )

        # Include score breakdown if available
        score_breakdown = analysis.get("final_score_breakdown")
        hiring_recommendation = analysis.get(
            "hiring_recommendation", analysis.get("verdict", "Pending")
        )

        interviews.append(
            {
                "id": a.id,
                "role": role or "Candidate",
                "company": (
                    get_user_company_name(a.job.recruiter)
                    if a.job and a.job.recruiter
                    else (
                        get_user_company_name(a.batch_job.recruiter)
                        if a.batch_job and a.batch_job.recruiter
                        else "Company"
                    )
                ),
                "date": a.created_at.strftime("%Y-%m-%d") if a.created_at else None,
                "score": round(score),
                "score_label": score_label,
                "score_breakdown": score_breakdown,
                "hiring_recommendation": hiring_recommendation,
                "verdict": analysis.get("recommendation", hiring_recommendation),
                "interview_type": "AI Interview",
                "duration": duration,
                "reasoning": analysis.get("summary", ""),
                "strengths": analysis.get("strengths", [])[:5],
                "weaknesses": analysis.get("concerns", analysis.get("risks", []))[:5],
                "performance_overview": performance_overview,
                "questions": questions_data[:20],
                "score_timeline": score_timeline,
                "highlights": highlights,
                "interview_details": {
                    "interview_id": f"INT-{a.id}",
                    "started_at": a.created_at.strftime("%Y-%m-%d %H:%M")
                    if a.created_at
                    else None,
                    "submitted_at": a.evaluation_completed_at.strftime("%Y-%m-%d %H:%M")
                    if a.evaluation_completed_at
                    else None,
                    "total_questions": len(questions_data),
                    "responses": len([q for q in questions_data if q["score"] > 0]),
                    "status": a.status,
                },
                "is_expired": a.status == "rejected",
                "days_remaining": 0,
                "interview_state": interview_state,
                "status": a.status,
                "is_current": a.id == app_id,
                "advanced_scoring": analysis.get("advanced_scoring"),
                "scoring_model": (_a_sc.scoring_model or "legacy")
                if _a_sc
                else "legacy",
                "is_rubric_driven": is_rubric_driven,
                "rubric_version": (
                    _a_sc.rubric_version
                    if _a_sc and _a_sc.rubric_version
                    else (rubric_summary.rubric_version if rubric_summary else 0)
                ),
                "rubric_seniority": getattr(_a_sc, "rubric_seniority", None) or "mid",
                "rubric_gaps": rubric_gaps,
                "rubric_categories": rubric_categories,
                "rubric_skill_scores": rubric_skill_scores,
                "evidence": rubric_evidence,
            }
        )

    return {
        "interviews": interviews,
        "candidate_name": candidate_name,
        "total_interviews": len(interviews),
    }


@router.get("/applications/{app_id}/logs")
def get_candidate_logs(
    app_id: int,
    request: Request,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    """
    Get the chat transcript (interrogation log) for a candidate application.
    """
    app = get_application_for_recruiter(app_id, recruiter, db)
    _iv_logs = app.evaluation_sessions[0] if app.evaluation_sessions else None
    _iv_log_val = getattr(_iv_logs, "interview_log", None) or getattr(
        app, "interview_log", None
    )

    if not _iv_log_val:
        return []
    try:
        log_data = json.loads(_iv_log_val)
        is_pro = (
            get_user_tier(recruiter) in ("pro", "pro_plus", "enterprise")
            or recruiter.role == "admin"
        )
        if not is_pro:
            if isinstance(log_data, list):
                for entry in log_data:
                    if isinstance(entry, dict):
                        for key in (
                            "name",
                            "candidate_name",
                            "full_name",
                            "email",
                            "phone",
                        ):
                            entry.pop(key, None)
            elif isinstance(log_data, dict):
                for key in ("name", "candidate_name", "full_name", "email", "phone"):
                    log_data.pop(key, None)
        return log_data
    except Exception as e:
        logger.error(f"Failed to parse interview log for app {app_id}: {e}")
        return []


@router.get("/applications/{app_id}/score-comparison")
async def get_score_comparison(
    app_id: int,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    """Compare candidate's CV score with interview score."""

    app = get_application_for_recruiter(app_id, recruiter, db)

    is_pro = (
        get_user_tier(recruiter) in ("pro", "pro_plus", "enterprise")
        or recruiter.role == "admin"
    )
    real_name_score = app.full_name or "Unknown"
    candidate_name_score = (
        real_name_score
        if is_pro
        else (
            real_name_score.split()[0][0] + ". Candidate"
            if real_name_score.split()
            else "Candidate"
        )
    )

    _cv_comp = app.cv_document
    _iv_comp = app.evaluation_sessions[0] if app.evaluation_sessions else None
    _es_comp = app.evaluation_sessions or []
    _sc_comp = (
        _es_comp[0].evaluation_result
        if _es_comp and _es_comp[0].evaluation_result
        else None
    )
    _sc_cv = _sc_comp.cv_score if _sc_comp else None
    _sc_score_comp = _sc_comp.final_score if _sc_comp else None
    _cv_text_comp = getattr(_cv_comp, "cv_text_anonymized", None) or getattr(
        app, "cv_text_anonymized", None
    )
    _cv_role_comp = getattr(_cv_comp, "declared_role", None) or getattr(
        app, "declared_role", None
    )
    _iv_log_comp = getattr(_iv_comp, "interview_log", None) or getattr(
        app, "interview_log", None
    )
    from backend.interview_turns import load_turns

    _iv_qa_comp = load_turns(db, app)
    _iv_questions_comp = getattr(_iv_comp, "interview_questions", None) or getattr(
        app, "interview_questions", None
    )
    _cv_analysis_comp = getattr(_cv_comp, "analysis_json", None) or getattr(
        app, "analysis_json", None
    )

    # Get anonymized CV text
    cv_text = _cv_text_comp or ""

    # ✅ IMPROVED: Handle different interview states
    if not _iv_log_comp or _iv_log_comp.strip() == "[]":
        # Interview not started or empty
        return {
            "state": "pending_interview",
            "candidate_name": candidate_name_score,
            "cv_score": _sc_cv or 0,
            "interview_score": None,
            "final_verdict": "Awaiting interview completion",
            "analysis_summary": (
                "The candidate's CV has been analyzed and scored. "
                "A detailed comparison will be available once they complete the AI interview. "
                "The comparison will highlight strengths, identify gaps, and provide a hiring recommendation."
            ),
            "key_deltas": [],
        }

    # Parse interview log
    try:
        interview_data = json.loads(_iv_log_comp)
        if not isinstance(interview_data, list):
            raise ValueError("Interview log is not a list")
        if not interview_data:
            raise ValueError("Interview log is empty")
    except (json.JSONDecodeError, ValueError) as parse_err:
        logger.error(f"Interview log parse error for app {app_id}: {parse_err}")
        return {
            "state": "error",
            "candidate_name": candidate_name_score,
            "cv_score": _sc_cv or 0,
            "interview_score": _sc_score_comp or 0,
            "final_verdict": "Unable to generate comparison due to data issue",
            "analysis_summary": (
                "There was an issue reading the candidate's interview data. "
                "Please contact support if this persists."
            ),
            "key_deltas": [],
        }

    # Calculate interview progress early for consistent use
    target_total_questions = 15  # Default for AI interviews
    completed_questions = 0
    try:
        # 1. Determine Total Target
        if _iv_questions_comp:
            questions_data = json.loads(_iv_questions_comp)
            if isinstance(questions_data, list) and len(questions_data) > 0:
                # If it's a fixed question bank (QCM), use its length
                if "options" in str(questions_data[0]):
                    target_total_questions = len(questions_data)

        # 2. Determine Completed Questions from structured data
        if _iv_qa_comp and isinstance(_iv_qa_comp, list):
            completed_questions = sum(1 for q in _iv_qa_comp if q.get("answer"))

        # 3. Fallback for completed count if structured data is empty (parse log)
        if completed_questions == 0 and _iv_log_comp:
            log_data = json.loads(_iv_log_comp)
            if isinstance(log_data, list):
                completed_questions = len(
                    [m for m in log_data if m.get("role") == "user"]
                )
    except (json.JSONDecodeError, TypeError, ValueError):
        pass

    # Ensure target_total_questions is at least as much as completed
    target_total_questions = max(target_total_questions, completed_questions)

    # Calculate linguistic analysis for prompt context
    linguistic_analysis = {}
    try:
        if _iv_qa_comp and isinstance(_iv_qa_comp, list) and len(_iv_qa_comp) > 0:
            response_lengths = [len(str(q.get("answer", ""))) for q in _iv_qa_comp]
            avg_len = (
                sum(response_lengths) / len(response_lengths) if response_lengths else 0
            )
            scores = [q.get("score", 0) for q in _iv_qa_comp if q.get("answer")]
            avg_score = sum(scores) / len(scores) if scores else 0

            clarity = (completed_questions / max(1, target_total_questions) * 5) + (
                avg_score / 10 * 5
            )

            linguistic_analysis = {
                "total_questions": target_total_questions,
                "answered_questions": completed_questions,
                "avg_response_length": round(avg_len, 1),
                "response_latency": 2.5,
                "structural_clarity": round(min(10, clarity), 1),
            }
    except Exception as e:
        logger.error(f"Error calculating linguistic analysis for comparison: {e}")

    # ==================== COST SAVING LAYER (TOKEN OPTIMIZATION) ====================
    try:
        # 1. BYPASS: If interview is in early stages (< 5 questions), avoid expensive AI audit
        if completed_questions < 5:
            logger.info(
                f"Bypassing AI audit for app {app_id} (only {completed_questions} questions) to save tokens."
            )
            comparison = {
                "analysis_summary": f"Initial interview phase. Intelligence Engine has analyzed {completed_questions} early responses. A full multi-dimensional audit will trigger after 5 validated responses.",
                "key_deltas": [
                    {
                        "topic": "Data Maturity",
                        "cv_impression": "Analyzing claims...",
                        "interview_reality": "Waiting for deeper technical evidence...",
                        "impact": "neutral",
                    }
                ],
                "final_verdict": "Initial Screening Phase",
            }
        else:
            # 2. CACHING: Check if a valid audit already exists for this exact interview state
            try:
                analysis_data = (
                    _cv_analysis_comp
                    if isinstance(_cv_analysis_comp, dict)
                    else (json.loads(_cv_analysis_comp) if _cv_analysis_comp else {})
                )
                cached_audit = analysis_data.get("intelligence_audit")

                # Cache is valid if content hash matches (no new data since last audit)
                current_log_hash = hashlib.sha256(
                    (_iv_log_comp or "").encode()
                ).hexdigest()
                if cached_audit and cached_audit.get("log_hash") == current_log_hash:
                    logger.info(
                        f"Using cached intelligence audit for app {app_id} to save money/tokens."
                    )
                    comparison = cached_audit.get("data")
                else:
                    # 3. LIVE AI AUDIT: Only call if no bypass and no valid cache
                    from backend.credit_service import (
                        consume_credits_or_402,
                        rollback_credits,
                    )

                    credit_tx = consume_credits_or_402(
                        db,
                        recruiter,
                        1,
                        "score_comparison",
                        reference_type="application",
                        reference_id=app_id,
                    )
                    try:
                        comparison = await generate_score_comparison(
                            cv_text=cv_text,
                            interview_log=_iv_log_comp,
                            cv_score=_sc_cv or 0,
                            interview_score=_sc_score_comp or 0,
                            role=_cv_role_comp or "General",
                            linguistic_analysis=linguistic_analysis,
                        )
                    except Exception:
                        rollback_credits(db, credit_tx)
                        raise

                    # Update cache in database
                    analysis_data["intelligence_audit"] = {
                        "log_hash": current_log_hash,
                        "timestamp": datetime.now(UTC).isoformat(),
                        "data": comparison,
                    }
                    sync_cv_document(db, app, analysis_json=analysis_data)
                    db.commit()  # Save the cache

            except Exception as cache_err:
                logger.warning(f"Cache/Audit error for app {app_id}: {cache_err}")
                # Fallback to live call if cache fails
                from backend.credit_service import (
                    consume_credits_or_402,
                    rollback_credits,
                )

                credit_tx = consume_credits_or_402(
                    db,
                    recruiter,
                    1,
                    "score_comparison",
                    reference_type="application",
                    reference_id=app_id,
                )
                try:
                    comparison = await generate_score_comparison(
                        cv_text=cv_text,
                        interview_log=_iv_log_comp,
                        cv_score=_sc_cv or 0,
                        interview_score=_sc_score_comp or 0,
                        role=_cv_role_comp or "General",
                        linguistic_analysis=linguistic_analysis,
                    )
                except Exception:
                    rollback_credits(db, credit_tx)
                    raise

            # Validate comparison response
            if not isinstance(comparison, dict):
                raise ValueError("Invalid comparison response format")

            # Ensure required fields exist
            comparison.setdefault("analysis_summary", "No analysis available")
            comparison.setdefault("key_deltas", [])
            comparison.setdefault("final_verdict", "Manual review recommended")

    except Exception as err:
        logger.error(
            f"Comparison generation failed for app {app_id}: {err}", exc_info=True
        )
        return {
            "state": "error",
            "candidate_name": candidate_name_score,
            "cv_score": _sc_cv or 0,
            "interview_score": _sc_score_comp or 0,
            "final_verdict": "Unable to generate AI-powered comparison",
            "analysis_summary": (
                "The comparison analysis encountered an error. "
                "Please try again in a few moments."
            ),
            "key_deltas": [],
        }

    # Calculate benchmark percentiles based on scores
    cv_score = _sc_cv or 0
    interview_score = _sc_score_comp or 0

    # Use consolidated counts
    total_questions = target_total_questions
    completion_rate = (
        (completed_questions / total_questions) * 100 if total_questions > 0 else 0
    )

    # ==================== NEW HIRING INTELLIGENCE ENGINE ====================

    # 1. PERFORMANCE SCORE (Interview Quality - 45%)
    # Already calculated as interview_score

    # 2. INTEGRITY SCORE (Verification Matrix - 35%)
    integrity_score = 50  # Default neutral

    key_deltas = comparison.get("key_deltas", []) if comparison else []

    # CRITICAL: Verification Degradation for incomplete interviews
    # If completion is under 50%, we cannot confidently say anything is "Verified"
    if completion_rate < 50 and key_deltas:
        for delta in key_deltas:
            if delta.get("impact") == "Positive":
                delta["impact"] = "Partial"
                delta["interview_reality"] = (
                    f"⚠️ [Insufficient Proof] {delta.get('interview_reality', '')}"
                )

    if key_deltas and isinstance(key_deltas, list):
        verified = sum(1 for d in key_deltas if d.get("impact") == "Positive")
        sum(1 for d in key_deltas if d.get("impact") == "Negative")
        partial = sum(
            1
            for d in key_deltas
            if d.get("impact") in ["Partial", "neutral", "Partial Match"]
        )
        total = len(key_deltas)
        # Verified=100%, Partial=50%, Gap=0%
        raw_integrity = ((verified * 100) + (partial * 50)) / total if total > 0 else 50

        # Apply completion penalty to integrity
        completion_multiplier = min(1.0, completion_rate / 80)  # Penalize if under 80%
        integrity_score = raw_integrity * completion_multiplier

    # 3. RELIABILITY SCORE (Completion - 20%)
    # Based on completion rate - minimum reliable = 10 questions
    minimum_reliable_questions = 10
    reliability_score = (
        min(100, (completed_questions / minimum_reliable_questions) * 100)
        if minimum_reliable_questions > 0
        else 0
    )

    # 4. BEHAVIORAL CONSISTENCY (from signals if available)
    consistency_score = 75  # Default - would be enhanced with behavioral analysis

    # 5. CONFIDENCE INDEX (Evidence-aware)
    # How confident are we based on data quantity
    confidence_multiplier = (
        min(1, completed_questions / minimum_reliable_questions)
        if minimum_reliable_questions > 0
        else 0
    )
    confidence_index = round(confidence_multiplier * 100, 1)

    # QUESTION DIFFICULTY WEIGHTING
    # Technical questions weighted 2x, contradiction detection 3x
    # This would require question metadata - for now we estimate

    # WEIGHTED SCORE CALCULATION
    weighted_score = (
        interview_score * 0.45  # Performance
        + integrity_score * 0.35  # Integrity
        + reliability_score * 0.20  # Reliability
    )

    # Apply confidence correction
    final_score = round(weighted_score * confidence_multiplier, 1)

    # ==================== NEW VERDICT SYSTEM ====================
    recommendation = "Proceed to Next Round"
    risk_level = "low"
    recommendation_type = "standard"

    # Critical: Check minimum data threshold
    if completed_questions < 5:
        recommendation = "🚫 Insufficient Data"
        risk_level = "high"
        recommendation_type = "insufficient"
    elif final_score >= 80 and confidence_index >= 80 and integrity_score >= 80:
        recommendation = "🔥 Fast Track to Final"
        risk_level = "low"
        recommendation_type = "fast_track"
    elif final_score >= 60 and confidence_index >= 60:
        recommendation = "✅ Proceed to Next Round"
        risk_level = "low"
        recommendation_type = "standard"
    elif final_score >= 40:
        recommendation = "🟡 Potential but Unverified"
        risk_level = "medium"
        recommendation_type = "caution"
    else:
        recommendation = "⚠️ High Risk"
        risk_level = "high"
        recommendation_type = "high_risk"

    # Override if integrity is very low
    if integrity_score < 40:
        recommendation = "⚠️ High Risk - Verification Gaps"
        risk_level = "high"
        recommendation_type = "integrity_fail"

    # Risk flags
    risk_flags = []
    if completion_rate < 50:
        risk_flags.append("Low completion rate")
    if confidence_index < 50:
        risk_flags.append("Low confidence - limited data")
    if integrity_score < 60:
        risk_flags.append("CV claims differ from interview")
    if interview_score < 40:
        risk_flags.append("Poor interview performance")

    # Calculate percentiles (simulated - in production would use actual database stats)
    role_pct = min(99, max(1, 100 - (cv_score / 100 * 50) - 20))
    ind_pct = min(99, max(1, 100 - (cv_score / 100 * 40) - 30))
    exp_pct = min(99, max(1, 100 - (interview_score / 100 * 60) - 10))

    # Determine verdict recommendation based on weighted score (considers completion)
    if weighted_score >= 80:
        pass
    elif weighted_score >= 60:
        pass
    elif weighted_score >= 40:
        pass
    else:
        pass

    # Add completion warning if candidate didn't finish
    if completion_rate < 100:
        f" (Only completed {int(completion_rate)}% of questions)"

    # Calculate estimated duration
    duration_minutes = 0
    if app.opened_at and app.interview_last_saved:
        delta = app.interview_last_saved - app.opened_at
        duration_minutes = max(0, delta.total_seconds() / 60)
    elif completed_questions > 0:
        # Fallback estimate: 1.5 minutes per answered question
        duration_minutes = completed_questions * 1.5

    # Extract question history for timeline dots
    question_history = []
    if _iv_qa_comp and isinstance(_iv_qa_comp, list):
        for q in _iv_qa_comp:
            question_history.append(
                {
                    "question": q.get("question", ""),
                    "score": q.get("score", 0),
                    "status": "completed" if q.get("answer") else "pending",
                }
            )

    # ✅ Return successful response with NEW hiring intelligence metrics
    return {
        "state": "ready",
        "candidate_name": candidate_name_score,
        # Core Metrics (for display)
        "cv_score": cv_score,
        "interview_score": interview_score,
        "completed_questions": completed_questions,
        "total_questions": total_questions,
        "completion_rate": round(completion_rate, 1),
        # Timeline Object for Frontend synchronization
        "timeline": {
            "completed_questions": completed_questions,
            "total_questions": total_questions,
            "duration_minutes": round(duration_minutes, 1),
            "completion_rate": round(completion_rate, 1),
            "question_history": question_history,
        },
        # NEW: Multi-dimensional scoring
        "performance_score": interview_score,  # Interview quality (45%)
        "integrity_score": round(integrity_score, 1),  # Verification truthfulness (35%)
        "reliability_score": round(
            reliability_score, 1
        ),  # Completion reliability (20%)
        "confidence_index": confidence_index,  # Evidence-based confidence
        "consistency_score": round(consistency_score, 1),  # Behavioral consistency
        # Final calculations
        "weighted_score": round(weighted_score, 1),  # Raw weighted (before confidence)
        "final_score": final_score,  # Final score with confidence applied
        # NEW: Verdict system
        "recommendation": recommendation,
        "risk_level": risk_level,
        "recommendation_type": recommendation_type,
        "risk_flags": risk_flags,
        "verdict_recommendation": recommendation
        + (f" ({completed_questions} questions)" if completed_questions < 10 else ""),
        # Benchmark (kept for backwards compatibility)
        "benchmark": {
            "role_percentile": f"Top {int(role_pct)}%",
            "role_bar_width": 100 - role_pct,
            "industry_percentile": f"Top {int(ind_pct)}%",
            "industry_bar_width": 100 - ind_pct,
            "experience_percentile": f"Top {int(exp_pct)}%",
            "experience_bar_width": 100 - exp_pct,
        },
        **comparison,  # Spread analysis_summary, key_deltas, final_verdict
    }


@router.get("/applications/{app_id}/scores")
def get_application_scores(
    app_id: int,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    app = get_application_for_recruiter(app_id, recruiter, db)

    is_pro = (
        get_user_tier(recruiter) in ("pro", "pro_plus", "enterprise")
        or recruiter.role == "admin"
    )
    real_name = app.full_name or "Unknown"
    candidate_name_score = (
        real_name
        if is_pro
        else (
            real_name.split()[0][0] + ". Candidate"
            if real_name.split()
            else "Candidate"
        )
    )

    _es_scores = app.evaluation_sessions or []
    _sc_scores = (
        _es_scores[0].evaluation_result
        if _es_scores and _es_scores[0].evaluation_result
        else None
    )
    _sc_scores_cv = _sc_scores.cv_score if _sc_scores else None
    _sc_scores_final = _sc_scores.final_score if _sc_scores else None
    _sc_rubric_score = _sc_scores.rubric_score if _sc_scores else None
    _sc_rubric_coverage = _sc_scores.rubric_coverage_pct if _sc_scores else None
    _sc_scoring_model = _sc_scores.scoring_model if _sc_scores else None
    _sc_rubric_version = _sc_scores.rubric_version if _sc_scores else None

    # Company-aware authorization verified by get_application_for_recruiter.

    # Phase 4: Load rubric breakdown
    rubric_summary = (
        db.query(EvaluationResult)
        .join(
            EvaluationSession,
            EvaluationResult.evaluation_session_id == EvaluationSession.id,
        )
        .filter(EvaluationSession.application_id == app_id)
        .first()
    )

    category_breakdown = []
    skill_breakdown = []
    gaps = []
    evidence = []
    rubric_available = False

    if rubric_summary:
        rubric_available = True
        breakdown_data = rubric_summary.score_breakdown or {}
        if isinstance(breakdown_data, str):
            breakdown_data = json.loads(breakdown_data) if breakdown_data else {}
        category_breakdown = (
            breakdown_data.get("category_scores", [])
            if isinstance(breakdown_data, dict)
            else []
        )
        skill_scores_dict = (
            breakdown_data.get("skill_scores", {})
            if isinstance(breakdown_data, dict)
            else {}
        )
        skill_breakdown = [
            {
                "name": name,
                "score": details.get("final_score", details.get("score", 0))
                if isinstance(details, dict)
                else 0,
                "is_required": details.get("is_required", False)
                if isinstance(details, dict)
                else False,
                "assessed": (
                    details.get("final_score", details.get("score", 0)) or 0
                )
                > 0
                if isinstance(details, dict)
                else False,
                "category": details.get("category", "")
                if isinstance(details, dict)
                else "",
                "explanation": details.get("explanation", "")
                if isinstance(details, dict)
                else "",
                "evidence": details.get("evidence", [])
                if isinstance(details, dict)
                else [],
                "weight": details.get("weight", details.get("normalized_weight"))
                if isinstance(details, dict)
                else None,
                "normalized_weight": details.get("normalized_weight")
                if isinstance(details, dict)
                else None,
                "level": details.get("level")
                if isinstance(details, dict)
                else None,
                "evidence_quality": details.get("evidence_quality", details.get("quality", "strong"))
                if isinstance(details, dict)
                else "strong",
            }
            for name, details in skill_scores_dict.items()
        ]
        gaps = (
            breakdown_data.get("gaps", []) if isinstance(breakdown_data, dict) else []
        )

        # Apply recruiter score overrides
        skill_overrides = (
            breakdown_data.get("overrides", {})
            if isinstance(breakdown_data, dict)
            else {}
        )
        if skill_overrides and isinstance(skill_overrides, dict):
            for skill_name, override in skill_overrides.items():
                existing = next(
                    (s for s in skill_breakdown if s["name"] == skill_name), None
                )
                if existing:
                    existing["score"] = override["new_score"]
                    existing["overridden"] = True
                else:
                    skill_breakdown.append(
                        {
                            "name": skill_name,
                            "score": override["new_score"],
                            "is_required": False,
                            "assessed": True,
                            "overridden": True,
                        }
                    )

        # Load evidence from RubricScoringDetail rows
        scoring_results = (
            db.query(RubricScoringDetail)
            .join(
                EvaluationResult,
                RubricScoringDetail.evaluation_result_id == EvaluationResult.id,
            )
            .join(
                EvaluationSession,
                EvaluationResult.evaluation_session_id == EvaluationSession.id,
            )
            .filter(EvaluationSession.application_id == app_id)
            .order_by(RubricScoringDetail.id.asc())
            .all()
        )
        evidence = [
            {
                "skill_name": r.criterion_name,
                "turn_number": idx,
                "question": r.question,
                "answer": r.answer,
                "matched_keywords": [],
                "missing_competencies": [],
                "explanation": r.feedback,
                "final_score": (skill_overrides.get(r.criterion_name, {}) or {}).get(
                    "new_score", r.score
                ),
                "overridden": r.criterion_name in (skill_overrides or {}),
            }
            for idx, r in enumerate(scoring_results, 1)
        ]

        logger.info(
            f"[SCORES-API] Rubric breakdown for app {app_id}: "
            f"{len(category_breakdown)} categories, {len(skill_breakdown)} skills, "
            f"{len(gaps)} gaps, {len(evidence)} evidence rows"
        )

    # ------------------------------------------------------------------
    # CV rubric-weighted breakdown (P1). Source of truth is the CV
    # document's analysis_json (persisted by sync_cv_document during
    # run_cv_analysis), NOT EvaluationResult.score_breakdown — the latter
    # is replaced wholesale by set_evaluation_result once an AI interview
    # completes, which would drop the CV-weighted keys. Per-skill evidence
    # rows come from RubricScoringDetail where source == "cv".
    # ------------------------------------------------------------------
    _cv_doc = getattr(app, "cv_document", None)
    _cv_analysis_json = getattr(_cv_doc, "analysis_json", None) or getattr(
        app, "analysis_json", None
    )
    _cv_analysis = {}
    if _cv_analysis_json:
        try:
            _cv_analysis = (
                _cv_analysis_json
                if isinstance(_cv_analysis_json, dict)
                else json.loads(_cv_analysis_json)
            )
        except Exception:
            _cv_analysis = {}

    # Three-state: True (rubric-weighted), False (generic_fallback with a
    # rubric attached), None (no rubric on the job/app → pure AI analysis).
    cv_rubric_weighted = _cv_analysis.get("cv_rubric_weighted")
    if cv_rubric_weighted is not None:
        cv_rubric_weighted = bool(cv_rubric_weighted)
    cv_scoring_method = _cv_analysis.get("scoring_method")
    cv_coverage_pct = _cv_analysis.get("coverage_pct")
    cv_missing_skills = _cv_analysis.get("missing_skills") or []

    _cv_skill_scores = _cv_analysis.get("skill_scores") or {}
    cv_skill_breakdown = [
        {
            "name": name,
            "score": round(float(details.get("score", 0) or 0), 1)
            if isinstance(details, dict)
            else 0,
            "weight": details.get("weight") if isinstance(details, dict) else None,
            "normalized_weight": (
                details.get("normalized_weight")
                if isinstance(details, dict)
                else None
            ),
            "level": details.get("level") if isinstance(details, dict) else None,
            "feedback": details.get("feedback") if isinstance(details, dict) else None,
            "category": details.get("category") if isinstance(details, dict) else None,
        }
        for name, details in _cv_skill_scores.items()
    ]

    cv_evidence_rows = (
        db.query(RubricScoringDetail)
        .join(
            EvaluationResult,
            RubricScoringDetail.evaluation_result_id == EvaluationResult.id,
        )
        .join(
            EvaluationSession,
            EvaluationResult.evaluation_session_id == EvaluationSession.id,
        )
        .filter(
            EvaluationSession.application_id == app_id,
            RubricScoringDetail.source == "cv",
        )
        .order_by(RubricScoringDetail.id.asc())
        .all()
    )
    cv_evidence = [
        {
            "skill_name": r.criterion_name,
            "score": r.score,
            "weight": r.weight,
            "feedback": r.feedback,
        }
        for r in cv_evidence_rows
    ]

    # Prefer the persisted evidence rows (they carry the same per-skill
    # data but are durable); fall back to the analysis_json breakdown.
    if not cv_evidence and cv_skill_breakdown:
        cv_evidence = [
            {
                "skill_name": s["name"],
                "score": s["score"],
                "weight": s["normalized_weight"],
                "feedback": s["feedback"],
            }
            for s in cv_skill_breakdown
        ]

    needs_review = _sc_scores.needs_review if _sc_scores else False
    needs_review_reason = _sc_scores.needs_review_reason if _sc_scores else None

    # Penalty transparency breakdown
    from backend.scoring_transparent import (
        calculate_integrity_penalty,
    )

    _iv = app.evaluation_sessions[0] if app.evaluation_sessions else None
    _pc_violations = []
    try:
        raw_violations = getattr(_iv, "proctoring_violations", None)
        if raw_violations:
            _pc_violations = json.loads(raw_violations)
    except Exception:
        pass
    integrity_penalty = calculate_integrity_penalty(_pc_violations)
    proctoring_count = len(_pc_violations)
    trust_score = max(0.0, 100.0 - integrity_penalty)

    penalty_breakdown = {
        "integrity_penalty": round(integrity_penalty, 1),
        "gaming_penalty": 10.0
        if (
            _sc_scores_final
            and _sc_scores
            and _sc_scores.verdict
            and "gaming" in str(_sc_scores.verdict).lower()
        )
        else 0.0,
        "timing_penalty": 0.0,
        "proctoring_violations_count": proctoring_count,
        "trust_score": round(trust_score, 1),
    }

    # ------------------------------------------------------------------
    # Frontend-aligned shape (matches recruiter-interview-analysis page):
    #   rubric, questions, ai_feedback, interview_details, status,
    #   recommendation, trust
    # ------------------------------------------------------------------
    def _qualifier(v):
        if v is None:
            return ""
        return "Excellent" if v >= 80 else "Good" if v >= 60 else "Fair"

    rubric_overview = [
        {
            "label": (c.get("name") if isinstance(c, dict) else "") or "Category",
            "score": round(float((c.get("score") if isinstance(c, dict) else 0) or 0)),
            "qualifier": _qualifier(
                round(float((c.get("score") if isinstance(c, dict) else 0) or 0))
            ),
        }
        for c in category_breakdown
        if isinstance(c, dict)
    ]

    questions_aligned = [
        {
            "id": idx,
            "title": (ev.get("question") or ev.get("skill_name") or f"Skill #{idx}")[
                :200
            ],
            "category": ev.get("skill_name") or "",
            "duration": "",
            "score": round(float(ev.get("final_score") or 0)),
            "label": _qualifier(round(float(ev.get("final_score") or 0))),
            "answer": (ev.get("answer") or "")[:300],
            "justification": ev.get("explanation") or "",
        }
        for idx, ev in enumerate(evidence, 1)
    ]

    ai_feedback_aligned = [
        {"title": s.get("name") or "Skill", "body": s.get("explanation") or ""}
        for s in skill_breakdown
        if s.get("explanation")
    ]

    interview_details_aligned = [
        {"label": "Rubric Version", "value": str(_sc_rubric_version or "—")},
        {
            "label": "Rubric Score",
            "value": str(_sc_rubric_score if _sc_rubric_score is not None else "—"),
        },
        {
            "label": "Coverage",
            "value": f"{_sc_rubric_coverage or 0}%",
        },
        {
            "label": "Assessed Skills",
            "value": str(len(skill_breakdown)),
        },
    ]

    _final = _sc_scores_final or 0
    rec_label = (
        "Strong Hire"
        if _final >= 75
        else "Hire"
        if _final >= 60
        else "Consider"
        if _final >= 45
        else "Low Priority"
    )
    recommendation_aligned = {
        "label": rec_label,
        "status": (app.status or "pending").upper(),
    }

    trust_aligned = {
        "score": round(trust_score),
        "coverage": int(_sc_rubric_coverage or 0),
        "quality": round(trust_score),
        "count": len(evidence),
    }

    return {
        "application_id": app_id,
        "candidate_name": candidate_name_score,
        "cv_score": _sc_scores_cv,
        "overall_score": _sc_scores_final,
        "score": _sc_scores_final,  # backward-compat alias
        "interview_score": _sc_scores_final,
        "analysis_score": _sc_scores_final,  # canonical: maps from EvaluationResult.final_score
        "scores": {
            "cv": _sc_scores_cv or 0,
            "interview": _sc_scores_final or 0,
        },
        # Phase 4: Rubric breakdown
        "rubric_score": _sc_rubric_score,
        "rubric_coverage_pct": _sc_rubric_coverage,
        "scoring_model": _sc_scoring_model,
        "rubric_version": _sc_rubric_version,
        "rubric_available": rubric_available,
        "category_breakdown": category_breakdown,
        "skill_breakdown": skill_breakdown,
        "gaps": gaps,
        "evidence": evidence,
        # CV rubric-weighted breakdown (P1)
        "cv_rubric_weighted": cv_rubric_weighted,
        "cv_scoring_method": cv_scoring_method,
        "cv_coverage_pct": cv_coverage_pct,
        "cv_skill_breakdown": cv_skill_breakdown,
        "cv_evidence": cv_evidence,
        "cv_missing_skills": cv_missing_skills,
        # Phase 5: Needs review flag
        "needs_review": needs_review,
        "needs_review_reason": needs_review_reason,
        # Phase 6: Penalty transparency
        "penalty_breakdown": penalty_breakdown,
        # Frontend-aligned analysis shape
        "rubric": rubric_overview,
        "questions": questions_aligned,
        "ai_feedback": ai_feedback_aligned,
        "interview_details": interview_details_aligned,
        "status": app.status,
        "recommendation": recommendation_aligned,
        "trust": trust_aligned,
        "is_rubric_driven": rubric_available,
    }


@router.get("/jobs/{job_id}/candidates/ranked")
def get_ranked_candidates(
    job_id: int,
    weight_cv: float = 0.25,
    weight_interview: float = 0.50,
    weight_rubric: float = 0.25,
    weight_human: float = 0.0,
    page: int = 1,
    per_page: int = 20,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    job = get_job_for_recruiter(job_id, recruiter, db)
    company_id = getattr(recruiter, "_company_id", None)

    offset = (page - 1) * per_page

    total = MetricsRepository(db).get_application_count_for_job(job_id, company_id)

    score_subq = (
        select(EvaluationResult.final_score)
        .select_from(EvaluationSession)
        .join(
            EvaluationResult,
            EvaluationResult.evaluation_session_id == EvaluationSession.id,
        )
        .where(EvaluationSession.application_id == Application.id)
        .order_by(EvaluationSession.id.desc())
        .limit(1)
        .correlate(Application)
        .scalar_subquery()
    )
    page_apps = (
        db.query(Application)
        .options(
            selectinload(Application.cv_document),
            selectinload(Application.evaluation_sessions).selectinload(
                EvaluationSession.evaluation_result
            ),
            undefer(Application.recruiter_notes),
        )
        .filter(Application.job_id == job_id, Application.company_id == company_id)
        .order_by(func.coalesce(score_subq, 0).desc())
        .offset(offset)
        .limit(per_page)
        .all()
    )

    ranked = []
    is_pro_ranked = (
        get_user_tier(recruiter) in ("pro", "pro_plus", "enterprise")
        or recruiter.role == "admin"
    )
    for app in page_apps:
        es = (
            db.query(EvaluationSession)
            .filter(EvaluationSession.application_id == app.id)
            .first()
        )
        _app_sc = scores_map.get(es.id) if es else None
        
        canonical = _app_sc
        if not canonical:
            canonical = ScoringService.ensure_score(app, db)
        cv_score = canonical.cv_score or 0
        rubric_score = canonical.rubric_score or 0
        composite = (
            canonical.final_score
            if canonical and canonical.final_score is not None
            else 0
        )
        rubric_coverage = None
        if canonical.rubric_coverage_pct is not None:
            rubric_coverage = {
                "skills_assessed": 0,
                "skills_total": 0,
                "coverage_pct": round(canonical.rubric_coverage_pct),
            }

        scorecard_count = 0
        
        time_in_stage = 0
        if app.updated_at:
            if app.updated_at.tzinfo is None:
                time_in_stage = (datetime.now(UTC).replace(tzinfo=None) - app.updated_at).days
            else:
                time_in_stage = (datetime.now(UTC) - app.updated_at).days

        if is_pro_ranked:
            name_label = app.full_name or "Candidate"
            email_label = app.email
            phone_label = app.phone
        else:
            real_name = app.full_name or "Unknown"
            name_label = f"{real_name.split()[0][0]}. Candidate"
            email_label = "hidden@candway.com"
            phone_label = "+216 ** *** ***"

        ranked.append(
            {
                "id": app.id,
                "name": name_label,
                "email": email_label,
                "phone": phone_label,
                "role": getattr(app.cv_document, "declared_role", None)
                or "Not specified",
                "final_score": round(composite, 1),
                "scores": {
                    "cv": round(cv_score, 1),
                    "interview": round(rubric_score, 1),
                    "rubric": round(rubric_score, 1),
                    "human": None,
                    "integrity": None,
                    "fraud": round(canonical.fraud_score if canonical else 0, 1),
                },
                "rubric_coverage": rubric_coverage,
                "weights": {
                    "cv": weight_cv,
                    "rubric": weight_rubric,
                    "human": 0.0,
                    "coverage": 0.25,
                },
                "status": app.status or "pending",
                "time_in_stage_days": time_in_stage,
                "interview_state": app.interview_state or "not_started",
                "scorecard_evaluations": scorecard_count,
                "notes_count": len(app.recruiter_notes or "") // 100
                if app.recruiter_notes
                else 0,
                "last_activity": app.updated_at.isoformat() if app.updated_at else None,
            }
        )

    ranked.sort(key=lambda c: c["final_score"] or 0, reverse=True)
    for i, c in enumerate(ranked):
        c["rank"] = offset + i + 1

    return {
        "job_id": job_id,
        "job_title": job.title,
        "candidates": ranked,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page,
    }


@router.get("/applications/{app_id}/ghost-data")
def get_ghost_candidate_data(
    app_id: int,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    """Generate anonymized ghost report for candidate."""

    # ✅ Robust feature access check (FeatureFlag-first, legacy matrix fallback)
    try:
        has_access = has_feature(
            db, "ghost_report", recruiter, getattr(recruiter, "company_id", None)
        )

        # Fallback for Pro/Pro+ tiers if permissions_json is missing the key
        if not has_access and get_user_tier(recruiter) in [
            "pro",
            "pro_plus",
            "enterprise",
        ]:
            has_access = True

    except Exception as feature_err:
        logger.error(
            f"Feature check failed for recruiter {recruiter.id}: {feature_err}"
        )
        has_access = (
            get_user_tier(recruiter) in ["pro", "pro_plus", "enterprise"]
            or recruiter.role == "admin"
        )

    if not has_access:
        plan = SubscriptionService.get_user_plan(recruiter, db)
        plan_name = plan.name if plan else "Free"
        raise HTTPException(
            status_code=403,
            detail=(
                f"Ghost Data Reports are not available in your {plan_name} plan. "
                f"Please upgrade to Pro+ to access anonymized candidate reports."
            ),
        )

    # Fetch application with company-aware authorization
    app = get_application_for_recruiter(app_id, recruiter, db)

    _cv_ghost = app.cv_document
    _iv_ghost = app.evaluation_sessions[0] if app.evaluation_sessions else None
    _es_ghost = app.evaluation_sessions or []
    _er_ghost = (
        _es_ghost[0].evaluation_result
        if _es_ghost and _es_ghost[0].evaluation_result
        else None
    )
    _sc_ghost = _er_ghost
    _sc_score_ghost = _sc_ghost.final_score if _sc_ghost else None
    _cv_role_ghost = getattr(_cv_ghost, "declared_role", None) or getattr(
        app, "declared_role", None
    )
    _iv_log_ghost = getattr(_iv_ghost, "interview_log", None) or getattr(
        app, "interview_log", None
    )
    _cv_analysis_ghost = getattr(_cv_ghost, "analysis_json", None) or getattr(
        app, "analysis_json", None
    )
    _sc_cv_ghost = _sc_ghost.cv_score if _sc_ghost else None

    # Company-aware authorization verified by get_application_for_recruiter.

    # ✅ IMPROVED: Safe analysis parsing
    try:
        analysis = (
            _cv_analysis_ghost
            if isinstance(_cv_analysis_ghost, dict)
            else (json.loads(_cv_analysis_ghost) if _cv_analysis_ghost else {})
        )
    except (json.JSONDecodeError, TypeError, ValueError):
        logger.error(f"Corrupted analysis_json for app {app_id}")
        analysis = {}

    # Anonymize summary
    summary = analysis.get("summary", "No summary available.")
    if app.full_name:
        summary = summary.replace(app.full_name, "The Candidate")
        # Optional: Replace pronouns for better anonymization
        summary = re.sub(r"\b(he|she)\b", "they", summary, flags=re.IGNORECASE)

    # ✅ IMPROVED: Interview highlight extraction using quality scoring
    highlights = extract_interview_highlights(
        _iv_log_ghost, max_count=3, app_score=_sc_score_ghost or 0
    )

    # Build metrics
    metrics = analysis.get("metrics")
    if not metrics:
        base_score = _sc_score_ghost or 50
        metrics = {
            "Technical": min(100, max(0, base_score + 5)),
            "Communication": min(100, max(0, base_score)),
            "Problem Solving": min(100, max(0, base_score + 3)),
            "Adaptability": 70,
            "Confidence": 75,
        }

    # Build experience
    experience = analysis.get("experience", [])
    if not experience:
        experience = [
            {
                "title": f"Senior {_cv_role_ghost or 'Professional'}",
                "duration": "4+ Years",
                "description": "Demonstrated expertise in core technologies and project leadership.",
            }
        ]

    return {
        "id": app.id,
        "ghost_name": f"Candidate #{app.id}",
        "role": _cv_role_ghost or "Technical Expert",
        "job_title": (
            app.job.title
            if app.job
            else (app.batch_job.title if app.batch_job else "Technical Role")
        ),
        "scores": {
            "cv": min(100, max(0, _sc_cv_ghost or 0)),
            "interview": min(100, max(0, _sc_score_ghost or 0)),
        },
        "summary": summary,
        "strengths": analysis.get(
            "strengths", ["Strong technical foundation", "Clear communication"]
        ),
        "weaknesses": analysis.get("weaknesses", ["Niche technology gaps"]),
        "experience": experience,
        "interview_highlights": highlights,
        "metrics": metrics,
        "prepared_by": get_user_name(recruiter) or recruiter.email,
        "agency": get_user_company_name(recruiter) or "Candway Verified Partner",
        "methodology": (
            "This report is generated using Candway's proprietary AI Technical Audit system. "
            "Evaluation combines deep NLP analysis of CV integrity with a dynamic technical interview "
            "designed to verify claimed skills through behavioral observation."
        ),
        "generated_at": datetime.now(UTC).isoformat(),
    }


@router.post("/applications/bulk-ghost-data")
def get_bulk_ghost_data(
    update: BulkIdRequest,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    # Check Feature Access Upfront with tier fallback (FeatureFlag-first)
    has_access = has_feature(
        db, "ghost_report", recruiter, getattr(recruiter, "company_id", None)
    )
    if not has_access and get_user_tier(recruiter) in ["pro", "pro_plus", "enterprise"]:
        has_access = True

    if not has_access:
        raise HTTPException(
            status_code=403,
            detail="The Ghost Formatter is a Pro feature. Please upgrade your subscription.",
        )

    if not update.app_ids:
        raise HTTPException(status_code=400, detail="No application IDs provided")
    results = []
    errors = []
    for app_id in update.app_ids:
        try:
            # We can just call the existing logic or helper
            data = get_ghost_candidate_data(app_id, recruiter, db)
            results.append(data)
        except HTTPException as he:
            # Pass through HTTP exceptions if needed, or just log
            errors.append(f"App {app_id}: {he.detail}")
            continue
        except Exception as e:
            logger.error(f"Bulk ghost data error for app {app_id}: {e}")
            continue
    if not results and errors:
        # If all failed, return the first error or a summary
        raise HTTPException(
            status_code=400,
            detail=f"Failed to generate reports. Errors: {'; '.join(errors[:3])}...",
        )
    return results


# ═══════════════════════════════════════════════════════════════
# CANDIDATE COMPARISON - Advanced Scoring Engine
# ═══════════════════════════════════════════════════════════════


@router.post("/applications/compare")
def compare_candidates(
    request: CompareRequest,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    """
    Advanced candidate comparison with enterprise-grade scoring.
    Uses weighted scoring, confidence adjustment, consistency validation,
    trust-aware ranking, and semantic skill matching.
    """
    if len(request.ids) < 2 or len(request.ids) > 5:
        raise HTTPException(
            status_code=400, detail="Select 2 to 5 candidates to compare"
        )

    apps = []
    for app_id in request.ids:
        apps.append(get_application_for_recruiter(app_id, recruiter, db))

    is_pro = (
        get_user_tier(recruiter) in ("pro", "pro_plus", "enterprise")
        or recruiter.role == "admin"
    )

    # Get job requirements if provided
    job_requirements = None
    if request.job_id:
        job = get_job_for_recruiter(request.job_id, recruiter, db)
        if job.required_skills:
            skills = [s.strip() for s in job.required_skills.split(",")]
            job_requirements = {"required_skills": skills}
    elif request.batch_id:
        batch = get_batch_for_recruiter(request.batch_id, recruiter, db)
        if batch.target_role:
            skills = [s.strip() for s in batch.target_role.split(",")]
            job_requirements = {"required_skills": skills}

    # Build application data for scoring engine
    applications_data = []
    for app in apps:
        app_data = _build_application_data_for_scoring(app, db, is_pro)
        applications_data.append(app_data)

    # Use the unified scoring engine
    try:
        engine = ScoringEngine()
        breakdowns = engine.compare_candidates(applications_data, job_requirements)

        # Match breakdowns back to application data to include id and metadata
        candidates = []
        for b in breakdowns:
            d = b.to_dict()
            # Find matching app_data to get id
            matching_app = next(
                (
                    a
                    for a in applications_data
                    if a.get("cv_score") == b.cv_score
                    and a.get("overall_score") == b.interview_score
                ),
                None,
            )
            if matching_app:
                d["id"] = matching_app.get("id")
                d["name"] = matching_app.get("name")
                d["role"] = matching_app.get("role")
                d["skills"] = matching_app.get("skills", [])
                d["experience_years"] = matching_app.get("experience_years", 0)
                d["location"] = matching_app.get("location", "Not specified")
                d["created_at"] = matching_app.get("created_at")
                d["status"] = matching_app.get("status")
            candidates.append(d)

        response = {"candidates": candidates}

        # Add score_gaps for frontend compatibility
        if candidates and len(candidates) > 1:
            top_score = candidates[0].get("final_score", 0)
            score_gaps = []
            for c in candidates[1:]:
                gap = top_score - c.get("final_score", 0)
                score_gaps.append(
                    {
                        "candidate_id": c.get("id"),
                        "gap": gap,
                        "vs": f"{gap} points behind leader",
                    }
                )
            response["score_gaps"] = score_gaps
        else:
            response["score_gaps"] = []

        # Add backward compatibility fields for frontend
        response["legacy"] = _build_legacy_response(candidates, is_pro)

        return response
    except Exception as e:
        logger.error(f"Comparison error: {e}")
        raise HTTPException(status_code=500, detail="Comparison failed")


@router.get("/applications/{app_id}/all-interviews")
def get_all_candidate_interviews(
    app_id: int,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    """Get all interviews/applications for the same candidate across jobs/campaigns."""
    try:
        return _get_all_candidate_interviews_impl(app_id, recruiter, db)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_all_candidate_interviews for app {app_id}: {e}")
        import traceback

        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail="Internal server error")
