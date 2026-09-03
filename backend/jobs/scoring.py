"""
Background Scoring Jobs
=========================

Scheduled background tasks for:
- Async bias audits (don't block interview completion)
- Drift monitoring checks (daily)
- Calibration sample collection
- Score recalibration when new human ratings arrive

Author: Candway Engineering
"""

import logging
from datetime import UTC, datetime, timedelta

logger = logging.getLogger("candway_app")

from backend.entity_writer import sync_cv_document  # noqa: E402
from backend.interview_turns import load_turns  # noqa: E402


async def run_async_bias_audit(application_id: int, company_id: int, db_session):
    """
    Run bias audit asynchronously after interview completion.
    Stores results in application's analysis_json.
    """
    try:
        import json

        from sqlalchemy.orm import selectinload

        from backend.ai.bias_detection import run_bias_audit
        from backend.database import Application

        app = (
            db_session.query(Application)
            .options(
                selectinload(Application.cv_document),
            )
            .filter(
                Application.id == application_id, Application.company_id == company_id
            )
            .first()
        )
        if not app:
            logger.warning(f"[ASYNC BIAS] App {application_id} not found")
            return

        _cv = app.cv_document
        qa_pairs = load_turns(db_session, app)
        _analysis_json = getattr(_cv, "analysis_json", None) or app.analysis_json

        if not qa_pairs:
            logger.info(f"[ASYNC BIAS] No QA pairs for app {application_id}")
            return

        report = run_bias_audit(
            qa_pairs=qa_pairs,
            candidate_language=app.language or "English",
            is_native_speaker=True,
            candidate_region=None,
        )

        # Store in analysis_json
        analysis = {}
        if _analysis_json:
            analysis = json.loads(_analysis_json)

        analysis["bias_audit"] = report.to_dict()
        analysis["bias_audit_timestamp"] = datetime.now(UTC).isoformat()
        sync_cv_document(db_session, app, analysis_json=analysis)
        db_session.commit()

        logger.info(
            f"[ASYNC BIAS] Audit complete for app {application_id}: fairness={report.fairness_score}"
        )

    except Exception as e:
        logger.error(f"[ASYNC BIAS] Failed for app {application_id}: {e}")
        raise


async def run_drift_check(company_id: int | None = None):
    """
    Run drift monitoring check across recent interviews for one company.
    If company_id is None, checks across all companies.
    """
    try:
        from sqlalchemy import func
        from sqlalchemy.orm import selectinload

        from backend.ai.drift_monitor import (
            create_snapshot_from_interviews,
            drift_monitor,
        )
        from backend.database import Application, EvaluationSession, SessionLocal

        with SessionLocal() as db:
            # Get interviews completed in last 24 hours
            cutoff = datetime.now(UTC) - timedelta(hours=24)
            # Subquery: latest EvaluationSession per application
            _latest_es = (
                db.query(
                    EvaluationSession.application_id,
                    func.max(EvaluationSession.id).label("max_id"),
                ).group_by(EvaluationSession.application_id)
            ).subquery("_latest_es")
            query = (
                db.query(Application)
                .options(selectinload(Application.evaluation_sessions))
                .join(_latest_es, _latest_es.c.application_id == Application.id)
                .join(EvaluationSession, EvaluationSession.id == _latest_es.c.max_id)
                .filter(
                    EvaluationSession.interview_state == "completed",
                    Application.final_eval_timestamp >= cutoff,
                )
            )
            if company_id is not None:
                query = query.filter(Application.company_id == company_id)
            recent_apps = query.all()

            if not recent_apps:
                logger.info("[DRIFT CHECK] No recent interviews to analyze")
                return

            interviews = []
            for app in recent_apps:
                qa_pairs = load_turns(db, app)

                for qa in qa_pairs:
                    if isinstance(qa, dict):
                        interviews.append(
                            {
                                "score": qa.get("score", 50),
                                "dimension_scores": {},
                                "response_time": qa.get("response_time_seconds", 0),
                                "error": qa.get("status") == "error",
                            }
                        )

            if not interviews:
                return

            snapshot = create_snapshot_from_interviews(interviews, "current")
            drift_monitor.record_snapshot(snapshot)

            # Check for drift
            report = drift_monitor.detect_drift(snapshot)

            if report.overall_drift_score >= 0.25:
                logger.warning(
                    f"[DRIFT CHECK] Significant drift detected: {report.overall_drift_score}"
                )
                logger.warning(f"[DRIFT CHECK] Alerts: {report.alerts}")
                logger.warning(f"[DRIFT CHECK] Recommendation: {report.recommendation}")

                # TODO: Send alert to admins
            else:
                logger.info(
                    f"[DRIFT CHECK] Model behavior stable: drift={report.overall_drift_score}"
                )

    except Exception as e:
        logger.error(f"[DRIFT CHECK] Failed: {e}")
        raise


async def collect_calibration_samples(company_id: int | None = None):
    """
    Collect calibration samples from interviews that have human reviews.
    If company_id is None, samples from all companies.
    """
    try:
        import json

        from sqlalchemy.orm import selectinload

        from backend.ai.calibration import calibration_store, create_calibration_sample
        from backend.database import Application, EvaluationSession, SessionLocal

        with SessionLocal() as db:
            # Find interviews with human overrides/reviews
            query = (
                db.query(Application)
                .options(
                    selectinload(Application.cv_document),
                    selectinload(Application.evaluation_sessions).selectinload(
                        EvaluationSession.evaluation_result
                    ),
                )
                .filter(
                    Application.evaluation_state == "override",
                    Application.recruiter_notes.isnot(None),
                )
            )
            if company_id is not None:
                query = query.filter(Application.company_id == company_id)
            reviewed_apps = query.limit(10).all()

            if not reviewed_apps:
                logger.info("[CALIBRATION] No new reviewed interviews to collect")
                return

            dataset = calibration_store.get_dataset("production")
            if not dataset:
                dataset = calibration_store.create_dataset("production")

            for app in reviewed_apps:
                _iv = app.evaluation_sessions[0] if app.evaluation_sessions else None
                _cv = app.cv_document
                _er = (
                    app.evaluation_sessions[0].evaluation_result
                    if app.evaluation_sessions
                    and app.evaluation_sessions[0].evaluation_result
                    else None
                )
                _sc = _er
                _ev = app.evaluation_state
                qa_pairs = load_turns(db, app)
                _analysis_json = (
                    getattr(_cv, "analysis_json", None) or app.analysis_json
                )
                _final_score = _sc.final_score if _sc else None
                _eval_state = getattr(_ev, "state", None) or app.evaluation_state
                _declared_role = (
                    getattr(_cv, "declared_role", None) or app.declared_role
                )

                sample_id = f"app_{app.id}"
                if any(s.sample_id == sample_id for s in dataset.samples):
                    continue

                # Extract AI scores
                ai_scores = {}
                if _analysis_json:
                    analysis = json.loads(_analysis_json)
                    breakdown = analysis.get("final_score_breakdown", {})
                    dims = breakdown.get("dimensions", {})
                    ai_scores = dims

                # Human ground truth must come from an actual recruiter evaluation,
                # NOT from EvaluationResult.final_score (which is the AI/canonical score).
                from backend.models.ats.interview import ScorecardSubmission

                human_ratings = {}

                human_submission = (
                    db.query(ScorecardSubmission)
                    .filter(
                        ScorecardSubmission.application_id == app.id,
                        ScorecardSubmission.company_id == app.company_id,
                    )
                    .order_by(ScorecardSubmission.submitted_at.desc())
                    .first()
                )

                if human_submission and human_submission.overall_score is not None:
                    human_ratings = {
                        "overall": float(human_submission.overall_score)
                    }
                    logger.info(
                        f"[CALIBRATION] Captured recruiter score "
                        f"{human_submission.overall_score} for app {app.id} "
                        f"from scorecard submission {human_submission.id}"
                    )

                if ai_scores and human_ratings:
                    sample = create_calibration_sample(
                        sample_id=sample_id,
                        role=_declared_role or "Professional",
                        seniority="Mid",
                        qa_pairs=qa_pairs,
                        human_ratings=human_ratings,
                        ai_scores=ai_scores,
                        metadata={"application_id": app.id, "score": _final_score},
                    )
                    dataset.add_sample(sample)
                    logger.info(
                        f"[CALIBRATION] Added sample {sample_id} with human_ratings={human_ratings}"
                    )
                elif ai_scores and not human_ratings:
                    logger.info(
                        f"[CALIBRATION] Skipping app {app.id}: no human_ratings available (evaluation_state={_eval_state})"
                    )

            logger.info(f"[CALIBRATION] Collected {len(reviewed_apps)} samples")

    except Exception as e:
        logger.error(f"[CALIBRATION] Collection failed: {e}")
        raise


async def run_score_recalibration(company_id: int | None = None):
    """
    Recalculate scores for recent interviews when scoring logic changes.
    If company_id is None, recalculates for all companies.
    """
    try:
        import json

        from sqlalchemy import func
        from sqlalchemy.orm import selectinload

        from backend.database import Application, EvaluationSession, SessionLocal
        from backend.scoring_service import ScoringService
        from backend.scoring_transparent import calculate_overall_score

        with SessionLocal() as db:
            cutoff = datetime.now(UTC) - timedelta(days=7)
            # Subquery: latest EvaluationSession per application
            _latest_es = (
                db.query(
                    EvaluationSession.application_id,
                    func.max(EvaluationSession.id).label("max_id"),
                ).group_by(EvaluationSession.application_id)
            ).subquery("_latest_es")
            query = (
                db.query(Application)
                .options(
                    selectinload(Application.cv_document),
                    selectinload(Application.evaluation_sessions).selectinload(
                        EvaluationSession.evaluation_result
                    ),
                )
                .join(_latest_es, _latest_es.c.application_id == Application.id)
                .join(EvaluationSession, EvaluationSession.id == _latest_es.c.max_id)
                .filter(
                    EvaluationSession.interview_state == "completed",
                    Application.final_eval_timestamp >= cutoff,
                )
            )
            if company_id is not None:
                query = query.filter(Application.company_id == company_id)
            recent_apps = query.all()

            recalibrated = 0
            for app in recent_apps:
                try:
                    _iv = (
                        app.evaluation_sessions[0] if app.evaluation_sessions else None
                    )
                    _cv = app.cv_document
                    _er = (
                        app.evaluation_sessions[0].evaluation_result
                        if app.evaluation_sessions
                        and app.evaluation_sessions[0].evaluation_result
                        else None
                    )
                    _sc = _er
                    qa_pairs = load_turns(db, app)
                    _analysis_json = (
                        getattr(_cv, "analysis_json", None) or app.analysis_json
                    )
                    _final_score = _sc.final_score if _sc else None
                    _declared_role = (
                        getattr(_cv, "declared_role", None) or app.declared_role
                    )
                    _proctoring_violations = getattr(_iv, "proctoring_violations", None)

                    q_scores = [
                        q.get("score", 50) for q in qa_pairs if isinstance(q, dict)
                    ]
                    answer_times = [
                        q.get("response_time_seconds", 0)
                        for q in qa_pairs
                        if isinstance(q, dict)
                    ]

                    skill_metrics = {}
                    if _analysis_json:
                        analysis = json.loads(_analysis_json)
                        breakdown = analysis.get("final_score_breakdown", {})
                        skill_metrics = breakdown.get("dimensions", {})

                    if not skill_metrics:
                        continue

                    violations = []
                    if _proctoring_violations:
                        violations = json.loads(_proctoring_violations)

                    new_breakdown = calculate_overall_score(
                        skill_metrics=skill_metrics,
                        question_scores=q_scores,
                        answered=len(q_scores),
                        total=15,
                        violations=violations,
                        role=_declared_role or "Professional",
                        seniority="Mid",
                        answer_times=answer_times,
                        qa_pairs=qa_pairs,
                    )

                    old_score = _final_score or 0
                    if abs(new_breakdown.final_score - old_score) > 2:
                        logger.warning(
                            "[RECALIBRATION] Score drift detected for app %s: "
                            "old=%.1f transparent=%.1f. "
                            "Skipping canonical write because transparent final_score "
                            "is not a canonical rubric component.",
                            app.id,
                            old_score,
                            new_breakdown.final_score,
                        )
                        recalibrated += 1

                except Exception as e:
                    logger.error(f"[RECALIBRATION] Failed for app {app.id}: {e}")

            if recalibrated > 0:
                db.commit()
                logger.info(f"[RECALIBRATION] Recalibrated {recalibrated} interviews")
            else:
                logger.info("[RECALIBRATION] No significant changes needed")

    except Exception as e:
        logger.error(f"[RECALIBRATION] Failed: {e}")
        raise


# Schedule configuration
SCHEDULED_JOBS = [
    {
        "name": "drift_check",
        "function": run_drift_check,
        "interval_hours": 24,
        "description": "Check for model scoring drift",
    },
    {
        "name": "calibration_collection",
        "function": collect_calibration_samples,
        "interval_hours": 12,
        "description": "Collect calibration samples from reviewed interviews",
    },
    {
        "name": "score_recalibration",
        "function": run_score_recalibration,
        "interval_hours": 168,  # Weekly
        "description": "Recalculate scores with latest scoring logic",
    },
]
