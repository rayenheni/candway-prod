import pytest
from sqlalchemy.orm import Session

from backend.database import Application, Company, User, Job, EvaluationSession, EvaluationResult, RubricScoringDetail
from backend.scoring_service import ScoringService, CANONICAL_WEIGHTS
from backend.routers.ai_interview.evaluation import run_background_final_evaluation
from backend.ai.anti_cheat import AntiCheatDetector

@pytest.fixture
def test_company(db_session: Session):
    company = db_session.query(Company).first()
    if not company:
        company = Company(name="Test Co", slug="test-co")
        db_session.add(company)
        db_session.commit()
        db_session.refresh(company)
    return company

@pytest.fixture
def test_application(db_session: Session, test_company: Company):
    app = Application(
        company_id=test_company.id,
        user_id=1,
        status="applied"
    )
    db_session.add(app)
    db_session.commit()
    db_session.refresh(app)
    yield app

    # Cleanup
    sess_ids = [s.id for s in db_session.query(EvaluationSession).filter(EvaluationSession.application_id == app.id).all()]
    if sess_ids:
        db_session.query(RubricScoringDetail).filter(RubricScoringDetail.evaluation_result_id.in_(
            db_session.query(EvaluationResult.id).filter(EvaluationResult.evaluation_session_id.in_(sess_ids))
        )).delete(synchronize_session=False)
        db_session.query(EvaluationResult).filter(EvaluationResult.evaluation_session_id.in_(sess_ids)).delete(synchronize_session=False)
        db_session.query(EvaluationSession).filter(EvaluationSession.application_id == app.id).delete(synchronize_session=False)
    db_session.query(Application).filter(Application.id == app.id).delete(synchronize_session=False)
    db_session.commit()


def test_regression_bug1_cv_plus_interview_composition(db_session: Session, test_application: Application):
    """Test 1: set_evaluation_result preserves cv_score and calculates canonical final_score."""
    ScoringService.set_cv_only(test_application, db_session, cv_score=70.0, computed_by="test_cv")
    db_session.commit()

    er = ScoringService.set_evaluation_result(
        app=test_application,
        db=db_session,
        eval_score=76.7,
        rubric_score=76.7,
        rubric_coverage_pct=100.0,
        scored_by="ai"
    )
    db_session.commit()
    db_session.refresh(er)

    assert er.cv_score == 70.0
    assert er.rubric_score == 76.7
    assert er.final_score != 76.7  # Must NOT be raw interview score

    # Expected canonical score: 70 * 0.25 + 76.7 * 0.50 + 100 * 0.25 = 17.5 + 38.35 + 25.0 = 80.85 -> 80.9
    expected = round(70.0 * 0.25 + 76.7 * 0.50 + 100.0 * 0.25, 1)
    assert er.final_score == expected


def test_regression_bug2_cv_score_preservation_when_override_is_none(db_session: Session, test_application: Application):
    """Test 2: compute_final_score with override_cv_score=None preserves existing cv_score."""
    er1 = ScoringService.set_cv_only(test_application, db_session, cv_score=85.0, computed_by="test_cv")
    db_session.commit()
    assert er1.cv_score == 85.0

    er2 = ScoringService.compute_final_score(
        test_application,
        db_session,
        computed_by="test_rubric_update",
        override_cv_score=None,
        override_rubric_score=60.0,
        override_rubric_coverage_pct=50.0
    )
    db_session.commit()
    db_session.refresh(er2)

    assert er2.cv_score == 85.0
    assert er2.rubric_score == 60.0


def test_regression_bug2_explicit_cv_override(db_session: Session, test_application: Application):
    """Test 3: explicit override_cv_score=70 updates existing cv_score=85."""
    er1 = ScoringService.set_cv_only(test_application, db_session, cv_score=85.0, computed_by="test_cv")
    db_session.commit()
    assert er1.cv_score == 85.0

    er2 = ScoringService.compute_final_score(
        test_application,
        db_session,
        computed_by="test_cv_override",
        override_cv_score=70.0
    )
    db_session.commit()
    db_session.refresh(er2)

    assert er2.cv_score == 70.0


@pytest.mark.asyncio
async def test_regression_bug3_evaluation_failure_no_synthetic_50(db_session: Session, test_application: Application):
    """Test 4: AI evaluation failure marks state failed and preserves scores without synthetic 50."""
    er1 = ScoringService.set_cv_only(test_application, db_session, cv_score=75.0, computed_by="test_cv")
    db_session.commit()

    es = EvaluationSession(
        application_id=test_application.id,
        company_id=test_application.company_id,
        status="pending"
    )
    db_session.add(es)
    db_session.commit()
    db_session.refresh(test_application)

    await run_background_final_evaluation(test_application.id, test_application.company_id)

    db_session.refresh(test_application)
    er = ScoringService.get_canonical_score(test_application.id, db_session)

    assert er.cv_score == 75.0
    assert er.final_score != 50.0


def test_formula_weights_exact_60_0(db_session: Session, test_application: Application):
    """Phase 9 Test A: CV=70, Rubric=80, Coverage=10 -> Expected 60.0."""
    er = ScoringService.compute_final_score(
        test_application,
        db_session,
        override_cv_score=70.0,
        override_rubric_score=80.0,
        override_rubric_coverage_pct=10.0
    )
    db_session.commit()
    # 70*0.25 + 80*0.50 + 10*0.25 = 17.5 + 40.0 + 2.5 = 60.0
    assert er.final_score == 60.0


def test_human_score_independence(db_session: Session, test_application: Application):
    """Phase 9 Test B: DB human_integrity_score=0 vs 100 produces identical final_score."""
    expected = round(70.0 * 0.25 + 80.0 * 0.50 + 50.0 * 0.25, 1)

    er1 = ScoringService.compute_final_score(
        test_application, db_session,
        override_cv_score=70.0,
        override_rubric_score=80.0,
        override_rubric_coverage_pct=50.0,
    )
    db_session.commit()
    assert er1.final_score == expected
    # score_breakdown must not contain a human component
    assert "human" not in (er1.score_breakdown or {})
    assert "human" not in (er1.score_breakdown or {}).get("weights", {})

    # Manually inject different DB values and recompute — must be ignored
    for val in (0.0, 50.0, 100.0):
        er1.human_integrity_score = val
        db_session.add(er1)
        db_session.commit()

        er_n = ScoringService.compute_final_score(
            test_application, db_session,
            override_cv_score=70.0,
            override_rubric_score=80.0,
            override_rubric_coverage_pct=50.0,
        )
        db_session.commit()
        assert er_n.final_score == expected, (
            f"human_integrity_score={val} changed final_score to {er_n.final_score}"
        )


def test_cv_only_formula_56_5(db_session: Session, test_application: Application):
    """Phase 9 Test C: CV=72, Coverage=10 (No rubric) -> 72*0.75 + 10*0.25 = 56.5."""
    er = ScoringService.compute_final_score(
        test_application, db_session, override_cv_score=72.0, override_rubric_score=None,
        override_rubric_coverage_pct=10.0
    )
    db_session.commit()
    assert er.final_score == 56.5


def test_penalty_bounded_and_single_application():
    """Phase 9 Test F & G: Penalty single application & bounding [0, 100]."""
    # 1. Bounded lower
    assert AntiCheatDetector.apply_cheat_penalty(5.0, 20) == 0.0
    # 2. Single application
    res = AntiCheatDetector.apply_cheat_penalty(80.0, 10)
    assert res == 70.0


def test_cv_breakdown_coverage_promoted_to_canonical_result(
    db_session: Session,
    test_application: Application,
):
    """CV breakdown coverage must become canonical EvaluationResult coverage."""
    er = ScoringService.compute_final_score(
        test_application,
        db_session,
        override_cv_score=20.0,
        extra_breakdown={
            "coverage_pct": 20.0,
            "scoring_method": "deterministic_keyword_weighted",
        },
    )
    db_session.commit()
    db_session.refresh(er)

    assert er.cv_score == 20.0
    assert er.rubric_coverage_pct == 20.0

    # No rubric => CV 75% + coverage 25%.
    # 20 * .75 + 20 * .25 = 20.
    assert er.final_score == 20.0
