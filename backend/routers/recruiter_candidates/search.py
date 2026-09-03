import csv
import io
import json
import re
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session, joinedload, selectinload

from backend.ai.llm import call_groq_cascade
from backend.authz import get_application_for_recruiter
from backend.database import (
    Application,
    BatchJob,
    Candidate,
    CompanyMember,
    EvaluationResult,
    EvaluationSession,
    Interview,
    Job,
    User,
)
from backend.dependencies import (
    get_db,
    get_pagination_meta,
    paginate,
    require_credits,
    require_pro_tier,
    require_recruiter,
)
from backend.entity_enricher import enrich_application_dict
from backend.logger import logger
from backend.models.evaluation.profile import CandidateProfile
from backend.profile_helpers import (
    get_user_avatar_url,
    get_user_email,
    get_user_headline,
    get_user_location,
    get_user_name,
    get_user_skills,
)
from backend.repository.metrics_repository import MetricsRepository
from backend.security import mask_candidate_data

router = APIRouter(tags=["Recruiter Candidates"])


_DISPLAY_STATUS_MAP = {
    "completed": "interviewing",
    "screening": "applied",
    "imported": "applied",
    "pending": "applied",
    "active": "invited",
    # offer_declined passes through unchanged so the recruiter list
    # shows "Offer Declined" (rendered by candidates-list.tsx).
    "offer_declined": "offer_declined",
}


def _candidate_photo_url(app, user) -> str:
    """Resolve the candidate photo: Candidate.photo_url, then profile avatar_url."""
    candidate = getattr(app, "candidate", None)
    photo = getattr(candidate, "photo_url", None) if candidate else None
    if not photo:
        photo = get_user_avatar_url(user) if user else None
    return photo or None


def _candidate_skills(app, user) -> list:
    """Best-effort top skills: profile skills (JSON), then CV-analysis skills."""
    skills = get_user_skills(user) if user else None
    if skills:
        try:
            parsed = json.loads(skills)
            if isinstance(parsed, list):
                return [str(s) for s in parsed[:6]]
        except Exception:
            pass
    a_json = getattr(app, "analysis_json", None)
    if isinstance(a_json, dict):
        extracted = a_json.get("extracted_skills") or a_json.get("skills")
        if isinstance(extracted, list):
            return [str(s) for s in extracted[:6]]
    doc = getattr(app, "cv_document", None)
    doc_skills = getattr(doc, "extracted_skills", None) if doc else None
    if isinstance(doc_skills, list):
        return [str(s) for s in doc_skills[:6]]
    return []


def _candidate_last_activity(app, interview_map) -> str:
    """Most recent activity timestamp (created_at, interview, or session save)."""
    last = app.created_at
    iv = interview_map.get(app.id) or {}
    iv_time = iv.get("scheduled_time")
    if iv_time:
        try:
            iv_dt = datetime.strptime(iv_time, "%Y-%m-%dT%H:%M:%S")
            last = max(last, iv_dt) if last else iv_dt
        except Exception:
            pass
    if last is None:
        return "Today"
    return last.strftime("%Y-%m-%dT%H:%M:%S")


def _display_status(status: str) -> str:
    """Canonical status remapping — single source of truth.

    Frontend MUST use this field instead of computing its own remapping.
    """
    return _DISPLAY_STATUS_MAP.get(status, status)


def _authorized_application_ids(db, recruiter):
    return [
        app_id
        for (app_id,) in db.query(Application.id).all()
        if get_application_for_recruiter(app_id, recruiter, db)
    ]


def _ownership_filter(db, recruiter):
    company_id = getattr(recruiter, "_company_id", None)
    return Application.company_id == company_id


def _build_base_query(db, recruiter):
    return (
        db.query(Application)
        .options(
            joinedload(Application.job),
            joinedload(Application.batch_job),
            joinedload(Application.owner),
            joinedload(Application.assignee),
            selectinload(Application.evaluation_sessions),
        )
        .outerjoin(Job)
        .outerjoin(BatchJob)
        .outerjoin(
            EvaluationSession, EvaluationSession.application_id == Application.id
        )
        .outerjoin(
            EvaluationResult,
            EvaluationResult.evaluation_session_id == EvaluationSession.id,
        )
        .filter(_ownership_filter(db, recruiter))
        .distinct()
    )


_interview_cache: dict = {}


def _preload_interviews(apps: list, db):
    if not apps:
        return
    app_ids = [a.id for a in apps if a.id]
    if not app_ids:
        return
    interviews = (
        db.query(Interview)
        .filter(Interview.application_id.in_(app_ids))
        .order_by(Interview.scheduled_time.desc())
        .all()
    )
    cache = {}
    for iv in interviews:
        if iv.application_id not in cache:
            cache[iv.application_id] = {
                "id": iv.id,
                "status": iv.status,
                "type": iv.type,
                "scheduled_time": iv.scheduled_time.isoformat()
                if iv.scheduled_time
                else None,
            }
    _interview_cache.clear()
    _interview_cache.update(cache)


def _candidate_to_result(app, recruiter, db):
    user = app.owner
    recruiter_tier = (
        getattr(getattr(recruiter, "recruiter_profile", None), "tier", None) or ""
    )
    is_pro = (
        recruiter_tier in ("pro", "pro_plus", "enterprise") or recruiter.role == "admin"
    )
    _s_candidate = getattr(app, "evaluation_sessions", None)
    s = (
        _s_candidate[0].evaluation_result
        if _s_candidate and _s_candidate[0].evaluation_result
        else None
    )
    score = (s.final_score if s else None) or 0
    cv_snippet = (
        (getattr(app, "cv_text_anonymized", None) or "")[:200]
        if getattr(app, "cv_text_anonymized", None)
        else ""
    )
    interview_state = _interview_cache.get(app.id)
    item = {
        "id": app.id,
        "user_id": app.user_id,
        "full_name": app.full_name or (get_user_name(user) if user else "Unknown"),
        "candidate_name": app.full_name or (get_user_name(user) if user else "Unknown"),
        "email": app.email or (get_user_email(user) if user else ""),
        "declared_role": getattr(app.cv_document, "declared_role", None)
        or getattr(app, "declared_role", None),
        "detected_role": getattr(app, "detected_role", None),
        "score": round(score, 1),
        "overall_score": round(score, 1),
        "cv_score": s.cv_score if s else None,
        "status": app.status,
        "display_status": _display_status(app.status),
        "source": app.source,
        "location": get_user_location(user) if user else None,
        "skills": (
            json.loads(get_user_skills(user)) if user and get_user_skills(user) else []
        )
        if user and get_user_skills(user)
        else [],
        "cv_snippet": cv_snippet,
        "job_title": app.job.title
        if app.job
        else (app.batch_job.title if app.batch_job else "General"),
        "interview_state": interview_state,
        "created_at": app.created_at.isoformat() if app.created_at else None,
        "available_from": None,
    }
    enrich_application_dict(item, app)
    return mask_candidate_data(item, is_pro)


@router.get("/candidates/search")
def search_candidates(
    q: Optional[str] = None,
    skills: Optional[str] = None,
    min_score: Optional[float] = None,
    max_score: Optional[float] = None,
    status: Optional[str] = None,
    role: Optional[str] = None,
    location: Optional[str] = None,
    source: Optional[str] = None,
    has_interview: Optional[bool] = None,
    available_from: Optional[str] = None,
    sort_by: Optional[str] = "overall_score",
    sort_order: Optional[str] = "desc",
    page: int = 1,
    per_page: int = 20,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    repo = MetricsRepository(db)
    company_id = getattr(recruiter, "_company_id", None)
    apps, total_count = repo.search_paginated_candidates(
        company_id=company_id,
        page=page,
        per_page=per_page,
        q=q,
        skills=skills,
        min_score=min_score,
        max_score=max_score,
        status=status,
        role=role,
        location=location,
        source=source,
        has_interview=has_interview,
        sort_by=sort_by or "overall_score",
        sort_order=sort_order or "desc",
    )
    _preload_interviews(apps, db)
    results = [_candidate_to_result(app, recruiter, db) for app in apps]

    return {
        "items": results,
        "pagination": get_pagination_meta(total_count, page, per_page),
    }


@router.post("/candidates/search/advanced")
def advanced_search(
    q: str,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    query = _build_base_query(db, recruiter).outerjoin(
        CandidateProfile, CandidateProfile.user_id == Application.user_id
    )

    and_terms = re.findall(r'(?:^|\s+)AND\s+("[^"]+?"|\S+)', q, re.IGNORECASE)
    or_terms = re.findall(r'(?:^|\s+)OR\s+("[^"]+?"|\S+)', q, re.IGNORECASE)
    not_terms = re.findall(r'(?:^|\s+)NOT\s+("[^"]+?"|\S+)', q, re.IGNORECASE)

    base_term = (
        re.split(r"\s+(?:AND|OR|NOT)\s+", q, maxsplit=1, flags=re.IGNORECASE)[0]
        .strip()
        .strip('"')
    )
    if base_term:
        t = f"%{base_term}%"
        query = query.filter(
            or_(
                Application.full_name.ilike(t),
                Application.declared_role.ilike(t),
                Application.detected_role.ilike(t),
                Application.cv_text_anonymized.ilike(t),
                CandidateProfile.skills.ilike(t),
            )
        )

    for term in and_terms:
        t = f"%{term.strip(chr(34))}%"
        query = query.filter(
            or_(
                Application.full_name.ilike(t),
                Application.declared_role.ilike(t),
                Application.detected_role.ilike(t),
                Application.cv_text_anonymized.ilike(t),
                CandidateProfile.skills.ilike(t),
            )
        )

    if or_terms:
        or_clauses = []
        for term in or_terms:
            t = f"%{term.strip(chr(34))}%"
            or_clauses.append(
                or_(
                    Application.full_name.ilike(t),
                    Application.declared_role.ilike(t),
                    Application.detected_role.ilike(t),
                    Application.cv_text_anonymized.ilike(t),
                    CandidateProfile.skills.ilike(t),
                )
            )
        query = query.filter(or_(*or_clauses))

    for term in not_terms:
        t = f"%{term.strip(chr(34))}%"
        query = query.filter(
            ~or_(
                Application.full_name.ilike(t),
                Application.declared_role.ilike(t),
                Application.detected_role.ilike(t),
                Application.cv_text_anonymized.ilike(t),
                CandidateProfile.skills.ilike(t),
            )
        )

    apps = (
        query.outerjoin(
            EvaluationSession, EvaluationSession.application_id == Application.id
        )
        .outerjoin(
            EvaluationResult,
            EvaluationResult.evaluation_session_id == EvaluationSession.id,
        )
        .order_by(func.coalesce(EvaluationResult.final_score, 0).desc())
        .limit(50)
        .all()
    )
    _preload_interviews(apps, db)
    results = [_candidate_to_result(app, recruiter, db) for app in apps]

    return {"items": results, "total": len(results)}


@router.get("/candidates/search/facets")
def search_facets(
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    repo = MetricsRepository(db)
    company_id = getattr(recruiter, "_company_id", None)
    return repo.get_search_facets(company_id)


@router.get("/candidates/search/export")
def export_candidates_csv(
    q: Optional[str] = None,
    skills: Optional[str] = None,
    min_score: Optional[float] = None,
    status: Optional[str] = None,
    role: Optional[str] = None,
    location: Optional[str] = None,
    source: Optional[str] = None,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    recruiter_tier = (
        getattr(getattr(recruiter, "recruiter_profile", None), "tier", None) or ""
    )
    is_pro = (
        recruiter_tier in ("pro", "pro_plus", "enterprise") or recruiter.role == "admin"
    )
    query = _build_base_query(db, recruiter).outerjoin(
        CandidateProfile, CandidateProfile.user_id == Application.user_id
    )

    if q:
        term = f"%{q}%"
        query = query.filter(
            or_(
                Application.full_name.ilike(term),
                Application.declared_role.ilike(term),
                Application.cv_text_anonymized.ilike(term),
                CandidateProfile.skills.ilike(term),
            )
        )
    if min_score is not None:
        query = query.filter(EvaluationResult.final_score >= min_score)
    if status:
        statuses = [s.strip() for s in status.split(",") if s.strip()]
        query = query.filter(Application.status.in_(statuses))
    if role:
        query = query.filter(
            or_(
                Application.declared_role.ilike(f"%{role}%"),
                Application.detected_role.ilike(f"%{role}%"),
            )
        )
    if location:
        query = query.filter(CandidateProfile.location.ilike(f"%{location}%"))
    if source:
        query = query.filter(Application.source == source)

    apps = (
        query.order_by(EvaluationResult.final_score.desc().nullslast())
        .limit(10000)
        .all()
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "Name",
            "Email",
            "Declared Role",
            "Detected Role",
            "Score",
            "Status",
            "Source",
            "Location",
            "Skills",
            "Job Title",
            "Created At",
        ]
    )

    def _csv_safe(val):
        s = str(val or "")
        if s and s[0] in ("=", "+", "-", "@", "\t", "\r"):
            return "'" + s
        return s

    for app in apps:
        user = app.owner
        _es_csv = app.evaluation_sessions or []
        _er_csv = (
            _es_csv[0].evaluation_result
            if _es_csv and _es_csv[0].evaluation_result
            else None
        )
        _sc = _er_csv
        if is_pro:
            name = app.full_name or (get_user_name(user) if user else "")
            email = app.email or (get_user_email(user) if user else "")
        else:
            real_name = app.full_name or (get_user_name(user) if user else "Unknown")
            name = f"{real_name.split()[0][0]}. Candidate" if real_name else "Candidate"
            email = "hidden@candway.com"
        writer.writerow(
            [
                _csv_safe(name),
                _csv_safe(email),
                _csv_safe(
                    getattr(app.cv_document, "declared_role", None)
                    or getattr(app, "declared_role", None)
                    or ""
                ),
                _csv_safe(getattr(app, "detected_role", None) or ""),
                _sc.final_score if _sc else 0,
                _csv_safe(app.status or ""),
                _csv_safe(app.source or ""),
                _csv_safe(get_user_location(user) if user else ""),
                _csv_safe(get_user_skills(user) if user else ""),
                _csv_safe(
                    app.job.title
                    if app.job
                    else (app.batch_job.title if app.batch_job else "")
                ),
                app.created_at.isoformat() if app.created_at else "",
            ]
        )

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=candidates_export_{date.today().isoformat()}.csv"
        },
    )


def _sign_cv_url(
    cv_file_path: str | None, subject_user_id: int | None, bearer_user_id: int
) -> str | None:
    """Wrap ``cv_file_path`` in a 5-minute signed URL.

    Bug B-29: previously the bare /uploads URL was returned and
    the recruiter got 403 from the ownership check. Now we sign
    it. Returns ``None`` if there's no path to sign or signing fails
    (in which case the recruiter can fall back to the application
    detail page).
    """
    if not cv_file_path or not subject_user_id:
        return cv_file_path
    try:
        from urllib.parse import urlparse

        from backend.signed_url import make_signed_cv_token

        parsed = urlparse(cv_file_path)
        file_path = parsed.path.lstrip("/")
        if file_path.startswith("uploads/"):
            file_path = file_path[len("uploads/") :]
        return make_signed_cv_token(
            file_path=file_path,
            subject_user_id=subject_user_id,
            bearer_user_id=bearer_user_id,
            ttl_seconds=300,
        )["url"]
    except Exception:
        return cv_file_path


class SearchQuery(BaseModel):
    query: str


@router.post("/search")
async def search_candidates_post(
    q: SearchQuery,
    _credit_tx: object = Depends(require_credits("ai_search", credits=2)),
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    # 1. Broad SQL Search (Recall Phase) with company isolation
    search_term = f"%{q.query}%"
    apps = (
        db.query(Application)
        .outerjoin(Job)
        .outerjoin(BatchJob)
        .outerjoin(Application.owner)
        .outerjoin(CandidateProfile, CandidateProfile.user_id == Application.user_id)
        .filter(
            _ownership_filter(db, recruiter),
            or_(
                Application.declared_role.ilike(search_term),
                Application.full_name.ilike(search_term),
                Job.title.ilike(search_term),
                BatchJob.title.ilike(search_term),
                CandidateProfile.skills.ilike(search_term),
                CandidateProfile.bio.ilike(search_term),
                CandidateProfile.headline.ilike(search_term),
            ),
        )
        .limit(15)
        .all()
    )
    if not apps:
        return []

    # 2. Prepare Data for AI Reranking
    candidates_data = []
    seen = set()
    for app in apps:
        if app.candidate_id in seen:
            continue
        seen.add(app.candidate_id)
        user = app.owner
        full_name = app.full_name or (get_user_name(user) if user else "Candidate")
        # safely get analysis summary
        summary = "No summary"
        _a_json = getattr(app, "analysis_json", None)
        if _a_json:
            try:
                analysis = _a_json if isinstance(_a_json, dict) else json.loads(_a_json)
                summary = analysis.get("summary", "No summary")
            except Exception as e:
                logger.error(f"Error parsing analysis JSON for app {app.id}: {e}")
                pass
        candidates_data.append(
            {
                "id": app.id,
                "name": full_name,
                "role": getattr(app.cv_document, "declared_role", None)
                or getattr(app, "declared_role", None),
                "bio_snippet": summary[:300],  # Limit token usage
                "skills": get_user_skills(user) if user else "Unknown",
            }
        )
    if not candidates_data:
        return []

    # 3. AI Reranking (Precision Phase)
    try:
        system_prompt = """You are an expert technical recruiter unique for your ability to match candidates to queries.
        Rank the provided candidates based on their relevance to the search query.
        Return a JSON object with a list 'rankings': [{"id": <app_id>, "relevance": <0-100>, "reason": "<short reason>"}]"""
        user_prompt = f"Query: {q.query}\nCandidates: {json.dumps(candidates_data)}"
        ai_response = await call_groq_cascade(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            json_mode=True,
        )
        rankings = ai_response.get("rankings", [])
        # Map back to results
        ranking_map = {r["id"]: r for r in rankings}
        results = []
        recruiter_tier = (
            getattr(getattr(recruiter, "recruiter_profile", None), "tier", None) or ""
        )
        is_pro = (
            recruiter_tier in ("pro", "pro_plus", "enterprise")
            or recruiter.role == "admin"
        )
        for cand in candidates_data:
            rank_info = ranking_map.get(
                cand["id"], {"relevance": 50, "reason": "Keyword match"}
            )
            item = {
                "id": cand["id"],
                "full_name": cand["name"],
                "candidate_name": cand["name"],
                "match_reason": rank_info.get("reason", "Potential match"),
                "relevance": rank_info.get("relevance", 50),
            }
            results.append(mask_candidate_data(item, is_pro))
        # Sort by relevance
        results.sort(key=lambda x: x["relevance"], reverse=True)
        return results
    except Exception as e:
        logger.error(f"AI Search Failed: {e}")
        # Fallback to basic results
        recruiter_tier = (
            getattr(getattr(recruiter, "recruiter_profile", None), "tier", None) or ""
        )
        is_pro = (
            recruiter_tier in ("pro", "pro_plus", "enterprise")
            or recruiter.role == "admin"
        )
        fallback = []
        for c in candidates_data:
            item = {
                "id": c["id"],
                "full_name": c["name"],
                "candidate_name": c["name"],
                "match_reason": "Keyword match (AI Unavailable)",
                "relevance": 60,
            }
            fallback.append(mask_candidate_data(item, is_pro))
        return fallback


@router.get("/applications")
def get_applications(
    page: int = 1,
    per_page: int = 50,
    q: Optional[str] = None,
    job_id: Optional[int] = None,
    batch_id: Optional[int] = None,
    status: Optional[str] = None,
    min_score: Optional[int] = None,
    role_filter: Optional[str] = None,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    # Build filter conditions as a base query (no joinedload to avoid LIMIT interference)
    base = db.query(Application.id)

    # Ownership logic: candidates assigned to recruiter OR in recruiter's company jobs/campaigns
    company_id = getattr(recruiter, "_company_id", None)
    owned_job_ids = (
        db.query(Job.id)
        .join(CompanyMember, CompanyMember.user_id == Job.recruiter_id)
        .filter(CompanyMember.company_id == company_id, CompanyMember.is_active)
        .all()
    )
    owned_job_ids = [r[0] for r in owned_job_ids]
    owned_batch_ids = (
        db.query(BatchJob.id)
        .join(CompanyMember, CompanyMember.user_id == BatchJob.recruiter_id)
        .filter(CompanyMember.company_id == company_id, CompanyMember.is_active)
        .all()
    )
    owned_batch_ids = [r[0] for r in owned_batch_ids]
    conditions = [Application.assigned_to == recruiter.id]
    if owned_job_ids:
        conditions.append(Application.job_id.in_(owned_job_ids))
    if owned_batch_ids:
        conditions.append(Application.batch_id.in_(owned_batch_ids))

    base = base.filter(or_(*conditions))

    if job_id:
        base = base.filter(Application.job_id == job_id)
    if batch_id:
        base = base.filter(Application.batch_id == batch_id)
    if status and status != "all":
        base = base.filter(Application.status == status)
    if role_filter:
        base = base.filter(Application.declared_role.ilike(f"%{role_filter}%"))
    if q:
        term = f"%{q}%"
        base = base.filter(
            or_(
                Application.full_name.ilike(term),
                Application.email.ilike(term),
            )
        )
    if min_score:
        base = (
            base.outerjoin(
                EvaluationSession, EvaluationSession.application_id == Application.id
            )
            .outerjoin(
                EvaluationResult,
                EvaluationResult.evaluation_session_id == EvaluationSession.id,
            )
            .filter(EvaluationResult.final_score >= min_score)
        )
    base = base.filter(
        ~and_(
            Application.job_id.is_(None),
            Application.batch_id.is_(None),
            Application.status.in_(["active", "pending"]),
        )
    )

    repo = MetricsRepository(db)
    _, total_count, unique_candidate_count = repo.get_paginated_applications(
        company_id=company_id,
        page=page,
        per_page=per_page,
        recruiter_id=recruiter.id,
        job_id=job_id,
        batch_id=batch_id,
        status=status,
        role_filter=role_filter,
        min_score=min_score,
        search=q,
    )
    paginated_ids = [
        r[0]
        for r in base.order_by(Application.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    ]

    apps = (
        db.query(Application)
        .options(
            joinedload(Application.job),
            joinedload(Application.batch_job),
            joinedload(Application.owner),
            joinedload(Application.assignee),
            selectinload(Application.evaluation_sessions).selectinload(
                EvaluationSession.evaluation_result
            ),
            selectinload(Application.cv_document),
        )
        .filter(Application.id.in_(paginated_ids))
        .all()
    )
    # Re-sort to match pagination order
    id_order = {aid: i for i, aid in enumerate(paginated_ids)}
    apps.sort(key=lambda a: id_order.get(a.id, 0))
    results = []
    seen_general_users = set()

    for app in apps:
        # Keep user_id dedup in Python for general applications
        if app.job_id is None and app.batch_id is None:
            if app.user_id in seen_general_users:
                continue
            seen_general_users.add(app.user_id)

        user = app.owner  # FIX PERF-04: use pre-loaded owner (joinedload applied above)
        _es_appget = app.evaluation_sessions or []
        _er_appget = (
            _es_appget[0].evaluation_result
            if _es_appget and _es_appget[0].evaluation_result
            else None
        )
        _sc = _er_appget
        current_score = _sc.final_score if _sc else 0

        def safe_json_get(json_str, key, default=""):
            try:
                if not json_str:
                    return default
                return json.loads(json_str).get(key, default)
            except Exception as e:
                logger.error(f"Error parsing analysis JSON in safe_json_get: {e}")
                return default

        recruiter_tier = (
            getattr(getattr(recruiter, "recruiter_profile", None), "tier", None) or ""
        )
        is_pro = (
            recruiter_tier in ("pro", "pro_plus", "enterprise")
            or recruiter.role == "admin"
        )
        item = {
            "id": app.id,
            "user_id": app.user_id,
            "job_id": app.job_id,
            "batch_id": app.batch_id,
            "candidate_name": app.full_name
            or (get_user_name(user) if user else "Unknown"),
            "candidate_email": app.email or (get_user_email(user) if user else ""),
            "email": app.email or (get_user_email(user) if user else ""),
            "photo_url": getattr(
                getattr(user, "candidate_profile", None), "avatar_url", None
            )
            if user
            else None,
            "job_title": app.job.title
            if app.job
            else (app.batch_job.title if app.batch_job else "General"),
            "batch_name": app.batch_job.title if app.batch_job else None,
            "role": getattr(app.cv_document, "declared_role", None)
            or getattr(app, "declared_role", None),
            "score": current_score,
            "cv_score": _sc.cv_score if _sc else None,
            "status": app.status,
            "display_status": _display_status(app.status),
            "source": app.source or "direct",
            "created_at": app.created_at.strftime("%Y-%m-%d")
            if app.created_at
            else "Today",
            "verdict": _sc.verdict
            if _sc and _sc.verdict
            else (
                (_sc.score_breakdown or {}).get("verdict")
                if _sc and _sc.score_breakdown
                else None
            ),
            "cv_url": _sign_cv_url(
                getattr(app, "cv_file_path", None), app.user_id, recruiter.id
            ),
            "location": get_user_location(user) if user else None,
            "headline": get_user_headline(user) if user else None,
            "interview_state": app.interview_state,
            "interview_progress": app.interview_progress or 0,
            "total_questions": 15,  # Default max turns
            "interview_last_saved": app.interview_last_saved.isoformat()
            if app.interview_last_saved
            else None,
            "analysis_summary": safe_json_get(
                getattr(app, "analysis_json", None), "summary", "No summary"
            ),
            "assigned_to": {"id": app.assignee.id, "name": get_user_name(app.assignee)}
            if app.assignee
            else None,
        }
        enrich_application_dict(item, app)
        results.append(mask_candidate_data(item, is_pro))
    pipeline_stats = {
        "total_applications": total_count,
        "total_candidates": unique_candidate_count,
        "new_this_week": repo.get_new_this_week(company_id, recruiter.id),
        "status_counts": repo.get_status_counts(company_id, recruiter.id),
        "conversion_rates": {
            "app_to_interview": 0,
            "overall": 0,
        },
    }
    funnel = repo.get_funnel(company_id, recruiter.id)
    pipeline_stats["conversion_rates"] = {
        "app_to_interview": round(funnel.interview / funnel.applied * 100, 1)
        if funnel.applied
        else 0,
        "overall": round(funnel.hired / funnel.applied * 100, 1)
        if funnel.applied
        else 0,
    }

    return {
        "items": results,
        "pipeline_stats": pipeline_stats,
        "pagination": {
            **get_pagination_meta(total_count, page, per_page),
            "total_candidates_unique": unique_candidate_count,
        },
    }


@router.get("/talent-pool")
def get_talent_pool(
    query: Optional[str] = None,
    min_score: Optional[int] = 70,
    verified_only: bool = False,
    location: Optional[str] = None,
    page: int = 1,
    per_page: int = 20,
    recruiter: User = Depends(require_pro_tier),
    db: Session = Depends(get_db),
):
    """
    Advanced candidate search for PRO recruiters with server-side pagination.
    """
    from backend.dependencies import get_pagination_meta

    company_id = getattr(recruiter, "_company_id", None)
    db_query = (
        db.query(Application)
        .options(selectinload(Application.evaluation_sessions))
        .filter(Application.company_id == company_id)
        .outerjoin(User, Application.user_id == User.id)
        .outerjoin(CandidateProfile, CandidateProfile.user_id == Application.user_id)
        .order_by(Application.created_at.desc())
    )
    if query:
        # SECURITY FIX: Use proper SQLAlchemy param binding instead of manual string cleaning
        search_term = f"%{query.strip()}%"
        db_query = db_query.filter(
            or_(
                Application.declared_role.ilike(search_term),
                Application.full_name.ilike(search_term),
            )
        )
    if min_score:
        safe_score = max(0, min(100, min_score))
        db_query = (
            db_query.outerjoin(
                EvaluationSession, EvaluationSession.application_id == Application.id
            )
            .outerjoin(
                EvaluationResult,
                EvaluationResult.evaluation_session_id == EvaluationSession.id,
            )
            .filter(EvaluationResult.final_score >= safe_score)
        )

    if verified_only:
        db_query = db_query.filter(
            (CandidateProfile.headline is not None) & (CandidateProfile.headline != "")
            | (CandidateProfile.bio is not None) & (CandidateProfile.bio != "")
        )
    if location:
        # Parameter binding via ILIKE
        loc_term = f"%{location.strip()}%"
        db_query = db_query.filter(CandidateProfile.location.ilike(loc_term))
    # Pagination
    repo = MetricsRepository(db)
    total_count = repo.get_total_candidates(company_id)
    apps = paginate(db_query, page, per_page).all()
    results = []
    seen_candidates = set()
    is_pro = True  # require_pro_tier ensures this
    for app in apps:
        if app.candidate_id in seen_candidates:
            continue
        seen_candidates.add(app.candidate_id)
        _a_json = getattr(app, "analysis_json", None)
        analysis = (
            _a_json
            if isinstance(_a_json, dict)
            else (json.loads(_a_json) if _a_json else {})
        )
        user = app.owner
        display_score = 0
        _es_pool = app.evaluation_sessions or []
        _er_pool = (
            _es_pool[0].evaluation_result
            if _es_pool and _es_pool[0].evaluation_result
            else None
        )
        item = {
            "id": app.id,
            "user_id": app.user_id,
            "full_name": app.full_name or (get_user_name(user) if user else "Unknown"),
            "candidate_name": app.full_name
            or (get_user_name(user) if user else "Unknown"),
            "role": getattr(app.cv_document, "declared_role", None)
            or getattr(app, "declared_role", None),
            "score": display_score,
            "display_status": _display_status(app.status),
            "cv_score": _er_pool.cv_score if _er_pool else None,
            "location": get_user_location(user) if user else "Tunis, TN",
            "photo_url": _candidate_photo_url(app, user),
            "analysis": {
                "strengths": analysis.get("strengths", []),
                "summary": analysis.get("summary", ""),
            },
        }
        results.append(mask_candidate_data(item, is_pro))
    return {
        "items": results,
        "pagination": get_pagination_meta(total_count, page, per_page),
    }


@router.get("/candidates/list")
def get_candidates_list(
    page: int = 1,
    per_page: int = 50,
    q: Optional[str] = None,
    status: Optional[str] = None,
    job_id: Optional[int] = None,
    min_score: Optional[int] = None,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    company_id = getattr(recruiter, "_company_id", None)
    repo = MetricsRepository(db)
    apps, total_count = repo.get_paginated_candidates(
        company_id=company_id,
        page=page,
        per_page=per_page,
        recruiter_id=recruiter.id,
        status=status,
        job_id=job_id,
        min_score=min_score,
        search=q,
    )
    total_apps_count = total_count

    recruiter_tier = (
        getattr(getattr(recruiter, "recruiter_profile", None), "tier", None) or ""
    )
    is_pro = (
        recruiter_tier in ("pro", "pro_plus", "enterprise") or recruiter.role == "admin"
    )
    app_ids = [app.id for app in apps]
    interview_map = {}
    if app_ids:
        from backend.database import Interview

        interviews = (
            db.query(Interview)
            .filter(Interview.application_id.in_(app_ids))
            .order_by(Interview.scheduled_time.desc())
            .all()
        )
        for iv in interviews:
            if iv.application_id not in interview_map:
                interview_map[iv.application_id] = {
                    "status": iv.status,
                    "type": iv.type,
                    "scheduled_time": iv.scheduled_time.strftime("%Y-%m-%dT%H:%M:%S")
                    if iv.scheduled_time
                    else None,
                    "id": iv.id,
                }
    results = []
    for app in apps:
        user = app.owner
        _es_list2 = app.evaluation_sessions or []
        _er_list2 = (
            _es_list2[0].evaluation_result
            if _es_list2 and _es_list2[0].evaluation_result
            else None
        )
        s_ent = _er_list2
        current_score = s_ent.final_score if s_ent else 0
        score_entity = (
            {
                "cv_score": s_ent.cv_score if s_ent else None,
                "final_score": s_ent.final_score if s_ent else None,
                "verdict": s_ent.verdict if s_ent else None,
                "fraud_score": s_ent.fraud_score if s_ent else None,
                "human_integrity_score": s_ent.human_integrity_score if s_ent else None,
                "rubric_coverage_pct": s_ent.rubric_coverage_pct if s_ent else None,
            }
            if s_ent
            else None
        )
        item = {
            "id": app.id,
            "user_id": app.user_id,
            "candidate_id": app.candidate_id,
            "job_id": app.job_id,
            "candidate_name": app.full_name
            or (get_user_name(user) if user else "Unknown"),
            "candidate_email": app.email or (get_user_email(user) if user else ""),
            "email": app.email or (get_user_email(user) if user else ""),
            "photo_url": _candidate_photo_url(app, user),
            "job_title": app.job.title
            if app.job
            else (app.batch_job.title if app.batch_job else "General"),
            "role": getattr(app.cv_document, "declared_role", None)
            or getattr(app, "declared_role", None),
            "score": current_score,
            "cv_score": s_ent.cv_score if s_ent else None,
            "score_entity": score_entity,
            "status": app.status,
            "display_status": _display_status(app.status),
            "created_at": app.created_at.strftime("%Y-%m-%d")
            if app.created_at
            else "Today",
            "location": get_user_location(user) if user else None,
            "headline": get_user_headline(user) if user else None,
            "source": app.source or "direct",
            "skills": _candidate_skills(app, user),
            "best_score": max(
                [n for n in (current_score, score_entity.get("cv_score") if score_entity else None) if n is not None] or [0]
            ),
            "last_activity": _candidate_last_activity(app, interview_map),
            "interview_state": app.interview_state,
            "latest_interview": interview_map.get(app.id),
            "assigned_to": {"id": app.assignee.id, "name": get_user_name(app.assignee)}
            if app.assignee
            else None,
            "is_declined": app.declined_at is not None
            or app.decline_reason is not None,
            "decline_reason": app.decline_reason,
        }
        results.append(mask_candidate_data(item, is_pro))
    return {
        "items": results,
        "pagination": {
            **get_pagination_meta(total_count, page, per_page),
            "total_applications": total_apps_count,
        },
    }


@router.get("/candidates/{candidate_id}")
def get_candidate_profile(
    candidate_id: int,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    """Candidate-scoped profile — resolves the person (Candidate row) and
    returns their full profile plus every application they have.

    Keyed by candidate_id, NOT application_id, so recruiters reach the
    person even when they have multiple applications (105, 99, ...).
    """
    company_id = getattr(recruiter, "_company_id", None)
    candidate = (
        db.query(Candidate)
        .filter(
            Candidate.id == candidate_id,
            Candidate.deleted_at.is_(None),
        )
        .first()
    )
    if candidate is None or (
        company_id is not None and candidate.company_id != company_id
    ):
        raise HTTPException(status_code=404, detail="Candidate not found")

    apps = (
        db.query(Application)
        .options(joinedload(Application.job), joinedload(Application.batch_job))
        .filter(
            Application.candidate_id == candidate.id,
            Application.company_id == company_id,
        )
        .order_by(Application.created_at.desc())
        .all()
    )

    def _score_for(app):
        _es = app.evaluation_sessions or []
        _er = _es[0].evaluation_result if _es and _es[0].evaluation_result else None
        if _er and _er.final_score is not None:
            return _er.final_score
        if _er and _er.cv_score is not None:
            return _er.cv_score
        return None

    best_app = max(apps, key=lambda a: (_score_for(a) is not None, _score_for(a) or 0, a.created_at or date.min)) if apps else None

    applications = [
        {
            "id": app.id,
            "job_id": app.job_id,
            "job_title": app.job.title
            if app.job
            else (app.batch_job.title if app.batch_job else "General"),
            "status": app.status,
            "display_status": _display_status(app.status),
            "score": _score_for(app),
            "source": app.source or "direct",
            "created_at": app.created_at.strftime("%Y-%m-%d")
            if app.created_at
            else None,
        }
        for app in apps
    ]

    profile = {
        "candidate_id": candidate.id,
        "candidate": {
            "id": candidate.id,
            "full_name": candidate.full_name,
            "email": candidate.email,
            "phone": candidate.phone,
            "photo_url": candidate.photo_url,
            "headline": candidate.headline,
            "location": candidate.location,
            "skills": candidate.skills,
        },
        "application_count": len(apps),
        "best_application_id": best_app.id if best_app else None,
        "applications": applications,
    }

    if best_app:
        from backend.routers.recruiter_candidates.applications import (
            get_application_details,
        )

        detail = get_application_details(best_app.id, recruiter, db)
        if isinstance(detail, dict):
            detail.pop("applications", None)
            profile.update(detail)

    return profile
