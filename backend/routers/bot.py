import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.bot_router import BotRouter
from backend.database import BotIntegration, User
from backend.dependencies import get_db, require_recruiter
from backend.slack_bot import SlackBot
from backend.teams_bot import TeamsBot

router = APIRouter(prefix="/bot", tags=["Bot Integrations"])


class ConnectRequest(BaseModel):
    platform: str
    code: str
    state: str = ""


class DisconnectRequest(BaseModel):
    platform: str


# ── Slack Endpoints ─────────────────────────────────────────────


@router.post("/slack/events")
async def slack_events(request: Request, db: Session = Depends(get_db)):
    body = await request.body()
    body_str = body.decode("utf-8")

    signature = request.headers.get("X-Slack-Signature", "")
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")

    if not SlackBot.verify_request(signature, timestamp, body_str):
        raise HTTPException(status_code=403, detail="Invalid signature")

    payload = json.loads(body_str)

    if payload.get("type") == "url_verification":
        return {"challenge": payload.get("challenge", "")}

    if payload.get("type") == "event_callback":
        event = payload.get("event", {})
        event_type = event.get("type", "")

        if event_type == "app_mention":
            text = event.get("text", "")
            user_id = event.get("user", "")
            channel = event.get("channel", "")

            integration = (
                db.query(BotIntegration)
                .filter(
                    BotIntegration.platform == "slack",
                    BotIntegration.platform_user_id == user_id,
                    BotIntegration.is_active,
                )
                .first()
            )
            if integration:
                recruiter = (
                    db.query(User).filter(User.id == integration.recruiter_id).first()
                )
                if recruiter:
                    reply = await SlackBot.handle_ai_chat(text, recruiter.id, db)
                    await SlackBot.send_message(
                        channel=channel,
                        blocks=[
                            {
                                "type": "section",
                                "text": {"type": "mrkdwn", "text": reply},
                            }
                        ],
                        text=reply,
                    )

        elif event_type == "message" and event.get("channel_type") == "im":
            text = event.get("text", "")
            user_id = event.get("user", "")
            channel = event.get("channel", "")

            if text.startswith("/"):
                integration = (
                    db.query(BotIntegration)
                    .filter(
                        BotIntegration.platform == "slack",
                        BotIntegration.platform_user_id == user_id,
                        BotIntegration.is_active,
                    )
                    .first()
                )
                if integration:
                    recruiter = (
                        db.query(User)
                        .filter(User.id == integration.recruiter_id)
                        .first()
                    )
                    if recruiter:
                        result = await SlackBot.handle_slash_command(
                            "", text.lstrip("/"), user_id, channel, db, recruiter
                        )
                        blocks = result.get("blocks", [])
                        fallback_text = result.get("text", "")
                        await SlackBot.send_message(
                            channel=channel, blocks=blocks, text=fallback_text
                        )

    return {"ok": True}


@router.post("/slack/interactive")
async def slack_interactive(request: Request, db: Session = Depends(get_db)):
    body = await request.form()
    payload_str = body.get("payload", "")

    if not payload_str:
        raise HTTPException(status_code=400, detail="Missing payload")

    payload = json.loads(payload_str)

    result = await SlackBot.handle_interactive(payload, db)
    return result


@router.get("/slack/auth-url")
async def slack_auth_url(recruiter: User = Depends(require_recruiter)):
    state = f"{recruiter.id}:{uuid.uuid4().hex[:8]}"
    url = await SlackBot.get_oauth_url(state)
    return {"url": url, "state": state}


# ── Teams Endpoints ─────────────────────────────────────────────


@router.post("/teams/messages")
async def teams_messages(request: Request, db: Session = Depends(get_db)):
    auth = request.headers.get("Authorization", "")

    if not TeamsBot.verify_request(auth):
        raise HTTPException(status_code=401, detail="Invalid auth")

    body = await request.json()
    result = await TeamsBot.handle_activity(body, db)
    return result


@router.get("/teams/auth-url")
async def teams_auth_url(recruiter: User = Depends(require_recruiter)):
    state = f"{recruiter.id}:{uuid.uuid4().hex[:8]}"
    url = await TeamsBot.get_oauth_url(state)
    return {"url": url, "state": state}


# ── Integration Management ──────────────────────────────────────


@router.post("/connect")
async def connect_bot(
    req: ConnectRequest,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    platform = req.platform.lower()

    if platform == "slack":
        oauth_result = await SlackBot.exchange_oauth_code(req.code)
        if not oauth_result or not oauth_result.get("ok"):
            raise HTTPException(
                status_code=400,
                detail=f"Slack OAuth failed: {oauth_result.get('error', 'unknown') if oauth_result else 'no response'}",
            )
        authed_user = oauth_result.get("authed_user", {}) or oauth_result.get(
            "authed_user", {}
        )
        bot_user_id = authed_user.get("id", "")
        team_id = oauth_result.get("team", {}).get("id", "")
        access_token = oauth_result.get("access_token", "")

        BotRouter.link_platform_account(
            platform="slack",
            platform_user_id=bot_user_id,
            candway_user_id=recruiter.id,
            db=db,
            platform_team_id=team_id,
            access_token=access_token,
        )

        return {"success": True, "platform": "slack", "user_id": bot_user_id}

    elif platform == "teams":
        token_result = await TeamsBot.exchange_oauth_code(req.code)
        if not token_result or "access_token" not in token_result:
            raise HTTPException(
                status_code=400,
                detail="Teams OAuth failed",
            )

        user_id = req.state.split(":")[0] if ":" in req.state else recruiter.id
        BotRouter.link_platform_account(
            platform="teams",
            platform_user_id=str(user_id),
            candway_user_id=recruiter.id,
            db=db,
            access_token=token_result.get("access_token"),
        )

        return {"success": True, "platform": "teams"}

    raise HTTPException(status_code=400, detail=f"Unsupported platform: {platform}")


@router.get("/status")
async def bot_status(
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    integrations = (
        db.query(BotIntegration)
        .filter(
            BotIntegration.recruiter_id == recruiter.id,
            BotIntegration.is_active,
        )
        .all()
    )

    platforms = {}
    for integration in integrations:
        platforms[integration.platform] = {
            "connected": True,
            "platform_user_id": integration.platform_user_id,
            "platform_team_id": integration.platform_team_id,
            "created_at": integration.created_at.isoformat()
            if integration.created_at
            else None,
        }

    return {
        "connected_platforms": platforms,
        "total_integrations": len(integrations),
        "has_slack": "slack" in platforms,
        "has_teams": "teams" in platforms,
    }


@router.post("/disconnect")
async def disconnect_bot(
    req: DisconnectRequest,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    platform = req.platform.lower()

    integrations = (
        db.query(BotIntegration)
        .filter(
            BotIntegration.recruiter_id == recruiter.id,
            BotIntegration.platform == platform,
            BotIntegration.is_active,
        )
        .all()
    )

    if not integrations:
        raise HTTPException(
            status_code=404, detail=f"No active {platform} integration found"
        )

    for integration in integrations:
        integration.is_active = False

    db.commit()

    return {"success": True, "platform": platform, "disconnected": True}


@router.post("/test-notification")
async def test_notification(
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    integrations = (
        db.query(BotIntegration)
        .filter(
            BotIntegration.recruiter_id == recruiter.id,
            BotIntegration.is_active,
        )
        .all()
    )

    if not integrations:
        raise HTTPException(status_code=400, detail="No active bot integrations found")

    for integration in integrations:
        if integration.platform == "slack":
            await SlackBot.send_message(
                channel=f"@{integration.platform_user_id}",
                blocks=[
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "Test notification from Candway! Your bot is working correctly.",
                        },
                    }
                ],
                text="Test notification from Candway",
            )
        elif integration.platform == "teams" and integration.conversation_ref:
            import json

            card = {
                "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                "type": "AdaptiveCard",
                "version": "1.4",
                "body": [
                    {
                        "type": "TextBlock",
                        "text": "Test Notification",
                        "weight": "bolder",
                    },
                    {
                        "type": "TextBlock",
                        "text": "Your Teams bot is working correctly!",
                        "wrap": True,
                    },
                ],
            }
            try:
                conv_ref = json.loads(integration.conversation_ref)
                await TeamsBot.send_proactive_notification(conv_ref, card)
            except (json.JSONDecodeError, TypeError):
                pass

    return {
        "success": True,
        "message": "Test notification sent to all active integrations",
    }


@router.get("/usage")
async def bot_usage(
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    integrations = (
        db.query(BotIntegration)
        .filter(BotIntegration.recruiter_id == recruiter.id)
        .all()
    )

    return {
        "total_integrations": len(integrations),
        "active_integrations": sum(1 for i in integrations if i.is_active),
        "platforms": list(set(i.platform for i in integrations)),
    }
