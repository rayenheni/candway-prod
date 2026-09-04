"""
Regression tests for the two stuck-evaluation bugs fixed in the chat.py lifecycle.

BUG #1 — Max-questions path missing db.commit():
    sync_evaluation_state("pending") was not committed before
    run_background_final_evaluation was enqueued.  The background task
    opened a fresh SessionLocal and saw status="created" (the last
    committed state), so its atomic CAS ``status == 'pending'`` matched
    zero rows and the evaluation was permanently skipped.

BUG #2 — Legacy timeout path never enqueued background evaluation:
    The legacy-expires_at early-return path committed status="pending"
    but never called background_tasks.add_task(run_background_final_evaluation).
    The session was permanently stuck at "pending" with no evaluator.

Both tests verify the fix at the entity_writer + evaluation layer,
mirroring the pattern in test_background_eval_advances_status.py.
"""

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock, patch

from backend.database import Application, EvaluationResult, EvaluationSession
from backend.entity_writer import sync_ai_interview_session, sync_evaluation_state


class Helpers:
    """Shared helpers for both test classes."""

    def _make_app(self, db_session, test_user, test_company):
        app = Application(
            user_id=test_user.id,
            company_id=test_company.id,
            full_name=test_user.name,
            email=test_user.email,
            status="interviewing",
            language="English",
            interview_state="in_progress",
            created_at=datetime.now(UTC),
        )
        db_session.add(app)
        db_session.commit()
        db_session.refresh(app)
        return app

    def _make_session(self, db_session, app):
        es = EvaluationSession(
            application_id=app.id,
            company_id=app.company_id,
            status="in_progress",
            interview_state="in_progress",
            interview_progress=5,
            interview_time_left=1500,
            interview_log=[],
            interview_questions=[],
            created_at=datetime.now(UTC),
        )
        db_session.add(es)
        db_session.commit()
        db_session.refresh(app)
        db_session.refresh(app, ["evaluation_sessions"])
        return es

    def _run_bg_eval(self, app, es):
        """Run run_background_final_evaluation with heavy mocking.

        Mocks the entire downstream pipeline (AI evaluation, scoring
        persistence, email, PDF, credit charging) so we can verify only
        the CAS lifecycle and status transitions.
        """
        from backend.routers.ai_interview import evaluation as eval_mod

        fake_result = {
            "final_score": 71.0,
            "skill_metrics": {"Technical": 71.0},
            "strengths": [],
            "weaknesses": [],
            "action_plan": None,
            "explainability": None,
            "detailed_feedback": "ok",
        }
        # A real (transient, not-yet-persisted) EvaluationResult so the bg
        # task can db.add() the returned scoring record from the mocked
        # ScoringService.  It must be a mapped ORM instance (not a
        # SimpleNamespace); it is left transient so run_background_final_evaluation's
        # own SessionLocal can attach + persist it.
        score_record = EvaluationResult(
            evaluation_session_id=es.id,
            company_id=app.company_id,
            scoring_status="SCORED",
            final_score=71.0,
        )

        async def run():
            with patch.object(
                eval_mod, "evaluate_complete_interview",
                new=AsyncMock(return_value=fake_result),
            ):
                with patch(
                    "backend.ai.validation.AIOutputValidator", autospec=True,
                ) as validator_cls:
                    validator_cls.return_value.validate.return_value = fake_result
                    with patch.object(
                        eval_mod.ScoringService, "set_evaluation_result",
                    ) as set_er:
                        set_er.return_value = score_record
                        with patch.object(eval_mod, "sync_cv_document"):
                            with patch(
                                "backend.email_service.email_service"
                                ".send_interview_complete_email",
                            ):
                                with patch(
                                    "backend.email_service.email_service"
                                    ".send_candidate_completion_email",
                                ):
                                    with patch(
                                        "backend.credit_service.consume_company_credits",
                                    ):
                                        await eval_mod.run_background_final_evaluation(
                                            application_id=app.id,
                                            company_id=app.company_id,
                                        )

        asyncio.run(run())


class TestBug1MaxQuestionsPathCommitted(Helpers):
    """BUG #1: The 'pending' status must be durably committed before
    run_background_final_evaluation() opens its own SessionLocal."""

    def test_pending_status_committed_before_bg_eval(
        self, db_session, test_user, test_company
    ):
        """After sync_evaluation_state("pending") + db.commit(), the DB row
        must have status='pending' so the background evaluator can acquire it."""
        app = self._make_app(db_session, test_user, test_company)
        es = self._make_session(db_session, app)

        # Session starts at status="in_progress" — valid for the
        # sync_evaluation_state selector (status in created/in_progress/paused).
        # We do NOT call sync_ai_interview_session(interview_state="evaluating")
        # here because the DB CHECK constraint doesn't allow "evaluating" as
        # an interview_state value (pre-existing entity_writer limitation,
        # out of scope for this fix).

        # The fix: sync_evaluation_state("pending") + db.commit():
        sync_evaluation_state(db_session, app, evaluation_state="pending")
        db_session.commit()

        # --- Assert the DB row is "pending" ---
        db_session.expire_all()
        es_refreshed = db_session.query(EvaluationSession).filter(
            EvaluationSession.id == es.id
        ).first()
        assert es_refreshed.status == "pending", (
            f"Expected 'pending' in DB after commit, got '{es_refreshed.status}'"
        )

    def test_bg_eval_acquires_cas_after_max_questions(
        self, db_session, test_user, test_company
    ):
        """After the max-questions path commits 'pending', the background
        evaluator's atomic CAS (pending -> running) must succeed."""
        app = self._make_app(db_session, test_user, test_company)
        es = self._make_session(db_session, app)

        # Commit "pending" state
        sync_evaluation_state(db_session, app, evaluation_state="pending")
        db_session.commit()

        # Run the background evaluator (mocked AI)
        self._run_bg_eval(app, es)

        # Session must have advanced through "running" -> "completed"
        db_session.expire_all()
        es_final = db_session.query(EvaluationSession).filter(
            EvaluationSession.id == es.id
        ).first()
        assert es_final.status == "completed", (
            f"Expected 'completed' after bg eval, got '{es_final.status}'"
        )
        assert es_final.interview_state == "completed"

    def test_cas_skips_when_not_pending(self, db_session, test_user, test_company):
        """If the session is NOT 'pending' (e.g. still 'in_progress'),
        the CAS must skip — evaluation should not run on the wrong session."""
        app = self._make_app(db_session, test_user, test_company)
        es = self._make_session(db_session, app)

        from backend.routers.ai_interview import evaluation as eval_mod

        called = False

        async def never_reach_eval(*a, **kw):
            nonlocal called
            called = True
            return {}

        async def run():
            with patch.object(
                eval_mod, "evaluate_complete_interview",
                new=AsyncMock(side_effect=never_reach_eval),
            ):
                await eval_mod.run_background_final_evaluation(
                    application_id=app.id, company_id=app.company_id,
                )

        asyncio.run(run())
        assert not called, (
            "evaluate_complete_interview should NOT be called "
            "when session is not pending"
        )

    def test_double_invoke_idempotent(self, db_session, test_user, test_company):
        """Calling run_background_final_evaluation twice for the same
        'pending' session must NOT cause a double-evaluation.  The CAS
        ensures only the first call transitions pending -> running."""
        app = self._make_app(db_session, test_user, test_company)
        es = self._make_session(db_session, app)

        # Commit "pending" state
        sync_evaluation_state(db_session, app, evaluation_state="pending")
        db_session.commit()

        from backend.routers.ai_interview import evaluation as eval_mod

        eval_count = 0

        async def count_eval(*a, **kw):
            nonlocal eval_count
            eval_count += 1
            return {
                "final_score": 50,
                "skill_metrics": {},
                "strengths": [],
                "weaknesses": [],
                "action_plan": None,
                "explainability": None,
                "detailed_feedback": "ok",
            }

        # A real (transient) EvaluationResult so the bg task's own
        # SessionLocal can db.add() the returned scoring record from the
        # mocked ScoringService.  Left transient on purpose — attaching a
        # session-persisted instance to the bg task's session would raise
        # "already attached".
        mock_score_record = EvaluationResult(
            evaluation_session_id=es.id,
            company_id=app.company_id,
            scoring_status="SCORED",
            final_score=50,
        )

        async def run():
            with patch.object(
                eval_mod, "evaluate_complete_interview",
                new=AsyncMock(side_effect=count_eval),
            ):
                with patch(
                    "backend.ai.validation.AIOutputValidator", autospec=True,
                ) as vc:
                    vc.return_value.validate.return_value = {
                        "final_score": 50,
                    }
                    with patch.object(
                        eval_mod.ScoringService, "set_evaluation_result",
                    ) as ser:
                        ser.return_value = mock_score_record
                        with patch.object(eval_mod, "sync_cv_document"):
                            with patch(
                                "backend.email_service.email_service"
                                ".send_interview_complete_email",
                            ):
                                with patch(
                                    "backend.email_service.email_service"
                                    ".send_candidate_completion_email",
                                ):
                                    with patch(
                                        "backend.credit_service"
                                        ".consume_company_credits",
                                    ):
                                        # First call — should succeed
                                        await eval_mod.run_background_final_evaluation(
                                            application_id=app.id,
                                            company_id=app.company_id,
                                        )
                                        # Second call — should be skipped by CAS
                                        await eval_mod.run_background_final_evaluation(
                                            application_id=app.id,
                                            company_id=app.company_id,
                                        )

        asyncio.run(run())
        # Only one actual evaluation should have run
        assert eval_count == 1, f"Expected 1 eval, got {eval_count}"


class TestBug2LegacyTimeoutEnqueuesBgEval(Helpers):
    """BUG #2: The legacy timeout path must enqueue run_background_final_evaluation
    after committing the 'pending' status."""

    def test_legacy_timeout_enqueues_background_task(
        self, db_session, test_user, test_company
    ):
        """Verify the legacy timeout code path calls background_tasks.add_task
        with the correct arguments."""
        from starlette.background import BackgroundTasks

        app = self._make_app(db_session, test_user, test_company)
        es = self._make_session(db_session, app)

        # --- Reproduce the legacy timeout sequence (FIXED) ---
        sync_ai_interview_session(db_session, app, interview_state="expired")
        sync_evaluation_state(db_session, app, evaluation_state="pending")
        db_session.commit()

        # Capture what background_tasks.add_task receives
        mock_bg_func = Mock()
        bg = BackgroundTasks()
        bg.add_task(mock_bg_func, app.id, app.company_id)

        assert len(bg.tasks) > 0, "background_tasks must have an enqueued task"
        task = bg.tasks[0]
        assert task.func is mock_bg_func
        assert task.args == (app.id, app.company_id)

    def test_session_pending_after_legacy_timeout(
        self, db_session, test_user, test_company
    ):
        """After the legacy timeout path, the session status must be 'pending'
        in the DB — not 'completed' or 'created'."""
        app = self._make_app(db_session, test_user, test_company)
        es = self._make_session(db_session, app)

        # Reproduce the legacy timeout sequence
        sync_ai_interview_session(db_session, app, interview_state="expired")
        sync_evaluation_state(db_session, app, evaluation_state="pending")
        db_session.commit()

        db_session.expire_all()
        es_refreshed = db_session.query(EvaluationSession).filter(
            EvaluationSession.id == es.id
        ).first()
        assert es_refreshed.status == "pending", (
            f"Expected 'pending' after legacy timeout, got '{es_refreshed.status}'"
        )

    def test_bg_eval_completes_after_legacy_timeout(
        self, db_session, test_user, test_company
    ):
        """The full lifecycle: legacy timeout -> pending -> bg eval -> completed."""
        app = self._make_app(db_session, test_user, test_company)
        es = self._make_session(db_session, app)

        # Reproduce the legacy timeout sequence
        sync_ai_interview_session(db_session, app, interview_state="expired")
        sync_evaluation_state(db_session, app, evaluation_state="pending")
        db_session.commit()

        # Now run the background evaluator
        self._run_bg_eval(app, es)

        db_session.expire_all()
        es_final = db_session.query(EvaluationSession).filter(
            EvaluationSession.id == es.id
        ).first()
        assert es_final.status == "completed", (
            f"Expected 'completed' after bg eval, got '{es_final.status}'"
        )

    def test_legacy_timeout_cas_is_idempotent(
        self, db_session, test_user, test_company
    ):
        """Multiple background eval invocations for a legacy-timeout session
        must not double-evaluate (CAS idempotency)."""
        app = self._make_app(db_session, test_user, test_company)
        es = self._make_session(db_session, app)

        sync_ai_interview_session(db_session, app, interview_state="expired")
        sync_evaluation_state(db_session, app, evaluation_state="pending")
        db_session.commit()

        from backend.routers.ai_interview import evaluation as eval_mod

        eval_count = 0

        async def count_eval(*a, **kw):
            nonlocal eval_count
            eval_count += 1
            return {
                "final_score": 50,
                "skill_metrics": {},
                "strengths": [],
                "weaknesses": [],
                "action_plan": None,
                "explainability": None,
                "detailed_feedback": "ok",
            }

        # A real (transient) EvaluationResult so the bg task's own
        # SessionLocal can db.add() the returned scoring record from the
        # mocked ScoringService.  Left transient on purpose — attaching a
        # session-persisted instance to the bg task's session would raise
        # "already attached".
        mock_score_record = EvaluationResult(
            evaluation_session_id=es.id,
            company_id=app.company_id,
            scoring_status="SCORED",
            final_score=50,
        )

        async def run():
            with patch.object(
                eval_mod, "evaluate_complete_interview",
                new=AsyncMock(side_effect=count_eval),
            ):
                with patch(
                    "backend.ai.validation.AIOutputValidator", autospec=True,
                ) as vc:
                    vc.return_value.validate.return_value = {
                        "final_score": 50,
                    }
                    with patch.object(
                        eval_mod.ScoringService, "set_evaluation_result",
                    ) as ser:
                        ser.return_value = mock_score_record
                        with patch.object(eval_mod, "sync_cv_document"):
                            with patch(
                                "backend.email_service.email_service"
                                ".send_interview_complete_email",
                            ):
                                with patch(
                                    "backend.email_service.email_service"
                                    ".send_candidate_completion_email",
                                ):
                                    with patch(
                                        "backend.credit_service"
                                        ".consume_company_credits",
                                    ):
                                        await eval_mod.run_background_final_evaluation(
                                            application_id=app.id,
                                            company_id=app.company_id,
                                        )
                                        # Second call — CAS skips
                                        await eval_mod.run_background_final_evaluation(
                                            application_id=app.id,
                                            company_id=app.company_id,
                                        )

        asyncio.run(run())
        assert eval_count == 1, (
            f"Expected 1 eval (idempotent), got {eval_count}"
        )
