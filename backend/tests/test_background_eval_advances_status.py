"""
Regression test — background final evaluation advances the application stage.

After a candidate completes an AI interview, the background evaluation must
advance ``Application.status`` from ``invited``/``interviewing``/``pending``/
``applied`` to ``screening`` (mirroring the manual ``evaluate-final`` endpoint)
and mark the app ``interview_state=completed`` / ``final_eval_done=True``.

Without this the recruiter pipeline kept every completed interview at
"Invited", under-counting the funnel.
"""

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

from backend.database import Application, EvaluationSession


class TestBackgroundEvalAdvancesStatus:
    def _make_app(self, db_session, test_user, test_company, status="invited"):
        app = Application(
            user_id=test_user.id,
            company_id=test_company.id,
            full_name=test_user.name,
            email=test_user.email,
            status=status,
            language="English",
            created_at=datetime.now(UTC),
        )
        db_session.add(app)
        db_session.commit()
        db_session.refresh(app)
        return app

    def _make_session(self, db_session, app, state="pending"):
        es = EvaluationSession(
            application_id=app.id,
            company_id=app.company_id,
            status=state,
            interview_state="in_progress",
            interview_progress=5,
            interview_time_left=1500,
            interview_log=[],
            interview_questions=[],
            created_at=datetime.now(UTC),
        )
        db_session.add(es)
        db_session.commit()
        return es

    def _run_bg_eval(self, app):
        from backend.routers.ai_interview import evaluation as eval_mod

        holder = {}

        fake_result = {
            "final_score": 71.0,
            "skill_metrics": {"Technical": 71.0},
            "strengths": [],
            "weaknesses": [],
            "action_plan": None,
            "explainability": None,
            "detailed_feedback": "ok",
        }

        async def run():
            with patch.object(
                eval_mod, "evaluate_complete_interview", new=AsyncMock(return_value=fake_result)
            ):
                with patch(
                    "backend.ai.validation.AIOutputValidator",
                    autospec=True,
                ) as validator_cls:
                    validator = validator_cls.return_value
                    # Validation success must return the validated payload.
                    # None is interpreted by production code as validation failure.
                    validator.validate.return_value = fake_result
                    with patch.object(
                        eval_mod.ScoringService, "set_evaluation_result"
                    ) as set_er:
                        holder["set_er"] = set_er
                        with patch.object(eval_mod, "sync_cv_document") as sync_cv:
                            with patch(
                                "backend.email_service.email_service.send_interview_complete_email"
                            ):
                                with patch(
                                    "backend.email_service.email_service.send_candidate_completion_email"
                                ):
                                    await eval_mod.run_background_final_evaluation(
                                        application_id=app.id,
                                        company_id=app.company_id,
                                    )

        asyncio.run(run())
        return holder["set_er"]

    def test_invited_app_advances_to_screening(
        self, db_session, test_user, test_company
    ):
        app = self._make_app(db_session, test_user, test_company, status="invited")
        self._make_session(db_session, app)

        set_er = self._run_bg_eval(app)

        db_session.refresh(app)
        assert app.status == "screening"
        assert app.interview_state == "completed"
        assert app.evaluation_source == "auto"
        assert set_er.called is True

    def test_interviewing_app_advances_to_screening(
        self, db_session, test_user, test_company
    ):
        app = self._make_app(db_session, test_user, test_company, status="interviewing")
        self._make_session(db_session, app)

        self._run_bg_eval(app)

        db_session.refresh(app)
        assert app.status == "screening"

    def test_hired_app_status_is_preserved(
        self, db_session, test_user, test_company
    ):
        app = self._make_app(db_session, test_user, test_company, status="hired")
        self._make_session(db_session, app)

        self._run_bg_eval(app)

        db_session.refresh(app)
        assert app.status == "hired"