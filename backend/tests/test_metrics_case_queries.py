"""Regression tests for conditional aggregates built with ``sqlalchemy.case``.

These queries used ``func.case(...)``, which SQLAlchemy renders as a call to
a SQL *function* named ``case`` (``case((x = 'hired'), 1)``) instead of a
``CASE WHEN ... THEN ... ELSE ... END`` expression. Every database rejects
that, so the endpoints backed by these queries always failed:

* MetricsRepository.get_source_attribution      (hired count)
* MetricsRepository.get_rubric_deep_analytics   (pass / high / low counts)
* GET /admin/settings/ab-testing/stats          (success count)
"""

from datetime import datetime, timedelta

from backend.database import (
    Application,
    EvaluationResult,
    EvaluationSession,
    User,
)
from backend.models.evaluation.ai import DBTestResult, PromptVariant
from backend.models.evaluation.scoring import RubricScoringDetail
from backend.repository.metrics_repository import MetricsRepository
from backend.routers.admin.settings import get_ab_test_stats


def _app(db, company_id, source, status):
    app = Application(company_id=company_id, source=source, status=status)
    db.add(app)
    db.flush()
    return app


def test_source_attribution_counts_hired_per_source(db_session, test_company):
    cid = test_company.id
    _app(db_session, cid, "LinkedIn", "hired")
    _app(db_session, cid, "LinkedIn", "screening")
    _app(db_session, cid, "LinkedIn", "rejected")
    _app(db_session, cid, None, "hired")  # grouped as "Direct"
    db_session.commit()

    result = MetricsRepository(db_session).get_source_attribution(cid)

    assert result["total_applications"] == 4
    linkedin = result["sources"]["LinkedIn"]
    assert (linkedin["total"], linkedin["hired"]) == (3, 1)
    assert linkedin["conversion_rate"] == 33.3
    assert result["sources"]["Direct"]["hired"] == 1


def test_rubric_deep_analytics_counts_pass_high_low(db_session, test_company):
    cid = test_company.id
    app = _app(db_session, cid, None, "screening")
    es = EvaluationSession(
        application_id=app.id,
        company_id=cid,
        status="completed",
        interview_state="completed",
    )
    db_session.add(es)
    db_session.flush()
    er = EvaluationResult(
        evaluation_session_id=es.id,
        company_id=cid,
        scoring_status="PENDING",
        computed_at=datetime.utcnow(),
    )
    db_session.add(er)
    db_session.flush()
    for score in (80.0, 60.0, 40.0, 20.0):  # 60 counts as passed/high
        db_session.add(
            RubricScoringDetail(
                evaluation_result_id=er.id,
                company_id=cid,
                criterion_name="SQL",
                score=score,
            )
        )
    db_session.commit()

    result = MetricsRepository(db_session).get_rubric_deep_analytics(
        cid, min_occurrences=3
    )

    [skill] = result["skill_pass_rates"]["skills"]
    assert skill["skill"] == "sql"
    assert skill["occurrences"] == 4
    assert skill["pass_rate"] == 50.0

    [kw] = result["keyword_efficacy"]["keywords"]
    assert (kw["high_ratio"], kw["low_ratio"]) == (50.0, 50.0)
    assert result["keyword_efficacy"]["total_results_with_keywords"] == 4


def test_admin_ab_test_stats_counts_successes(db_session, test_company):
    cid = test_company.id
    variant = PromptVariant(
        company_id=cid, prompt_type="interview_question", version="v2"
    )
    db_session.add(variant)
    db_session.flush()
    for status in ("success", "success", "success", "failure"):
        db_session.add(
            DBTestResult(
                company_id=cid,
                variant_id=variant.id,
                version="v2",
                variant="B",
                status=status,
                response_time_ms=100.0,
                executed_at=datetime.utcnow() - timedelta(hours=1),
            )
        )
    admin = User(
        email="ab-stats-admin@example.com",
        name="AB Admin",
        role="admin",
        is_super_admin=True,
    )
    db_session.add(admin)
    db_session.commit()

    result = get_ab_test_stats(days=7, current_user=admin, db=db_session)

    assert result["total_prompt_calls"] == 4
    [row] = result["stats"]
    assert row["prompt_type"] == "interview_question"
    assert (row["total_calls"], row["successful_calls"]) == (4, 3)
    assert row["success_rate"] == 75.0
