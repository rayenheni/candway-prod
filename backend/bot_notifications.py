import json
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from backend.database import Application, BotIntegration, Interview, User
from backend.logger import logger
from backend.slack_bot import SlackBot
from backend.teams_bot import TeamsBot


class BotNotificationService:
    @staticmethod
    def _get_active_integrations(recruiter_id: int, db: Session) -> list:
        return (
            db.query(BotIntegration)
            .filter(
                BotIntegration.recruiter_id == recruiter_id,
                BotIntegration.is_active,
            )
            .all()
        )

    @staticmethod
    async def notify_new_application(application_id: int, db: Session):
        app = db.query(Application).filter(Application.id == application_id).first()
        if not app or not app.assigned_to:
            return

        integrations = BotNotificationService._get_active_integrations(
            app.assigned_to, db
        )
        if not integrations:
            return

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "New Application Received",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"*{app.full_name}* applied for *{app.declared_role or 'a role'}*\n"
                        f"Status: `{app.status}`"
                    ),
                },
            },
        ]

        for integration in integrations:
            if integration.platform == "slack":
                await SlackBot.send_message(
                    channel=f"@{integration.platform_user_id}",
                    blocks=blocks,
                    text=f"New application from {app.full_name}",
                )
            elif integration.platform == "teams" and integration.conversation_ref:
                card = {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard",
                    "version": "1.4",
                    "body": [
                        {
                            "type": "TextBlock",
                            "text": "New Application Received",
                            "weight": "bolder",
                            "size": "medium",
                        },
                        {
                            "type": "TextBlock",
                            "text": f"{app.full_name} applied for {app.declared_role or 'a role'}",
                            "wrap": True,
                        },
                    ],
                }
                try:
                    conv_ref = json.loads(integration.conversation_ref)
                    await TeamsBot.send_proactive_notification(conv_ref, card)
                except (json.JSONDecodeError, TypeError):
                    logger.error(
                        f"Invalid conversation_ref for Teams integration {integration.id}"
                    )

    @staticmethod
    async def notify_interview_reminder(interview_id: int, db: Session):
        interview = db.query(Interview).filter(Interview.id == interview_id).first()
        if not interview:
            return

        app = (
            db.query(Application)
            .filter(Application.id == interview.application_id)
            .first()
        )
        if not app or not app.assigned_to:
            return

        integrations = BotNotificationService._get_active_integrations(
            app.assigned_to, db
        )
        if not integrations:
            return

        time_str = (
            interview.scheduled_time.strftime("%B %d at %I:%M %p")
            if interview.scheduled_time
            else "TBD"
        )

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "Interview Reminder",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"*{app.full_name}* — {interview.type}\n"
                        f"Scheduled: {time_str}\n"
                        f"Duration: {interview.duration_minutes}min"
                    ),
                },
            },
        ]

        for integration in integrations:
            if integration.platform == "slack":
                await SlackBot.send_message(
                    channel=f"@{integration.platform_user_id}",
                    blocks=blocks,
                    text=f"Interview reminder: {app.full_name}",
                )
            elif integration.platform == "teams" and integration.conversation_ref:
                card = {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard",
                    "version": "1.4",
                    "body": [
                        {
                            "type": "TextBlock",
                            "text": "Interview Reminder",
                            "weight": "bolder",
                            "size": "medium",
                        },
                        {
                            "type": "TextBlock",
                            "text": f"{app.full_name} — {interview.type} at {time_str}",
                            "wrap": True,
                        },
                    ],
                }
                try:
                    conv_ref = json.loads(integration.conversation_ref)
                    await TeamsBot.send_proactive_notification(conv_ref, card)
                except (json.JSONDecodeError, TypeError):
                    logger.error(
                        f"Invalid conversation_ref for Teams integration {integration.id}"
                    )

    @staticmethod
    async def send_daily_digest(recruiter_id: int, db: Session):
        from backend.database import Application as AppModel
        from backend.database import Interview

        recruiter = db.query(User).filter(User.id == recruiter_id).first()
        if not recruiter:
            return

        integrations = BotNotificationService._get_active_integrations(recruiter_id, db)
        if not integrations:
            return

        now = datetime.now(UTC).replace(tzinfo=None)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)

        new_apps = (
            db.query(AppModel)
            .filter(
                AppModel.assigned_to == recruiter_id,
                AppModel.created_at >= today_start,
                AppModel.created_at < today_end,
            )
            .count()
        )

        today_interviews = (
            db.query(Interview)
            .join(AppModel, Interview.application_id == AppModel.id)
            .filter(
                AppModel.assigned_to == recruiter_id,
                Interview.scheduled_time >= today_start,
                Interview.scheduled_time < today_end,
                Interview.status == "scheduled",
            )
            .count()
        )

        pending_review = (
            db.query(AppModel)
            .filter(
                AppModel.assigned_to == recruiter_id,
                AppModel.status == "pending",
            )
            .count()
        )

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "Daily Digest",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"Good morning, {recruiter.name or 'there'}!\n\n"
                        f":inbox_tray: *New applications:* {new_apps}\n"
                        f":calendar: *Interviews today:* {today_interviews}\n"
                        f":mag: *Pending review:* {pending_review}"
                    ),
                },
            },
        ]

        for integration in integrations:
            if integration.platform == "slack":
                await SlackBot.send_message(
                    channel=f"@{integration.platform_user_id}",
                    blocks=blocks,
                    text="Your Candway daily digest",
                )
            elif integration.platform == "teams" and integration.conversation_ref:
                card = {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard",
                    "version": "1.4",
                    "body": [
                        {
                            "type": "TextBlock",
                            "text": "Daily Digest",
                            "weight": "bolder",
                            "size": "medium",
                        },
                        {
                            "type": "FactSet",
                            "facts": [
                                {"title": "New applications", "value": str(new_apps)},
                                {
                                    "title": "Interviews today",
                                    "value": str(today_interviews),
                                },
                                {
                                    "title": "Pending review",
                                    "value": str(pending_review),
                                },
                            ],
                        },
                    ],
                }
                try:
                    conv_ref = json.loads(integration.conversation_ref)
                    await TeamsBot.send_proactive_notification(conv_ref, card)
                except (json.JSONDecodeError, TypeError):
                    logger.error(
                        f"Invalid conversation_ref for Teams integration {integration.id}"
                    )
