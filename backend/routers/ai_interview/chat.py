import asyncio
import html
import json
from typing import Optional, Tuple

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text, update
from sqlalchemy.orm import Session, selectinload

from backend.ai.engine import InterviewEngine
from backend.ai.interview import evaluate_answer, generate_skill_driven_turn
from backend.ai.interview_customization import update_engine_state
from backend.ai.security import AISecurity
from backend.ai.state_machine import (
    InterviewState,
    get_interview_strategy,
    initialize_engine_state,
)
from backend.authz import get_application_for_recruiter
from backend.database import Application, CandidateInteraction, EvaluationSession, EvaluationResult, User
from backend.dependencies import get_current_user, get_db, get_interview_access
from backend.entity_writer import (
    sync_ai_interview_session,
    sync_cv_document,
    sync_evaluation_state,
)
from backend.logger import logger
from backend.metrics import record_ai_call
from backend.routers.ai_interview.evaluation import run_background_final_evaluation
from backend.routers.ai_interview.utils import (
    DIMENSION_WEIGHTS,
    INTERVIEW_TOTAL_QUESTIONS,
    _msg,
    _utcnow,
    calculate_adaptive_score,
    get_fallback_turn,
    is_lazy_answer,
    normalize_interview_language,
    safe_user_id,
    safe_user_role,
)
from backend.scoring_engine import (
    calculate_overall_score,
)
from backend.scoring_service import ScoringService
from backend.scoring_transparent import get_recommendation, get_score_label
from backend.simple_rate_limiter import interview_rate_limiter

router = APIRouter(tags=["ai-interview"])


def _compute_remaining_seconds(expires_at, now=None):
    """Compute remaining interview seconds from the authoritative deadline.

    Returns int seconds remaining (>=0).  If expires_at is None or in the
    past, returns 0.
    """
    if expires_at is None:
        return 0
    now = now or _utcnow()
    delta = (expires_at - now).total_seconds()
    return max(0, int(delta))


class ChatRequest(BaseModel):
    candidate_id: int
    message: str = Field(..., max_length=5000)
    language: Optional[str] = Field(None, max_length=50)
    session_id: Optional[int] = None


class PracticeRequest(BaseModel):
    message: str = Field(..., max_length=5000)
    role: str = Field("Software Engineer", max_length=100)
    language: Optional[str] = Field("English", max_length=50)
    history: Optional[list] = []
    current_score: Optional[float] = 75.0


@router.post("/interview/chat")
async def interview_chat(
    req: ChatRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    auth: Tuple[Optional[User], Application] = Depends(get_interview_access),
):
    logger.debug(f"interview_chat START for candidate {req.candidate_id}")
    current_user, app = auth
    logger.debug(
        f"after auth - user: {current_user.id if current_user else None}, app: {app.id if app else None}"
    )
    if not app:
        logger.error(f"app is None for candidate {req.candidate_id}")
    try:
        return await _interview_chat_core(
            req, db, current_user, background_tasks, application=app
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"CRASH in Interview Chat: {req.candidate_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Internal interview processing error"
        )


@router.post("/interview/practice")
async def practice_interview(
    req: PracticeRequest, current_user: User = Depends(get_current_user)
):
    identifier = f"practice_{safe_user_id(current_user)}"
    is_allowed, retry_after = interview_rate_limiter.is_allowed(
        identifier, max_requests=20, window_seconds=600
    )
    if not is_allowed:
        raise HTTPException(
            status_code=429,
            detail=f"Practice rate limit reached. Please wait {retry_after} seconds.",
            headers={"Retry-After": str(retry_after)},
        )

    if not req.message or not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    if len(req.message) > 5000:
        raise HTTPException(
            status_code=400, detail="Message too long (max 5000 characters)"
        )

    is_safe, reason = AISecurity.detect_prompt_injection(req.message)
    if not is_safe:
        return {
            "reply": "Please focus on professional interview topics.",
            "type": "warning",
            "feedback": f"Input flagged: {reason}",
            "current_score": 0,
            "skills": {
                "Technical": 0,
                "Communication": 0,
                "Problem Solving": 0,
                "Adaptability": 0,
                "Confidence": 0,
            },
            "is_practice": True,
        }

    history = req.history or []
    sanitized_message = AISecurity.sanitize_input(req.message)
    history.append({"role": "user", "content": sanitized_message})

    ai_turns = sum(1 for m in history if m.get("role") == "assistant")
    current_q_index = ai_turns + 1
    practice_language = normalize_interview_language(req.language) or "English"

    is_handshake = req.message.lower().strip() in [
        "ready",
        "start",
        "begin",
        "commencer",
        "yalla",
        "go",
        "hi",
        "hello",
        "arabic",
        "french",
        "english",
        "ok",
        "okay",
    ]

    PRACTICE_TOTAL = 5
    if current_q_index > PRACTICE_TOTAL:
        return {
            "reply": "Practice session complete! You answered all 5 questions.",
            "type": "complete",
            "current_score": req.current_score or 75,
            "feedback": "Great practice! Ready for the real interview?",
            "skills": {
                "Technical": 75,
                "Communication": 75,
                "Problem Solving": 75,
                "Adaptability": 75,
                "Confidence": 75,
            },
            "total_questions": PRACTICE_TOTAL,
            "current_question": PRACTICE_TOTAL,
            "is_practice": True,
            "progress": {
                "current": PRACTICE_TOTAL,
                "total": PRACTICE_TOTAL,
                "percentage": 100,
            },
        }

    try:
        ai_response = await generate_interview_turn_with_timeout(
            cv_context="Practice mode - no CV context available. Generate generic questions for the role.",
            declared_role=req.role or "Software Engineer",
            history=history[-20:],
            current_q_index=current_q_index,
            total_questions=PRACTICE_TOTAL,
            language=practice_language,
            job_title=req.role,
            job_description=None,
            app_id=0,
            current_score=req.current_score or 75.0,
        )
    except Exception as e:
        logger.error(f"Practice interview AI error: {e}", exc_info=True)
        ai_response = get_fallback_turn(
            current_q_index, req.role, req.current_score or 75.0, practice_language
        )

    previous_ai_text = ""
    for msg in reversed(history[:-1]):
        if msg.get("role") == "assistant":
            previous_ai_text = msg.get("content", "")
            break

    is_lazy = is_lazy_answer(sanitized_message, previous_ai_text, practice_language)
    if is_lazy and not is_handshake:
        new_score = calculate_adaptive_score(
            req.current_score or 75.0, 10.0, current_q_index, False
        )
        ai_response["feedback"] = _msg("practice_lazy_feedback", practice_language)
    else:
        raw_score = ai_response.get("current_score", req.current_score or 75.0)
        new_score = calculate_adaptive_score(
            req.current_score or 75.0, raw_score, current_q_index, is_handshake
        )

    ai_response["current_score"] = new_score
    ai_response["is_practice"] = True
    ai_response["total_questions"] = PRACTICE_TOTAL
    ai_response["current_question"] = current_q_index
    ai_response["progress"] = {
        "current": current_q_index,
        "total": PRACTICE_TOTAL,
        "percentage": round((current_q_index / PRACTICE_TOTAL) * 100),
    }

    reply_text = ai_response.get("reply", "Dynamic error during practice generation.")

    if (
        isinstance(reply_text, str)
        and reply_text.strip().startswith("{")
        and reply_text.strip().endswith("}")
    ):
        try:
            import json

            reply_text = json.loads(reply_text)
        except Exception:
            pass

    if isinstance(reply_text, dict):
        parts = []
        company = reply_text.get("company_context", "")
        team = reply_text.get("team_size", "")
        stack = reply_text.get("tech_stack", "")
        scenario = reply_text.get("scenario", "")
        problem = reply_text.get("problem", "")
        action = reply_text.get("actionRequest", reply_text.get("action_request", ""))

        if company or team or stack:
            context_str = "Context: " + ", ".join(filter(None, [company, team, stack]))
            parts.append(context_str)

        if scenario:
            parts.append(scenario)
        if problem:
            parts.append(problem)
        if action:
            parts.append(action)

        if not parts:
            prompt = reply_text.get("prompt", "")
            if prompt:
                parts.append(prompt)

        if parts:
            reply_text = "\n\n".join(parts)
        else:
            try:
                clean_dict = {
                    k: v
                    for k, v in reply_text.items()
                    if k not in ["scenario_type", "type", "current_score", "skills"]
                }
                reply_text = " ".join([str(v) for v in clean_dict.values()])
            except Exception:
                import json

                reply_text = json.dumps(reply_text)

    history.append({"role": "assistant", "content": str(reply_text)})
    ai_response["history"] = history

    return ai_response


async def _interview_chat_core(
    req: ChatRequest,
    db: Session,
    current_user: Optional[User],
    background_tasks: BackgroundTasks,
    application: Optional[Application] = None,
):
    engine_state = None
    turn_claimed = False
    expected_seq = 0

    if not req.message or not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    if len(req.message) > 5000:
        raise HTTPException(
            status_code=400, detail="Message too long (maximum 5000 characters)"
        )
    if current_user:
        identifier = f"user_{safe_user_id(current_user)}"
    else:
        identifier = f"app_{req.candidate_id}"

    is_allowed, retry_after = interview_rate_limiter.is_allowed(
        identifier, max_requests=10, window_seconds=300
    )
    if not is_allowed:
        raise HTTPException(
            status_code=429,
            detail=f"Too many requests. Please wait {retry_after} seconds before trying again.",
            headers={"Retry-After": str(retry_after)},
        )
    logger.debug(f"_interview_chat_core START for app {req.candidate_id}")
    engine = InterviewEngine(db)
    logger.debug("Engine initialized")

    if application:
        app = application
    else:
        if current_user and safe_user_role(current_user) in ["recruiter", "admin"]:
            app = get_application_for_recruiter(req.candidate_id, current_user, db)
        else:
            query = (
                db.query(Application)
                .options(
                    selectinload(Application.job),
                    selectinload(Application.cv_document),
                    selectinload(Application.evaluation_sessions).selectinload(
                        EvaluationSession.evaluation_result
                    ),
                    selectinload(Application.evaluation_sessions).selectinload(
                        EvaluationSession.config_snapshot
                    ),
                )
                .with_for_update()
                .filter(Application.id == req.candidate_id)
            )
            if current_user and safe_user_role(current_user) not in [
                "recruiter",
                "admin",
            ]:
                query = query.filter(Application.user_id == current_user.id)
            app = query.first()

    if not app and req.session_id:
        es = (
            db.query(EvaluationSession)
            .filter(EvaluationSession.id == req.session_id)
            .first()
        )
        if es:
            app = (
                db.query(Application)
                .options(
                    selectinload(Application.cv_document),
                    selectinload(Application.evaluation_sessions).selectinload(
                        EvaluationSession.evaluation_result
                    ),
                    selectinload(Application.evaluation_sessions).selectinload(
                        EvaluationSession.config_snapshot
                    ),
                )
                .filter(Application.id == es.application_id)
                .first()
            )

    if not app:
        db.commit()
        raise HTTPException(status_code=404, detail="Application not found")

    _cv = app.cv_document
    _es = app.evaluation_sessions[0] if app.evaluation_sessions else None
    _er = getattr(_es, "evaluation_result", None) if _es else None

    _ALLOWED_INTERVIEW_START_STATUSES = {"invited", "interviewing", "shortlisted"}

    # Auto-start the interview if it hasn't been initialized yet (no session
    # or no EvaluationConfigSnapshot). The InterviewStarter resolves and freezes
    # the recruiter-configured snapshot (time limit, language, skills, rubric,
    # instructions) so the interview always honours the configured settings.
    # Previously the chat raised a 500 for applications whose interview was
    # never explicitly started (e.g. interview_state=NULL).
    # Guard: job/campaign applications require recruiter invitation before the
    # interview can start. Self-assessments (no job_id, no batch_id) remain
    # auto-start so the existing audit/onboarding flow is preserved.
    if (
        app.job_id is not None
        or app.batch_id is not None
    ) and app.status not in _ALLOWED_INTERVIEW_START_STATUSES:
        raise HTTPException(
            status_code=403,
            detail="Interview has not been scheduled yet. Please wait for the recruiter to invite you.",
        )
    # LEGACY TIMEOUT GUARD
    # Sessions created before expires_at/config snapshots may still have a
    # stale Application.opened_at. If the interview already has history or
    # progress, never auto-start a new session before evaluating that deadline.
    #
    # This MUST run before the auto-start/config-snapshot block below.
    _legacy_history = getattr(_es, "interview_log", None) if _es is not None else None
    if not _legacy_history:
        _legacy_history = getattr(app, "interview_log", None)

    if isinstance(_legacy_history, str):
        try:
            _legacy_history = json.loads(_legacy_history)
        except Exception:
            _legacy_history = []

    _legacy_progress = (
        getattr(_es, "interview_progress", None)
        if _es is not None
        else None
    ) or getattr(app, "interview_progress", None) or 0

    _legacy_state = (
        getattr(_es, "interview_state", None)
        if _es is not None
        else None
    ) or getattr(app, "interview_state", None)

    _legacy_expires_at = getattr(_es, "expires_at", None) if _es is not None else None

    # For pre-expires_at sessions, reconstruct the deadline from opened_at.
    if (
        _legacy_expires_at is None
        and app.opened_at is not None
        and _legacy_state != "not_started"
        and (_legacy_history or int(_legacy_progress) > 0)
    ):
        from datetime import timedelta

        _legacy_duration = (
            getattr(_es, "interview_time_left", None)
            if _es is not None
            else None
        ) or getattr(app, "interview_time_left", None) or 1800

        _legacy_expires_at = app.opened_at + timedelta(
            seconds=int(_legacy_duration)
        )

    if _legacy_expires_at is not None and _compute_remaining_seconds(
        _legacy_expires_at
    ) <= 0:
        _already_expired = _legacy_state in ("completed", "expired")

        if not _already_expired:
            sync_ai_interview_session(
                db,
                app,
                interview_state="expired",
            )
            sync_evaluation_state(
                db,
                app,
                evaluation_state="pending",
            )
            db.commit()
            background_tasks.add_task(
                run_background_final_evaluation, app.id, app.company_id
            )

            # Preserve the last known score. Never turn an expired interview
            # into an artificial zero.
            _legacy_result = (
                db.query(EvaluationResult)
                .filter(
                    EvaluationResult.evaluation_session_id == _es.id
                )
                .order_by(EvaluationResult.id.desc())
                .first()
                if _es is not None
                else None
            )

            _legacy_score = (
                getattr(_legacy_result, "final_score", None)
                if _legacy_result is not None
                else None
            )

            if _legacy_score is None:
                _legacy_score = 0.0

            _legacy_total = INTERVIEW_TOTAL_QUESTIONS

            return {
                "reply": "Interview time has expired.",
                "type": "timeout",
                "time_limit_reached": True,
                "current_score": float(_legacy_score),
                "total_questions": int(_legacy_total),
                "current_question": 0,
                "progress": {
                    "current": 0,
                    "total": int(_legacy_total),
                    "percentage": round(float(_legacy_score)),
                },
            }

        raise HTTPException(
            status_code=410,
            detail="Interview time has expired. Please contact support to reset.",
        )

    if _es is None or getattr(_es, "config_snapshot", None) is None:
        try:
            # A never-started interview must not inherit a stale tracking
            # opened_at from an older lifecycle. Clear it before InterviewStarter
            # creates the authoritative expires_at deadline.
            _start_history = getattr(_es, "interview_log", None) or app.interview_log
            if isinstance(_start_history, str):
                try:
                    _start_history = json.loads(_start_history)
                except Exception:
                    _start_history = []
            _start_progress = (
                getattr(_es, "interview_progress", None)
                if _es is not None
                else None
            ) or 0
            _start_state = (
                getattr(_es, "interview_state", None)
                if _es is not None
                else None
            ) or app.interview_state

            if (
                _start_state == "not_started"
                and not _start_history
                and int(_start_progress) == 0
                and app.opened_at is not None
            ):
                logger.info(
                    "[INTERVIEW] Clearing stale opened_at for fresh app %s",
                    app.id,
                )
                app.opened_at = None
                db.commit()

            from backend.rubric.interview_starter import InterviewStarter

            started_session = InterviewStarter.start(
                db,
                app,
                override_language=req.language,
            )
            _es = started_session
            _er = getattr(_es, "evaluation_result", None) if _es else None

            # InterviewStarter establishes the authoritative deadline.
            # Refresh the local value because _expires_at was resolved before
            # auto-start and therefore was None for a brand-new session.
            _expires_at = getattr(_es, "expires_at", None)

            logger.info(
                "Auto-started interview for app %s with snapshot %s",
                app.id,
                getattr(getattr(_es, "config_snapshot", None), "id", None),
            )
        except Exception as start_err:
            logger.error(
                f"Failed to auto-start interview for app {app.id}: {start_err}"
            )

    _interview_log_chat = getattr(_es, "interview_log", None) or app.interview_log
    _analysis_json_chat = getattr(_cv, "analysis_json", None) or app.analysis_json
    _final_score_chat = _er.final_score if _er else None
    _cv_score_chat = _er.cv_score if _er else None

    # Preserve an already-computed score when auto-start created a newer
    # EvaluationSession without an EvaluationResult. This is important for
    # timeout/reset flows: starting a fresh session must never erase the
    # candidate's last known score.
    if _final_score_chat is None or float(_final_score_chat or 0) <= 0:
        try:
            _previous_result = (
                db.query(EvaluationResult)
                .join(
                    EvaluationSession,
                    EvaluationResult.evaluation_session_id == EvaluationSession.id,
                )
                .filter(
                    EvaluationSession.application_id == app.id,
                    EvaluationResult.final_score.isnot(None),
                )
                .order_by(EvaluationResult.id.desc())
                .first()
            )
            if _previous_result is not None:
                _final_score_chat = _previous_result.final_score
                if _cv_score_chat is None:
                    _cv_score_chat = _previous_result.cv_score
        except Exception as score_err:
            logger.warning(
                "Failed to recover previous evaluation score for app %s: %s",
                app.id,
                score_err,
            )
    _declared_role_chat = getattr(_cv, "declared_role", None) or app.declared_role
    _cv_text_chat = getattr(_cv, "cv_text_anonymized", None) or app.cv_text_anonymized

    if (
        getattr(_es, "status", None) == "completed"
        or app.interview_state == "completed"
    ):
        raise HTTPException(
            status_code=409, detail="This interview has already been completed."
        )

    # --- Authoritative timeout check (Invariant 1+2) ---
    # Use expires_at as the single source of truth for remaining time.
    # For sessions created before the expires_at migration, fall back to
    # the legacy computation from opened_at + interview_time_left.
    #
    # Initialize safe numeric defaults BEFORE timeout handling. The timeout
    # contract must never expose None for score/question/progress fields.
    _snap_time_limit = None
    _snap_language = None
    reader = None
    total_questions = INTERVIEW_TOTAL_QUESTIONS

    _expires_at = getattr(_es, "expires_at", None)
    if _expires_at is None and app.opened_at:
        _duration = (
            _snap_time_limit
            or getattr(_es, "interview_time_left", None)
            or app.interview_time_left
            or 1800
        )
        from datetime import timedelta
        _expires_at = app.opened_at + timedelta(seconds=_duration or 1800)

    iv_state = getattr(_es, "interview_state", None) or app.interview_state

    # A reset/fresh interview may still have a legacy Application.opened_at
    # from an older lifecycle. It must NOT cause an immediate timeout.
    _pre_history = getattr(_es, "interview_log", None) or app.interview_log
    if isinstance(_pre_history, str):
        try:
            _pre_history = json.loads(_pre_history)
        except Exception:
            _pre_history = []
    _pre_progress = (
        getattr(_es, "interview_progress", None)
        if _es is not None
        else None
    ) or 0

    _fresh_lifecycle = (
        iv_state == "not_started"
        and not _pre_history
        and int(_pre_progress) == 0
    )

    if _fresh_lifecycle:
        # Ignore stale legacy deadline data. A new authoritative deadline
        # will be created when the interview actually starts.
        _expires_at = None

    _remaining = _compute_remaining_seconds(_expires_at)

    if _remaining <= 0:
        _already_terminal = iv_state in ("completed", "expired")

        # A newly detected timeout must return the timeout contract so the
        # candidate UI can finalize gracefully without losing the last score.
        # Subsequent requests against an already-expired session remain 410.
        if not _already_terminal:
            sync_ai_interview_session(db, app, interview_state="expired")
            sync_evaluation_state(db, app, evaluation_state="pending")
            db.commit()
            background_tasks.add_task(
                run_background_final_evaluation, app.id, app.company_id
            )

            # Timeout response is a strict API contract:
            # never leak NULL/None into numeric fields consumed by the UI.
            # Prefer the final interview score when available.
            # If final_score is still 0/pending at timeout, preserve the
            # already-computed CV score instead of returning 0 to the UI.
            if _final_score_chat is not None and float(_final_score_chat) > 0:
                _timeout_score = float(_final_score_chat)
            elif _cv_score_chat is not None:
                _timeout_score = float(_cv_score_chat)
            else:
                _timeout_score = 0.0
            _timeout_total = int(total_questions or INTERVIEW_TOTAL_QUESTIONS)

            return {
                "reply": "Interview time has expired.",
                "type": "timeout",
                "time_limit_reached": True,
                "current_score": _timeout_score,
                "total_questions": _timeout_total,
                "current_question": 0,
                "progress": {
                    "current": 0,
                    "total": _timeout_total,
                    "percentage": round(_timeout_score),
                },
            }

        raise HTTPException(
            status_code=410,
            detail="Interview time has expired. Please contact support to reset.",
        )

    # -- Centralized config access via EvaluationConfigReader --
    if _es and _es.config_snapshot:
        try:
            from backend.rubric.config_reader import EvaluationConfigReader

            reader = EvaluationConfigReader(_es)
            total_questions = reader.get_total_questions()
            _snap_time_limit = reader.get_time_limit()
            _snap_language = reader.get_language()
        except Exception as e:
            logger.error(f"Failed to read config snapshot for app {app.id}: {e}")
    if not total_questions:
        logger.warning(
            f"App {app.id}: no EvaluationConfigSnapshot -- using default total"
        )
        total_questions = INTERVIEW_TOTAL_QUESTIONS

    # Honour the recruiter-configured time limit from the snapshot. The
    # snapshot is the frozen source of truth for the interview settings.
    if _snap_time_limit and (not getattr(_es, "interview_time_left", None)):
        _es.interview_time_left = _snap_time_limit
        sync_ai_interview_session(db, app, interview_time_left=_snap_time_limit)
        db.commit()

    current_seq = app.interview_turn_seq or 0

    if current_seq % 2 != 0:
        logger.info(
            f"[IDEMPOTENCY] Turn sequence {current_seq} is ODD (Processing). Rejecting concurrent request for app {app.id}"
        )
        _log_len = len(_interview_log_chat) if isinstance(_interview_log_chat, list) else len(json.loads(_interview_log_chat or "[]"))
        return {
            "reply": "I'm currently thinking about your last answer. Please wait a moment...",
            "type": "wait",
            "current_question": (_log_len // 2) + 1,
            "progress": {
                "current": (_log_len // 2) + 1,
                "total": total_questions,
                "percentage": round(float(_final_score_chat or 0)),
            },
        }

    expected_seq = current_seq
    _es_id_turn = _es.id if _es else None
    if _es_id_turn:
        result = db.execute(
            update(EvaluationSession)
            .where(EvaluationSession.id == _es_id_turn)
            .where(EvaluationSession.interview_turn_seq == expected_seq)
            .values(interview_turn_seq=expected_seq + 1)
        )
    else:
        result = db.execute(text("SELECT 0"), {})
    db.commit()

    if _es_id_turn and result.rowcount == 0:
        logger.info(
            f"[IDEMPOTENCY] Turn sequence changed concurrently for app {app.id}"
        )
        return {
            "reply": "Your answer is being processed.",
            "type": "duplicate",
        }
    if not _es_id_turn:
        logger.warning(
            f"[IDEMPOTENCY] No EvaluationSession for app {app.id} -- skipping turn claim"
        )

    turn_claimed = True
    try:
        cv_context = _cv_text_chat or ""
        getattr(app, "job_title", None) or (
            app.batch_job.title if app.batch_job else "General Role"
        )
        job_description = getattr(app, "job_description", None) or (
            app.batch_job.description if app.batch_job else ""
        )
        # Once an EvaluationConfigSnapshot exists, its language is immutable
        # and authoritative for every subsequent interview turn.
        #
        # The snapshot may store either canonical names ("French") or
        # short ISO values ("fr"/"en"/"ar") depending on how it was created.
        # Normalize both representations before passing the language to the AI.
        if _snap_language:
            language_context = (
                normalize_interview_language(_snap_language)
                or "English"
            )
        else:
            language_context = (
                normalize_interview_language(req.language)
                or normalize_interview_language(getattr(app, "language", None))
                or "English"
            )

        if app.language != language_context:
            app.language = language_context
            db.commit()

        from backend.ai.interview_customization import (
            load_instruction_state,
        )

        # Read instructions from snapshot via reader
        if _es and _es.config_snapshot and reader:
            raw_instructions = reader.get_instructions()
            custom_q_prompt = reader.get_question_generation_prompt()
        else:
            raise RuntimeError(
                f"App {app.id}: no snapshot interview_instructions -- "
                f"snapshot must be created at interview start"
            )
        interview_instructions = raw_instructions

        history = []
        if _interview_log_chat:
            if isinstance(_interview_log_chat, list):
                history = _interview_log_chat
            elif _interview_log_chat != "null":
                try:
                    history = json.loads(_interview_log_chat)
                    if not isinstance(history, list):
                        history = []
                except Exception as e:
                    logger.error(
                        f"Failed to parse interview log for app {req.candidate_id}: {e}"
                    )
                    history = []

        load_instruction_state(history)

        sanitized_message = AISecurity.sanitize_input(req.message)
        is_safe, reason = AISecurity.detect_prompt_injection(sanitized_message)

        if not is_safe:
            user_id_log = (
                safe_user_id(current_user) if current_user else f"Guest:{app.id}"
            )
            logger.warning(
                f"SECURITY ALERT: User {user_id_log} attempted injection: {reason}"
            )
            await engine.record_answer(app.id, -1, f"[VIOLATION] {reason}")

            history.append({"role": "user", "content": sanitized_message})
            ai_reply = _msg("security_block", language_context)
            history.append({"role": "assistant", "content": ai_reply})
            sync_ai_interview_session(db, app, interview_log=history)
            db.commit()

            return {
                "reply": ai_reply,
                "type": "warning",
                "feedback": _msg("integrity_feedback", language_context, reason=reason),
                "current_score": _final_score_chat,
                "total_questions": total_questions,
                "current_question": len(history) // 2 + 1,
                "progress": {
                    "current": len(history) // 2 + 1,
                    "total": total_questions,
                    "percentage": round(_final_score_chat or 0),
                },
            }

        base_time = _snap_time_limit or (_es.interview_time_left if _es else None) or app.interview_time_left or 1800
        has_history = bool(history)
        fresh_interview = not has_history

        # Only set opened_at + expires_at on the very first start.
        # If expires_at already exists (DB reset / resume), respect it.
        if _expires_at is None:
            _now = _utcnow()
            if not app.opened_at:
                # SQLAlchemy/SQLite may return DB datetimes as naive.
                # Normalize the value written by the interview lifecycle
                # to the same representation used by the application.
                app.opened_at = _now.replace(tzinfo=None)
            from datetime import timedelta
            _expires = (app.opened_at or _now) + timedelta(seconds=base_time)
            sync_ai_interview_session(
                db, app,
                interview_time_left=base_time,
                expires_at=_expires,
            )
            db.commit()
            _expires_at = _expires
        elif not app.opened_at:
            app.opened_at = _utcnow()
            db.commit()

        # Remaining time derived from the authoritative deadline (Invariant 1).
        _remaining = _compute_remaining_seconds(_expires_at)
        if _remaining <= 0 and not fresh_interview:
            # Terminal timeout: finalize + lock (Invariant 3).
            _es_final = app.evaluation_sessions[0] if app.evaluation_sessions else None
            _already_terminal = (
                getattr(_es_final, "interview_state", None) in ("completed", "expired")
                or app.interview_state in ("completed", "expired")
            )
            if not _already_terminal:
                sync_ai_interview_session(db, app, interview_state="expired")
                sync_evaluation_state(db, app, evaluation_state="pending")
                db.commit()
                background_tasks.add_task(
                    run_background_final_evaluation, app.id, app.company_id
                )
            raise HTTPException(
                status_code=410,
                detail="Interview time has expired. Please contact support to reset.",
            )

        HANDSHAKE_WORDS = {
            "ready",
            "start",
            "begin",
            "start interview",
            "commencer",
            "yalla",
            "hi",
            "hello",
            "bonjour",
        }
        ALWAYS_LAZY = {"ok", "okay", "d'accord", "go", "yes", "no", "oui", "non"}

        ai_turns = sum(1 for m in history if m.get("role") == "assistant")
        current_q_index = ai_turns + 1
        msg_lower = sanitized_message.lower().strip()
        is_handshake = current_q_index <= 1 and msg_lower in HANDSHAKE_WORDS

        # Track if the first user message was a handshake
        had_handshake = False
        for m in history:
            if m.get("role") == "user":
                had_handshake = m.get("content", "").lower().strip() in HANDSHAKE_WORDS
                break

        if (
            is_handshake
            and (getattr(_es, "interview_state", None) or app.interview_state)
            == "not_started"
            and (
                app.job_id is None
                and app.batch_id is None
                or app.status in _ALLOWED_INTERVIEW_START_STATUSES
            )
        ):
            from backend.rubric.interview_starter import InterviewStarter

            InterviewStarter.start(
                db,
                app,
                override_language=req.language,
            )
            db.commit()
            # Refresh session after start
            _es_loaded = (
                db.query(Application)
                .options(
                    selectinload(Application.evaluation_sessions).selectinload(
                        EvaluationSession.config_snapshot
                    )
                )
                .filter(Application.id == app.id)
                .first()
            )
            if _es_loaded and _es_loaded.evaluation_sessions:
                _es = _es_loaded.evaluation_sessions[0]
                reader = EvaluationConfigReader(_es)
                total_questions = reader.get_total_questions()

        should_append = True
        if history and history[-1].get("role") == "user":
            if history[-1].get("content", "") == sanitized_message:
                should_append = False
                logger.info(f"[IDEMPOTENCY] Deduped duplicate message for app {app.id}")

        if should_append:
            history.append({"role": "user", "content": sanitized_message})
            if is_handshake:
                # Mark handshake signals so the transcript serializers can
                # filter them from what candidates/recruiters see (M-4).
                history[-1]["_handshake"] = True
            sync_ai_interview_session(db, app, interview_log=history)

        real_question_count = current_q_index - (1 if had_handshake else 0)
        if real_question_count > total_questions and not is_handshake:
            await engine.transition_to(
                app.id, InterviewState.EVALUATING, reason="Max questions reached"
            )
            sync_evaluation_state(db, app, evaluation_state="pending")
            db.commit()
            background_tasks.add_task(
                run_background_final_evaluation, app.id, app.company_id
            )
            return {
                "reply": _msg("completion_reply", language_context),
                "type": "complete",
                "current_score": round(float(_final_score_chat or 0), 2),
                "progress": {
                    "current": total_questions,
                    "total": total_questions,
                    "percentage": 100,
                },
            }

        if not is_handshake and should_append:
            await engine.record_answer(app.id, current_q_index - 1, sanitized_message)

        if isinstance(_analysis_json_chat, dict):
            analysis_data = _analysis_json_chat
        else:
            analysis_data = json.loads(_analysis_json_chat or "{}")
        engine_state = analysis_data.get("engine_v2_state")

        if not engine_state:
            skills_list_raw = analysis_data.get("skills") or []
            skills_list = []
            for s in skills_list_raw:
                if isinstance(s, str):
                    skills_list.append(s)
                elif isinstance(s, dict):
                    skills_list.append(s.get("name") or s.get("skill") or str(s))
                elif s:
                    skills_list.append(str(s))

            initial_metrics = analysis_data.get("skill_metrics")

            if not initial_metrics and _cv_score_chat:
                s = float(_cv_score_chat)
                initial_metrics = {
                    "Technical": int(s),
                    "Communication": int(s),
                    "Problem Solving": int(s),
                    "Adaptability": int(s),
                    "Confidence": int(s),
                    "Consistency": 100,
                    "Soft Skills": int(s),
                }
                if not ScoringService.get_canonical_score(app.id, db):
                    ScoringService.compute_final_score(
                        app,
                        db,
                        computed_by="chat_init",
                        override_cv_score=s,
                    )

            strategy = get_interview_strategy(skills_list, 0.5)
            engine_state = initialize_engine_state(
                strategy,
                skills=skills_list,
                initial_metrics=initial_metrics,
                max_turns=total_questions,
            )

        # Load rubric from snapshot via reader
        job_rubric = None
        job_rubric_db_id = None
        rubric_categories = None
        if _es and _es.config_snapshot and reader:
            parsed_rubric = reader.get_rubric()
            if parsed_rubric.raw_json:
                try:
                    from backend.rubric.rubric_schema import JobRubric

                    job_rubric = JobRubric(**parsed_rubric.raw_json)
                    job_rubric_db_id = parsed_rubric.id
                    rubric_categories = job_rubric.categories if job_rubric else None
                    logger.info(
                        f"[RUBRIC] Using snapshot-reconstructed rubric {parsed_rubric.id} for app {app.id}"
                    )
                except Exception as e:
                    logger.warning(
                        f"[RUBRIC] Failed to reconstruct rubric {parsed_rubric.id} from snapshot: {e}"
                    )

        if not job_rubric:
            logger.warning(
                f"App {app.id}: no rubric in snapshot -- proceeding without rubric-based scoring"
            )

        # Track covered skills from rubric in engine_state
        if "covered_skills" not in engine_state:
            engine_state["covered_skills"] = []

        # Inject rubric skill scores into live_skill_metrics for talent graph
        if job_rubric:
            live = engine_state.get("live_skill_metrics", {})
            live_conf = engine_state.get("live_skill_confidence", {})
            for cat in job_rubric.categories:
                for sub in getattr(cat, "subcategories", []):
                    for sk in getattr(sub, "skills", []):
                        skname = sk.name
                        if skname not in live:
                            live[skname] = 0.0
                            live_conf[skname] = 25.0
            engine_state["live_skill_metrics"] = live
            engine_state["live_skill_confidence"] = live_conf

        last_eval = {
            "score": _final_score_chat or _cv_score_chat or 50,
            "quality": "normal",
            "feedback": "",
            "reasoning": "",
        }
        if not is_handshake and sanitized_message:
            last_q = next(
                (
                    m["content"]
                    for m in reversed(history[:-1])
                    if m["role"] == "assistant"
                ),
                "",
            )
            last_focus = engine_state.get("current_focus")
            history_summary = "\n".join(
                [
                    f"Q: {h['question']}\nA: {h['answer'][:100]}"
                    for h in engine_state.get("history", [])[-5:]
                ]
            )

            prev_answers = [
                h.get("answer", "")
                for h in engine_state.get("history", [])
                if h.get("answer")
            ]
            try:
                last_eval = await evaluate_answer(
                    question=last_q,
                    answer=sanitized_message,
                    focus=last_focus,
                    history_summary=history_summary,
                    declared_role=_declared_role_chat,
                    language=language_context,
                    previous_answers=prev_answers,
                    app=app,
                    job_rubric=job_rubric,
                    job_rubric_db_id=job_rubric_db_id,
                    answer_id=current_q_index - 1,
                )
                logger.info(
                    f"[EVAL-RESULT] App {app.id} score={last_eval.get('score')} "
                    f"skills={last_eval.get('skills',{})!r} "
                    f"quality={last_eval.get('quality')} "
                    f"reasoning={str(last_eval.get('reasoning',''))[:200]}"
                )
            except Exception as eval_err:
                logger.warning(
                    f"[EVALUATION] Failed for app {app.id}, using previous score: {eval_err}"
                )
                # Reuse the candidate's most recent real score instead of
                # injecting a neutral 50 that would distort the average.
                _prev_scored = [
                    h.get("score")
                    for h in engine_state.get("history", [])
                    if h.get("score") is not None and h.get("score") > 0
                ]
                _fallback_score = (
                    _prev_scored[-1]
                    if _prev_scored
                    else (float(_cv_score_chat) if _cv_score_chat else 0.0)
                )
                last_eval = {
                    "score": float(_fallback_score),
                    "eval_failed": True,
                    "quality": "adequate",
                    "feedback": "Evaluation unavailable for this answer.",
                    "reasoning": "Evaluation processing error, using previous score.",
                    "skills": {},
                }

            is_lazy_penalty = False
            if len(sanitized_message) < 4:
                is_lazy_penalty = True
            elif msg_lower in ALWAYS_LAZY and len(last_q) > 40:
                is_lazy_penalty = True
            if is_lazy_penalty:
                logger.info(
                    f"[SCORING] Lazy answer detected for app {app.id}. Applying hard penalty."
                )
                last_eval["score"] = 20
                last_eval["quality"] = "vague"
                last_eval["feedback"] = (
                    "Your answer was too brief. Technical roles require detailed evidence and context."
                )

            if last_eval.get("gaming_detected"):
                engine_state["sigma"] = engine_state.get("sigma", 25.0) + 15.0
                logger.warning(
                    f"[V3 ANTI-GAMING] Pattern detected for app {app.id}. Sigma spiked."
                )

            _cat_scores = last_eval.get("skills")
            _debug_info = {
                "app_id": app.id, "turn": engine_state.get("turn", 0),
                "last_focus": last_focus, "eval_score": last_eval["score"],
                "category_scores": _cat_scores,
                "pre_live_skills": dict(engine_state.get("live_skill_metrics", {})),
                "pre_skill_scores_keys": list(engine_state.get("skill_scores", {}).keys()),
                "is_handshake": is_handshake,
                "sanitized_message_len": len(sanitized_message) if sanitized_message else 0,
            }
            logger.info(
                f"[SCORING-DEBUG] App {app.id} turn={engine_state.get('turn',0)} "
                f"last_focus={last_focus} eval_score={last_eval['score']} "
                f"category_scores={_cat_scores!r} "
                f"covered_skills={engine_state.get('covered_skills',[])} "
                f"pre_live_skills={engine_state.get('live_skill_metrics',{})!r}"
            )
            engine_state = update_engine_state(
                engine_state, last_focus, last_eval["score"], _cat_scores
            )
            _debug_info["post_live_skills"] = dict(engine_state.get("live_skill_metrics", {}))
            logger.info(
                f"[SCORING-DEBUG-POST] App {app.id} "
                f"post_live_skills={engine_state.get('live_skill_metrics',{})!r} "
                f"post_skill_scores={engine_state.get('skill_scores',{})!r}"
            )
            try:
                import tempfile, json as _dj, os as _os
                with open(_os.path.join(tempfile.gettempdir(), "scoring_debug.json"), "w") as _f:
                    _dj.dump(_debug_info, _f, indent=2, default=str)
            except Exception:
                pass

            # Early exit: if candidate scores <35 avg after 3+ questions with no improvement
            from backend.ai.interview_customization import should_early_exit

            if should_early_exit(engine_state):
                engine_state["max_turns"] = engine_state.get("turn", 0)
                logger.info(
                    f"[EARLY EXIT] App {app.id} triggering early exit at turn {engine_state['turn']}"
                )

            sync_ai_interview_session(
                db, app, interview_progress=engine_state.get("turn", 0)
            )
            sync_ai_interview_session(db, app, interview_state="in_progress")
            try:
                db.commit()
            except Exception as _prog_err:
                logger.warning(
                    f"[PROGRESS] Failed to commit progress for app {app.id}: {_prog_err}"
                )

            live_metrics = engine_state.get("live_skill_metrics", {})

            # --- Post-timeout guard (Invariant 2) ---
            # If time expired while the AI was generating a question or
            # evaluating the answer, do NOT score or persist new state.
            _remaining_now = _compute_remaining_seconds(_expires_at)
            if _remaining_now <= 0:
                logger.info(
                    f"[TIMEOUT-GUARD] App {app.id} expired during processing. "
                    f"Discarding this turn's scoring."
                )
                sync_ai_interview_session(db, app, interview_state="expired")
                sync_evaluation_state(db, app, evaluation_state="pending")
                db.commit()
                background_tasks.add_task(
                    run_background_final_evaluation, app.id, app.company_id
                )
                return {
                    "reply": _msg("timeout_reply", language_context),
                    "type": "timeout",
                    "time_limit_reached": True,
                    "time_left": 0,
                    "current_score": round(float(_final_score_chat or 0), 2),
                    "progress": {
                        "current": engine_state.get("turn", 0),
                        "total": total_questions,
                        "percentage": 100,
                        "state": "completed",
                    },
                }

            logger.info(
                f"[SCORING-BLOCK] App {app.id} live_metrics={live_metrics!r} "
                f"nonzero={{k:v for k,v in live_metrics.items() if v > 0}}"
            )
            if live_metrics:
                q_scores = [
                    h.get("score", 50)
                    for h in engine_state.get("history", [])
                    if h.get("score") is not None
                ]

                violations = []
                try:
                    _pc_violations_chat = getattr(_es, "proctoring_violations", None)
                    if _pc_violations_chat:
                        violations = json.loads(_pc_violations_chat)
                except Exception:
                    pass

                cheat_already_penalized = (
                    last_eval.get("cheat_detected", False)
                    or last_eval.get("cheat_penalty", 0) > 0
                )
                gaming_detected = (
                    last_eval.get("gaming_detected", False)
                    and not cheat_already_penalized
                )

                answered = engine_state.get("turn", 0)
                total = engine_state.get("max_turns", total_questions)

                breakdown = calculate_overall_score(
                    skill_metrics=live_metrics,
                    question_scores=q_scores,
                    answered=answered,
                    total=total,
                    violations=violations,
                    gaming_detected=gaming_detected,
                )

                engine_state["score_breakdown"] = breakdown.to_dict()
                engine_state["score_label"] = get_score_label(breakdown.final_score)
                engine_state["hiring_decision"] = get_recommendation(
                    breakdown.final_score, breakdown.integrity_penalty
                )

                logger.info(
                    f"[SCORING] Q{answered}/{total} | Base={breakdown.base_score:.1f} "
                    f"Momentum=+{breakdown.momentum_bonus:.1f} Complete=+{breakdown.completeness_bonus:.1f} "
                    f"Integrity=-{breakdown.integrity_penalty:.1f} "
                    f"Gaming=-{breakdown.gaming_penalty:.1f} | Final={breakdown.final_score:.1f} ({engine_state['score_label']})"
                )
                logger.info(
                    "[SCORING-DATA] live_metrics=%s skill_scores=%s q_scores=%s",
                    {k: v for k, v in live_metrics.items() if v > 0},
                    {k: v for k, v in engine_state.get("skill_scores", {}).items() if v},
                    q_scores,
                )
            else:
                engine_state["score_label"] = get_score_label(last_eval.get("score", 0))

            engine_state["history"].append(
                {
                    "question": last_q,
                    "answer": sanitized_message,
                    "focus": last_focus,
                    "score": last_eval["score"],
                    "quality": last_eval["quality"],
                    "feedback": last_eval.get("feedback", ""),
                    "reasoning": last_eval.get("reasoning", ""),
                    "timestamp": _utcnow().isoformat(),
                }
            )

            if last_eval.get("feedback"):
                ai_feedback = CandidateInteraction(
                    application_id=app.id,
                    user_id=None,
                    type="ai_feedback",
                    subject=f"AI Feedback - Question {current_q_index}",
                    content=last_eval["feedback"],
                    is_automated=True,
                    company_id=app.company_id,
                )
                db.add(ai_feedback)
                logger.info(
                    f"[FEEDBACK] Saved AI feedback to interactions for app {app.id}"
                )

            try:
                from backend.interview_turns import load_turns

                current_qa = load_turns(db, app)
                if not isinstance(current_qa, list):
                    current_qa = []

                response_time = 0
                question_sent_ts = 0
                for m in reversed(history[:-1]):
                    if m.get("role") == "assistant":
                        question_sent_ts = m.get("_sent_at", 0)
                        break
                if question_sent_ts > 0:
                    response_time = round((_utcnow().timestamp() - question_sent_ts), 1)

                now_ts = _utcnow().timestamp()
                qa_entry = {
                    "number": current_q_index,
                    "question": last_q,
                    "answer": sanitized_message,
                    "score": last_eval["score"],
                    "feedback": last_eval.get("feedback", ""),
                    "reasoning": last_eval.get("reasoning", ""),
                    "quality": last_eval.get("quality", "normal"),
                    "type": last_focus or "general",
                    "difficulty": "medium",
                    "question_timestamp": now_ts,
                    "answer_timestamp": _utcnow().isoformat(),
                    "response_time_seconds": response_time,
                    "status": "answered" if last_eval["score"] > 0 else "pending",
                }
                current_qa.append(qa_entry)

                try:
                    from backend.interview_turns import write_turn

                    write_turn(
                        db,
                        app,
                        int(current_q_index or 0) or len(current_qa),
                        question=last_q,
                        answer=sanitized_message,
                        score=last_eval.get("score"),
                        feedback=last_eval.get("feedback"),
                        reasoning=last_eval.get("reasoning"),
                        quality=last_eval.get("quality"),
                        type_=last_focus or "general",
                        difficulty="medium",
                        response_time_seconds=response_time,
                        status="answered"
                        if last_eval.get("score", 0) > 0
                        else "pending",
                        question_timestamp=qa_entry.get("question_timestamp"),
                        answer_timestamp=qa_entry.get("answer_timestamp"),
                    )
                except Exception as turn_err:
                    logger.warning(
                        f"[TURNS] write_turn failed for app {app.id} turn "
                        f"{current_q_index}: {turn_err}"
                    )
            except Exception as qa_err:
                logger.error(f"Failed to save structured QA for app {app.id}: {qa_err}")

        calibration_data = None
        _calibration_json = (
            getattr(_es, "calibration_json", None) or app.calibration_json
        )
        if _calibration_json:
            try:
                calibration_data = json.loads(_calibration_json)
            except Exception:
                pass

        turn_resp = await generate_skill_driven_turn(
            state=engine_state,
            cv_context=cv_context,
            declared_role=_declared_role_chat,
            language=language_context,
            job_description=job_description,
            intelligence_layer=analysis_data,
            calibration_data=calibration_data,
            recruiter_instructions=interview_instructions,
            custom_question_prompt=custom_q_prompt,
            rubric_categories=rubric_categories,
            rubric_seniority=job_rubric.seniority if job_rubric else "mid",
        )

        # Track the selected focus as a covered rubric skill
        if rubric_categories and "covered_skills" in engine_state:
            selected_focus = turn_resp.get("focus", "")
            logger.info(
                f"[FOCUS] App {app.id} selected_focus={selected_focus!r} "
                f"covered_before={engine_state['covered_skills']}"
            )
            if selected_focus.lower() not in [
                s.lower() for s in engine_state["covered_skills"]
            ]:
                engine_state["covered_skills"].append(selected_focus)
            logger.info(f"[FOCUS] App {app.id} covered_after={engine_state['covered_skills']}")

        question_sent_at = _utcnow().timestamp()
        history.append(
            {
                "role": "assistant",
                "content": turn_resp["reply"],
                "_sent_at": question_sent_at,
            }
        )
        sync_ai_interview_session(db, app, interview_log=history)
        analysis_data["engine_v2_state"] = engine_state
        sync_cv_document(db, app, analysis_json=analysis_data)
        sync_ai_interview_session(db, app, interview_progress=engine_state["turn"])
        db.commit()

        is_complete = engine_state["turn"] >= engine_state["max_turns"]

        if is_complete:
            sync_ai_interview_session(db, app, interview_state="completed")
            sync_evaluation_state(db, app, evaluation_state="pending")
            db.commit()
            background_tasks.add_task(
                run_background_final_evaluation, app.id, app.company_id
            )
            logger.info(
                f"[INTERVIEW] Interview {app.id} marked as complete. Background evaluation triggered."
            )

        record_ai_call(success=True)
        # Recompute remaining from the authoritative deadline.
        _time_left_resp = _compute_remaining_seconds(_expires_at)
        _live_breakdown = engine_state.get("score_breakdown") or {}
        _live_score_resp = (
            _live_breakdown.get("final_score")
            if isinstance(_live_breakdown, dict) and _live_breakdown.get("final_score")
            else (_final_score_chat or last_eval.get("score"))
        )
        return {
            "reply": turn_resp["reply"],
            "hint_text": turn_resp.get("hint_text"),
            "type": "complete" if is_complete else "question",
            "current_score": _live_score_resp,
            "time_left": _time_left_resp,
            "score_label": engine_state.get("score_label", ""),
            "score_breakdown": engine_state.get("score_breakdown"),
            "scoring_weights": DIMENSION_WEIGHTS,
            "skills": engine_state.get("live_skill_metrics", {}),
            "skill_confidence": engine_state.get("live_skill_confidence", {}),
            "confidence_score": engine_state.get("confidence_score", 50.0),
            "hire_probability": engine_state.get("hire_probability", 0.0),
            "momentum": engine_state.get("momentum", 0.0),
            "hiring_decision": engine_state.get("hiring_decision", "N/A"),
            "feedback": last_eval.get("feedback", ""),
            "score_reasoning": last_eval.get("reasoning", ""),
            "focus": turn_resp.get("focus", "") if not is_handshake else "",
            "is_vague": last_eval.get("quality") == "vague",
            "current_question": engine_state["turn"],
            "progress": {
                "current": engine_state["turn"],
                "total": engine_state["max_turns"],
                "percentage": int(
                    (engine_state["turn"] / engine_state["max_turns"]) * 100
                ),
            },
            "language": language_context,
            "is_complete": is_complete,
        }

    except Exception as e:
        record_ai_call(success=False)
        logger.error(f"Critical error in _interview_chat_core: {e}", exc_info=True)
        raise
    finally:
        if turn_claimed and _es_id_turn:
            try:
                result = db.execute(
                    update(EvaluationSession)
                    .where(EvaluationSession.id == _es_id_turn)
                    .where(
                        EvaluationSession.interview_turn_seq
                        == expected_seq + 1
                    )
                    .values(interview_turn_seq=expected_seq + 2)
                )
                db.commit()

                if result.rowcount != 1:
                    logger.error(
                        f"[IDEMPOTENCY] Lock state changed unexpectedly "
                        f"for app {app.id}: expected seq {expected_seq + 1}"
                    )
                else:
                    logger.info(
                        f"[IDEMPOTENCY] Turn completed. "
                        f"Unlocked with seq {expected_seq + 2}"
                    )
            except Exception as lock_err:
                logger.error(
                    f"[IDEMPOTENCY] Failed to release lock for app {app.id}: {lock_err}"
                )
                try:
                    db.rollback()
                    result_retry = db.execute(
                        update(EvaluationSession)
                        .where(EvaluationSession.id == _es_id_turn)
                        .where(
                            EvaluationSession.interview_turn_seq
                            == expected_seq + 1
                        )
                        .values(interview_turn_seq=expected_seq + 2)
                    )
                    db.commit()

                    if result_retry.rowcount != 1:
                        logger.error(
                            f"[IDEMPOTENCY] Retry could not release lock safely "
                            f"for app {app.id}: expected seq {expected_seq + 1}"
                        )
                except Exception:
                    logger.error(f"[IDEMPOTENCY] CRITICAL: Could not release lock for app {app.id} even after retry")
            try:
                _remaining_final = _compute_remaining_seconds(_expires_at)
                sync_ai_interview_session(
                    db, app, interview_time_left=_remaining_final
                )
                db.commit()
            except Exception as e:
                logger.error(
                    f"[TIME LEFT] Failed to persist interview_time_left for app {app.id}: {e}"
                )


async def generate_interview_turn_with_timeout(
    cv_context: str,
    declared_role: str,
    history: list,
    current_q_index: int,
    total_questions: int,
    language: str,
    job_title: str,
    job_description: str,
    app_id: int,
    current_score: float,
    initial_skills: dict = None,
    seniority_level: str = "Junior",
    interview_instructions: dict = None,
    instruction_state: dict = None,
) -> dict:
    response = None
    from backend.ai.llm import call_groq_cascade

    try:
        from backend.ai.worker import interview_queue

        task_data = {
            "cv_context": cv_context,
            "declared_role": declared_role,
            "history": history,
            "current_q_index": current_q_index,
            "current_score": current_score,
            "total_questions": total_questions,
            "language": language,
            "job_title": job_title,
            "job_description": job_description,
            "app_id": app_id,
            "initial_skills": initial_skills,
            "seniority_level": seniority_level,
            "interview_instructions": interview_instructions,
            "instruction_state": instruction_state,
        }

        task_id = await interview_queue.enqueue_task(task_data)

        async with asyncio.timeout(120):
            response = await interview_queue.wait_for_result(task_id)

        if not response:
            raise Exception("Worker timed out or returned no result")

        if response and isinstance(response, dict):
            reply_val = str(response.get("reply", "")).lower()
            if "connectivity issues" in reply_val or "manually reviewing" in reply_val:
                logger.error(
                    f"[AI ERROR] App {app_id}: Caught connectivity error dict, triggering Layer 2 retry."
                )
                raise Exception("Connectivity error dict returned by worker")
            elif "reply" not in response:
                logger.warning(
                    f"[AI WARNING] App {app_id}: Missing 'reply' field after generation"
                )
                raise Exception("Missing 'reply' field in worker response")
            else:
                logger.info(
                    f"[AI SUCCESS] App {app_id}: Q{current_q_index} generated successfully"
                )
                return response
        else:
            logger.warning(
                f"[AI WARNING] App {app_id}: Invalid response type/structure on attempt 1"
            )
            raise Exception("Invalid response type from worker")

    except asyncio.TimeoutError:
        logger.warning(
            f"[AI TIMEOUT] App {app_id} Q{current_q_index}: Timeout on first attempt (120s), retrying..."
        )
        record_ai_call(success=False, timeout=True)
    except Exception as e:
        logger.error(
            f"[AI ERROR] App {app_id} Q{current_q_index}: {type(e).__name__}: {e}"
        )
        record_ai_call(success=False)

    try:
        logger.info(f"[AI RETRY] App {app_id}: Attempting faster retry model...")
        async with asyncio.timeout(60):
            prompt = f"The candidate is interviewing for {declared_role}. This is turn {current_q_index}/{total_questions}. Ask one deep technical question relevant to this role and the interview context."
            response = await call_groq_cascade(
                [
                    {
                        "role": "system",
                        "content": f"You are an expert technical interviewer for {declared_role}. Ask ONE concise, challenging technical question. Output only the question text.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.5,
                max_tokens=200,
                json_mode=False,
            )

            if response and isinstance(response, str):
                logger.info(
                    f"[RETRY SUCCESS] App {app_id}: Got text response from faster model"
                )
                return {
                    "reply": response.strip(),
                    "current_score": current_score,
                    "feedback": _msg("response_noted", language),
                    "skills": initial_skills.copy()
                    if initial_skills
                    else {
                        "Technical": current_score,
                        "Communication": round(current_score * 0.92, 1),
                        "Problem Solving": round(current_score * 1.05, 1)
                        if current_score < 90
                        else 95,
                        "Adaptability": round(current_score * 0.88, 1),
                        "Confidence": round(current_score * 0.95, 1),
                    },
                }

    except Exception as e:
        logger.error(f"[FALLBACK ERROR] App {app_id}: {type(e).__name__}: {e}")

    if not response or not isinstance(response, dict) or "reply" not in response:
        logger.error(
            f"[AI TOTAL FAIL] App {app_id}: All attempts failed. Triggering hard fallback question."
        )
        response = get_fallback_turn(
            current_q_index, declared_role, current_score, language
        )

    if response and "reply" in response:
        response["reply"] = html.unescape(str(response["reply"]))

    if response and "feedback" in response:
        response["feedback"] = html.unescape(str(response["feedback"]))

    return response
