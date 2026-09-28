"""P0-2 regression: the final AI-interview score is the rubric aggregation.

Pipeline under test (real code, only the LLM skill-extraction call mocked):

    answer -> evidence (extracted skills) -> per-turn rubric skill scores
    (RubricScoringDetail, source="interview") -> aggregate_scores against the
    rubric pinned in the interview session snapshot -> canonical final score.

Before the fix the background evaluation called
``aggregate_scores(interview_id=...)`` which raised TypeError; the error was
swallowed and the holistic LLM score was used with a fabricated coverage of
100 and the CV score dropped to 0 (final = LLM * 0.5 + 25).

Canonical formula (scoring_service.CANONICAL_WEIGHTS, rubric present):
    final = cv * 0.25 + rubric * 0.50 + coverage * 0.25
"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest

import backend.routers.ai_interview.evaluation as evaluation_mod
from backend.ai.interview import AnswerEvaluationUnavailable, evaluate_answer
from backend.database import (
    Application,
    EvaluationResult,
    EvaluationSession,
    Job,
    RubricScoringDetail,
)
from backend.models.evaluation.config_snapshot import EvaluationConfigSnapshot
from backend.rubric.rubric_schema import JobRubric
from backend.rubric.scoring_aggregator import aggregate_scores
from backend.scoring_service import ScoringService

CV_SCORE = 80.0


def _skill(name, basic, mid, top):
    return {
        "name": name,
        "weight": 1.0,
        "levels": {
            "mid": [
                {"score_threshold": 40, "keywords": basic, "description": "basic"},
                {"score_threshold": 70, "keywords": mid, "description": "solid"},
                {"score_threshold": 90, "keywords": top, "description": "expert"},
            ]
        },
    }


RUBRIC = {
    "job_id": 1,
    "version": 3,
    "seniority": "mid",
    "categories": [
        {
            "name": "Engineering",
            "weight": 1.0,
            "subcategories": [
                {
                    "name": "Backend",
                    "weight": 1.0,
                    "skills": [
                        _skill("Python", ["python"], ["async"], ["profiling"]),
                        _skill("SQL", ["select"], ["index"], ["query plan"]),
                    ],
                }
            ],
        }
    ],
}
JOB_RUBRIC = JobRubric(**RUBRIC)


def _final(cv, rubric, coverage):
    return round(cv * 0.25 + rubric * 0.50 + coverage * 0.25, 1)


@pytest.fixture
def interview_app(db_session, test_company, test_recruiter):
    """Application with a CV score (session 1) and a pinned-rubric interview
    session (session 2) that the candidate is about to answer in."""
    job = Job(
        recruiter_id=test_recruiter.id,
        company_id=test_company.id,
        title="Backend Engineer",
        description="Python / SQL",
    )
    db_session.add(job)
    db_session.flush()
    app = Application(
        company_id=test_company.id,
        job_id=job.id,
        full_name="Candidate",
        email="cand@example.com",
        status="invited",
    )
    db_session.add(app)
    db_session.commit()

    # Session 1: CV analysis result (the CV score must survive the interview).
    ScoringService.set_cv_only(app, db_session, cv_score=CV_SCORE, computed_by="cv")
    db_session.commit()

    snap = EvaluationConfigSnapshot(
        company_id=test_company.id,
        source_type="job",
        source_id=job.id,
        hash=uuid.uuid4().hex,
        rubric_version=RUBRIC["version"],
        total_questions=5,
        language="en",
        config_json={},
        resolved_rubric_json=RUBRIC,
    )
    db_session.add(snap)
    db_session.flush()
    interview_session = EvaluationSession(
        application_id=app.id,
        company_id=test_company.id,
        status="in_progress",
        interview_state="in_progress",
        evaluation_config_snapshot_id=snap.id,
    )
    db_session.add(interview_session)
    db_session.commit()
    db_session.refresh(app)
    return app


async def _answer(app, answer, focus, extracted):
    """One real interview turn; only the LLM skill extraction is mocked."""
    with patch(
        "backend.ai.interview.call_groq_cascade",
        new_callable=AsyncMock,
        return_value={"extracted_skills": extracted, "feedback": "ok"},
    ):
        return await evaluate_answer(
            question=f"Tell me about your {focus} experience.",
            answer=answer,
            focus=focus,
            history_summary="",
            declared_role="Backend Engineer",
            app=app,
            job_rubric=JOB_RUBRIC,
        )


def _ev(skill, sentence):
    return {"skill_name": skill, "evidence_sentences": [sentence]}


async def _finish(db_session, app, llm=None):
    """Mark the interview finished and run the real background evaluation."""
    es = _interview_session(db_session, app)
    es.status = "pending"
    es.interview_state = "evaluating"
    db_session.commit()
    llm = llm or AsyncMock(return_value={"final_score": 99.0})
    with patch.object(evaluation_mod, "evaluate_complete_interview", llm):
        await evaluation_mod.run_background_final_evaluation(app.id, app.company_id)
    db_session.expire_all()
    return llm


def _interview_session(db_session, app):
    return (
        db_session.query(EvaluationSession)
        .filter(EvaluationSession.application_id == app.id)
        .order_by(EvaluationSession.id.desc())
        .first()
    )


def _interview_result(db_session, app):
    es = _interview_session(db_session, app)
    return (
        db_session.query(EvaluationResult)
        .filter(EvaluationResult.evaluation_session_id == es.id)
        .first()
    )


PY_STRONG = "I use profiling to find hot paths in our Python services."
SQL_STRONG = "I read the query plan before adding any index."
PY_SOLID = "I wrote async Python workers for the ingestion pipeline."


# ── 1. Strong evidence ────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_strong_evidence_on_every_skill(db_session, interview_app):
    r1 = await _answer(interview_app, PY_STRONG, "Python", [_ev("Python", PY_STRONG)])
    r2 = await _answer(interview_app, SQL_STRONG, "SQL", [_ev("SQL", SQL_STRONG)])
    assert r1["skills"] == {"python": 90}
    assert r2["skills"] == {"sql": 90}

    llm = await _finish(db_session, interview_app)

    er = _interview_result(db_session, interview_app)
    assert er.rubric_score == 90.0
    assert er.rubric_coverage_pct == 100.0
    assert er.cv_score == CV_SCORE
    assert er.final_score == _final(CV_SCORE, 90, 100)  # 90.0
    llm.assert_not_called()  # the holistic LLM score is not used with a rubric
    assert _interview_session(db_session, interview_app).status == "completed"


# ── 2 + 6. Partial evidence / missing skills contribute 0 ─────────────────
@pytest.mark.asyncio
async def test_partial_evidence_scores_only_demonstrated_skills(
    db_session, interview_app
):
    r = await _answer(interview_app, PY_SOLID, "Python", [_ev("Python", PY_SOLID)])
    assert r["skills"] == {"python": 70}

    await _finish(db_session, interview_app)

    er = _interview_result(db_session, interview_app)
    # Python 70, SQL not assessed -> 0; equal weights -> 35. Coverage 1/2.
    assert er.rubric_score == 35.0
    assert er.rubric_coverage_pct == 50.0
    assert er.final_score == _final(CV_SCORE, 35, 50)  # 50.0


# ── 3. "I don't know." ─────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_i_dont_know_scores_zero(db_session, interview_app):
    r = await _answer(interview_app, "I don't know.", "Python", [])
    assert r["score"] == 0
    assert r["skills"] == {}

    await _finish(db_session, interview_app)

    er = _interview_result(db_session, interview_app)
    assert er.rubric_score == 0.0
    assert er.rubric_coverage_pct == 0.0
    # Only the (preserved) CV component remains; no fabricated coverage.
    assert er.final_score == _final(CV_SCORE, 0, 0)  # 20.0


# ── 4. Long irrelevant answer ─────────────────────────────────────────────
@pytest.mark.asyncio
async def test_long_irrelevant_answer_scores_zero(db_session, interview_app):
    long_answer = (
        "Last summer I travelled across the south of the country, tried many "
        "local dishes, learned to cook couscous with my grandmother and spent "
        "evenings reading novels about history and old maritime routes. "
    ) * 6  # ~200 words, no rubric evidence
    r = await _answer(
        interview_app,
        long_answer,
        "Python",
        [_ev("Cooking", "learned to cook couscous with my grandmother")],
    )
    assert r["score"] == 0  # no word-count credit when a rubric exists

    await _finish(db_session, interview_app)

    er = _interview_result(db_session, interview_app)
    assert er.rubric_score == 0.0
    assert er.rubric_coverage_pct == 0.0


# ── 5. Off-skill answer ────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_off_skill_answer_gets_no_credit_for_the_asked_skill(
    db_session, interview_app
):
    # Asked about Python; the answer only evidences SQL. The sentence even
    # contains a Python level keyword ("async"): it must NOT be re-attributed
    # to Python (the removed "last resort" force-mapping did exactly that).
    sql_only = "I added an index to the async jobs table after reading the plan."
    r = await _answer(interview_app, sql_only, "Python", [_ev("SQL", sql_only)])
    assert r["score"] == 0
    assert "python" not in r["skills"]

    await _finish(db_session, interview_app)

    er = _interview_result(db_session, interview_app)
    assert er.rubric_score == 0.0
    rows = db_session.query(RubricScoringDetail).filter(
        RubricScoringDetail.source == "interview",
        RubricScoringDetail.score > 0,
    )
    assert rows.count() == 0


def test_aggregator_missing_skills_contribute_zero():
    from backend.rubric.rubric_engine import SkillScoreResult

    def res(name, score):
        return SkillScoreResult(
            skill_name=name,
            skill_id="",
            base_score=score,
            quality="medium",
            quality_multiplier=1.0,
            final_score=score,
            confidence_lower=0,
            confidence_upper=0,
            evidence_sentences=[],
            matched_level="",
            matched_keywords=[],
            missing_competencies=[],
            explanation="",
        )

    summary = aggregate_scores(
        application_id=1,
        rubric=JOB_RUBRIC,
        all_answer_results={1: {"python": res("python", 90)}},
    )
    assert summary.overall_score == 45
    assert summary.overall_coverage_pct == 50
    empty = aggregate_scores(application_id=1, rubric=JOB_RUBRIC, all_answer_results={})
    assert empty.overall_score == 0 and empty.overall_coverage_pct == 0


# ── 7. Evidence persistence failure does not erase the computed score ─────
@pytest.mark.asyncio
async def test_evidence_persistence_failure_keeps_turn_score(interview_app):
    baseline = await _answer(
        interview_app, PY_SOLID, "Python", [_ev("Python", PY_SOLID)]
    )
    with patch(
        "backend.ai.interview._persist_turn_rubric_evidence",
        side_effect=RuntimeError("simulated DB failure"),
    ) as persist:
        r = await _answer(interview_app, PY_SOLID, "Python", [_ev("Python", PY_SOLID)])
    persist.assert_called_once()
    assert r["skills"] == baseline["skills"] == {"python": 70}
    assert r["score"] == baseline["score"] > 0


# ── 8 / 9 / 10. Final score composition ───────────────────────────────────
@pytest.mark.asyncio
async def test_final_uses_rubric_keeps_cv_and_never_fabricates_coverage(
    db_session, interview_app
):
    await _answer(interview_app, PY_STRONG, "Python", [_ev("Python", PY_STRONG)])
    await _finish(db_session, interview_app)

    er = _interview_result(db_session, interview_app)
    assert er.rubric_score == 45.0  # Python 90, SQL 0
    assert er.rubric_coverage_pct == 50.0  # measured, not 100
    assert er.cv_score == CV_SCORE  # carried from the CV session, not 0
    assert er.final_score == _final(CV_SCORE, 45, 50)  # 55.0
    # Old behaviour would have been LLM(99) * 0.5 + 25 = 74.5
    assert er.final_score != 74.5


@pytest.mark.asyncio
async def test_cv_rows_are_not_mixed_into_the_interview_score(
    db_session, interview_app
):
    # A CV-analysis detail row claiming 90 on SQL must not count as
    # interview evidence.
    er = ScoringService.ensure_pending_score(interview_app, db_session)
    db_session.add(
        RubricScoringDetail(
            evaluation_result_id=er.id,
            company_id=er.company_id,
            criterion_name="SQL",
            score=90.0,
            source="cv",
        )
    )
    db_session.commit()
    await _answer(interview_app, PY_STRONG, "Python", [_ev("Python", PY_STRONG)])
    await _finish(db_session, interview_app)

    assert _interview_result(db_session, interview_app).rubric_score == 45.0


def test_set_evaluation_result_without_coverage_does_not_fabricate_100(
    db_session, interview_app
):
    """LLM-fallback path (no measured coverage): coverage stays 0, CV kept."""
    er = ScoringService.set_evaluation_result(
        app=interview_app, db=db_session, eval_score=60.0
    )
    assert er.rubric_coverage_pct == 0.0
    assert er.cv_score == CV_SCORE
    assert er.final_score == _final(CV_SCORE, 60, 0)  # 50.0, not 75.0


# ── No silent fallback / provider failure is distinguishable ─────────────
@pytest.mark.asyncio
async def test_rubric_aggregation_error_fails_evaluation_without_llm_fallback(
    db_session, interview_app
):
    await _answer(interview_app, PY_STRONG, "Python", [_ev("Python", PY_STRONG)])
    with patch.object(
        evaluation_mod,
        "_aggregate_interview_rubric_evidence",
        side_effect=TypeError("contract broken"),
    ):
        llm = await _finish(db_session, interview_app)

    llm.assert_not_called()
    assert _interview_session(db_session, interview_app).status == "failed"
    assert _interview_result(db_session, interview_app).final_score is None


@pytest.mark.asyncio
async def test_provider_failure_is_not_a_fabricated_score(interview_app):
    with patch(
        "backend.ai.interview.call_groq_cascade",
        new_callable=AsyncMock,
        return_value={"error": "provider down"},
    ):
        with pytest.raises(AnswerEvaluationUnavailable):
            await evaluate_answer(
                question="q",
                answer=PY_STRONG,
                focus="Python",
                history_summary="",
                declared_role="Backend Engineer",
                app=interview_app,
                job_rubric=JOB_RUBRIC,
            )
    with patch(
        "backend.ai.interview.call_groq_cascade",
        new_callable=AsyncMock,
        side_effect=ConnectionError("timeout"),
    ):
        with pytest.raises(AnswerEvaluationUnavailable):
            await evaluate_answer(
                question="q",
                answer=PY_STRONG,
                focus="Python",
                history_summary="",
                declared_role="Backend Engineer",
                app=interview_app,
                job_rubric=JOB_RUBRIC,
            )
