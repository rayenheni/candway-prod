import json
import os
from datetime import UTC, datetime
from typing import Optional

import httpx
from sqlalchemy import desc
from sqlalchemy.orm import Session

from backend.database import (
    Application,
    BotIntegration,
    EvaluationResult,
    EvaluationSession,
    Job,
    User,
)
from backend.logger import logger

TEAMS_APP_ID = os.getenv("TEAMS_APP_ID", "")
TEAMS_APP_PASSWORD = os.getenv("TEAMS_APP_PASSWORD", "")
TEAMS_TENANT_ID = os.getenv("TEAMS_TENANT_ID", "")


class TeamsBot:
    _http_client: Optional[httpx.AsyncClient] = None
    _token_cache: dict = {"token": "", "expires_at": 0.0}

    @classmethod
    def _get_client(cls) -> httpx.AsyncClient:
        if cls._http_client is None or cls._http_client.is_closed:
            cls._http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(15.0, connect=5.0),
            )
        return cls._http_client

    @staticmethod
    async def _get_access_token() -> Optional[str]:
        now = datetime.now(UTC).timestamp()
        if (
            TeamsBot._token_cache["token"]
            and TeamsBot._token_cache["expires_at"] > now + 60
        ):
            return TeamsBot._token_cache["token"]

        if not TEAMS_APP_ID or not TEAMS_APP_PASSWORD:
            return None

        client = TeamsBot._get_client()
        try:
            resp = await client.post(
                f"https://login.microsoftonline.com/{TEAMS_TENANT_ID}/oauth2/v2.0/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": TEAMS_APP_ID,
                    "client_secret": TEAMS_APP_PASSWORD,
                    "scope": "https://api.botframework.com/.default",
                },
            )
            data = resp.json()
            token = data.get("access_token")
            expires_in = data.get("expires_in", 3600)
            if token:
                TeamsBot._token_cache["token"] = token
                TeamsBot._token_cache["expires_at"] = now + expires_in
                return token
        except Exception as e:
            logger.error(f"Teams auth error: {e}")
        return None

    @staticmethod
    def verify_request(auth_header: str) -> bool:
        if not auth_header or not auth_header.startswith("Bearer "):
            return False
        return True

    @staticmethod
    async def handle_activity(activity: dict, db: Session) -> dict:
        activity_type = activity.get("type", "")
        if activity_type == "message":
            text = activity.get("text", "")
            user_id = activity.get("from", {}).get("id", "")
            conversation = activity.get("conversation", {})
            tenant_id = activity.get("conversation", {}).get(
                "tenantId", TEAMS_TENANT_ID
            )
            return await TeamsBot.handle_message(
                text, conversation, user_id, tenant_id, db
            )
        elif activity_type == "conversationUpdate":
            members_added = activity.get("membersAdded", [])
            for member in members_added:
                if member.get("id") != TEAMS_APP_ID:
                    conversation = activity.get("conversation", {})
                    await TeamsBot._save_conversation_ref(
                        activity.get("from", {}).get("id", ""),
                        conversation,
                        tenant_id or TEAMS_TENANT_ID,
                        db,
                    )
            return {"status": 200}
        elif activity_type == "invoke":
            name = activity.get("name", "")
            if name == "task/fetch":
                return await TeamsBot._handle_task_fetch(activity.get("value", {}), db)
            elif name == "task/submit":
                return await TeamsBot._handle_task_submit(activity.get("value", {}), db)
            return {"status": 200}
        return {"status": 200}

    @staticmethod
    async def handle_message(
        text: str,
        conversation_ref: dict,
        user_id: str,
        tenant_id: str,
        db: Session,
    ) -> dict:
        text = text.strip().lower()
        parts = text.split(None, 1)
        cmd = parts[0] if parts else ""
        arg = parts[1] if len(parts) > 1 else ""

        if cmd in ("top", "top candidates"):
            job_title = arg or None
            integration = (
                db.query(BotIntegration)
                .filter(
                    BotIntegration.platform_user_id == user_id,
                    BotIntegration.platform == "teams",
                    BotIntegration.is_active,
                )
                .first()
            )
            if not integration:
                return TeamsBot._text_reply(
                    "Please connect your Candway account first."
                )
            recruiter = (
                db.query(User).filter(User.id == integration.recruiter_id).first()
            )
            if not recruiter:
                return TeamsBot._text_reply("Recruiter not found.")

            query = db.query(Application).filter(
                Application.assigned_to == recruiter.id
            )
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
            apps = query.order_by(desc(latest_score).nullslast()).limit(5).all()

            if not apps:
                return TeamsBot._text_reply("No candidates found.")

            cards = [TeamsBot._create_candidate_card(app) for app in apps]
            attachment = {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard",
                    "version": "1.4",
                    "body": [
                        {
                            "type": "TextBlock",
                            "text": f"Top Candidates{' for ' + job_title if job_title else ''}",
                            "weight": "bolder",
                            "size": "medium",
                        }
                    ]
                    + cards,
                },
            }
            return TeamsBot._activity_reply([attachment])

        elif cmd in ("stats", "pipeline"):
            job_id = int(arg) if arg.isdigit() else None
            integration = (
                db.query(BotIntegration)
                .filter(
                    BotIntegration.platform_user_id == user_id,
                    BotIntegration.platform == "teams",
                    BotIntegration.is_active,
                )
                .first()
            )
            if not integration:
                return TeamsBot._text_reply(
                    "Please connect your Candway account first."
                )
            recruiter = (
                db.query(User).filter(User.id == integration.recruiter_id).first()
            )
            if not recruiter:
                return TeamsBot._text_reply("Recruiter not found.")

            jobs = db.query(Job).filter(Job.recruiter_id == recruiter.id)
            if job_id:
                jobs = jobs.filter(Job.id == job_id)
            jobs = jobs.all()

            if not jobs:
                return TeamsBot._text_reply("No jobs found.")

            card = TeamsBot._create_stats_card(jobs, db)
            attachment = {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": card,
            }
            return TeamsBot._activity_reply([attachment])

        elif cmd in ("help", "commands"):
            return TeamsBot._text_reply(
                "Available commands:\n"
                "- `top [job_title]` — Top candidates\n"
                "- `stats [job_id]` — Pipeline stats\n"
                "- `help` — This message"
            )

        else:
            return TeamsBot._text_reply(
                "Unknown command. Type `help` to see available commands."
            )

    @staticmethod
    def _create_candidate_card(app) -> dict:
        es = (app.evaluation_sessions or [None])[0]
        er = es.evaluation_result if es else None
        score = (
            er.final_score if er and er.final_score is not None else (app.cv_score or 0)
        )
        return {
            "type": "ColumnSet",
            "columns": [
                {
                    "type": "Column",
                    "width": "auto",
                    "items": [
                        {
                            "type": "TextBlock",
                            "text": f"{app.full_name}",
                            "weight": "bolder",
                        }
                    ],
                },
                {
                    "type": "Column",
                    "width": "stretch",
                    "items": [
                        {
                            "type": "TextBlock",
                            "text": (
                                f"Role: {app.declared_role or 'N/A'} | "
                                f"Score: {score:.0f}/100"
                            ),
                            "wrap": True,
                            "size": "small",
                        }
                    ],
                },
            ],
        }

    @staticmethod
    def _create_stats_card(jobs: list, db: Session) -> dict:
        body = [
            {
                "type": "TextBlock",
                "text": "Pipeline Statistics",
                "weight": "bolder",
                "size": "medium",
            }
        ]
        for job in jobs:
            total = db.query(Application).filter(Application.job_id == job.id).count()
            screening = (
                db.query(Application)
                .filter(Application.job_id == job.id, Application.status == "screening")
                .count()
            )
            interviewing = (
                db.query(Application)
                .filter(
                    Application.job_id == job.id,
                    Application.status == "interviewing",
                )
                .count()
            )
            offers = (
                db.query(Application)
                .filter(Application.job_id == job.id, Application.status == "offer")
                .count()
            )
            body.append(
                {
                    "type": "TextBlock",
                    "text": (
                        f"{job.title}: Total {total} | "
                        f"Screening {screening} | Interview {interviewing} | "
                        f"Offers {offers}"
                    ),
                    "wrap": True,
                    "size": "small",
                }
            )

        return {
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "type": "AdaptiveCard",
            "version": "1.4",
            "body": body,
        }

    @staticmethod
    async def _handle_task_fetch(value: dict, db: Session) -> dict:
        return {
            "task": {
                "type": "continue",
                "value": {
                    "title": "Candway Action",
                    "height": 400,
                    "width": 600,
                    "card": {
                        "contentType": "application/vnd.microsoft.card.adaptive",
                        "content": {
                            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                            "type": "AdaptiveCard",
                            "version": "1.4",
                            "body": [
                                {
                                    "type": "TextBlock",
                                    "text": "Candway Recruiting",
                                    "weight": "bolder",
                                    "size": "large",
                                },
                                {
                                    "type": "TextBlock",
                                    "text": "Use slash commands or type help to get started.",
                                    "wrap": True,
                                },
                            ],
                        },
                    },
                },
            }
        }

    @staticmethod
    async def _handle_task_submit(value: dict, db: Session) -> dict:
        return {"task": {"type": "message", "value": "Action completed."}}

    @staticmethod
    def _text_reply(text: str) -> dict:
        return {
            "type": "message",
            "text": text,
            "attachments": [],
        }

    @staticmethod
    def _activity_reply(attachments: list) -> dict:
        return {
            "type": "message",
            "text": "",
            "attachments": attachments,
        }

    @staticmethod
    async def _save_conversation_ref(
        user_id: str, conversation: dict, tenant_id: str, db: Session
    ):
        integration = (
            db.query(BotIntegration)
            .filter(
                BotIntegration.platform_user_id == user_id,
                BotIntegration.platform == "teams",
            )
            .first()
        )
        if integration:
            integration.conversation_ref = json.dumps(conversation)
            integration.platform_team_id = tenant_id
            db.commit()

    @staticmethod
    async def send_proactive_notification(conversation_ref: dict, card: dict):
        token = await TeamsBot._get_access_token()
        if not token:
            return

        service_url = conversation_ref.get(
            "serviceUrl", "https://smba.trafficmanager.net/amer/"
        )
        activity = {
            "type": "message",
            "conversation": conversation_ref,
            "attachments": [
                {
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": card,
                }
            ],
        }

        client = TeamsBot._get_client()
        try:
            conv_id = conversation_ref.get("id", "")
            await client.post(
                f"{service_url}v3/conversations/{conv_id}/activities",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json=activity,
            )
        except Exception as e:
            logger.error(f"Teams proactive notification error: {e}")

    @staticmethod
    async def get_oauth_url(state: str) -> str:
        return (
            f"https://login.microsoftonline.com/{TEAMS_TENANT_ID}/oauth2/v2.0/authorize?"
            f"client_id={TEAMS_APP_ID}&response_type=code&"
            f"redirect_uri={os.getenv('TEAMS_REDIRECT_URI', '')}&"
            f"response_mode=query&scope=User.Read&state={state}"
        )

    @staticmethod
    async def exchange_oauth_code(code: str) -> Optional[dict]:
        client = TeamsBot._get_client()
        try:
            resp = await client.post(
                f"https://login.microsoftonline.com/{TEAMS_TENANT_ID}/oauth2/v2.0/token",
                data={
                    "client_id": TEAMS_APP_ID,
                    "client_secret": TEAMS_APP_PASSWORD,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": os.getenv("TEAMS_REDIRECT_URI", ""),
                },
            )
            return resp.json()
        except Exception as e:
            logger.error(f"Teams OAuth exchange error: {e}")
            return None
