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


def _do_upload(client, auth_headers, declared_role="Python Developer"):
    return client.post(
        "/api/v1/candidate/upload-cv",
        headers=auth_headers,
        files={"file": ("resume.txt", b"fake CV content", "text/plain")},
        data={"declared_role": declared_role},
    )


@pytest.fixture
def cv_upload_setup(db_session, test_user, monkeypatch):
    """Candidate + plan + deterministic offline AI/file layers for upload-cv."""
    from backend.candidate_subscription_service import CandidateSubscriptionService
    from backend.models.evaluation.profile import CandidateProfile
    from backend.models.foundation.subscription import SubscriptionPlan

    profile = (
        db_session.query(CandidateProfile)
        .filter(CandidateProfile.user_id == test_user.id)
        .first()
    )
    if profile is None:
        profile = CandidateProfile(
            user_id=test_user.id,
            candidate_cv_uploads_this_month=0,
            candidate_ai_analyses_this_month=0,
        )
        db_session.add(profile)
    else:
        profile.candidate_cv_uploads_this_month = 0
        profile.candidate_ai_analyses_this_month = 0

    test_plan = SubscriptionPlan(
        name="CV Upload Quota Test",
        slug="cv-upload-quota-test",
        target_audience="candidate",
        candidate_cv_uploads_limit=1,
        candidate_ai_analyses_limit=10,
        is_active=True,
    )
    db_session.add(test_plan)
    db_session.flush()
    test_user.current_plan_id = test_plan.id
    db_session.commit()

    monkeypatch.setattr(
        CandidateSubscriptionService,
        "reset_usage_if_needed",
        staticmethod(lambda user, db: None),
    )

    import backend.ai as backend_ai
    import backend.cv_service as cv_service
    import backend.file_security as file_security

    monkeypatch.setattr(
        file_security,
        "scan_for_malware",
        lambda content, filename: (True, "clean"),
    )
    monkeypatch.setattr(
        cv_service,
        "extract_text_from_file",
        lambda content, filename: (
            "Experienced Python developer with FastAPI and SQLAlchemy. "
            "Built production APIs and automated tests."
        ),
    )

    return test_user, profile, test_plan


def test_cv_upload_exhausted_returns_403(
    client, auth_headers, db_session, monkeypatch, cv_upload_setup
):
    user, profile, plan = cv_upload_setup

    async def fake_analyze_cv(text, role):
        return {"score": 70, "detected_role": "Python Developer"}

    import backend.ai as backend_ai

    monkeypatch.setattr(backend_ai, "analyze_cv", fake_analyze_cv)

    profile.candidate_cv_uploads_this_month = plan.candidate_cv_uploads_limit
    db_session.commit()

    resp = _do_upload(client, auth_headers)
    assert resp.status_code == 403

    db_session.refresh(profile)
    assert profile.candidate_cv_uploads_this_month == plan.candidate_cv_uploads_limit

    from backend.database import Application

    apps = (
        db_session.query(Application)
        .filter(Application.user_id == user.id)
        .all()
    )
    assert len(apps) == 0


def test_cv_upload_success_consumes_exactly_one(
    client, auth_headers, db_session, monkeypatch, cv_upload_setup
):
    user, profile, plan = cv_upload_setup

    async def fake_analyze_cv(text, role):
        return {
            "score": 70,
            "detected_role": "Python Developer",
            "verdict": "qualified",
        }

    import backend.ai as backend_ai

    monkeypatch.setattr(backend_ai, "analyze_cv", fake_analyze_cv)

    resp = _do_upload(client, auth_headers)
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["success"] is True
    assert payload["status"] == "analyzed"

    db_session.refresh(profile)
    assert profile.candidate_cv_uploads_this_month == 1
    assert profile.candidate_ai_analyses_this_month == 1


def test_cv_upload_ai_none_failure_does_not_consume_quota(
    client, auth_headers, db_session, monkeypatch, cv_upload_setup
):
    user, profile, plan = cv_upload_setup

    async def fake_analyze_cv(text, role):
        return None

    import backend.ai as backend_ai

    monkeypatch.setattr(backend_ai, "analyze_cv", fake_analyze_cv)

    resp = _do_upload(client, auth_headers)
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["success"] is False
    assert payload["status"] == "failed"

    db_session.refresh(profile)
    assert profile.candidate_cv_uploads_this_month == 0
    assert profile.candidate_ai_analyses_this_month == 0


def test_cv_upload_ai_error_dict_failure_does_not_consume_quota(
    client, auth_headers, db_session, monkeypatch, cv_upload_setup
):
    user, profile, plan = cv_upload_setup

    async def fake_analyze_cv(text, role):
        return {
            "error": "CV analysis failed",
            "score": 0,
            "verdict": "Error",
        }

    import backend.ai as backend_ai

    monkeypatch.setattr(backend_ai, "analyze_cv", fake_analyze_cv)

    resp = _do_upload(client, auth_headers)
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["success"] is False
    assert payload["status"] == "failed"

    db_session.refresh(profile)
    assert profile.candidate_cv_uploads_this_month == 0
    assert profile.candidate_ai_analyses_this_month == 0


def test_cv_upload_unlimited_plan_records_usage_never_blocks(
    client, auth_headers, db_session, monkeypatch, cv_upload_setup
):
    user, profile, plan = cv_upload_setup

    async def fake_analyze_cv(text, role):
        return {"score": 70, "detected_role": "Python Developer"}

    import backend.ai as backend_ai

    monkeypatch.setattr(backend_ai, "analyze_cv", fake_analyze_cv)

    plan.candidate_cv_uploads_limit = -1
    db_session.commit()
    profile.candidate_cv_uploads_this_month = 999
    db_session.commit()

    resp = _do_upload(client, auth_headers)
    assert resp.status_code == 200
    assert resp.json()["success"] is True

    db_session.refresh(profile)
    assert profile.candidate_cv_uploads_this_month == 1000


def test_cv_upload_cannot_exceed_limit_and_does_not_overcount(
    client, auth_headers, db_session, monkeypatch, cv_upload_setup
):
    user, profile, plan = cv_upload_setup

    async def fake_analyze_cv(text, role):
        return {"score": 70, "detected_role": "Python Developer"}

    import backend.ai as backend_ai

    monkeypatch.setattr(backend_ai, "analyze_cv", fake_analyze_cv)

    first = _do_upload(client, auth_headers)
    assert first.status_code == 200

    second = _do_upload(client, auth_headers)
    assert second.status_code == 403

    db_session.refresh(profile)
    assert profile.candidate_cv_uploads_this_month == 1

    from backend.database import Application

    apps = (
        db_session.query(Application)
        .filter(Application.user_id == user.id)
        .all()
    )
    assert len(apps) == 1


def test_cv_upload_missing_profile_is_seeded(
    client, auth_headers, db_session, monkeypatch, cv_upload_setup
):
    user, profile, plan = cv_upload_setup

    async def fake_analyze_cv(text, role):
        return {"score": 70, "detected_role": "Python Developer"}

    import backend.ai as backend_ai

    monkeypatch.setattr(backend_ai, "analyze_cv", fake_analyze_cv)

    db_session.delete(profile)
    db_session.commit()

    resp = _do_upload(client, auth_headers)
    assert resp.status_code == 200
    assert resp.json()["success"] is True

    fresh = (
        db_session.query(CandidateProfile)
        .filter(CandidateProfile.user_id == user.id)
        .one()
    )
    assert fresh.candidate_cv_uploads_this_month == 1
