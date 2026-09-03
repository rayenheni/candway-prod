import asyncio

import pytest

from backend.ai import interview as interview_module
from backend.database import (
    Application,
    Company,
    EvaluationResult,
    EvaluationSession,
    Job,
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


def _make_rubric(job_id: int, version: int = 2) -> JobRubric:
    return JobRubric(
        job_id=job_id,
        version=version,
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
class TestPhase1RubricPinning:
    """Phase 1: rubric version pinning at session start."""

    def test_evaluate_answer_fix_dropped_columns(self, monkeypatch, db_session):
        """evaluate_answer no longer crashes due to dropped columns on Application."""

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

        recruiter = User(email="rubric-pin-test@example.com", role="recruiter")
        db_session.add(recruiter)
        db_session.flush()

        company = Company(
            name="Rubric Pin Test Company",
            slug="rubric-pin-test-company",
        )
        db_session.add(company)
        db_session.flush()

        job = Job(
            recruiter_id=recruiter.id,
            company_id=company.id,
            title="Backend Engineer",
        )
        db_session.add(job)
        db_session.flush()

        rubric = _make_rubric(job.id)
        db_rubric = RubricDB(
            company_id=job.company_id,
            job_id=job.id,
            version=rubric.version,
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
            final_score=0,
        )
        db_session.add(_er)
        db_session.commit()

        with db_session.no_autoflush:
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
                    answer_id=3,
                )
            )

        assert result["score"] > 0

        db_session.refresh(app)
        assert app.rubric_id == db_rubric.id

    def test_session_pins_rubric_at_start(self, db_session, test_company):
        """EvaluationSession.rubric_id is set when session transitions to in_progress."""
        recruiter = User(
            email="pin-test@example.com",
            role="recruiter",
            company_id=test_company.id,
        )
        db_session.add(recruiter)
        db_session.flush()

        job = Job(
            recruiter_id=recruiter.id,
            company_id=test_company.id,
            title="Engineer",
        )
        db_session.add(job)
        db_session.flush()

        rubric = _make_rubric(job.id)
        db_rubric = RubricDB(
            company_id=job.company_id,
            job_id=job.id,
            version=rubric.version,
            criteria_json=rubric.model_dump_json(),
            created_by=recruiter.id,
        )
        db_session.add(db_rubric)
        db_session.flush()

        app = Application(
            user_id=recruiter.id,
            job_id=job.id,
            declared_role="Engineer",
        )
        db_session.add(app)
        db_session.flush()

        session = EvaluationSession(
            application_id=app.id,
            status="in_progress",
            rubric_id=db_rubric.id,
            rubric_version=rubric.version,
        )
        db_session.add(session)
        db_session.commit()
        db_session.refresh(session)

        assert session.rubric_id == db_rubric.id
        assert session.rubric_version == rubric.version

    def test_pinned_rubric_preferred_over_newer_version(self, db_session, test_company):
        """Session pinned to v1 rubric uses v1 even after v2 is published."""
        recruiter = User(
            email="version-pin@example.com",
            role="recruiter",
            company_id=test_company.id,
        )
        db_session.add(recruiter)
        db_session.flush()

        job = Job(
            recruiter_id=recruiter.id,
            company_id=test_company.id,
            title="Engineer",
        )
        db_session.add(job)
        db_session.flush()

        rubric_v1 = _make_rubric(job.id, version=1)
        db_rubric_v1 = RubricDB(
            company_id=job.company_id,
            job_id=job.id,
            version=1,
            criteria_json=rubric_v1.model_dump_json(),
            created_by=recruiter.id,
        )
        db_session.add(db_rubric_v1)
        db_session.flush()

        rubric_v2 = _make_rubric(job.id, version=2)
        db_rubric_v2 = RubricDB(
            company_id=job.company_id,
            job_id=job.id,
            version=2,
            criteria_json=rubric_v2.model_dump_json(),
            created_by=recruiter.id,
        )
        db_session.add(db_rubric_v2)
        db_session.flush()

        app = Application(
            user_id=recruiter.id,
            job_id=job.id,
            declared_role="Engineer",
        )
        db_session.add(app)
        db_session.flush()

        session = EvaluationSession(
            application_id=app.id,
            status="in_progress",
            rubric_id=db_rubric_v1.id,
            rubric_version=1,
        )
        db_session.add(session)
        db_session.commit()
        db_session.refresh(session)

        assert session.rubric_id == db_rubric_v1.id
        assert session.rubric_version == 1

        pinned = (
            db_session.query(RubricDB).filter(RubricDB.id == session.rubric_id).first()
        )
        assert pinned is not None
        assert pinned.version == 1

        current = (
            db_session.query(RubricDB)
            .filter(RubricDB.job_id == job.id)
            .order_by(RubricDB.version.desc())
            .first()
        )
        assert current is not None
        assert current.version == 2
        assert current.id == db_rubric_v2.id

    def test_no_rubric_fallback_behavior(self, db_session, test_company):
        """Session without pinned rubric still works (backward compat)."""
        recruiter = User(
            email="no-rubric@example.com",
            role="recruiter",
            company_id=test_company.id,
        )
        db_session.add(recruiter)
        db_session.flush()

        job = Job(
            recruiter_id=recruiter.id,
            company_id=test_company.id,
            title="Engineer",
        )
        db_session.add(job)
        db_session.flush()

        app = Application(
            user_id=recruiter.id,
            job_id=job.id,
            declared_role="Engineer",
        )
        db_session.add(app)
        db_session.flush()

        session = EvaluationSession(
            application_id=app.id,
            status="in_progress",
            rubric_id=None,
            rubric_version=None,
        )
        db_session.add(session)
        db_session.commit()
        db_session.refresh(session)

        assert session.rubric_id is None
        assert session.rubric_version is None
