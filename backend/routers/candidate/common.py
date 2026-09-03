import asyncio
import json
import logging
import os

from backend.enums import ApplicationStatus

logger = logging.getLogger(__name__)

VALID_APPLICATION_STATUSES = {s.value for s in ApplicationStatus} | {
    "applied",
    "analyzing",
    "analyzed",
    "analysis_failed",
    "failed",
    "invited",
    "imported",
    "preselected",
    "under_review",
    "expired",
}


async def _check_api_rate_limit(
    identifier: str, max_requests: int, window_seconds: int
):
    """Async bridge around the Redis rate limiter with a stable return contract."""
    if os.getenv("TESTING") == "true":
        return True, 0

    from backend.redis_rate_limiter import check_rate_limit

    is_allowed, metadata = await check_rate_limit(
        identifier=identifier,
        max_requests=max_requests,
        window_seconds=window_seconds,
    )
    retry_after = metadata.get("retry_after", 0) if isinstance(metadata, dict) else 0
    return is_allowed, retry_after


def _check_api_rate_limit_sync(identifier: str, max_requests: int, window_seconds: int):
    """Sync wrapper for endpoints that run in threadpool workers."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run,
                    _check_api_rate_limit(identifier, max_requests, window_seconds),
                )
                return future.result()
        else:
            return loop.run_until_complete(
                _check_api_rate_limit(identifier, max_requests, window_seconds)
            )
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(
                _check_api_rate_limit(identifier, max_requests, window_seconds)
            )
        finally:
            loop.close()
    except Exception:
        return True, 0


def safe_load_json(json_value, default_value=None):
    """Safely load JSON from either a serialized string or native JSON value.

    SQLAlchemy JSON columns are returned as native Python dict/list values,
    while legacy Text columns may still contain serialized JSON strings.
    """
    if default_value is None:
        default_value = {}

    if json_value is None or json_value == "":
        return default_value

    # SQLAlchemy JSON columns can already return native Python JSON values.
    if isinstance(json_value, (dict, list, int, float, bool)):
        return json_value

    if not isinstance(json_value, str):
        logger.warning(
            "Unsupported JSON value type: %s",
            type(json_value).__name__,
        )
        return default_value

    if len(json_value) > 256_000:
        logger.warning(
            f"JSON payload too large: {len(json_value)} bytes, rejecting"
        )
        return default_value

    try:
        return json.loads(json_value)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON: {str(e)[:100]}")
        return default_value
    except Exception as e:
        logger.error(f"Unexpected error parsing JSON: {type(e).__name__}")
        return default_value


def normalize_interview_log_for_dashboard(raw_log, raw_qa) -> list:
    """
    Normalize interview history into the candidate-dashboard chat format.

    Supports:
      - canonical {role, content} messages
      - legacy {question, answer, feedback} records
      - legacy QA logs
    """
    import json

    def parse(value):
        if value is None:
            return []
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except Exception:
                return []
        return value if isinstance(value, list) else []

    normalized = []

    # Prefer the actual interview log when present.
    log = parse(raw_log)
    qa = parse(raw_qa)

    for item in log:
        if not isinstance(item, dict):
            continue

        # Already canonical chat message.
        if item.get("role") and "content" in item:
            normalized.append(
                {
                    "role": item.get("role"),
                    "content": str(item.get("content") or ""),
                }
            )
            continue

        # Legacy Q/A record.
        question = item.get("question")
        answer = item.get("answer")
        feedback = item.get("feedback")

        if question:
            normalized.append(
                {
                    "role": "assistant",
                    "content": str(question),
                }
            )

        if answer:
            normalized.append(
                {
                    "role": "user",
                    "content": str(answer),
                }
            )

        if feedback:
            normalized.append(
                {
                    "role": "assistant",
                    "content": str(feedback),
                }
            )

    # If no usable interview_log exists, normalize legacy QA data.
    if not normalized:
        for item in qa:
            if not isinstance(item, dict):
                continue

            question = item.get("question") or item.get("q")
            answer = item.get("answer") or item.get("a")
            feedback = item.get("feedback")

            if question:
                normalized.append(
                    {
                        "role": "assistant",
                        "content": str(question),
                    }
                )

            if answer:
                normalized.append(
                    {
                        "role": "user",
                        "content": str(answer),
                    }
                )

            if feedback:
                normalized.append(
                    {
                        "role": "assistant",
                        "content": str(feedback),
                    }
                )

    return normalized
