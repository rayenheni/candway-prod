import json
import logging
from datetime import UTC, datetime

from backend.database import AuditLog, SessionLocal

logger = logging.getLogger(__name__)


def _utcnow():
    return datetime.now(UTC).replace(tzinfo=None)


async def log_ai_interaction(
    model: str,
    messages: list,
    response_content: str,
    duration_ms: int,
    status: str = "success",
    user_id: int = None,
):
    """
    Trakin Observer: Logs AI interactions to the database for audit and cost analysis.
    Executed asynchronously to avoid blocking the main thread.
    """
    try:
        # Calculate approximate token count (rough estimate: 4 chars = 1 token)
        prompt_text = json.dumps(messages)
        prompt_tokens = len(prompt_text) / 4
        completion_tokens = len(str(response_content)) / 4
        total_tokens = prompt_tokens + completion_tokens

        details = {
            "model": model,
            "duration_ms": duration_ms,
            "tokens": {
                "prompt": int(prompt_tokens),
                "completion": int(completion_tokens),
                "total": int(total_tokens),
            },
            "status": status,
            "timestamp": _utcnow().isoformat(),
        }

        # redact long prompts in details if needed, but for Trakin we want full observability
        # We might want to truncate extremely long responses to save DB space
        if len(str(response_content)) > 5000:
            details["response_snippet"] = str(response_content)[:200] + "...(truncated)"

        db = SessionLocal()
        audit = AuditLog(
            user_id=user_id,  # Can be None if system task
            action="ai_inference",
            target_id=model,
            details=json.dumps(details),
            ip_address="internal_trakin",
        )
        db.add(audit)
        db.commit()
        db.close()

    except Exception as e:
        logger.error(f"[TRAKIN] Failed to log AI interaction: {e}")
