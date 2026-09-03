"""
Backfill extracted entities from existing Application rows.

Populates CvDocument, AIInterviewSession, ApplicationScore, and EvaluationState
from the legacy Application columns.

Safe to run multiple times (upsert via application_id unique constraint).
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import (
    Application, CvDocument, AIInterviewSession,
    ApplicationScore, EvaluationState, SessionLocal
)
from backend.logger import logger


def backfill_cv_documents(db):
    apps = db.query(Application).filter(
        Application.cv_text_anonymized.isnot(None)
        | Application.analysis_json.isnot(None)
    ).all()
    count = 0
    for app in apps:
        existing = db.query(CvDocument).filter(CvDocument.application_id == app.id).first()
        if existing:
            continue
        doc = CvDocument(
            application_id=app.id,
            cv_text=app.cv_text_anonymized,
            cv_file_path=app.cv_file_path,
            cv_text_anonymized=app.cv_text_anonymized,
            cv_embedding=app.cv_embedding,
            analysis_json=_safe_json(app.analysis_json),
            cv_review_json=_safe_json(app.cv_review_json),
            roadmap_json=_safe_json(app.roadmap_json),
            detected_role=app.detected_role,
            declared_role=app.declared_role,
        )
        db.add(doc)
        count += 1
    db.commit()
    logger.info(f"Backfilled {count} CvDocument rows")


def backfill_ai_interview_sessions(db):
    from sqlalchemy import or_
    apps = db.query(Application).filter(
        or_(
            Application.interview_state != "not_started",
            Application.interview_qa_structured.isnot(None),
        )
    ).all()
    count = 0
    for app in apps:
        existing = db.query(AIInterviewSession).filter(
            AIInterviewSession.application_id == app.id
        ).first()
        if existing:
            continue
        session = AIInterviewSession(
            application_id=app.id,
            interview_state=app.interview_state or "not_started",
            interview_progress=app.interview_progress or 0,
            interview_time_left=app.interview_time_left or 1800,
            interview_last_saved=app.interview_last_saved,
            interview_log=_safe_json(app.interview_log),
            interview_questions=_safe_json(app.interview_questions),
            interview_qa_structured=_safe_json(app.interview_qa_structured),
            generated_questions=_safe_json(app.generated_questions),
            proctoring_violations=_safe_json(app.proctoring_violations),
            video_file_path=app.video_file_path,
            video_transcript=app.video_transcript,
            video_analysis_json=_safe_json(app.video_analysis_json),
            interview_reset_count=app.interview_reset_count or 0,
            interview_last_reset_at=app.interview_last_reset_at,
            interview_turn_seq=app.interview_turn_seq or 0,
            calibration_json=_safe_json(app.calibration_json),
            calibration_score=app.calibration_score,
            calibration_verified_skills=_safe_json(app.calibration_verified_skills),
        )
        db.add(session)
        count += 1
    db.commit()
    logger.info(f"Backfilled {count} AIInterviewSession rows")


def backfill_application_scores(db):
    apps = db.query(Application).filter(
        Application.overall_score.isnot(None)
    ).all()
    count = 0
    for app in apps:
        existing = db.query(ApplicationScore).filter(
            ApplicationScore.application_id == app.id
        ).first()
        if existing:
            continue
        score = ApplicationScore(
            application_id=app.id,
            cv_score=app.cv_score,
            final_score=app.overall_score or 0,
            composite_score=app.overall_score or 0,
            verdict=app.verdict,
            fraud_score=app.fraud_score or 0.0,
            fraud_reported_by=app.fraud_reported_by,
            fraud_reported_at=app.fraud_reported_at,
            scoring_model=app.scoring_model or "legacy",
        )
        db.add(score)
        count += 1
    db.commit()
    logger.info(f"Backfilled {count} ApplicationScore rows")


def backfill_evaluation_states(db):
    all_apps = db.query(Application).all()
    count = 0
    for app in all_apps:
        ev = app.evaluation_state
        if ev and ev.evaluation_state:
            continue
        existing = db.query(EvaluationState).filter(
            EvaluationState.application_id == app.id
        ).first()
        if existing:
            continue
        state = EvaluationState(
            application_id=app.id,
            evaluation_state=ev.evaluation_state if ev else "pending",
            evaluation_started_at=ev.evaluation_started_at if ev else None,
            evaluation_completed_at=ev.evaluation_completed_at if ev else None,
            final_eval_done=ev.final_eval_done if ev else False,
            final_eval_timestamp=ev.final_eval_timestamp if ev else None,
        )
        db.add(state)
        count += 1
    db.commit()
    logger.info(f"Backfilled {count} EvaluationState rows")


def _safe_json(val):
    if val is None:
        return None
    if isinstance(val, (dict, list)):
        return val
    import json
    try:
        return json.loads(val)
    except (json.JSONDecodeError, TypeError):
        return None


if __name__ == "__main__":
    db = SessionLocal()
    try:
        backfill_cv_documents(db)
        backfill_ai_interview_sessions(db)
        backfill_application_scores(db)
        backfill_evaluation_states(db)
        logger.info("Backfill complete")
    finally:
        db.close()
