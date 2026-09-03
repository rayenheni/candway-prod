import pytest
from fastapi import HTTPException

from backend.candidate_subscription_service import CandidateSubscriptionService
from backend.models.evaluation.profile import CandidateProfile
from backend.models.foundation.subscription import SubscriptionPlan


@pytest.fixture
def candidate_with_plan(db_session, test_user):
    profile = db_session.query(CandidateProfile).filter(
        CandidateProfile.user_id == test_user.id
    ).first()

    if profile is None:
        profile = CandidateProfile(
            user_id=test_user.id,
            candidate_ai_analyses_this_month=0,
        )
        db_session.add(profile)
        db_session.commit()

    plan = SubscriptionPlan(
        name="Candidate Test",
        slug="candidate-test",
        target_audience="candidate",
        candidate_ai_analyses_limit=3,
    )
    db_session.add(plan)
    db_session.commit()

    return test_user, profile, plan


def test_ai_analysis_reservation_increments_atomically(
    db_session, candidate_with_plan, monkeypatch
):
    user, profile, plan = candidate_with_plan

    monkeypatch.setattr(
        CandidateSubscriptionService,
        "get_candidate_plan",
        staticmethod(lambda user, db: plan),
    )
    monkeypatch.setattr(
        CandidateSubscriptionService,
        "reset_usage_if_needed",
        staticmethod(lambda user, db: None),
    )

    CandidateSubscriptionService.check_ai_analysis_limit(user, db_session)

    db_session.refresh(profile)
    assert profile.candidate_ai_analyses_this_month == 1


def test_ai_analysis_limit_blocks_at_limit(
    db_session, candidate_with_plan, monkeypatch
):
    user, profile, plan = candidate_with_plan

    profile.candidate_ai_analyses_this_month = 3
    db_session.commit()

    monkeypatch.setattr(
        CandidateSubscriptionService,
        "get_candidate_plan",
        staticmethod(lambda user, db: plan),
    )
    monkeypatch.setattr(
        CandidateSubscriptionService,
        "reset_usage_if_needed",
        staticmethod(lambda user, db: None),
    )

    with pytest.raises(HTTPException) as exc:
        CandidateSubscriptionService.check_ai_analysis_limit(user, db_session)

    assert exc.value.status_code == 403

    db_session.refresh(profile)
    assert profile.candidate_ai_analyses_this_month == 3


def test_ai_analysis_rollback_returns_one_reservation(
    db_session, candidate_with_plan, monkeypatch
):
    user, profile, plan = candidate_with_plan

    profile.candidate_ai_analyses_this_month = 1
    db_session.commit()

    CandidateSubscriptionService.rollback_ai_analysis_limit(
        user, db_session
    )

    db_session.refresh(profile)
    assert profile.candidate_ai_analyses_this_month == 0
