import json
from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.authz import get_application_for_recruiter
from backend.database import (
    Comment,
    TaggedNote,
    User,
)
from backend.dependencies import get_db, require_recruiter
from backend.profile_helpers import get_user_name

router = APIRouter(tags=["Recruiter Enhancements - Previews"])


class HoverPreviewResponse(BaseModel):
    id: int
    candidate_name: str
    email: str
    role: str
    overall_score: float
    cv_score: float
    trust_score: float
    interview_state: str
    interview_progress: int
    total_questions: int
    skills: List[str]
    strengths: List[str]
    weaknesses: List[str]
    summary: str
    created_at: str
    status: str
    assigned_to: Optional[dict]
    tags: List[str]
    notes_count: int
    comments_count: int


@router.get("/hover-preview/{app_id}")
def get_hover_preview(
    app_id: int,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    """Rich preview data for hover cards on pipeline"""
    app = get_application_for_recruiter(app_id, recruiter, db)

    # Parse analysis data
    analysis = {}
    try:
        if app.analysis_json:
            analysis = json.loads(app.analysis_json)
    except Exception:
        pass

    # Get skills
    skills = []
    owner_profile = getattr(app.owner, "candidate_profile", None) if app.owner else None
    owner_skills = owner_profile.skills if owner_profile else None
    if app.owner and owner_skills:
        try:
            skills = (
                json.loads(owner_skills)
                if isinstance(owner_skills, str)
                else owner_skills
            )
        except Exception:
            skills = [s.strip() for s in str(owner_skills).split(",")]

    # Calculate trust score from proctoring violations
    _iv_preview = app.evaluation_sessions[0] if app.evaluation_sessions else None
    _pc_preview = getattr(_iv_preview, "proctoring_violations", None)
    trust_score = 100.0
    try:
        if _pc_preview:
            violations = json.loads(_pc_preview)
            for v in violations:
                if isinstance(v, dict):
                    severity = v.get("severity", "medium")
                    penalty = {"low": 5, "medium": 10, "high": 20}.get(severity, 10)
                    trust_score -= penalty
            trust_score = max(0, trust_score)
    except Exception:
        pass

    # Get tagged notes count
    notes_count = (
        db.query(TaggedNote)
        .filter(TaggedNote.application_id == app_id, not TaggedNote.is_resolved)
        .count()
    )

    # Get comments count
    comments_count = (
        db.query(Comment)
        .filter(Comment.application_id == app_id, Comment.deleted_at.is_(None))
        .count()
    )

    # Get tags from notes
    tags = set()
    all_notes = db.query(TaggedNote).filter(TaggedNote.application_id == app_id).all()
    for note in all_notes:
        if note.tags:
            try:
                note_tags = json.loads(note.tags)
                tags.update(note_tags)
            except Exception:
                pass

    # Total questions
    total_questions = 15
    try:
        if app.interview_questions:
            questions = json.loads(app.interview_questions)
            if isinstance(questions, list):
                total_questions = len(questions)
    except Exception:
        pass

    recruiter_tier = (
        getattr(getattr(recruiter, "recruiter_profile", None), "tier", None) or ""
    )
    is_pro = (
        recruiter_tier in ("pro", "pro_plus", "enterprise") or recruiter.role == "admin"
    )

    _es_preview = app.evaluation_sessions or []
    _er_preview = (
        _es_preview[0].evaluation_result
        if _es_preview and _es_preview[0].evaluation_result
        else None
    )

    return {
        "id": app.id,
        "candidate_name": app.full_name
        or (get_user_name(app.owner) if app.owner else "Unknown")
        if is_pro
        else "Anonymous Candidate",
        "email": app.email if is_pro else "hidden@candway.com",
        "role": app.declared_role or "General",
        "overall_score": (_er_preview.final_score if _er_preview else None) or 0,
        "cv_score": (_er_preview.cv_score if _er_preview else None) or 0,
        "trust_score": round(trust_score, 1),
        "interview_state": app.interview_state or "not_started",
        "interview_progress": app.interview_progress or 0,
        "total_questions": total_questions,
        "skills": skills[:10] if is_pro else [],
        "strengths": analysis.get("strengths", [])[:5] if is_pro else [],
        "weaknesses": analysis.get("weaknesses", [])[:5] if is_pro else [],
        "summary": analysis.get("summary", "No analysis available")[:200]
        if is_pro
        else "Upgrade to view details",
        "created_at": app.created_at.strftime("%b %d, %Y")
        if app.created_at
        else "Recently",
        "status": app.status,
        "assigned_to": {"id": app.assignee.id, "name": app.assignee.name}
        if app.assignee
        else None,
        "tags": list(tags),
        "notes_count": notes_count,
        "comments_count": comments_count,
    }
