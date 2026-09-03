import glob
import json
import os
import time
from datetime import UTC, datetime
from typing import Any, Dict

from sqlalchemy.orm import Session

from backend.ai.state_machine import InterviewState, InterviewStateMachine
from backend.encryption import encrypt_text
from backend.entity_writer import sync_ai_interview_session
from backend.logger import logger

# Directory for durable event logs (File-based fallback for Kafka/Redis).
# CANDWAY_EVENTS_DIR overrides the location to keep PII out of the source
# tree; the default is kept inside the package for backwards compatibility
# with deployments that have not yet set the variable.
_DEFAULT_EVENTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "interviews_events"
)
EVENTS_DIR = os.environ.get("CANDWAY_EVENTS_DIR", _DEFAULT_EVENTS_DIR)
os.makedirs(EVENTS_DIR, exist_ok=True)

# Set CANDWAY_ENCRYPT_EVENT_LOG=1 to encrypt the per-event ``data``
# payload on disk. Event type, timestamp, and app_id stay plaintext
# so on-call can still tail/grep ``app_42.events.jsonl`` and see
# the high-level event stream. PII inside the data dict (full
# questions, free-form answers, evaluation rationale) is encrypted.
ENCRYPT_EVENT_LOG = os.environ.get("CANDWAY_ENCRYPT_EVENT_LOG", "1") != "0"

# Log rotation settings
MAX_EVENT_FILE_SIZE = 5 * 1024 * 1024  # 5MB per event file
MAX_EVENT_FILES = 5  # Keep at most 5 rotated files per app
MAX_EVENT_AGE_DAYS = 30  # Delete event files older than 30 days


class EventLogger:
    """Durably logs interview lifecycle events to disk with rotation."""

    @staticmethod
    def _rotate_if_needed(filepath: str):
        """Rotate event file if it exceeds MAX_EVENT_FILE_SIZE."""
        if not os.path.exists(filepath):
            return

        file_size = os.path.getsize(filepath)
        if file_size < MAX_EVENT_FILE_SIZE:
            return

        # Rotate existing numbered files
        for i in range(MAX_EVENT_FILES - 1, 0, -1):
            old_path = f"{filepath}.{i}"
            new_path = f"{filepath}.{i + 1}"
            if os.path.exists(old_path):
                if i + 1 > MAX_EVENT_FILES:
                    os.remove(old_path)
                else:
                    os.rename(old_path, new_path)

        # Move current to .1
        rotated_path = f"{filepath}.1"
        os.rename(filepath, rotated_path)
        logger.info(f"[EVENT ROTATION] Rotated {filepath} (size: {file_size} bytes)")

    @staticmethod
    def cleanup_old_events():
        """Remove event files older than MAX_EVENT_AGE_DAYS."""
        if not os.path.exists(EVENTS_DIR):
            return

        cutoff = time.time() - (MAX_EVENT_AGE_DAYS * 86400)
        for filepath in glob.glob(os.path.join(EVENTS_DIR, "*.events.jsonl*")):
            if os.path.getmtime(filepath) < cutoff:
                try:
                    os.remove(filepath)
                    logger.info(f"[EVENT CLEANUP] Removed old event file: {filepath}")
                except OSError as e:
                    logger.error(f"[EVENT CLEANUP] Failed to remove {filepath}: {e}")

    @staticmethod
    def log(app_id: int, event_type: str, data: Dict[str, Any]):
        if not os.path.exists(EVENTS_DIR):
            os.makedirs(EVENTS_DIR, exist_ok=True)

        filename = f"app_{app_id}.events.jsonl"
        filepath = os.path.join(EVENTS_DIR, filename)

        # Rotate if file is too large
        EventLogger._rotate_if_needed(filepath)

        # Periodic cleanup (every 100th log call approximately)
        if hash(event_type) % 100 == 0:
            EventLogger.cleanup_old_events()

        timestamp = datetime.now(UTC).isoformat()
        if ENCRYPT_EVENT_LOG:
            # Keep timestamp + event_type + app_id in plaintext so
            # operators can still grep / tail the file and see what
            # happened. The free-form ``data`` payload — which
            # includes full question text, the candidate's answer,
            # and AI feedback — is encrypted with the same Fernet
            # key as the DB columns. Result: a leaked log file
            # shows "TURN_STARTED at 14:23" with an opaque blob
            # where the question would be.
            event = {
                "timestamp": timestamp,
                "event_type": event_type,
                "app_id": app_id,
                "data_encrypted": True,
                "data": encrypt_text(json.dumps(data, default=str)),
            }
        else:
            event = {
                "timestamp": timestamp,
                "event_type": event_type,
                "app_id": app_id,
                "data": data,
            }

        try:
            with open(filepath, "a", encoding="utf-8") as f:
                f.write(json.dumps(event, default=str) + "\n")
        except Exception as e:
            logger.error(f"Failed to log event for app {app_id}: {e}")


class InterviewEngine:
    """
    Orchestrates the AI interview lifecycle using the state machine.
    Ensures state integrity and durable logging.
    """

    def __init__(self, db: Session):
        self.db = db

    def _resolve_app(self, app):
        """Resolve app object from app_id if needed.

        Avoids module-level ORM imports — uses lazy import only for the
        id-to-object lookup when callers pass a raw int.
        """
        if isinstance(app, int):
            from backend.database import Application

            obj = self.db.query(Application).filter(Application.id == app).first()
            if not obj:
                raise ValueError(f"Application {app} not found")
            return obj
        return app

    async def transition_to(self, app_id, to_state: InterviewState, reason: str = ""):
        """Safely transition an interview to a new state."""
        app = self._resolve_app(app_id)
        from_state = app.interview_state or InterviewState.NOT_STARTED.value

        # Normalize DB state string to Enum (handles legacy "idle" + case)
        from_enum = InterviewStateMachine.from_db_value(from_state)

        # IDEMPOTENCY: If already in target state, ignore (prevents 500 errors on redundant signals)
        if from_enum == to_state:
            logger.debug(
                f"[ENGINE] App {app_id} already in state {to_state}. Skipping transition."
            )
            return

        if InterviewStateMachine.can_transition(from_enum, to_state):
            logger.info(
                f"[ENGINE] App {app_id} transitioning: {from_enum} -> {to_state} ({reason})"
            )
            sync_ai_interview_session(self.db, app, interview_state=to_state.value)
            sync_ai_interview_session(
                self.db,
                app,
                interview_last_saved=datetime.now(UTC).replace(tzinfo=None),
            )

            # Durable Log
            EventLogger.log(
                app_id,
                "STATE_TRANSITION",
                {"from": from_enum.value, "to": to_state.value, "reason": reason},
            )

            self.db.commit()
        else:
            logger.warning(
                f"[ENGINE] Blocked illegal transition for app {app_id}: {from_enum} -> {to_state}"
            )
            raise ValueError(f"Illegal transition from {from_enum} to {to_state}")

    async def record_turn_start(self, app_id: int, q_index: int, question: str):
        """Log that a question has been presented to the user."""
        EventLogger.log(
            app_id,
            "TURN_STARTED",
            {
                "q_index": q_index,
                "question": question[:200] + "..." if len(question) > 200 else question,
            },
        )

    async def record_answer(self, app_id: int, q_index: int, answer: str):
        """Log that a user has provided an answer."""
        EventLogger.log(
            app_id,
            "ANSWER_RECEIVED",
            {"q_index": q_index, "answer_length": len(answer)},
        )

    async def record_evaluation(
        self, app_id: int, q_index: int, evaluation_data: Dict[str, Any]
    ):
        """Log the AI's evaluation of an answer."""
        EventLogger.log(
            app_id,
            "EVALUATION_COMPLETED",
            {
                "q_index": q_index,
                "score": evaluation_data.get("current_score"),
                "quality": evaluation_data.get("answer_quality"),
            },
        )

    async def force_fail(self, app_id: int, error: str):
        """Move interview to FAILED state due to technical error."""
        await self.transition_to(app_id, InterviewState.FAILED, reason=error)

    async def transition_app(self, app, to_state: InterviewState, reason: str = ""):
        """Convenience wrapper that accepts an app object directly."""
        await self.transition_to(
            app.id if isinstance(app, int) else app.id, to_state, reason
        )
