import json
from datetime import datetime
from typing import Optional, Tuple

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.authz import get_application_for_recruiter
from backend.database import Application, User
from backend.dependencies import get_db, get_interview_access
from backend.entity_writer import sync_ai_interview_session
from backend.logger import logger
from backend.routers.ai_interview.utils import (
    INTERVIEW_TOTAL_QUESTIONS,
    _utcnow,
    normalize_interview_language,
    safe_user_id,
    safe_user_role,
)
from backend.scoring_service import ScoringService
from backend.scoring_transparent import VIOLATION_PENALTIES, normalize_violation_type

router = APIRouter(tags=["ai-interview"])


def _resolve_app_for_candidate(
    db: Session, current_user: Optional[User], application_id: int
) -> Optional[Application]:
    """Resolve an application for a logged-in candidate (ownership-scoped).

    Returns None for true guests — the get_interview_access dependency already
    resolved the application for them via guest JWT/HMAC. This avoids calling
    get_current_company_id() (a FastAPI dependency) as a plain function, which
    crashed with an AttributeError and turned a 404 case into a 500.
    """
    if not current_user:
        return None
    return (
        db.query(Application)
        .filter(
            Application.id == application_id,
            Application.user_id == current_user.id,
        )
        .first()
    )


class ProctoringSyncRequest(BaseModel):
    application_id: int
    violation_type: str = Field(..., max_length=100)
    timestamp: str = Field(..., max_length=100)
    details: str = Field("", max_length=1000)


@router.post("/interview/sync-proctoring")
async def sync_proctoring(
    req: ProctoringSyncRequest,
    db: Session = Depends(get_db),
    auth: Tuple[Optional[User], Application] = Depends(get_interview_access),
):
    current_user, app = auth
    if not app:
        if current_user and safe_user_role(current_user) in ["recruiter", "admin"]:
            app = get_application_for_recruiter(req.application_id, current_user, db)
        else:
            app = (
                db.query(Application)
                .filter(Application.id == req.application_id)
                .first()
            )
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    if current_user and app.user_id and app.user_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Not authorized to sync proctoring for this application",
        )
    try:
        _iv_session = app.evaluation_sessions[0] if app.evaluation_sessions else None
        violations = json.loads(
            getattr(_iv_session, "proctoring_violations", None) or "[]"
        )

        now = _utcnow()
        if violations:
            last_v = violations[-1]
            try:
                last_time = datetime.fromisoformat(last_v.get("server_timestamp"))
                if (
                    last_v.get("type") == req.violation_type
                    and (now - last_time).total_seconds() < 5
                ):
                    raise HTTPException(
                        status_code=429,
                        detail=f"Request throttled. {len(violations)} violations detected.",
                    )
            except HTTPException:
                raise
            except Exception:
                pass

        violations.append(
            {
                "type": normalize_violation_type(req.violation_type),
                "timestamp": req.timestamp,
                "details": req.details,
                "server_timestamp": now.isoformat(),
            }
        )
        sync_ai_interview_session(db, app, proctoring_violations=json.dumps(violations))

        CRITICAL_VIOLATIONS = {
            normalize_violation_type(t)
            for t in {"DevTools opened", "Multiple faces detected"}
        }
        HIGH_VIOLATIONS = {
            normalize_violation_type(t)
            for t in {"Tab switch detected", "Suspiciously fast answer"}
        }

        sum(1 for v in violations if v.get("type") in CRITICAL_VIOLATIONS)
        sum(1 for v in violations if v.get("type") in HIGH_VIOLATIONS)

        # Trust score uses the same VIOLATION_PENALTIES as final scoring
        # so the candidate sees the same penalty values that affect their score.
        # Values are negative since we start at 100 and trust decreases.
        trust = 100.0
        for v in violations:
            vtype = normalize_violation_type(v.get("type", "unknown"))
            penalty = -(VIOLATION_PENALTIES.get(vtype, 5))
            trust = max(0.0, trust + penalty)

        should_flag = trust < 60 or len(violations) > 15

        if should_flag:
            sync_ai_interview_session(db, app, interview_state="flagged")
            ScoringService.set_verdict(
                app,
                db,
                verdict=f"Proctoring: {len(violations)} violations, trust={round(trust)}%",
                computed_by="proctoring",
            )
            logger.warning(
                f"[PROCTOR] Flagged app {app.id}: {len(violations)} violations, trust={round(trust)}%"
            )

        review_recommended = trust < 40 or len(violations) > 20

        db.commit()
        return {
            "status": "synced",
            "count": len(violations),
            "server_trust_score": round(trust, 1),
            "review_recommended": review_recommended,
        }
    except Exception as e:
        logger.error(f"Proctoring sync failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to sync proctoring data")


@router.post("/interview/resume")
async def resume_interview(
    payload: dict,
    db: Session = Depends(get_db),
    auth: Tuple[Optional[User], Application] = Depends(get_interview_access),
):
    current_user, app = auth
    application_id = payload.get("application_id")
    if not application_id:
        raise HTTPException(status_code=400, detail="application_id required")

    if not app:
        if current_user and safe_user_role(current_user) in ["recruiter", "admin"]:
            app = get_application_for_recruiter(application_id, current_user, db)
        elif current_user:
            app = _resolve_app_for_candidate(db, current_user, application_id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    if current_user and safe_user_role(current_user) not in ["recruiter", "admin"]:
        if app.user_id and app.user_id != current_user.id:
            raise HTTPException(
                status_code=403, detail="Not authorized to access this application"
            )

    _ALLOWED_INTERVIEW_START_STATUSES = {"invited", "interviewing", "shortlisted"}

    if app.interview_state not in ["in_progress", "paused", "flagged"]:
        # Allow resume of expired/failed interviews only if they were reset
        if app.interview_state == "expired":
            return {
                "can_resume": False,
                "reason": "Interview has timed out. Please contact support to reset.",
                "progress": 0,
                "time_left": 0,
            }
        return {
            "can_resume": False,
            "reason": f"Interview is {app.interview_state}",
            "progress": 0,
        }
    if (
        app.job_id is not None
        or app.batch_id is not None
    ) and app.status not in _ALLOWED_INTERVIEW_START_STATUSES:
        return {
            "can_resume": False,
            "reason": "Interview has not been scheduled yet. Please wait for the recruiter to invite you.",
            "progress": 0,
        }

    # --- Backfill expires_at for pre-migration sessions ---
    _es_for_resume = app.evaluation_sessions[0] if app.evaluation_sessions else None
    _expires = getattr(_es_for_resume, "expires_at", None) if _es_for_resume else None

    # Snapshot is authoritative for interview configuration.
    # Only fall back to legacy persisted values for pre-snapshot sessions.
    _snapshot_time_limit = None
    try:
        if _es_for_resume and getattr(_es_for_resume, "config_snapshot", None):
            from backend.rubric.config_reader import EvaluationConfigReader
            _snapshot_time_limit = EvaluationConfigReader(
                _es_for_resume
            ).get_time_limit()
    except Exception as e:
        logger.warning(
            "Could not read snapshot time limit while resuming app %s: %s",
            app.id,
            e,
        )

    if _expires is None and app.opened_at:
        from datetime import timedelta

        _duration = (
            _snapshot_time_limit
            or getattr(_es_for_resume, "interview_time_left", None)
            or app.interview_time_left
            or 1800
        )

        _expires = app.opened_at + timedelta(seconds=_duration)

        if _es_for_resume:
            sync_ai_interview_session(
                db,
                app,
                expires_at=_expires,
            )

    # --- Check if the deadline has already passed ---
    if _expires:
        from backend.routers.ai_interview.chat import _compute_remaining_seconds
        _rem = _compute_remaining_seconds(_expires)
        if _rem <= 0:
            sync_ai_interview_session(db, app, interview_state="expired")
            db.commit()
            return {
                "can_resume": False,
                "reason": "Interview has timed out.",
                "progress": 0,
                "time_left": 0,
            }

    # NOTE: We do NOT reset opened_at here.  The original opened_at + expires_at
    # is the authoritative deadline.  Resume only changes the interview_state.
    sync_ai_interview_session(db, app, interview_state="in_progress")
    db.commit()

    history = []
    if app.interview_log:
        if isinstance(app.interview_log, list):
            history = app.interview_log
        elif app.interview_log != "null":
            try:
                history = json.loads(app.interview_log)
                if not isinstance(history, list):
                    history = []
            except Exception as e:
                logger.error(
                    f"Failed to parse resume log for app {application_id}: {e}"
                )
                history = []
    # Filter system handshake signals (marked _handshake) out of the
    # transcript so candidates don't see a ghost "ready" message (M-4).
    visible_history = [
        m for m in history if isinstance(m, dict) and not m.get("_handshake")
    ]
    skill_metrics = None
    cv_skill_metrics = None
    try:
        if app.analysis_json:
            analysis = json.loads(app.analysis_json)
            skill_metrics = analysis.get("skill_metrics")
            cv_skill_metrics = analysis.get("cv_skill_metrics") or skill_metrics
    except Exception:
        pass
    qa_history = []
    try:
        from backend.interview_turns import load_turns

        qa_history = load_turns(db, app)
    except Exception:
        pass

    _er = (
        app.evaluation_sessions[0].evaluation_result
        if app.evaluation_sessions and app.evaluation_sessions[0].evaluation_result
        else None
    )

    # Compute time_left from the authoritative deadline.
    # expires_at always wins; legacy values are only a fallback.
    _time_left_resume = 0
    if _expires:
        from backend.routers.ai_interview.chat import _compute_remaining_seconds
        _time_left_resume = _compute_remaining_seconds(_expires)
    else:
        _time_left_resume = max(
            0,
            _snapshot_time_limit
            or getattr(_es_for_resume, "interview_time_left", None)
            or app.interview_time_left
            or 1800,
        )

    # Read frozen interview configuration from the EvaluationConfigSnapshot.
    # The snapshot is the authoritative source for total_questions.
    _resume_total_questions = 15
    try:
        if _es_for_resume and getattr(_es_for_resume, "config_snapshot", None):
            from backend.rubric.config_reader import EvaluationConfigReader
            _resume_total_questions = EvaluationConfigReader(
                _es_for_resume
            ).get_total_questions()
    except Exception as e:
        logger.warning(
            "Could not read interview total_questions from snapshot for app %s: %s",
            app.id,
            e,
        )

    return {
        "can_resume": True,
        "application_id": app.id,
        "progress": max(app.interview_progress or 0, len(visible_history) // 2),
        "total_questions": _resume_total_questions,
        "history": visible_history,
        "qa_history": qa_history,
        "current_score": (_er.final_score if _er else None) or 75,
        "language": normalize_interview_language(app.language) or "English",
        "last_saved": app.interview_last_saved.isoformat()
        if app.interview_last_saved
        else None,
        "state": app.interview_state,
        "time_left": _time_left_resume,
        "skill_metrics": skill_metrics,
        "cv_skill_metrics": cv_skill_metrics,
    }


@router.post("/interview/pause")
async def pause_interview(
    payload: dict,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    auth: Tuple[Optional[User], Application] = Depends(get_interview_access),
):
    current_user, app = auth
    application_id = payload.get("application_id")
    if not application_id:
        raise HTTPException(status_code=400, detail="application_id required")

    if not app:
        if current_user and safe_user_role(current_user) in ["recruiter", "admin"]:
            app = get_application_for_recruiter(application_id, current_user, db)
        elif current_user:
            app = _resolve_app_for_candidate(db, current_user, application_id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    if current_user and safe_user_role(current_user) not in ["recruiter", "admin"]:
        if app.user_id and app.user_id != current_user.id:
            raise HTTPException(
                status_code=403, detail="Not authorized to access this application"
            )

    # NOTE: Do NOT accept time_left from the client.  The expires_at
    # deadline on EvaluationSession is the single source of truth.
    # The client cannot extend the interview by sending a different value.

    sync_ai_interview_session(
        db, app, interview_state="paused", interview_last_saved=_utcnow()
    )

    db.commit()

    from backend.routers.career import run_proactive_roadmap_generation

    target_role = app.declared_role or getattr(app, "job_title", "Professional")
    if current_user:
        if current_user:
            background_tasks.add_task(
                run_proactive_roadmap_generation, current_user.id, target_role, db
            )
    else:
        logger.info(f"[ROADMAP] Skipping for guest app {app.id}")

    db.commit()
    user_id_log = safe_user_id(current_user) if current_user else f"Guest:{app.id}"
    # Use the frozen snapshot configuration for progress reporting.
    _pause_total_questions = 15
    try:
        _pause_es = (
            app.evaluation_sessions[-1]
            if app.evaluation_sessions
            else None
        )
        if _pause_es and getattr(_pause_es, "config_snapshot", None):
            from backend.rubric.config_reader import EvaluationConfigReader
            _pause_total_questions = EvaluationConfigReader(
                _pause_es
            ).get_total_questions()
    except Exception as e:
        logger.warning(
            "Could not read snapshot total_questions while pausing app %s: %s",
            app.id,
            e,
        )

    logger.info(
        f"Interview paused: user_id={user_id_log}, app_id={application_id}, "
        f"progress={app.interview_progress}/{_pause_total_questions}"
    )

    return {
        "success": True,
        "message": "Interview paused successfully. You can resume anytime from your dashboard.",
        "progress": app.interview_progress,
        "total_questions": _pause_total_questions,
        "percentage": round(
            (app.interview_progress / _pause_total_questions) * 100
        )
        if app.interview_progress
        else 0,
    }


@router.get("/interview/time")
async def get_interview_time(
    db: Session = Depends(get_db),
    auth: Tuple[Optional[User], Application] = Depends(get_interview_access),
):
    current_user, app = auth
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    es = None
    if app.evaluation_sessions:
        es = sorted(
            app.evaluation_sessions,
            key=lambda s: s.updated_at or s.created_at or datetime.min,
            reverse=True,
        )[0]

    expires_at = getattr(es, "expires_at", None) if es else None

    if expires_at:
        from backend.routers.ai_interview.chat import _compute_remaining_seconds
        time_left = _compute_remaining_seconds(expires_at)
    else:
        time_left = (
            getattr(es, "interview_time_left", None)
            or app.interview_time_left
            or 1800
        )

    return {
        "time_left": time_left,
        "interview_state": app.interview_state or "not_started",
        "interview_progress": app.interview_progress or 0,
    }


class EndInterviewRequest(BaseModel):
    application_id: int
    reason: str = "candidate_ended"


@router.post("/interview/end")
async def end_interview(
    payload: EndInterviewRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    auth: Tuple[Optional[User], Application] = Depends(get_interview_access),
):
    """Finish the interview early and trigger the final evaluation.

    The End button on the interview room previously only navigated away,
    leaving the session in_progress forever and never producing an
    analysis/score. This endpoint transitions the session to EVALUATING
    and enqueues the background final evaluation so candidates who end
    early still receive their results.
    """
    current_user, app = auth
    if not app:
        if current_user and safe_user_role(current_user) in ["recruiter", "admin"]:
            app = get_application_for_recruiter(
                payload.application_id, current_user, db
            )
        elif current_user:
            app = _resolve_app_for_candidate(db, current_user, payload.application_id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    if current_user and safe_user_role(current_user) not in ["recruiter", "admin"]:
        if app.user_id and app.user_id != current_user.id:
            raise HTTPException(
                status_code=403, detail="Not authorized to access this application"
            )

    current_state = getattr(app, "interview_state", None) or "not_started"
    if current_state in ("completed", "expired"):
        return {
            "success": True,
            "message": f"Interview already {current_state}.",
            "interview_state": current_state,
        }

    from backend.entity_writer import sync_evaluation_state
    from backend.routers.ai_interview.evaluation import run_background_final_evaluation

    sync_ai_interview_session(db, app, interview_state="evaluating")
    sync_evaluation_state(db, app, evaluation_state="pending")
    db.commit()
    background_tasks.add_task(run_background_final_evaluation, app.id, app.company_id)
    logger.info(
        f"[END] Interview {app.id} ended early by user "
        f"{safe_user_id(current_user) if current_user else 'Guest'} (reason={payload.reason}). "
        f"Background evaluation triggered."
    )
    return {
        "success": True,
        "message": "Interview ended. Generating your analysis...",
        "interview_state": "evaluating",
        "application_id": app.id,
    }
