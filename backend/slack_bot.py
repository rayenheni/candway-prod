import hashlib
import hmac
import os
import time
from datetime import UTC, datetime, timedelta
from typing import Optional

import httpx
from sqlalchemy import desc
from sqlalchemy.orm import Session

from backend.ai.llm import call_groq_cascade
from backend.database import (
    Application,
    EvaluationResult,
    EvaluationSession,
    Interview,
    Job,
    User,
)
from backend.logger import logger

SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET", "")
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN", "")
SLACK_APP_TOKEN = os.getenv("SLACK_APP_TOKEN", "")
SLACK_CLIENT_ID = os.getenv("SLACK_CLIENT_ID", "")
SLACK_CLIENT_SECRET = os.getenv("SLACK_CLIENT_SECRET", "")

COMMAND_HELP = """*Candway Bot Commands*
`/candway top [job_title]` — Show top candidates for a role
`/candway search [query]` — Search candidates
`/candway stats [job_id]` — Pipeline stats for a job
`/candway interviews [today|tomorrow|week]` — Upcoming interviews
`/candway recent` — Recent applications
`/candway offer [candidate_id] [stage]` — Update candidate stage
`/candway help` — Show this message"""


class SlackBot:
    _http_client: Optional[httpx.AsyncClient] = None

    @classmethod
    def _get_client(cls) -> httpx.AsyncClient:
        if cls._http_client is None or cls._http_client.is_closed:
            cls._http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(15.0, connect=5.0),
            )
        return cls._http_client

    @staticmethod
    def verify_request(signature: str, timestamp: str, body: str) -> bool:
        if not SLACK_SIGNING_SECRET:
            return False
        if abs(time.time() - float(timestamp)) > 60 * 5:
            return False
        sig_basestring = f"v0:{timestamp}:{body}"
        my_sig = (
            "v0="
            + hmac.new(
                SLACK_SIGNING_SECRET.encode(),
                sig_basestring.encode(),
                hashlib.sha256,
            ).hexdigest()
        )
        return hmac.compare_digest(my_sig, signature)

    @staticmethod
    async def handle_slash_command(
        command: str,
        text: str,
        user_id: str,
        channel_id: str,
        db: Session,
        recruiter: User,
    ) -> dict:
        parts = text.strip().split(None, 1)
        subcmd = parts[0].lower() if parts else ""
        arg = parts[1] if len(parts) > 1 else ""

        if subcmd == "top":
            return await SlackBot.handle_top_candidates(arg or None, recruiter.id, db)
        elif subcmd == "search":
            return await SlackBot.handle_search(arg, recruiter.id, db)
        elif subcmd == "stats":
            job_id = int(arg) if arg.isdigit() else None
            return await SlackBot.handle_stats(job_id, recruiter.id, db)
        elif subcmd == "interviews":
            return await SlackBot.handle_interviews(arg or "today", recruiter.id, db)
        elif subcmd == "recent":
            return await SlackBot.handle_recent(recruiter.id, db)
        elif subcmd == "offer":
            parts2 = arg.split()
            if len(parts2) >= 2 and parts2[0].isdigit():
                return await SlackBot.handle_offer(
                    int(parts2[0]), parts2[1], recruiter.id, db
                )
            return SlackBot._text_response(
                "Usage: /candway offer [candidate_id] [stage]"
            )
        elif subcmd == "help" or subcmd == "":
            return SlackBot._text_response(COMMAND_HELP)
        else:
            return SlackBot._text_response(
                f"Unknown command `{subcmd}`. Try `/candway help`"
            )

    @staticmethod
    async def handle_top_candidates(
        job_title: Optional[str], recruiter_id: int, db: Session
    ) -> dict:
        query = db.query(Application).filter(Application.assigned_to == recruiter_id)
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
            return SlackBot._text_response(
                f"No candidates found{' for ' + job_title if job_title else ''}"
            )

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"Top Candidates{' for ' + job_title if job_title else ''}",
                },
            },
            {"type": "divider"},
        ]
        for app in apps:
            blocks.append(SlackBot._format_candidate_card(app))
        return {"response_type": "ephemeral", "blocks": blocks}

    @staticmethod
    async def handle_search(query: str, recruiter_id: int, db: Session) -> dict:
        if not query:
            return SlackBot._text_response("Please provide a search query")
        apps = (
            db.query(Application)
            .filter(
                Application.assigned_to == recruiter_id,
                Application.full_name.ilike(f"%{query}%"),
            )
            .order_by(Application.created_at.desc())
            .limit(10)
            .all()
        )
        if not apps:
            return SlackBot._text_response(f"No candidates matching `{query}`")

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"Search results: {query}"},
            },
            {"type": "divider"},
        ]
        for app in apps:
            blocks.append(SlackBot._format_candidate_card(app))
        return {"response_type": "ephemeral", "blocks": blocks}

    @staticmethod
    async def handle_stats(
        job_id: Optional[int], recruiter_id: int, db: Session
    ) -> dict:
        jobs = db.query(Job).filter(Job.recruiter_id == recruiter_id)
        if job_id:
            jobs = jobs.filter(Job.id == job_id)
        jobs = jobs.all()

        if not jobs:
            return SlackBot._text_response("No jobs found")

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "Pipeline Statistics"},
            },
            {"type": "divider"},
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
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": (
                            f"*{job.title}*\n"
                            f"Total: {total} | Screening: {screening} | "
                            f"Interviewing: {interviewing} | Offers: {offers}"
                        ),
                    },
                }
            )
        return {"response_type": "ephemeral", "blocks": blocks}

    @staticmethod
    async def handle_interviews(period: str, recruiter_id: int, db: Session) -> dict:
        now = datetime.now(UTC).replace(tzinfo=None)
        if period == "tomorrow":
            start = now + timedelta(days=1)
            end = start + timedelta(days=1)
            label = "Tomorrow"
        elif period == "week":
            start = now
            end = now + timedelta(days=7)
            label = "This Week"
        else:
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=1)
            label = "Today"

        interviews = (
            db.query(Interview)
            .join(Application, Interview.application_id == Application.id)
            .filter(
                Application.assigned_to == recruiter_id,
                Interview.scheduled_time >= start,
                Interview.scheduled_time < end,
                Interview.status == "scheduled",
            )
            .order_by(Interview.scheduled_time)
            .all()
        )

        if not interviews:
            return SlackBot._text_response(f"No interviews scheduled {label.lower()}")

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"Interviews {label}"},
            },
            {"type": "divider"},
        ]
        for iv in interviews:
            app = (
                db.query(Application)
                .filter(Application.id == iv.application_id)
                .first()
            )
            candidate_name = app.full_name if app else "Unknown"
            time_str = (
                iv.scheduled_time.strftime("%I:%M %p") if iv.scheduled_time else "TBD"
            )
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": (
                            f"*{candidate_name}* — {iv.type}\n"
                            f"Time: {time_str} | Duration: {iv.duration_minutes}min"
                        ),
                    },
                }
            )
        return {"response_type": "ephemeral", "blocks": blocks}

    @staticmethod
    async def handle_recent(recruiter_id: int, db: Session) -> dict:
        apps = (
            db.query(Application)
            .filter(Application.assigned_to == recruiter_id)
            .order_by(Application.created_at.desc())
            .limit(5)
            .all()
        )
        if not apps:
            return SlackBot._text_response("No recent applications")

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "Recent Applications"},
            },
            {"type": "divider"},
        ]
        for app in apps:
            blocks.append(SlackBot._format_candidate_card(app))
        return {"response_type": "ephemeral", "blocks": blocks}

    @staticmethod
    async def handle_offer(
        candidate_id: int, stage: str, recruiter_id: int, db: Session
    ) -> dict:
        app = (
            db.query(Application)
            .filter(
                Application.id == candidate_id,
                Application.assigned_to == recruiter_id,
            )
            .first()
        )
        if not app:
            return SlackBot._text_response("Candidate not found")

        valid_stages = [
            "pending",
            "screening",
            "interviewing",
            "offer",
            "rejected",
            "hired",
        ]
        stage = stage.lower()
        if stage not in valid_stages:
            return SlackBot._text_response(
                f"Invalid stage. Valid stages: {', '.join(valid_stages)}"
            )

        app.status = stage
        db.commit()
        return SlackBot._text_response(f"Updated *{app.full_name}* to `{stage}`")

    @staticmethod
    async def handle_interactive(payload: dict, db: Session) -> dict:
        action_type = payload.get("type")
        if action_type == "block_actions":
            actions = payload.get("actions", [])
            for action in actions:
                action_id = action.get("action_id", "")
                value = action.get("value", "")
                if action_id == "view_candidate":
                    return {
                        "response_action": "update",
                        "blocks": [
                            {
                                "type": "section",
                                "text": {
                                    "type": "mrkdwn",
                                    "text": f"Opening candidate profile for application {value}...",
                                },
                            }
                        ],
                    }
                elif action_id == "schedule_interview":
                    return {
                        "response_action": "update",
                        "blocks": [
                            {
                                "type": "section",
                                "text": {
                                    "type": "mrkdwn",
                                    "text": (
                                        f"To schedule an interview for application {value}, "
                                        f"use the Candway web interface."
                                    ),
                                },
                            }
                        ],
                    }
        elif action_type == "view_submission":
            return {"response_action": "clear"}
        return {"response_action": "ack"}

    @staticmethod
    def _format_candidate_card(app) -> dict:
        es = (app.evaluation_sessions or [None])[0]
        er = es.evaluation_result if es else None
        score = (
            er.final_score if er and er.final_score is not None else (app.cv_score or 0)
        )
        status_emoji = {
            "pending": ":hourglass_flowing_sand:",
            "screening": ":mag:",
            "interviewing": ":microphone:",
            "offer": ":rocket:",
            "rejected": ":x:",
            "hired": ":tada:",
        }.get(app.status, ":bust_in_silhouette:")

        return {
            "type": "section",
            "block_id": f"candidate_{app.id}",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"{status_emoji} *{app.full_name}*\n"
                    f"Role: {app.declared_role or 'N/A'} | "
                    f"Score: {score:.0f}/100 | "
                    f"Status: `{app.status}`"
                ),
            },
            "accessory": {
                "type": "button",
                "text": {"type": "plain_text", "text": "View Profile"},
                "action_id": "view_candidate",
                "value": str(app.id),
            },
        }

    @staticmethod
    def _text_response(text: str) -> dict:
        return {
            "response_type": "ephemeral",
            "blocks": [
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": text},
                }
            ],
        }

    @staticmethod
    async def send_message(channel: str, blocks: list, text: str = ""):
        if not SLACK_BOT_TOKEN:
            logger.error("SLACK_BOT_TOKEN not set")
            return
        client = SlackBot._get_client()
        try:
            resp = await client.post(
                "https://slack.com/api/chat.postMessage",
                headers={
                    "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
                    "Content-Type": "application/json",
                },
                json={"channel": channel, "blocks": blocks, "text": text},
            )
            data = resp.json()
            if not data.get("ok"):
                logger.error(f"Slack send_message failed: {data.get('error')}")
        except Exception as e:
            logger.error(f"Slack send_message error: {e}")

    @staticmethod
    async def open_modal(trigger_id: str, view: dict):
        if not SLACK_BOT_TOKEN:
            return
        client = SlackBot._get_client()
        try:
            await client.post(
                "https://slack.com/api/views.open",
                headers={
                    "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
                    "Content-Type": "application/json",
                },
                json={"trigger_id": trigger_id, "view": view},
            )
        except Exception as e:
            logger.error(f"Slack open_modal error: {e}")

    @staticmethod
    async def handle_ai_chat(user_message: str, recruiter_id: int, db: Session) -> str:
        prompt = (
            f"You are Candway's recruiting assistant. A recruiter says: {user_message}\n"
            f"Respond helpfully about candidates, hiring, or direct them to /candway commands."
        )
        try:
            result = await call_groq_cascade(prompt, max_tokens=300)
            return result.get("text", "I'm not sure how to help with that.")
        except Exception as e:
            logger.error(f"AI chat error: {e}")
            return "Sorry, I had trouble processing your message."

    @staticmethod
    async def get_oauth_url(state: str) -> str:
        return (
            f"https://slack.com/oauth/v2/authorize?"
            f"client_id={SLACK_CLIENT_ID}&scope=chat:write,commands,"
            f"users:read,channels:read,reactions:read&state={state}"
        )

    @staticmethod
    async def exchange_oauth_code(code: str) -> Optional[dict]:
        client = SlackBot._get_client()
        try:
            resp = await client.post(
                "https://slack.com/api/oauth.v2.access",
                data={
                    "client_id": SLACK_CLIENT_ID,
                    "client_secret": SLACK_CLIENT_SECRET,
                    "code": code,
                },
            )
            return resp.json()
        except Exception as e:
            logger.error(f"Slack OAuth exchange error: {e}")
            return None
