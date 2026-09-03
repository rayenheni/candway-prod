import json
from datetime import UTC, datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import and_, desc
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.database import (
    ActivityLog,
    Application,
    BatchJob,
    CandidateRating,
    Comment,
    Interview,
    InterviewParticipant,
    Job,
    TeamMember,
    User,
)
from backend.dependencies import (
    get_db,
    pwd_context,
    require_recruiter,
)
from backend.email_utils import send_email
from backend.logger import logger
from backend.models.profile import RecruiterProfile
from backend.profile_helpers import get_user_email, get_user_name
from backend.tenant import get_current_company_id

router = APIRouter(tags=["Recruiter Collaboration - Team"])


def _utcnow():
    return datetime.now(UTC).replace(tzinfo=None)


def log_activity(
    db: Session,
    user_id: int,
    action: str,
    application_id: int = None,
    details: dict = None,
    company_id: int = None,
):
    try:
        activity = ActivityLog(
            user_id=user_id,
            application_id=application_id,
            company_id=company_id,
            action=action,
            details=json.dumps(details) if details else None,
        )
        db.add(activity)
        db.flush()
    except Exception as e:
        logger.error(f"Failed to log activity: {e}")


def format_activity(activity: ActivityLog, db: Session) -> dict:
    user = db.query(User).filter(User.id == activity.user_id).first()

    try:
        details = json.loads(activity.details) if activity.details else {}
    except Exception:
        details = {}

    return {
        "id": activity.id,
        "user_name": get_user_name(user) if user else "Unknown",
        "action": activity.action,
        "details": details,
        "created_at": activity.created_at,
    }


class AddTeamMemberRequest(BaseModel):
    email: Optional[str] = None
    name: Optional[str] = None
    role: Optional[str] = "member"
    user_id: Optional[int] = None


class ChangeRoleRequest(BaseModel):
    role: str


class ReassignCandidatesRequest(BaseModel):
    to_member_id: int
    application_ids: Optional[List[int]] = None


class TeamMemberResponse(BaseModel):
    id: int
    member_id: int
    member_name: str
    member_email: str
    role: str
    status: str
    added_at: datetime

    model_config = ConfigDict(from_attributes=True)


@router.post("/team", status_code=status.HTTP_201_CREATED)
def add_team_member(
    data: AddTeamMemberRequest,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    member = None

    if data.user_id:
        member = db.query(User).filter(User.id == data.user_id).first()
        if not member:
            raise HTTPException(status_code=404, detail="User not found")
    elif data.email:
        member = db.query(User).filter(User.email == data.email).first()

    if member:
        if member.id == recruiter.id:
            raise HTTPException(
                status_code=400, detail="You cannot add yourself to your team"
            )
        existing = (
            db.query(TeamMember)
            .filter(
                and_(
                    TeamMember.owner_id == recruiter.id,
                    TeamMember.member_id == member.id,
                    TeamMember.status == "active",
                )
            )
            .first()
        )
        if existing:
            raise HTTPException(status_code=400, detail="User is already a team member")
        member_id = member.id
        member_name = get_user_name(member) or get_user_email(member).split("@")[0]
        member_email = get_user_email(member)
    else:
        if not data.email or not data.name:
            raise HTTPException(
                status_code=400,
                detail="Email and name are required to create a new team member account",
            )

        import secrets
        import string

        existing_user = db.query(User).filter(User.email == data.email).first()
        if existing_user:
            raise HTTPException(
                status_code=400,
                detail="A user with this email already exists. Search for them instead.",
            )

        temp_password = "".join(
            secrets.choice(string.ascii_letters + string.digits) for _ in 12
        )
        hashed_pw = pwd_context.hash(temp_password)

        new_user = User(
            email=data.email,
            name=data.name,
            hashed_password=hashed_pw,
            role="recruiter",
            tier="free",
            email_verified=True,
        )
        db.add(new_user)
        db.flush()
        member_id = new_user.id
        member_name = data.name
        member_email = data.email

        # Create RecruiterProfile for the new user
        recruiter_profile = RecruiterProfile(
            user_id=member_id,
            name=data.name,
            email=data.email,
        )
        db.add(recruiter_profile)
        db.flush()

        try:
            settings = get_settings()
            login_url = f"{settings.frontend_url}/login/recruiter"
            subject = "You've been added to a Candway team!"
            body = f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <h2 style="color: #4f46e5;">Welcome to the team!</h2>
                <p><strong>{get_user_name(recruiter)}</strong> has added you to their recruitment team on Candway.</p>
                <div style="background: #f3f4f6; padding: 15px; border-left: 4px solid #4f46e5; margin: 20px 0;">
                    <p style="margin: 0;"><strong>Your login:</strong></p>
                    <p style="margin: 4px 0 0;"><strong>Email:</strong> {data.email}</p>
                    <p style="margin: 4px 0 0;"><strong>Temporary password:</strong> {temp_password}</p>
                    <p style="margin: 8px 0 0; font-size: 12px; color: #6b7280;">Please change your password after first login.</p>
                </div>
                <a href="{login_url}" style="display: inline-block; background: #4f46e5; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; margin: 20px 0;">
                    Login to Candway
                </a>
            </div>
            """
            send_email(data.email, subject, body)
            logger.info(f"Invitation email sent to {data.email}")
        except Exception as e:
            logger.error(f"Failed to send invitation email: {e}")

    team_member = TeamMember(
        owner_id=recruiter.id,
        member_id=member_id,
        company_id=getattr(recruiter, "_company_id", None),
        role=data.role or "member",
        status="active",
    )
    db.add(team_member)
    db.commit()
    db.refresh(team_member)

    log_activity(
        db,
        recruiter.id,
        "team_member_added",
        details={
            "member_id": member_id,
            "member_email": member_email,
            "role": team_member.role,
            "new_account": not bool(member),
        },
        company_id=getattr(recruiter, "_company_id", None),
    )

    logger.info(
        f"Added team member {member_email} to recruiter {get_user_email(recruiter)}"
    )

    return {
        "success": True,
        "member": {
            "id": team_member.id,
            "member_id": member_id,
            "member_name": member_name,
            "member_email": member_email,
            "role": team_member.role,
            "new_account": not bool(member),
        },
    }


@router.get("/team")
def get_team_members(
    recruiter: User = Depends(require_recruiter), db: Session = Depends(get_db)
):
    members = (
        db.query(TeamMember)
        .filter(
            and_(TeamMember.owner_id == recruiter.id, TeamMember.status == "active")
        )
        .all()
    )

    if not members:
        return []

    member_ids = [m.member_id for m in members]
    users = db.query(User).filter(User.id.in_(member_ids)).all()
    user_map = {u.id: u for u in users}

    result = []
    for m in members:
        member_user = user_map.get(m.member_id)
        result.append(
            {
                "id": m.id,
                "member_id": m.member_id,
                "member_name": get_user_name(member_user) if member_user else "Unknown",
                "member_email": get_user_email(member_user) if member_user else "",
                "member_avatar": getattr(
                    getattr(member_user, "recruiter_profile", None), "avatar_url", None
                )
                if member_user
                else None,
                "role": m.role,
                "status": m.status,
                "added_at": m.added_at,
            }
        )

    return result


@router.delete("/team/{member_id}")
def remove_team_member(
    member_id: int,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    member = (
        db.query(TeamMember)
        .filter(
            and_(
                TeamMember.id == member_id,
                TeamMember.owner_id == recruiter.id,
                TeamMember.status == "active",
            )
        )
        .first()
    )

    if not member:
        raise HTTPException(status_code=404, detail="Team member not found")

    member.status = "inactive"
    member.removed_at = _utcnow()
    db.commit()

    logger.info(
        f"Removed team member {member_id} from recruiter {get_user_email(recruiter)}"
    )

    return {"success": True}


@router.get("/team/{member_id}/performance")
def get_member_performance(
    member_id: int,
    days: int = 30,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    member = (
        db.query(TeamMember)
        .filter(
            and_(
                TeamMember.id == member_id,
                TeamMember.owner_id == recruiter.id,
                TeamMember.status == "active",
            )
        )
        .first()
    )

    if not member:
        raise HTTPException(status_code=404, detail="Team member not found")

    cutoff_date = _utcnow() - timedelta(days=days)

    apps = (
        db.query(Application).filter(Application.assigned_to == member.member_id).all()
    )

    status_counts = {}
    for app in apps:
        status = app.status or "pending"
        status_counts[status] = status_counts.get(status, 0) + 1

    comments_count = (
        db.query(Comment)
        .filter(
            and_(Comment.user_id == member.member_id, Comment.created_at >= cutoff_date)
        )
        .count()
    )

    ratings_count = (
        db.query(CandidateRating)
        .filter(
            and_(
                CandidateRating.user_id == member.member_id,
                CandidateRating.created_at >= cutoff_date,
            )
        )
        .count()
    )

    interviews_count = (
        db.query(InterviewParticipant)
        .join(Interview)
        .filter(
            and_(
                InterviewParticipant.user_id == member.member_id,
                Interview.created_at >= cutoff_date,
            )
        )
        .count()
    )

    member_user = db.query(User).filter(User.id == member.member_id).first()

    total_apps = len(apps)
    score = (
        (total_apps * 3)
        + (comments_count * 2)
        + (ratings_count * 5)
        + (interviews_count * 10)
    )

    return {
        "member_id": member.member_id,
        "member_name": get_user_name(member_user) if member_user else "Unknown",
        "period_days": days,
        "total_candidates": total_apps,
        "pipeline": status_counts,
        "comments": comments_count,
        "ratings": ratings_count,
        "interviews": interviews_count,
        "activity_score": score,
    }


@router.get("/team/performance")
def get_all_team_performance(
    days: int = 30,
    recruiter: User = Depends(require_recruiter),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db),
):
    try:
        from sqlalchemy import and_, or_

        cutoff_date = _utcnow() - timedelta(days=days)

        result = []

        job_ids = [
            j.id for j in db.query(Job).filter(Job.company_id == company_id).all()
        ]
        batch_ids = [
            b.id
            for b in db.query(BatchJob).filter(BatchJob.company_id == company_id).all()
        ]

        if job_ids or batch_ids:
            my_apps = (
                db.query(Application)
                .filter(
                    or_(
                        Application.job_id.in_(job_ids) if job_ids else False,
                        Application.batch_id.in_(batch_ids) if batch_ids else False,
                    )
                )
                .all()
            )
        else:
            my_apps = []

        assigned_apps = (
            db.query(Application).filter(Application.assigned_to == recruiter.id).all()
        )

        all_my_apps = my_apps + assigned_apps
        all_my_app_ids = [app.id for app in all_my_apps]

        my_status_counts = {}
        for app in all_my_apps:
            status = app.status or "pending"
            my_status_counts[status] = my_status_counts.get(status, 0) + 1

        if all_my_app_ids:
            my_comments = (
                db.query(Comment)
                .filter(
                    and_(
                        Comment.application_id.in_(all_my_app_ids),
                        Comment.created_at >= cutoff_date,
                    )
                )
                .count()
            )
            my_ratings = (
                db.query(CandidateRating)
                .filter(
                    and_(
                        CandidateRating.application_id.in_(all_my_app_ids),
                        CandidateRating.created_at >= cutoff_date,
                    )
                )
                .count()
            )
        else:
            my_comments = 0
            my_ratings = 0

        my_interviews = (
            db.query(InterviewParticipant)
            .join(Interview)
            .filter(
                and_(
                    InterviewParticipant.user_id == recruiter.id,
                    Interview.created_at >= cutoff_date,
                )
            )
            .count()
        )

        my_score = (
            (len(all_my_apps) * 3)
            + (my_comments * 2)
            + (my_ratings * 5)
            + (my_interviews * 10)
        )

        result.append(
            {
                "user_id": recruiter.id,
                "name": get_user_name(recruiter)
                or get_user_email(recruiter).split("@")[0],
                "email": get_user_email(recruiter),
                "role": "owner",
                "total_candidates": len(all_my_apps),
                "pipeline": my_status_counts,
                "comments": my_comments,
                "ratings": my_ratings,
                "interviews": my_interviews,
                "activity_score": my_score,
            }
        )

        members = (
            db.query(TeamMember)
            .filter(
                and_(TeamMember.owner_id == recruiter.id, TeamMember.status == "active")
            )
            .all()
        )

        for m in members:
            member_user = db.query(User).filter(User.id == m.member_id).first()

            if all_my_app_ids:
                apps = (
                    db.query(Application)
                    .filter(
                        and_(
                            Application.id.in_(all_my_app_ids),
                            Application.assigned_to == m.member_id,
                        )
                    )
                    .all()
                )
            else:
                apps = []

            status_counts = {}
            for app in apps:
                status = app.status or "pending"
                status_counts[status] = status_counts.get(status, 0) + 1

            app_ids = [app.id for app in apps]
            if app_ids:
                comments = (
                    db.query(Comment)
                    .filter(
                        and_(
                            Comment.application_id.in_(app_ids),
                            Comment.created_at >= cutoff_date,
                        )
                    )
                    .count()
                )
                ratings = (
                    db.query(CandidateRating)
                    .filter(
                        and_(
                            CandidateRating.application_id.in_(app_ids),
                            CandidateRating.created_at >= cutoff_date,
                        )
                    )
                    .count()
                )
            else:
                comments = 0
                ratings = 0

            interviews = (
                db.query(InterviewParticipant)
                .join(Interview)
                .filter(
                    and_(
                        InterviewParticipant.user_id == m.member_id,
                        Interview.created_at >= cutoff_date,
                    )
                )
                .count()
            )

            score = (len(apps) * 3) + (comments * 2) + (ratings * 5) + (interviews * 10)

            result.append(
                {
                    "team_member_id": m.id,
                    "user_id": m.member_id,
                    "name": get_user_name(member_user) if member_user else "Unknown",
                    "email": get_user_email(member_user) if member_user else "",
                    "role": m.role,
                    "total_candidates": len(apps),
                    "pipeline": status_counts,
                    "comments": comments,
                    "ratings": ratings,
                    "interviews": interviews,
                    "activity_score": score,
                }
            )

        return result

    except Exception as e:
        logger.error(f"Error in get_all_team_performance: {e}")
        import traceback

        traceback.print_exc()
        return [
            {
                "error": "Performance data unavailable",
                "user_id": recruiter.id,
                "name": get_user_name(recruiter) or "User",
                "email": get_user_email(recruiter),
                "role": "owner",
                "total_candidates": 0,
                "pipeline": {},
                "comments": 0,
                "ratings": 0,
                "interviews": 0,
                "activity_score": 0,
            }
        ]


@router.patch("/team/{member_id}/role")
def change_member_role(
    member_id: int,
    data: ChangeRoleRequest,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    if data.role not in ("member", "admin"):
        raise HTTPException(
            status_code=400, detail="Invalid role. Must be 'member' or 'admin'"
        )

    member = (
        db.query(TeamMember)
        .filter(
            and_(
                TeamMember.id == member_id,
                TeamMember.owner_id == recruiter.id,
                TeamMember.status == "active",
            )
        )
        .first()
    )

    if not member:
        raise HTTPException(status_code=404, detail="Team member not found")

    member.role = data.role
    db.commit()

    log_activity(
        db,
        recruiter.id,
        "team_role_changed",
        details={"target_id": member.member_id, "new_role": data.role},
        company_id=getattr(recruiter, "_company_id", None),
    )

    logger.info(
        f"Changed role of team member {member_id} to {data.role} by {get_user_email(recruiter)}"
    )
    return {"success": True, "role": data.role}


@router.get("/team/search")
def search_users_for_team(
    q: str,
    recruiter: User = Depends(require_recruiter),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db),
):
    if not q or len(q) < 2:
        return []

    from backend.models.foundation.company import CompanyMember

    existing_member_ids = set(
        m.member_id
        for m in db.query(TeamMember)
        .filter(
            and_(TeamMember.owner_id == recruiter.id, TeamMember.status == "active")
        )
        .all()
    )
    existing_member_ids.add(recruiter.id)

    users = (
        db.query(User)
        .join(CompanyMember, CompanyMember.user_id == User.id)
        .filter(
            and_(
                CompanyMember.company_id == company_id,
                User.role == "recruiter",
                User.id.notin_(existing_member_ids),
                (User.name.ilike(f"%{q}%") | User.email.ilike(f"%{q}%")),
            )
        )
        .limit(20)
        .all()
    )

    return [
        {
            "id": u.id,
            "name": get_user_name(u) or get_user_email(u).split("@")[0],
        }
        for u in users
    ]


@router.get("/team/{member_id}/detail")
def get_member_detail(
    member_id: int,
    days: int = 30,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    if member_id == recruiter.id:
        member_user = recruiter
        team_member = None
    else:
        team_member = (
            db.query(TeamMember)
            .filter(
                and_(
                    TeamMember.id == member_id,
                    TeamMember.owner_id == recruiter.id,
                    TeamMember.status == "active",
                )
            )
            .first()
        )
        if not team_member:
            raise HTTPException(status_code=404, detail="Team member not found")
        member_user = db.query(User).filter(User.id == team_member.member_id).first()
        if not member_user:
            raise HTTPException(status_code=404, detail="User not found")

    cutoff_date = _utcnow() - timedelta(days=days)

    if member_id == recruiter.id:
        job_ids = [
            j.id for j in db.query(Job).filter(Job.recruiter_id == recruiter.id).all()
        ]
        batch_ids = [
            b.id
            for b in db.query(BatchJob)
            .filter(BatchJob.recruiter_id == recruiter.id)
            .all()
        ]
        apps = (
            db.query(Application)
            .filter(
                (Application.job_id.in_(job_ids) if job_ids else False)
                | (Application.batch_id.in_(batch_ids) if batch_ids else False)
                | (Application.assigned_to == recruiter.id)
            )
            .all()
        )
    else:
        apps = (
            db.query(Application)
            .filter(Application.assigned_to == team_member.member_id)
            .all()
        )

    status_counts = {}
    for app in apps:
        status = app.status or "pending"
        status_counts[status] = status_counts.get(status, 0) + 1

    app_ids = [app.id for app in apps]
    comments_count = (
        db.query(Comment)
        .filter(
            and_(Comment.user_id == member_user.id, Comment.created_at >= cutoff_date)
        )
        .count()
        if app_ids
        else 0
    )
    ratings_count = (
        db.query(CandidateRating)
        .filter(
            and_(
                CandidateRating.user_id == member_user.id,
                CandidateRating.created_at >= cutoff_date,
            )
        )
        .count()
        if app_ids
        else 0
    )
    interviews_count = (
        db.query(InterviewParticipant)
        .join(Interview)
        .filter(
            and_(
                InterviewParticipant.user_id == member_user.id,
                Interview.created_at >= cutoff_date,
            )
        )
        .count()
    )

    recent_activities = (
        db.query(ActivityLog)
        .filter(
            and_(
                ActivityLog.user_id == member_user.id,
                ActivityLog.created_at >= cutoff_date,
            )
        )
        .order_by(desc(ActivityLog.created_at))
        .limit(10)
        .all()
    )

    score = (
        (len(apps) * 3)
        + (comments_count * 2)
        + (ratings_count * 5)
        + (interviews_count * 10)
    )

    return {
        "user_id": member_user.id,
        "name": get_user_name(member_user) or get_user_email(member_user).split("@")[0],
        "email": get_user_email(member_user),
        "avatar_url": getattr(
            getattr(member_user, "recruiter_profile", None), "avatar_url", None
        )
        if member_user
        else None,
        "role": "owner" if member_id == recruiter.id else team_member.role,
        "joined_at": team_member.added_at if team_member else None,
        "total_candidates": len(apps),
        "pipeline": status_counts,
        "comments": comments_count,
        "ratings": ratings_count,
        "interviews": interviews_count,
        "activity_score": score,
        "recent_activities": [format_activity(a, db) for a in recent_activities],
    }


@router.post("/team/{member_id}/reassign")
def reassign_candidates(
    member_id: int,
    data: ReassignCandidatesRequest,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    if member_id == recruiter.id:
        raise HTTPException(
            status_code=400, detail="Cannot reassign from yourself via this endpoint"
        )

    source = (
        db.query(TeamMember)
        .filter(
            and_(
                TeamMember.id == member_id,
                TeamMember.owner_id == recruiter.id,
                TeamMember.status == "active",
            )
        )
        .first()
    )
    if not source:
        raise HTTPException(status_code=404, detail="Source team member not found")

    if data.to_member_id == recruiter.id:
        target_user = recruiter
    else:
        target = (
            db.query(TeamMember)
            .filter(
                and_(
                    TeamMember.id == data.to_member_id,
                    TeamMember.owner_id == recruiter.id,
                    TeamMember.status == "active",
                )
            )
            .first()
        )
        if not target:
            raise HTTPException(status_code=404, detail="Target team member not found")
        target_user = db.query(User).filter(User.id == target.member_id).first()
        if not target_user:
            raise HTTPException(status_code=404, detail="Target user not found")

    if data.application_ids:
        apps = (
            db.query(Application)
            .filter(
                and_(
                    Application.assigned_to == source.member_id,
                    Application.id.in_(data.application_ids),
                )
            )
            .all()
        )
    else:
        apps = (
            db.query(Application)
            .filter(Application.assigned_to == source.member_id)
            .all()
        )

    if not apps:
        raise HTTPException(status_code=400, detail="No candidates to reassign")

    count = 0
    for app in apps:
        app.assigned_to = target_user.id
        log_activity(
            db,
            recruiter.id,
            "candidate_reassigned",
            application_id=app.id,
            details={"from": source.member_id, "to": target_user.id},
            company_id=app.company_id,
        )
        count += 1

    db.commit()

    logger.info(
        f"Reassigned {count} candidates from {source.member_id} to {target_user.id}"
    )
    return {"success": True, "reassigned_count": count}
