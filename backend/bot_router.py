from datetime import UTC, datetime, timedelta
from typing import Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

from backend.database import (
    Application,
    BotIntegration,
    EvaluationResult,
    EvaluationSession,
    Interview,
    Job,
    User,
)
from backend.logger import logger


class BotRouter:
    _rate_limit_store: dict = {}

    @staticmethod
    def _get_app_score(app) -> float:
        es = (app.evaluation_sessions or [None])[0]
        er = es.evaluation_result if es else None
        return (
            er.final_score if er and er.final_score is not None else (app.cv_score or 0)
        )

    @staticmethod
    def _check_rate_limit(user_id: int) -> bool:
        now = datetime.now(UTC).timestamp()
        key = f"bot_rate:{user_id}"
        timestamps = BotRouter._rate_limit_store.get(key, [])
        timestamps = [t for t in timestamps if now - t < 60]
        if len(timestamps) >= 10:
            return False
        timestamps.append(now)
        BotRouter._rate_limit_store[key] = timestamps
        return True

    @staticmethod
    async def process_command(
        platform: str,
        command: str,
        params: dict,
        user: User,
        db: Session,
    ) -> dict:
        if not BotRouter._check_rate_limit(user.id):
            return {
                "error": "Rate limit exceeded. Please wait before sending more commands.",
                "rate_limited": True,
            }

        action_map = {
            "top_candidates": BotRouter._action_top_candidates,
            "search_candidates": BotRouter._action_search_candidates,
            "pipeline_stats": BotRouter._action_pipeline_stats,
            "upcoming_interviews": BotRouter._action_upcoming_interviews,
            "get_application": BotRouter._action_get_application,
            "update_status": BotRouter._action_update_status,
            "schedule_interview": BotRouter._action_schedule_interview,
            "send_message": BotRouter._action_send_message,
            "create_note": BotRouter._action_create_note,
            "get_notifications": BotRouter._action_get_notifications,
        }

        handler = action_map.get(command)
        if not handler:
            return {"error": f"Unknown action: {command}"}

        try:
            return await handler(platform, params, user, db)
        except Exception as e:
            logger.error(f"BotRouter error: {e}")
            return {"error": str(e)}

    @staticmethod
    async def _action_top_candidates(
        platform: str, params: dict, user: User, db: Session
    ) -> dict:
        job_title = params.get("job_title")
        limit = min(params.get("limit", 5), 20)

        query = db.query(Application).filter(Application.assigned_to == user.id)
        if job_title:
            query = query.filter(Application.declared_role.ilike(f"%{job_title}%"))
        latest_score = (
            db.query(EvaluationResult.final_score)
            .join(
                EvaluationSession,
                EvaluationResult.evaluation_session_id == EvaluationSession.id,
            )
            .filter(EvaluationSession.application_id == Application.id)
            .order_by(EvaluationResult.id.desc())
            .limit(1)
            .correlate(Application)
            .scalar_subquery()
        )
        apps = query.order_by(desc(latest_score).nullslast()).limit(limit).all()

        return {
            "platform": platform,
            "action": "top_candidates",
            "candidates": [
                {
                    "id": a.id,
                    "name": a.full_name,
                    "role": a.declared_role,
                    "score": BotRouter._get_app_score(a),
                    "status": a.status,
                }
                for a in apps
            ],
            "total": len(apps),
        }

    @staticmethod
    async def _action_search_candidates(
        platform: str, params: dict, user: User, db: Session
    ) -> dict:
        query_text = params.get("query", "")
        if not query_text:
            return {"error": "Query is required"}

        apps = (
            db.query(Application)
            .filter(
                Application.assigned_to == user.id,
                Application.full_name.ilike(f"%{query_text}%"),
            )
            .order_by(Application.created_at.desc())
            .limit(20)
            .all()
        )

        return {
            "platform": platform,
            "action": "search_candidates",
            "query": query_text,
            "candidates": [
                {
                    "id": a.id,
                    "name": a.full_name,
                    "role": a.declared_role,
                    "score": BotRouter._get_app_score(a),
                    "status": a.status,
                }
                for a in apps
            ],
            "total": len(apps),
        }

    @staticmethod
    async def _action_pipeline_stats(
        platform: str, params: dict, user: User, db: Session
    ) -> dict:
        job_id = params.get("job_id")
        jobs = db.query(Job).filter(Job.recruiter_id == user.id)
        if job_id:
            jobs = jobs.filter(Job.id == job_id)
        jobs = jobs.all()

        stats = []
        for job in jobs:
            total = db.query(Application).filter(Application.job_id == job.id).count()
            by_status = {}
            for s in (
                "pending",
                "screening",
                "interviewing",
                "offer",
                "rejected",
                "hired",
            ):
                by_status[s] = (
                    db.query(Application)
                    .filter(Application.job_id == job.id, Application.status == s)
                    .count()
                )
            stats.append(
                {
                    "job_id": job.id,
                    "title": job.title,
                    "total": total,
                    "by_status": by_status,
                }
            )

        return {"platform": platform, "action": "pipeline_stats", "jobs": stats}

    @staticmethod
    async def _action_upcoming_interviews(
        platform: str, params: dict, user: User, db: Session
    ) -> dict:
        period = params.get("period", "today")
        now = datetime.now(UTC).replace(tzinfo=None)

        if period == "tomorrow":
            start = now + timedelta(days=1)
            end = start + timedelta(days=1)
        elif period == "week":
            start = now
            end = now + timedelta(days=7)
        else:
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=1)

        interviews = (
            db.query(Interview)
            .join(Application, Interview.application_id == Application.id)
            .filter(
                Application.assigned_to == user.id,
                Interview.scheduled_time >= start,
                Interview.scheduled_time < end,
                Interview.status == "scheduled",
            )
            .order_by(Interview.scheduled_time)
            .all()
        )

        items = []
        for iv in interviews:
            app = (
                db.query(Application)
                .filter(Application.id == iv.application_id)
                .first()
            )
            items.append(
                {
                    "id": iv.id,
                    "candidate_name": app.full_name if app else "Unknown",
                    "candidate_id": iv.application_id,
                    "type": iv.type,
                    "scheduled_time": iv.scheduled_time.isoformat()
                    if iv.scheduled_time
                    else None,
                    "duration_minutes": iv.duration_minutes,
                }
            )

        return {
            "platform": platform,
            "action": "upcoming_interviews",
            "period": period,
            "interviews": items,
        }

    @staticmethod
    async def _action_get_application(
        platform: str, params: dict, user: User, db: Session
    ) -> dict:
        app_id = params.get("application_id")
        app = (
            db.query(Application)
            .filter(Application.id == app_id, Application.assigned_to == user.id)
            .first()
        )
        if not app:
            return {"error": "Application not found"}
        return {
            "platform": platform,
            "action": "get_application",
            "application": {
                "id": app.id,
                "name": app.full_name,
                "role": app.declared_role,
                "score": BotRouter._get_app_score(app),
                "status": app.status,
                "created_at": app.created_at.isoformat() if app.created_at else None,
            },
        }

    @staticmethod
    async def _action_update_status(
        platform: str, params: dict, user: User, db: Session
    ) -> dict:
        app_id = params.get("application_id")
        new_status = params.get("status", "")
        valid_statuses = [
            "pending",
            "screening",
            "interviewing",
            "offer",
            "rejected",
            "hired",
        ]

        if new_status not in valid_statuses:
            return {"error": f"Invalid status. Valid: {', '.join(valid_statuses)}"}

        app = (
            db.query(Application)
            .filter(Application.id == app_id, Application.assigned_to == user.id)
            .first()
        )
        if not app:
            return {"error": "Application not found"}

        old_status = app.status
        app.status = new_status
        db.commit()

        return {
            "platform": platform,
            "action": "update_status",
            "application_id": app_id,
            "old_status": old_status,
            "new_status": new_status,
            "success": True,
        }

    @staticmethod
    async def _action_schedule_interview(
        platform: str, params: dict, user: User, db: Session
    ) -> dict:
        return {
            "platform": platform,
            "action": "schedule_interview",
            "message": "Use the Candway web interface to schedule interviews.",
        }

    @staticmethod
    async def _action_send_message(
        platform: str, params: dict, user: User, db: Session
    ) -> dict:
        return {
            "platform": platform,
            "action": "send_message",
            "message": "Use the Candway web interface to send messages.",
        }

    @staticmethod
    async def _action_create_note(
        platform: str, params: dict, user: User, db: Session
    ) -> dict:
        return {
            "platform": platform,
            "action": "create_note",
            "message": "Use the Candway web interface to create notes.",
        }

    @staticmethod
    async def _action_get_notifications(
        platform: str, params: dict, user: User, db: Session
    ) -> dict:
        from backend.database import Notification

        notifications = (
            db.query(Notification)
            .filter(Notification.user_id == user.id, not Notification.is_read)
            .order_by(Notification.created_at.desc())
            .limit(20)
            .all()
        )
        return {
            "platform": platform,
            "action": "get_notifications",
            "notifications": [
                {
                    "id": n.id,
                    "type": n.type,
                    "title": n.title,
                    "message": n.message,
                    "created_at": n.created_at.isoformat() if n.created_at else None,
                }
                for n in notifications
            ],
        }

    @staticmethod
    def get_user_from_platform(
        platform: str, platform_user_id: str, db: Session
    ) -> Optional[User]:
        integration = (
            db.query(BotIntegration)
            .filter(
                BotIntegration.platform == platform,
                BotIntegration.platform_user_id == platform_user_id,
                BotIntegration.is_active,
            )
            .first()
        )
        if integration:
            return db.query(User).filter(User.id == integration.recruiter_id).first()
        return None

    @staticmethod
    def link_platform_account(
        platform: str,
        platform_user_id: str,
        candway_user_id: int,
        db: Session,
        platform_team_id: Optional[str] = None,
        access_token: Optional[str] = None,
    ):
        existing = (
            db.query(BotIntegration)
            .filter(
                BotIntegration.platform == platform,
                BotIntegration.platform_user_id == platform_user_id,
            )
            .first()
        )
        if existing:
            existing.recruiter_id = candway_user_id
            existing.is_active = True
            if platform_team_id:
                existing.platform_team_id = platform_team_id
            if access_token:
                existing.access_token = access_token
        else:
            integration = BotIntegration(
                recruiter_id=candway_user_id,
                platform=platform,
                platform_user_id=platform_user_id,
                platform_team_id=platform_team_id,
                access_token=access_token,
                is_active=True,
            )
            db.add(integration)
        db.commit()
