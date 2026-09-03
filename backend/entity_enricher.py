"""
Entity enrichment helpers for API serialization.

Bridges the gap between legacy Application god-column dicts and extracted
entities.  Each function takes a raw dict (built from an Application ORM row)
and returns an enriched copy with entity-namespaced fields.

Safe to call on every response — skips entities that weren't eager-loaded.
"""

import json
from datetime import datetime
from typing import Any, Dict


def enrich_with_application_score(app_dict: Dict[str, Any], app) -> Dict[str, Any]:
    """Add ``score_entity`` block from ``EvaluationResult`` only.

    Phase-1: fallback to Application legacy mirror columns removed.
    Applications without an EvaluationResult row get all-None fields.
    """
    sessions = getattr(app, "evaluation_sessions", []) or []
    s = None
    if sessions:
        s = sorted(sessions, key=lambda item: item.id or 0, reverse=True)[
            0
        ].evaluation_result
    if s is not None:
        app_dict["score_entity"] = {
            "cv_score": s.cv_score,
            "rubric_score": s.rubric_score,
            "human_integrity_score": s.human_integrity_score,
            "rubric_coverage_pct": s.rubric_coverage_pct,
            "final_score": s.final_score,
            "composite_score": s.composite_score
            if s.composite_score is not None
            else s.final_score,
            "score_breakdown": s.score_breakdown,
            "verdict": s.verdict
            or (
                (s.score_breakdown or {}).get("verdict") if s.score_breakdown else None
            ),
            "fraud_score": s.fraud_score,
            "scoring_model": s.scoring_model,
            "rubric_version": s.rubric_version,
            "computed_at": s.computed_at,
        }
    else:
        app_dict["score_entity"] = None
    return app_dict


def enrich_with_interview_session(app_dict: Dict[str, Any], app) -> Dict[str, Any]:
    """Add ``interview_entity`` block from ``EvaluationSession`` only."""
    sess = None
    if hasattr(app, "evaluation_sessions") and app.evaluation_sessions:
        sessions = sorted(
            app.evaluation_sessions,
            key=lambda s: s.updated_at or s.created_at or datetime.min,
            reverse=True,
        )
        sess = sessions[0]
    if sess is not None:
        app_dict["interview_entity"] = {
            "interview_state": sess.interview_state,
            "interview_progress": sess.interview_progress,
            "interview_time_left": sess.interview_time_left,
            "interview_last_saved": sess.interview_last_saved,
            "interview_log": sess.interview_log,
            "interview_questions": sess.interview_questions,
            "generated_questions": sess.generated_questions,
            "proctoring_violations": sess.proctoring_violations
            if isinstance(sess.proctoring_violations, list)
            else json.loads(sess.proctoring_violations)
            if isinstance(sess.proctoring_violations, str)
            else [],
            "video_file_path": sess.video_file_path,
            "video_transcript": sess.video_transcript,
            "video_analysis_json": sess.video_analysis_json,
            "calibration_json": sess.calibration_json,
            "calibration_score": sess.calibration_score,
            "calibration_verified_skills": sess.calibration_verified_skills,
            "started_at": sess.started_at,
            "completed_at": sess.completed_at,
        }
    else:
        app_dict["interview_entity"] = None
    return app_dict


def enrich_with_cv_document(app_dict: Dict[str, Any], app) -> Dict[str, Any]:
    """Add ``cv_entity`` block from ``CvDocument`` or fallback."""
    doc = getattr(app, "cv_document", None)
    if doc is not None:
        app_dict["cv_entity"] = {
            "cv_text": doc.cv_text,
            "cv_file_path": doc.cv_file_path,
            "cv_text_anonymized": doc.cv_text_anonymized,
            "extracted_skills": doc.extracted_skills,
            "analysis_json": doc.analysis_json,
            "cv_review_json": doc.cv_review_json,
            "roadmap_json": doc.roadmap_json,
            "detected_role": doc.detected_role,
            "declared_role": doc.declared_role,
        }
    else:
        app_dict["cv_entity"] = {
            "cv_file_path": app_dict.get("cv_file_path"),
            "cv_text_anonymized": app_dict.get("cv_text_anonymized"),
            "analysis_json": app_dict.get("analysis_json"),
            "roadmap_json": app_dict.get("roadmap_json"),
            "detected_role": app_dict.get("detected_role"),
            "declared_role": app_dict.get("declared_role"),
        }
    return app_dict


def enrich_application_dict(app_dict: Dict[str, Any], app) -> Dict[str, Any]:
    """Apply all entity enrichments to a dict built from an Application row."""
    enrich_with_application_score(app_dict, app)
    enrich_with_interview_session(app_dict, app)
    enrich_with_cv_document(app_dict, app)
    return app_dict
