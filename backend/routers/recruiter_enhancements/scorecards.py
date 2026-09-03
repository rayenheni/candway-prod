import json
from datetime import UTC, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import desc, or_
from sqlalchemy.orm import Session, joinedload

from backend.authz import (
    get_application_for_recruiter,
    get_interview_for_recruiter,
    get_scorecard_for_recruiter,
)
from backend.database import (
    InterviewFeedback,
    InterviewScorecard,
    Job,
    ScorecardSubmission,
    User,
)
from backend.dependencies import get_db, require_recruiter
from backend.security import sanitize_content
from backend.tenant import get_current_company_id

router = APIRouter(tags=["Recruiter Enhancements - Scorecards"])


def _utcnow():
    return datetime.now(UTC).replace(tzinfo=None)


class ScorecardCreate(BaseModel):
    role_type: str
    name: str
    description: Optional[str] = None
    criteria_json: list


class ScorecardSubmissionCreate(BaseModel):
    scorecard_id: int
    interview_id: Optional[int] = None
    application_id: int
    scores_json: dict
    recommendation: Optional[str] = None
    notes: Optional[str] = None


@router.get("/scorecards")
def get_scorecards(
    role_type: Optional[str] = None,
    recruiter: User = Depends(require_recruiter),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db),
):
    query = db.query(InterviewScorecard).filter(
        or_(
            InterviewScorecard.company_id == company_id,
            InterviewScorecard.is_system,
        ),
        InterviewScorecard.is_active,
    )

    if role_type:
        query = query.filter(InterviewScorecard.role_type == role_type)

    scorecards = query.order_by(
        desc(InterviewScorecard.is_system), InterviewScorecard.name
    ).all()

    return [
        {
            "id": s.id,
            "role_type": s.role_type,
            "name": s.name,
            "description": s.description,
            "criteria": json.loads(s.criteria_json),
            "is_system": s.is_system,
            "created_at": s.created_at.isoformat(),
        }
        for s in scorecards
    ]


@router.post("/scorecards", status_code=status.HTTP_201_CREATED)
def create_scorecard(
    data: ScorecardCreate,
    recruiter: User = Depends(require_recruiter),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db),
):
    scorecard = InterviewScorecard(
        company_id=company_id,
        recruiter_id=recruiter.id,
        role_type=sanitize_content(data.role_type),
        name=sanitize_content(data.name),
        description=sanitize_content(data.description) if data.description else None,
        criteria_json=json.dumps(data.criteria_json),
    )
    db.add(scorecard)
    db.commit()
    db.refresh(scorecard)

    return {"success": True, "scorecard_id": scorecard.id}


@router.post("/scorecards/submit", status_code=status.HTTP_201_CREATED)
def submit_scorecard(
    data: ScorecardSubmissionCreate,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    """Submit a completed scorecard evaluation"""
    scorecard = get_scorecard_for_recruiter(data.scorecard_id, recruiter, db)

    # Enforce application tenant isolation before creating the submission.
    # A valid scorecard must never be usable against another company's application.
    application = get_application_for_recruiter(
        data.application_id,
        recruiter,
        db,
    )

    # Calculate weighted overall score
    criteria = json.loads(scorecard.criteria_json)
    scores = data.scores_json
    total_weight = 0
    weighted_sum = 0

    for criterion in criteria:
        name = criterion.get("name", "").lower().replace(" ", "_")
        weight = criterion.get("weight", 1)
        max_score = criterion.get("max_score", 5)
        raw_score = scores.get(name, 0)

        normalized = (raw_score / max_score) * 100 if max_score > 0 else 0
        weighted_sum += normalized * weight
        total_weight += weight

    overall = (weighted_sum / total_weight) if total_weight > 0 else 0

    submission = ScorecardSubmission(
        scorecard_id=data.scorecard_id,
        interview_id=data.interview_id,
        application_id=data.application_id,
        evaluator_id=recruiter.id,
        company_id=scorecard.company_id,
        scores_json=json.dumps(data.scores_json),
        overall_score=round(overall, 1),
        recommendation=data.recommendation,
        notes=data.notes,
    )
    db.add(submission)

    # Update interview feedback if interview exists
    if data.interview_id:
        interview = get_interview_for_recruiter(data.interview_id, recruiter, db)
        if interview:
            interview.status = "completed"
            interview.completed_at = _utcnow()

            # Create InterviewFeedback from scorecard
            rec_to_feedback = {
                "strong_yes": "strong_yes",
                "yes": "yes",
                "maybe": "maybe",
                "no": "no",
                "strong_no": "strong_no",
            }
            fb = InterviewFeedback(
                interview_id=data.interview_id,
                interviewer_id=recruiter.id,
                company_id=interview.company_id,
                overall_rating=min(5, max(1, round(overall / 20))),
                recommendation=rec_to_feedback.get(data.recommendation, "maybe"),
                additional_notes=data.notes,
            )
            db.add(fb)

    db.commit()
    db.refresh(submission)

    return {"success": True, "submission_id": submission.id, "overall_score": overall}


@router.get("/scorecards/{scorecard_id}")
def get_scorecard(
    scorecard_id: int,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    s = get_scorecard_for_recruiter(scorecard_id, recruiter, db)
    return {
        "id": s.id,
        "role_type": s.role_type,
        "name": s.name,
        "description": s.description,
        "criteria": json.loads(s.criteria_json),
        "is_system": s.is_system,
        "is_active": s.is_active,
        "created_at": s.created_at.isoformat(),
    }


@router.put("/scorecards/{scorecard_id}")
def update_scorecard(
    scorecard_id: int,
    data: ScorecardCreate,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    s = get_scorecard_for_recruiter(scorecard_id, recruiter, db)
    if s.is_system:
        raise HTTPException(status_code=403, detail="Cannot modify system scorecard")
    s.role_type = data.role_type
    s.name = data.name
    s.description = data.description
    s.criteria_json = json.dumps(data.criteria_json)
    db.commit()
    db.refresh(s)
    return {"success": True, "scorecard_id": s.id}


@router.delete("/scorecards/{scorecard_id}")
def delete_scorecard(
    scorecard_id: int,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    s = get_scorecard_for_recruiter(scorecard_id, recruiter, db)
    if s.is_system:
        raise HTTPException(status_code=403, detail="Cannot delete system scorecard")
    db.delete(s)
    db.commit()
    return {"success": True}


@router.get("/scorecards/by-role/{role_type}")
def get_scorecards_by_role(
    role_type: str,
    recruiter: User = Depends(require_recruiter),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db),
):
    scorecards = (
        db.query(InterviewScorecard)
        .filter(
            or_(
                InterviewScorecard.company_id == company_id,
                InterviewScorecard.is_system,
            ),
            InterviewScorecard.role_type == role_type,
            InterviewScorecard.is_active,
        )
        .order_by(desc(InterviewScorecard.is_system), InterviewScorecard.name)
        .all()
    )
    return [
        {
            "id": s.id,
            "role_type": s.role_type,
            "name": s.name,
            "description": s.description,
            "criteria": json.loads(s.criteria_json),
            "is_system": s.is_system,
        }
        for s in scorecards
    ]


@router.post("/scorecards/from-rubric/{job_id}")
def generate_scorecard_from_rubric(
    job_id: int,
    recruiter: User = Depends(require_recruiter),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db),
):
    from backend.database import Rubric

    job = db.query(Job).filter(Job.id == job_id, Job.company_id == company_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    rubric = db.query(Rubric).filter(Rubric.job_id == job_id, Rubric.is_active).first()
    if not rubric:
        raise HTTPException(status_code=404, detail="No rubric found for this job")
    raw = rubric.criteria_json or ""
    rubric_data = (
        json.loads(raw)
        if isinstance(raw, str) and raw
        else (raw if isinstance(raw, dict) else {})
    )
    criteria = []
    categories = rubric_data.get("categories", rubric_data.get("sections", []))
    for cat in categories:
        criteria.append(
            {
                "name": cat.get("name", "Category"),
                "weight": cat.get("weight", 1),
                "max_score": cat.get("max_score", 5),
                "questions": cat.get("questions", cat.get("criteria", [])),
            }
        )
    if not criteria:
        skills = rubric_data.get("skills", rubric_data.get("required_skills", []))
        for skill in skills:
            criteria.append(
                {
                    "name": skill
                    if isinstance(skill, str)
                    else skill.get("name", "Skill"),
                    "weight": 1,
                    "max_score": 5,
                    "questions": [],
                }
            )
    if not criteria:
        criteria = [
            {"name": "Overall Fit", "weight": 1, "max_score": 5, "questions": []}
        ]
    scorecard = InterviewScorecard(
        company_id=company_id,
        recruiter_id=recruiter.id,
        role_type=job.title.lower().replace(" ", "_"),
        name=f"{job.title} Scorecard",
        description=f"Auto-generated from rubric for {job.title}",
        criteria_json=json.dumps(criteria),
    )
    db.add(scorecard)
    db.commit()
    db.refresh(scorecard)
    return {
        "success": True,
        "scorecard_id": scorecard.id,
        "criteria_count": len(criteria),
    }


@router.get("/scorecards/submissions/{application_id}")
def get_scorecard_submissions(
    application_id: int,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    """Get all scorecard submissions for an application"""
    get_application_for_recruiter(application_id, recruiter, db)
    submissions = (
        db.query(ScorecardSubmission)
        .options(
            joinedload(ScorecardSubmission.evaluator),
            joinedload(ScorecardSubmission.scorecard),
        )
        .filter(ScorecardSubmission.application_id == application_id)
        .order_by(desc(ScorecardSubmission.submitted_at))
        .all()
    )

    return [
        {
            "id": s.id,
            "scorecard_name": s.scorecard.name,
            "evaluator_name": s.evaluator.name if s.evaluator else "Unknown",
            "scores": json.loads(s.scores_json),
            "overall_score": s.overall_score,
            "recommendation": s.recommendation,
            "notes": s.notes,
            "submitted_at": s.submitted_at.isoformat(),
        }
        for s in submissions
    ]
