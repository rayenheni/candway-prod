"""One-liner helpers to write domain entities.

Usage:
    from backend.entity_writer import (
        sync_cv_document, sync_ai_interview_session, sync_evaluation_state,
    )

    sync_cv_document(db, app, declared_role="Engineer", cv_text_anonymized="...")
    sync_ai_interview_session(db, app, interview_state="completed", interview_log=[...])
    sync_evaluation_state(db, app, evaluation_state="completed")
"""

import logging
from typing import Any, Optional

from backend.database import (
    Application,
    CvDocument,
    EvaluationSession,
)
from backend.optimistic_lock import retry_stale

logger = logging.getLogger(__name__)

# Sentinel used by sync helpers so None can mean "explicitly clear this field".
_UNSET = object()


@retry_stale()
def sync_cv_document(
    db: Any,
    app: Application,
    *,
    cv_text: Optional[str] = None,
    cv_text_anonymized: Optional[str] = None,
    analysis_json: Optional[Any] = None,
    roadmap_json: Optional[Any] = None,
    declared_role: Optional[str] = None,
    detected_role: Optional[str] = None,
    cv_embedding: Optional[str] = None,
    cv_file_path: Optional[str] = None,
    extracted_skills: Optional[Any] = None,
    cv_review_json: Optional[Any] = None,
) -> CvDocument:
    obj = app.cv_document
    if obj is None:
        obj = CvDocument(application_id=app.id, company_id=app.company_id)
        db.add(obj)
        app.cv_document = obj
    if cv_text is not None:
        obj.cv_text = cv_text
    if cv_text_anonymized is not None:
        obj.cv_text_anonymized = cv_text_anonymized
    if analysis_json is not None:
        # CvDocument.analysis_json is a SQLAlchemy JSON column.
        # Accept both native Python JSON values and legacy callers that
        # still pass json.dumps(...), but never persist a JSON string
        # containing another JSON document.
        if isinstance(analysis_json, str):
            import json

            try:
                analysis_json = json.loads(analysis_json)
            except (TypeError, ValueError):
                logger.warning(
                    "sync_cv_document: analysis_json is not valid JSON "
                    "for application %s; preserving as string",
                    app.id,
                )
        obj.analysis_json = analysis_json
    if roadmap_json is not None:
        obj.roadmap_json = roadmap_json
    if declared_role is not None:
        obj.declared_role = declared_role
    if detected_role is not None:
        obj.detected_role = detected_role
    if cv_embedding is not None:
        obj.cv_embedding = cv_embedding
    if cv_file_path is not None:
        obj.cv_file_path = cv_file_path
    if extracted_skills is not None:
        obj.extracted_skills = extracted_skills
    if cv_review_json is not None:
        obj.cv_review_json = cv_review_json
    return obj


@retry_stale()
def sync_ai_interview_session(
    db: Any,
    app: Application,
    *,
    interview_state: Optional[str] = None,
    interview_progress: Optional[int] = None,
    interview_time_left: Optional[int] = None,
    interview_last_saved: Any = _UNSET,
    interview_log: Optional[Any] = None,
    interview_questions: Optional[Any] = None,
    proctoring_violations: Optional[Any] = None,
    turn_seq: Optional[int] = None,
    video_file_path: Optional[str] = None,
    video_transcript: Optional[str] = None,
    video_analysis_json: Optional[Any] = None,
    generated_questions: Optional[Any] = None,
    calibration_json: Optional[Any] = None,
    calibration_score: Optional[float] = None,
    calibration_verified_skills: Optional[Any] = None,
    interview_reset_count: Optional[int] = None,
    interview_last_reset_at: Optional[Any] = None,
    rubric_id: Optional[int] = None,
    rubric_version: Optional[int] = None,
    evaluation_config_snapshot_id: Optional[int] = None,
    expires_at: Optional[Any] = None,
) -> EvaluationSession:
    eval_session = None
    if app.evaluation_sessions:
        # Reuse the newest session that belongs to the current
        # interview lifecycle. Invitation-created sessions use
        # status="pending", interview_state="not_started".
        #
        # Never fall back to an arbitrary historical session
        # (e.g. app.evaluation_sessions[0]).
        # Application.evaluation_sessions is ordered by
        # EvaluationSession.id DESC, so iteration already starts
        # with the newest session. Do NOT use reversed() here:
        # that would prefer historical sessions.
        for s in app.evaluation_sessions:
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
            application_id=app.id,
            company_id=app.company_id,
            rubric_id=app.rubric_id,
        )
        db.add(eval_session)
        app.evaluation_sessions.append(eval_session)
    eval_session.company_id = app.company_id
    if interview_state is not None:
        eval_session.interview_state = interview_state
        status_map = {
            "not_started": "created",
            "in_progress": "in_progress",
            "completed": "completed",
            "expired": "completed",
            "flagged": "flagged",
            "paused": "paused",
        }
        eval_session.status = status_map.get(interview_state, "created")
    if interview_progress is not None:
        eval_session.interview_progress = interview_progress
    if interview_time_left is not None:
        eval_session.interview_time_left = interview_time_left
    if interview_last_saved is not _UNSET:
        eval_session.interview_last_saved = interview_last_saved
    if interview_log is not None:
        eval_session.interview_log = interview_log
    if interview_questions is not None:
        eval_session.interview_questions = interview_questions
    if proctoring_violations is not None:
        eval_session.proctoring_violations = proctoring_violations
    if turn_seq is not None:
        eval_session.interview_turn_seq = turn_seq
    if video_file_path is not None:
        eval_session.video_file_path = video_file_path
    if video_transcript is not None:
        eval_session.video_transcript = video_transcript
    if video_analysis_json is not None:
        eval_session.video_analysis_json = video_analysis_json
    if generated_questions is not None:
        eval_session.generated_questions = generated_questions
    if calibration_json is not None:
        eval_session.calibration_json = calibration_json
    if calibration_score is not None:
        eval_session.calibration_score = calibration_score
    if calibration_verified_skills is not None:
        eval_session.calibration_verified_skills = calibration_verified_skills
    if interview_reset_count is not None:
        eval_session.interview_reset_count = interview_reset_count
    if interview_last_reset_at is not None:
        eval_session.interview_last_reset_at = interview_last_reset_at
    if rubric_id is not None:
        eval_session.rubric_id = rubric_id
    if rubric_version is not None:
        eval_session.rubric_version = rubric_version
    if evaluation_config_snapshot_id is not None:
        eval_session.evaluation_config_snapshot_id = evaluation_config_snapshot_id
    if expires_at is not None:
        eval_session.expires_at = expires_at

    return eval_session


@retry_stale()
def sync_evaluation_state(
    db: Any,
    app: Application,
    *,
    evaluation_state: Optional[str] = None,
    evaluation_source: Optional[str] = None,
    evaluation_completed_at: Optional[Any] = None,
) -> None:
    eval_session = None
    if app.evaluation_sessions:
        for s in app.evaluation_sessions:
            if s.status in ("created", "in_progress", "paused"):
                eval_session = s
                break
        if eval_session is None:
            eval_session = app.evaluation_sessions[-1]
    if eval_session is None:
        return
    if evaluation_state is not None:
        eval_session.status = evaluation_state
    if evaluation_source is not None:
        eval_session.source = evaluation_source
    if evaluation_completed_at is not None:
        eval_session.completed_at = evaluation_completed_at
