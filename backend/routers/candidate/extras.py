import json
import logging
from datetime import datetime

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session, selectinload

from backend.database import Application, AuditLog, EvaluationSession, User
from backend.dependencies import get_current_user, get_db
from backend.enums import canonicalize_status
from backend.profile_helpers import get_user_email, get_user_name

router = APIRouter(tags=["candidate"])

logger = logging.getLogger(__name__)


@router.get("/badges")
def get_candidate_badges(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
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
    scores = []
    for a in apps:
        _er = (
            a.evaluation_sessions[0].evaluation_result
            if a.evaluation_sessions and a.evaluation_sessions[0].evaluation_result
            else None
        )
        if _er:
            scores.append(_er.final_score)
    max_score = max(scores) if scores else 0
    num_interviews = len(scores)

    sorted_apps_by_date = sorted(apps, key=lambda x: x.created_at or datetime.min)

    if num_interviews >= 1:
        first_app = sorted_apps_by_date[0] if sorted_apps_by_date else None
        badges.append(
            {
                "id": "first_steps",
                "name": "First Steps",
                "icon": "fa-shoe-prints",
                "description": "Completed your first AI interview",
                "color": "slate",
                "earned_date": first_app.created_at.isoformat()
                if first_app and first_app.created_at
                else None,
            }
        )

    if max_score >= 60:
        star_app = next(
            (
                a
                for a in sorted_apps_by_date
                if a.evaluation_sessions
                and a.evaluation_sessions[0].evaluation_result
                and a.evaluation_sessions[0].evaluation_result.final_score
                and a.evaluation_sessions[0].evaluation_result.final_score >= 60
            ),
            None,
        )
        badges.append(
            {
                "id": "rising_star",
                "name": "Rising Star",
                "icon": "fa-star",
                "description": "Scored 60+ in an AI interview",
                "color": "blue",
                "earned_date": star_app.created_at.isoformat()
                if star_app and star_app.created_at
                else None,
            }
        )

    if max_score >= 80:
        expert_app = next(
            (
                a
                for a in sorted_apps_by_date
                if a.evaluation_sessions
                and a.evaluation_sessions[0].evaluation_result
                and a.evaluation_sessions[0].evaluation_result.final_score
                and a.evaluation_sessions[0].evaluation_result.final_score >= 80
            ),
            None,
        )
        badges.append(
            {
                "id": "expert",
                "name": "Expert Performer",
                "icon": "fa-award",
                "description": "Scored 80+ in an AI interview",
                "color": "purple",
                "earned_date": expert_app.created_at.isoformat()
                if expert_app and expert_app.created_at
                else None,
            }
        )

    if max_score >= 90:
        super_app = next(
            (
                a
                for a in sorted_apps_by_date
                if a.evaluation_sessions
                and a.evaluation_sessions[0].evaluation_result
                and a.evaluation_sessions[0].evaluation_result.final_score
                and a.evaluation_sessions[0].evaluation_result.final_score >= 90
            ),
            None,
        )
        badges.append(
            {
                "id": "superstar",
                "name": "Superstar",
                "icon": "fa-crown",
                "description": "Scored 90+ — top talent tier",
                "color": "amber",
                "earned_date": super_app.created_at.isoformat()
                if super_app and super_app.created_at
                else None,
            }
        )

    if num_interviews >= 3:
        badges.append(
            {
                "id": "interview_pro",
                "name": "Interview Pro",
                "icon": "fa-microphone",
                "description": f"Completed {num_interviews} AI interviews",
                "color": "emerald",
                "earned_date": sorted_apps_by_date[2].created_at.isoformat()
                if len(sorted_apps_by_date) >= 3 and sorted_apps_by_date[2].created_at
                else None,
            }
        )

    if max_score >= 100:
        badges.append(
            {
                "id": "perfect",
                "name": "Perfect Score",
                "icon": "fa-gem",
                "description": "Achieved a flawless 100/100 score",
                "color": "rose",
                "earned_date": None,
            }
        )

    return {
        "badges": badges,
        "total_interviews": num_interviews,
        "highest_score": max_score,
    }


@router.get("/export")
def export_data(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    audit = AuditLog(
        user_id=current_user.id,
        action="data_export",
        target_id=str(current_user.id),
        details="User requested full data export (GDPR compliance)",
        ip_address="system",
    )
    db.add(audit)
    db.commit()
    apps = db.query(Application).filter(Application.user_id == current_user.id).all()
    apps_data = []
    for app in apps:
        apps_data.append(
            {
                "id": app.id,
                "date": app.created_at.isoformat(),
                "role": app.declared_role,
                "score": app.evaluation_sessions[0].evaluation_result.final_score
                if app.evaluation_sessions
                and app.evaluation_sessions[0].evaluation_result
                else None,
                "verdict": app.evaluation_sessions[0].evaluation_result.verdict
                if app.evaluation_sessions
                and app.evaluation_sessions[0].evaluation_result
                and hasattr(app.evaluation_sessions[0].evaluation_result, "verdict")
                else None,
                "analysis": json.loads(app.analysis_json) if app.analysis_json else {},
            }
        )
    return {
        "user_info": {
            "name": get_user_name(current_user),
            "email": get_user_email(current_user),
            "joined": current_user.created_at.isoformat(),
        },
        "applications": apps_data,
    }


@router.post("/career/roadmap")
async def generate_career_roadmap_shim(
    payload: dict = Body(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from backend.routers.career import generate_and_save_roadmap

    target_role = payload.get("target_role", "Professional")
    current_skills = payload.get("current_skills", [])
    data = await generate_and_save_roadmap(
        user_id=current_user.id,
        target_role=target_role,
        current_skills=current_skills,
        db=db,
    )
    if not data:
        raise HTTPException(status_code=500, detail="AI failed to generate roadmap")
    return data


@router.get("/debug/application/{app_id}")
def debug_application_status(
    app_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from backend.config import get_settings

    settings = get_settings()
    if not settings.debug and current_user.role != "admin":
        raise HTTPException(
            status_code=403, detail="Debug endpoints are disabled in production"
        )

    app = db.query(Application).filter(Application.id == app_id).first()
    if not app:
        return {
            "found": False,
            "message": f"Application {app_id} does not exist in the database.",
        }

    is_admin = current_user.role == "admin"
    if app.user_id and app.user_id != current_user.id and not is_admin:
        raise HTTPException(status_code=404, detail="Application not found")
    if not app.user_id and not is_admin:
        app_email = (app.email or "").strip().lower()
        if app_email != current_user.email.strip().lower():
            raise HTTPException(status_code=404, detail="Application not found")

    owner_email = (
        get_user_email(current_user) if app.user_id == current_user.id else "Restricted"
    )
    is_owned_by_you = app.user_id == current_user.id

    return {
        "found": True,
        "id": app.id,
        "status": canonicalize_status(app.status),
        "is_owned_by_you": is_owned_by_you,
        "owner_email": owner_email,
        "linked_email": app.email if is_owned_by_you or is_admin else None,
        "your_email": get_user_email(current_user),
        "user_id": app.user_id,
        "your_id": current_user.id,
    }


@router.get("/debug/history/count")
def debug_history_count(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    from backend.config import get_settings

    settings = get_settings()
    if not settings.debug and current_user.role != "admin":
        raise HTTPException(
            status_code=403, detail="Debug endpoints are disabled in production"
        )

    apps = db.query(Application).filter(Application.user_id == current_user.id).all()
    return {"count": len(apps), "ids": [a.id for a in apps]}
