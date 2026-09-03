import asyncio

import pytest

from backend.ai import interview as interview_module
from backend.database import (
    Application,
    EvaluationResult,
    EvaluationSession,
    Job,
    RubricScoringDetail,
    User,
)
from backend.database import (
    Rubric as RubricDB,
)
from backend.rubric.rubric_schema import (
    CategoryDefinition,
    JobRubric,
    LevelDescriptor,
    SkillDefinition,
    SubcategoryDefinition,
)


def _make_rubric(job_id: int) -> JobRubric:
    return JobRubric(
        job_id=job_id,
        version=1,
        categories=[
            CategoryDefinition(
                name="Technical",
                weight=1.0,
                subcategories=[
                    SubcategoryDefinition(
                        name="Backend",
                        weight=1.0,
                        skills=[
                            SkillDefinition(
                                name="Python",
                                weight=1.0,
                                levels={
                                    "junior": [],
                                    "mid": [
                                        LevelDescriptor(
                                            score_threshold=100,
                                            description="Builds production APIs",
                                            keywords=["python", "built", "api"],
                                        )
                                    ],
                                    "senior": [],
                                },
                            )
                        ],
                    )
                ],
            )
        ],
    )


@pytest.mark.usefixtures("db_session")
class TestPhase2RubricGate:
    """Phase 2: rubric gate uses job_rubric presence, not scoring_model."""

    def test_first_answer_rubric_scored_when_rubric_pinned(
        self, monkeypatch, db_session
    ):
        """Turn 1 uses rubric path when rubric is pinned on session."""

        async def fake_call_groq_cascade(*args, **kwargs):
            return {
                "extracted_skills": [
                    {
                        "skill_name": "Python",
                        "evidence_sentences": [
                            "I built a Python API used in production."
                        ],
                    }
                ],
                "feedback": "Evidence extracted.",
            }

        monkeypatch.setattr(
            interview_module, "call_groq_cascade", fake_call_groq_cascade
        )

        recruiter = User(email="phase2-rubric-first@example.com", role="recruiter")
        db_session.add(recruiter)
        db_session.flush()

        job = Job(recruiter_id=recruiter.id, company_id=test_company.id, title="Backend Engineer")
        db_session.add(job)
        db_session.flush()

        rubric = _make_rubric(job.id)
        db_rubric = RubricDB(
            company_id=job.company_id,
            job_id=job.id,
            version=rubric.version,
            is_active=1,
            criteria_json=rubric.model_dump_json(),
            created_by=recruiter.id,
        )
        db_session.add(db_rubric)
        db_session.flush()

        app = Application(
            user_id=recruiter.id,
            job_id=job.id,
            declared_role="Backend Engineer",
        )
        db_session.add(app)
        db_session.flush()

        # Pin rubric on session (Phase 1 behavior)
        session = EvaluationSession(
            application_id=app.id,
            interview_state="in_progress",
            rubric_id=db_rubric.id,
            rubric_version=1,
        )
        db_session.add(session)
        db_session.flush()

        _er = EvaluationResult(
            evaluation_session_id=session.id,
            scoring_status="SCORED",
            scoring_model="legacy",
            rubric_seniority="mid",
            rubric_version=1,
            final_score=0,
        )
        db_session.add(_er)
        db_session.commit()

        result = asyncio.run(
            interview_module.evaluate_answer(
                question="Tell me about Python.",
                answer="I built a Python API used in production.",
                focus="Python",
                history_summary="",
                declared_role="Backend Engineer",
                app=app,
                job_rubric=rubric,
                job_rubric_db_id=db_rubric.id,
                answer_id=1,
            )
        )

        assert result["score"] > 0, f"Expected rubric score > 0, got {result['score']}"

        rows = (
            db_session.query(RubricScoringDetail).filter_by(application_id=app.id).all()
        )
        assert len(rows) == 1, "Expected 1 RubricScoringDetail row for turn 1"
        assert rows[0].answer_id == 1
        assert rows[0].rubric_id == db_rubric.id

        db_session.refresh(_er)
        assert _er.scoring_model == "rubric", (
            f"scoring_model should be 'rubric' after rubric evaluation, got '{_er.scoring_model}'"
        )

    def test_first_answer_heuristic_when_no_rubric(self, monkeypatch, db_session):
        """Turn 1 falls back to heuristic when no rubric for job."""

        async def fake_call_groq_cascade(*args, **kwargs):
            return {
                "extracted_skills": [
                    {
                        "skill_name": "Python",
                        "evidence_sentences": [
                            "I built a Python API used in production."
                        ],
                    }
                ],
                "feedback": "No rubric available.",
            }

        monkeypatch.setattr(
            interview_module, "call_groq_cascade", fake_call_groq_cascade
        )

        user = User(email="phase2-no-rubric@example.com", role="candidate")
        db_session.add(user)
        db_session.flush()

        job = Job(recruiter_id=user.id, company_id=test_company.id, title="Backend Engineer")
        db_session.add(job)
        db_session.flush()

        app = Application(
            user_id=user.id,
            job_id=job.id,
            declared_role="Backend Engineer",
        )
        db_session.add(app)
        db_session.flush()

        _es = EvaluationSession(application_id=app.id, status="completed")
        db_session.add(_es)
        db_session.flush()
        _er = EvaluationResult(
            evaluation_session_id=_es.id,
            scoring_status="SCORED",
            scoring_model="legacy",
            final_score=0,
        )
        db_session.add(_er)
        db_session.commit()

        result = asyncio.run(
            interview_module.evaluate_answer(
                question="Tell me about Python.",
                answer="I built a Python API used in production.",
                focus="Python",
                history_summary="",
                declared_role="Backend Engineer",
                app=app,
                job_rubric=None,
                job_rubric_db_id=None,
                answer_id=1,
            )
        )

        assert "score" in result

        rows = (
            db_session.query(RubricScoringDetail).filter_by(application_id=app.id).all()
        )
        assert len(rows) == 0, "Expected no RubricScoringDetail when no rubric"

    def test_rubric_scoring_model_written_after_evaluation(
        self, monkeypatch, db_session
    ):
        """scoring_model on EvaluationResult is 'rubric' after rubric scoring."""

        async def fake_call_groq_cascade(*args, **kwargs):
            return {
                "extracted_skills": [
                    {
                        "skill_name": "Python",
                        "evidence_sentences": [
                            "I built a Python API used in production."
                        ],
                    }
                ],
                "feedback": "Evidence extracted.",
            }

        monkeypatch.setattr(
            interview_module, "call_groq_cascade", fake_call_groq_cascade
        )

        recruiter = User(email="phase2-model-write@example.com", role="recruiter")
        db_session.add(recruiter)
        db_session.flush()

        job = Job(recruiter_id=recruiter.id, company_id=test_company.id, title="Backend Engineer")
        db_session.add(job)
        db_session.flush()

        rubric = _make_rubric(job.id)
        db_rubric = RubricDB(
            company_id=job.company_id,
            job_id=job.id,
            version=rubric.version,
            is_active=1,
            criteria_json=rubric.model_dump_json(),
            created_by=recruiter.id,
        )
        db_session.add(db_rubric)
        db_session.flush()

        app = Application(
            user_id=recruiter.id,
            job_id=job.id,
            declared_role="Backend Engineer",
        )
        db_session.add(app)
        db_session.flush()

        _es = EvaluationSession(application_id=app.id, status="completed")
        db_session.add(_es)
        db_session.flush()
        _er = EvaluationResult(
            evaluation_session_id=_es.id,
            scoring_status="SCORED",
            scoring_model="legacy",
            rubric_seniority="mid",
            final_score=0,
        )
        db_session.add(_er)
        db_session.commit()

        asyncio.run(
            interview_module.evaluate_answer(
                question="Tell me about Python.",
                answer="I built a Python API used in production.",
                focus="Python",
                history_summary="",
                declared_role="Backend Engineer",
                app=app,
                job_rubric=rubric,
                job_rubric_db_id=db_rubric.id,
                answer_id=1,
            )
        )

        db_session.refresh(_er)
        assert _er.scoring_model == "rubric", (
            f"Expected scoring_model='rubric', got '{_er.scoring_model}'"
        )

    def test_no_scoring_result_when_no_rubric(self, monkeypatch, db_session):
        """No RubricScoringDetail rows written when job_rubric is None."""

        async def fake_call_groq_cascade(*args, **kwargs):
            return {
                "extracted_skills": [
                    {
                        "skill_name": "Python",
                        "evidence_sentences": [
                            "I built a Python API used in production."
                        ],
                    }
                ],
                "feedback": "Generic analysis.",
            }

        monkeypatch.setattr(
            interview_module, "call_groq_cascade", fake_call_groq_cascade
        )

        user = User(email="phase2-no-result@example.com", role="candidate")
        db_session.add(user)
        db_session.flush()

        job = Job(recruiter_id=user.id, company_id=test_company.id, title="Backend Engineer")
        db_session.add(job)
        db_session.flush()

        app = Application(
            user_id=user.id,
            job_id=job.id,
            declared_role="Backend Engineer",
        )
        db_session.add(app)
        db_session.flush()

        _es = EvaluationSession(application_id=app.id, status="completed")
        db_session.add(_es)
        db_session.flush()
        _er = EvaluationResult(
            evaluation_session_id=_es.id,
            scoring_status="SCORED",
            scoring_model="legacy",
            final_score=0,
        )
        db_session.add(_er)
        db_session.commit()

        asyncio.run(
            interview_module.evaluate_answer(
                question="Tell me about Python.",
                answer="I built a Python API used in production.",
                focus="Python",
                history_summary="",
                declared_role="Backend Engineer",
                app=app,
                job_rubric=None,
                job_rubric_db_id=None,
                answer_id=1,
            )
        )

        rows = (
            db_session.query(RubricScoringDetail).filter_by(application_id=app.id).all()
        )
        assert len(rows) == 0, f"Expected 0 RubricScoringDetail, got {len(rows)}"
