"""
Helpers for the ``interview_turns`` table.

Turn writes go through ``write_turn()`` and reads go through
``load_turns()``. The legacy ``Application.interview_qa_structured``
JSON bag was removed in Phase 3B (June 2026).
"""

import logging
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.database import Application, EvaluationSession, InterviewTurn

logger = logging.getLogger(__name__)


def _to_dt(value: Any) -> Optional[datetime]:
    """Coerce a bag timestamp (float or ISO string) to datetime."""
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value), tz=UTC)
        except (OverflowError, OSError, ValueError):
            return None
    if isinstance(value, str):
        try:
            cleaned = value.replace("Z", "+00:00")
            return datetime.fromisoformat(cleaned)
        except ValueError:
            return None
    return None


def write_turn(
    db: Session,
    application: Application,
    turn_number: int,
    *,
    question: Optional[str] = None,
    answer: Optional[str] = None,
    score: Optional[float] = None,
    feedback: Optional[str] = None,
    reasoning: Optional[str] = None,
    quality: Optional[str] = None,
    type_: Optional[str] = None,
    difficulty: Optional[str] = None,
    response_time_seconds: Optional[float] = None,
    status: Optional[str] = None,
    question_timestamp: Any = None,
    answer_timestamp: Any = None,
) -> InterviewTurn:
    """Insert (or update) a single turn row.

    Idempotent on (evaluation_session_id, turn_number): a re-write for
    the same turn overwrites the existing row so the chat
    handler can call this on every answer without a separate
    check.
    """
    # Resolve the current interview lifecycle session only.
    # Do not blindly use the newest/historical session: an application may
    # contain completed/expired sessions from previous interview attempts.
    eval_session = None

    if application.evaluation_sessions:
        for s in reversed(application.evaluation_sessions):
            if (
                s.interview_state in (
                    "not_started",
                    "in_progress",
                    "paused",
                    "flagged",
                )
                and s.status in (
                    "pending",
                    "created",
                    "in_progress",
                    "paused",
                    "flagged",
                )
            ):
                eval_session = s
                break

    if eval_session is None:
        eval_session = EvaluationSession(
            application_id=application.id,
            company_id=application.company_id,
            rubric_id=application.rubric_id,
            status="created",
            interview_state="not_started",
        )
        db.add(eval_session)
        application.evaluation_sessions.append(eval_session)
        db.flush()

    eval_session_id = eval_session.id
    existing = (
        db.query(InterviewTurn)
        .filter(
            InterviewTurn.evaluation_session_id == eval_session_id,
            InterviewTurn.turn_number == turn_number,
        )
        .first()
    )
    if existing is None:
        existing = InterviewTurn(
            application_id=None,
            evaluation_session_id=eval_session_id,
            company_id=application.company_id,
            user_id=application.user_id,
            turn_number=turn_number,
        )
        db.add(existing)

    existing.company_id = application.company_id
    existing.evaluation_session_id = eval_session_id
    existing.question = question if question is not None else existing.question
    existing.answer = answer if answer is not None else existing.answer
    if score is not None:
        existing.score = score
    existing.feedback = feedback if feedback is not None else existing.feedback
    existing.reasoning = reasoning if reasoning is not None else existing.reasoning
    if quality is not None:
        existing.quality = quality
    if type_ is not None:
        existing.type = type_
    if difficulty is not None:
        existing.difficulty = difficulty
    if response_time_seconds is not None:
        existing.response_time_seconds = response_time_seconds
    if status is not None:
        existing.status = status
    q_dt = _to_dt(question_timestamp)
    if q_dt is not None:
        existing.question_timestamp = q_dt
    a_dt = _to_dt(answer_timestamp)
    if a_dt is not None:
        existing.answer_timestamp = a_dt

    db.flush()
    return existing


def load_turns(
    db: Session,
    application: Application,
) -> List[Dict[str, Any]]:
    """Return the list of turns for an application.

    Reads from the ``interview_turns`` table ordered by
    ``turn_number``. Returns an empty list if no turns exist.
    """
    sessions = sorted(
        application.evaluation_sessions, key=lambda s: s.id or 0, reverse=True
    )
    if not sessions:
        return []
    eval_session_id = sessions[0].id
    rows = (
        db.query(InterviewTurn)
        .filter(InterviewTurn.evaluation_session_id == eval_session_id)
        .order_by(InterviewTurn.turn_number.asc())
        .all()
    )
    out: List[Dict[str, Any]] = []
    for r in rows:
        out.append(
            {
                "id": r.id,
                "number": r.turn_number,
                "question": r.question,
                "answer": r.answer,
                "score": r.score,
                "feedback": r.feedback or "",
                "reasoning": r.reasoning or "",
                "quality": r.quality or "normal",
                "type": r.type or "general",
                "difficulty": r.difficulty or "medium",
                "response_time_seconds": r.response_time_seconds,
                "status": r.status or "answered",
                "question_timestamp": (
                    r.question_timestamp.isoformat() if r.question_timestamp else None
                ),
                "answer_timestamp": (
                    r.answer_timestamp.isoformat() if r.answer_timestamp else None
                ),
            }
        )
    return out
