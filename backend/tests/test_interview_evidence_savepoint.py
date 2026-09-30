"""Regression tests: per-turn rubric evidence persistence must never destroy
the computed turn score, and a persistence failure must not poison the
caller's SQLAlchemy session.

Before the fix, any exception while writing RubricScoringDetail rows inside
evaluate_answer() escaped to the function-wide ``except`` and the real rubric
score was silently replaced by the neutral fallback (50).  The writes now run
in a SAVEPOINT (``_persist_turn_rubric_evidence``) and failures are logged.
"""

import copy
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from backend.ai.interview import _persist_turn_rubric_evidence, evaluate_answer
from backend.database import Application
from backend.models.evaluation.scoring import RubricScoringDetail
from backend.rubric.rubric_schema import JobRubric
from backend.tests.test_ai_interview_quality_fixes import RUBRIC_DICT


def _mid_level_rubric() -> JobRubric:
    # An Application without an evaluation session is scored at the default
    # "mid" seniority, so the rubric needs a "mid" level to produce results.
    data: dict[str, Any] = copy.deepcopy(RUBRIC_DICT)
    data["seniority"] = "mid"
    skill = data["categories"][0]["subcategories"][0]["skills"][0]
    skill["levels"] = {"mid": skill["levels"]["senior"]}
    return JobRubric(**data)


job_rubric = _mid_level_rubric()

ANSWER = "Reduced churn 32% by redesigning onboarding."
FALLBACK_SCORE = 50  # evaluate_answer()'s generic error fallback

MOCK_LLM = {
    "extracted_skills": [
        {"skill_name": "Problem Solving", "evidence_sentences": [ANSWER]},
    ],
    "feedback": "Concise evidence-backed answer.",
}


@pytest.fixture
def app(db_session, test_company, test_user):
    application = Application(
        user_id=test_user.id, company_id=test_company.id, status="applied"
    )
    db_session.add(application)
    db_session.commit()
    db_session.refresh(application)
    return application


async def _evaluate(app):
    with patch(
        "backend.ai.interview.call_groq_cascade",
        new_callable=AsyncMock,
        return_value=MOCK_LLM,
    ):
        return await evaluate_answer(
            question="How do you handle churn?",
            answer=ANSWER,
            focus="Problem Solving",
            history_summary="",
            declared_role="Senior Product Manager",
            app=app,
            job_rubric=job_rubric,
        )


@pytest.mark.asyncio
async def test_evidence_persistence_failure_preserves_real_score(db_session, app):
    baseline = await _evaluate(app)
    # Sanity: the happy path really wrote evidence and produced a rubric score.
    assert db_session.query(RubricScoringDetail).count() >= 1
    assert baseline["score"] != FALLBACK_SCORE

    with patch(
        "backend.scoring_service.ScoringService.ensure_pending_score",
        side_effect=SQLAlchemyError("simulated DB failure"),
    ):
        res = await _evaluate(app)

    assert res["score"] == baseline["score"]
    assert res["skills"] == baseline["skills"]


def test_evidence_savepoint_isolates_flush_failure(db_session, app):
    # A pending change made by the caller before the evidence write.
    app.status = "screening"

    bad_result = SimpleNamespace(final_score=80.0, skill_id=None, explanation=None)
    with pytest.raises(IntegrityError):
        # criterion_name=None violates NOT NULL at flush time.
        _persist_turn_rubric_evidence(
            app,
            "How do you handle churn?",
            "I rebuilt the onboarding funnel and measured churn weekly.",
            {None: bad_result},
        )

    # Without the SAVEPOINT the session would now be in a failed state and
    # this commit would raise PendingRollbackError.
    db_session.commit()
    db_session.expire_all()
    assert db_session.get(Application, app.id).status == "screening"
    assert db_session.query(RubricScoringDetail).count() == 0
