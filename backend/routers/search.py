"""
Advanced Search Router for Candway ATS
Provides complex filtering for candidates and applications
"""

import json
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload, selectinload

from backend.database import Application, EvaluationResult, EvaluationSession, Job, User
from backend.dependencies import get_db, require_recruiter
from backend.logger import logger
from backend.profile_helpers import get_user_email, get_user_name, get_user_tier
from backend.security import mask_candidate_data

router = APIRouter(prefix="/search", tags=["Advanced Search"])


class AdvancedSearchSchema(BaseModel):
    query: Optional[str] = None
    min_score: Optional[float] = None
    max_score: Optional[float] = None
    status: Optional[List[str]] = None
    role: Optional[str] = None
    location: Optional[str] = None
    skills: Optional[List[str]] = None
    min_rating: Optional[float] = None  # Uses ApplicationScore.final_score
    date_from: Optional[str] = None
    date_to: Optional[str] = None


@router.post("/candidates")
async def advanced_candidate_search(
    criteria: AdvancedSearchSchema,
    user: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    """
    Perform advanced search on candidates using multiple criteria
    """
    try:
        company_id = getattr(user, "_company_id", None)
        query = (
            db.query(Application)
            .options(selectinload(Application.evaluation_sessions))
            .filter(Application.company_id == company_id)
        )

        # Text Query (Search in name, email, cv_text, role)
        if criteria.query:
            search_pattern = f"%{criteria.query}%"
            query = query.outerjoin(User, Application.user_id == User.id).filter(
                or_(
                    User.name.ilike(search_pattern),
                    User.email.ilike(search_pattern),
                    Application.full_name.ilike(search_pattern),
                    Application.email.ilike(search_pattern),
                    Application.cv_text_anonymized.ilike(search_pattern),
                    Application.declared_role.ilike(search_pattern),
                )
            )

        # Score filtering
        if (
            criteria.min_score is not None
            or criteria.max_score is not None
            or criteria.min_rating is not None
        ):
            query = query.outerjoin(
                EvaluationSession, EvaluationSession.application_id == Application.id
            ).outerjoin(
                EvaluationResult,
                EvaluationResult.evaluation_session_id == EvaluationSession.id,
            )
        if criteria.min_score is not None:
            query = query.filter(EvaluationResult.final_score >= criteria.min_score)
        if criteria.max_score is not None:
            query = query.filter(EvaluationResult.final_score <= criteria.max_score)

        # Status filtering
        if criteria.status:
            query = query.filter(Application.status.in_(criteria.status))

        # Job Role
        if criteria.role:
            role_term = f"%{criteria.role.strip()}%"
            query = query.outerjoin(Job).filter(
                or_(
                    Job.title.ilike(role_term),
                    Application.declared_role.ilike(role_term),
                )
            )
        # Ratings (using EvaluationResult.final_score)
        if criteria.min_rating is not None:
            query = query.filter(EvaluationResult.final_score >= criteria.min_rating)

        # Skills (Simple string match in CV text for now)
        if criteria.skills:
            for skill in criteria.skills:
                if skill.strip():
                    skill_term = f"%{skill.strip()}%"
                    query = query.filter(
                        Application.cv_text_anonymized.ilike(skill_term)
                    )

        # Date filtering
        if criteria.date_from:
            query = query.filter(Application.created_at >= criteria.date_from)
        if criteria.date_to:
            query = query.filter(Application.created_at <= criteria.date_to)

        # Apply sorting and limit
        query = query.order_by(Application.created_at.desc()).limit(100)
        results = query.all()

        # Deduplication: Keep only the latest application per user_id or email
        unique_results = {}
        for app in results:
            key = app.user_id if app.user_id else (app.email or app.id)
            if key not in unique_results:
                unique_results[key] = app

        deduplicated_results = list(unique_results.values())
        is_pro = get_user_tier(user) == "pro" or user.role == "admin"

        results_list = []
        for app in deduplicated_results:
            _er_search = (
                app.evaluation_sessions[0].evaluation_result
                if app.evaluation_sessions
                and app.evaluation_sessions[0].evaluation_result
                else None
            )
            results_list.append(
                mask_candidate_data(
                    {
                        "id": app.id,
                        "full_name": get_user_name(app.owner)
                        if app.owner
                        else (app.full_name or "Candidate"),
                        "candidate_email": get_user_email(app.owner)
                        if app.owner
                        else app.email,
                        "role": app.job.title
                        if app.job
                        else (
                            app.batch_job.title
                            if app.batch_job
                            else (app.declared_role or "Candidate")
                        ),
                        "status": app.status,
                        "score": (_er_search.cv_score if _er_search else None)
                        or (_er_search.final_score if _er_search else None)
                        or 0,
                        "cv_score": (_er_search.cv_score if _er_search else None) or 0,
                        "is_locked": not is_pro,
                        "analysis": json.loads(app.analysis_json)
                        if app.analysis_json
                        else None,
                        "applied_at": app.created_at.isoformat()
                        if app.created_at
                        else None,
                    },
                    is_pro,
                )
            )

        return {
            "success": True,
            "count": len(deduplicated_results),
            "results": results_list,
        }

    except Exception:
        import traceback

        logger.error(f"Search failed: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Search failed")


def cosine_similarity(v1, v2):
    """Compute cosine similarity between two vectors."""
    if not v1 or not v2:
        return 0.0
    try:
        dot_product = sum(a * b for a, b in zip(v1, v2))
        magnitude1 = sum(a * a for a in v1) ** 0.5
        magnitude2 = sum(b * b for b in v2) ** 0.5
        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0
        return dot_product / (magnitude1 * magnitude2)
    except Exception:
        return 0.0


@router.get("/talent-scout")
async def talent_scout_search(
    query: str = Query(...),
    user: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    """
    Semantic search for candidates using vector embeddings.
    Falls back to text search if no embeddings available.
    """
    try:
        from backend.ai.llm import get_embedding

        company_id = getattr(user, "_company_id", None)
        authorized_filter = Application.company_id == company_id

        # 1. Generate Query Embedding
        query_vector = await get_embedding(query)

        # 2. Fetch candidates with embeddings (Priority given to high CV scores to keep loop performant)
        candidates_query = (
            db.query(Application)
            .options(
                joinedload(Application.owner),
                joinedload(Application.job),
                joinedload(Application.batch_job),
                selectinload(Application.evaluation_sessions),
            )
            .filter(authorized_filter)
            .filter(Application.cv_embedding is not None)
            .outerjoin(
                EvaluationSession, EvaluationSession.application_id == Application.id
            )
            .outerjoin(
                EvaluationResult,
                EvaluationResult.evaluation_session_id == EvaluationSession.id,
            )
            .order_by(EvaluationResult.final_score.desc().nullslast())
            .limit(200)
        )

        candidates = candidates_query.all()

        logger.info(
            f"Talent Scout: Analyzing top {len(candidates)} candidates with embeddings"
        )

        if len(candidates) == 0:
            # FALLBACK: Use text-based search if no embeddings
            text_results = (
                db.query(Application)
                .options(
                    joinedload(Application.owner),
                    joinedload(Application.job),
                    joinedload(Application.batch_job),
                    selectinload(Application.evaluation_sessions),
                )
                .filter(authorized_filter)
                .filter(
                    or_(
                        Application.full_name.ilike(f"%{query}%"),
                        Application.declared_role.ilike(f"%{query}%"),
                        Application.email.ilike(f"%{query}%"),
                    )
                )
                .limit(50)
                .all()
            )

            results = []
            seen_emails = set()
            is_pro = get_user_tier(user) == "pro" or user.role == "admin"
            for app in text_results:
                email = get_user_email(app.owner) if app.owner else app.email
                if email in seen_emails:
                    continue
                seen_emails.add(email)
                _er_txt = (
                    app.evaluation_sessions[0].evaluation_result
                    if app.evaluation_sessions
                    and app.evaluation_sessions[0].evaluation_result
                    else None
                )

                results.append(
                    {
                        "id": app.id,
                        "full_name": get_user_name(app.owner)
                        if app.owner
                        else (app.full_name or "Candidate"),
                        "candidate_email": email,
                        "role": app.job.title
                        if app.job
                        else (
                            app.batch_job.title
                            if app.batch_job
                            else (app.declared_role or "Candidate")
                        ),
                        "status": app.status,
                        "score": (_er_txt.final_score if _er_txt else None) or 0,
                        "is_locked": not is_pro,
                        "analysis": json.loads(app.analysis_json)
                        if app.analysis_json
                        else None,
                        "applied_at": app.created_at.isoformat()
                        if app.created_at
                        else None,
                        "semantic_score": 50,
                    }
                )

            return {
                "success": True,
                "query": query,
                "count": len(results),
                "results": results[:20],
                "message": "Text search results",
            }

        results = []
        seen_emails = set()
        for app in candidates:
            email = app.owner.email if app.owner else app.email
            if email in seen_emails:
                continue
            seen_emails.add(email)
            _er_vec = (
                app.evaluation_sessions[0].evaluation_result
                if app.evaluation_sessions
                and app.evaluation_sessions[0].evaluation_result
                else None
            )

            try:
                cv_vector = json.loads(app.cv_embedding)
                similarity = (
                    cosine_similarity(query_vector, cv_vector) if query_vector else 0.0
                )

                results.append(
                    {
                        "id": app.id,
                        "full_name": get_user_name(app.owner)
                        if app.owner
                        else (app.full_name or "Candidate"),
                        "candidate_email": get_user_email(app.owner)
                        if app.owner
                        else app.email,
                        "role": app.job.title
                        if app.job
                        else (
                            app.batch_job.title
                            if app.batch_job
                            else (app.declared_role or "Candidate")
                        ),
                        "status": app.status,
                        "score": (_er_vec.final_score if _er_vec else None) or 0,
                        "is_locked": not (
                            get_user_tier(user) == "pro" or user.role == "admin"
                        ),
                        "analysis": json.loads(app.analysis_json)
                        if app.analysis_json
                        else None,
                        "applied_at": app.created_at.isoformat()
                        if app.created_at
                        else None,
                        "semantic_score": round(similarity * 100, 1),
                    }
                )
            except Exception:
                continue

        results.sort(key=lambda x: x.get("score") or 0, reverse=True)

        return {
            "success": True,
            "query": query,
            "count": len(results),
            "results": results[:30],
        }
    except Exception as e:
        logger.error(f"Talent Scout failed: {e}")
        import traceback

        traceback.print_exc()
        return {
            "success": False,
            "error": "Search service error. Please try again later.",
            "message": "Search service error. Please try again later.",
        }
