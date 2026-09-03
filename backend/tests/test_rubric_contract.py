import asyncio

from backend.ai import interview as interview_module
from backend.database import (
    Application,
    Company,
    CompanyMember,
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


def _sample_rubric(job_id: int) -> JobRubric:
    return JobRubric(
        job_id=job_id,
        version=2,
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


def test_evaluate_answer_persists_db_rubric_id_and_turn(monkeypatch, db_session):
    async def fake_call_groq_cascade(*args, **kwargs):
        return {
            "extracted_skills": [
                {
                    "skill_name": "Python",
                    "evidence_sentences": ["I built a Python API used in production."],
                }
            ],
            "feedback": "Evidence extracted.",
        }

    monkeypatch.setattr(interview_module, "call_groq_cascade", fake_call_groq_cascade)

    company = Company(
        name="Rubric Test Company",
        slug="rubric-test-company",
    )
    db_session.add(company)
    db_session.flush()

    recruiter = User(email="rubric-owner@example.com", role="recruiter")
    db_session.add(recruiter)
    db_session.flush()

    member = CompanyMember(
        company_id=company.id,
        user_id=recruiter.id,
        role="admin",
        is_active=True,
    )
    db_session.add(member)
    db_session.flush()

    job = Job(
        recruiter_id=recruiter.id,
        company_id=company.id,
        title="Backend Engineer",
    )
    db_session.add(job)
    db_session.flush()

    rubric = _sample_rubric(job.id)
    db_rubric = RubricDB(
        job_id=job.id,
        company_id=company.id,
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
        company_id=company.id,
        declared_role="Backend Engineer",
    )
    db_session.add(app)
    db_session.flush()

    _es = EvaluationSession(
        application_id=app.id,
        company_id=company.id,
        rubric_id=db_rubric.id,
        status="completed",
    )
    db_session.add(_es)
    db_session.flush()
    _er = EvaluationResult(
        evaluation_session_id=_es.id,
        company_id=company.id,
        rubric_id=db_rubric.id,
        scoring_status="SCORED",
        scoring_model="rubric",
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
            answer_id=3,
        )
    )

    assert result["score"] > 0
    rows = (
        db_session.query(RubricScoringDetail)
        .join(
            EvaluationResult,
            RubricScoringDetail.evaluation_result_id == EvaluationResult.id,
        )
        .join(
            EvaluationSession,
            EvaluationResult.evaluation_session_id == EvaluationSession.id,
        )
        .filter(EvaluationSession.application_id == app.id)
        .all()
    )
    assert len(rows) >= 1
