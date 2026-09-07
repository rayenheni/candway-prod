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


@pytest.fixture
def free_plan_setup(client, auth_headers, db_session, monkeypatch, cv_upload_setup):
    """Free-plan shape: 2 CV uploads and 1 AI analysis per month."""
    user, profile, plan = cv_upload_setup
    plan.candidate_cv_uploads_limit = 2
    plan.candidate_ai_analyses_limit = 1
    db_session.commit()
    return user, profile, plan


def test_second_upload_succeeds_when_ai_limit_exhausted(
    client, auth_headers, db_session, monkeypatch, free_plan_setup
):
    """CV #2 must NOT fail merely because the AI-analysis allowance is used up."""
    user, profile, plan = free_plan_setup

    async def fake_analyze_cv(text, role):
        return {
            "score": 70,
            "detected_role": "Python Developer",
            "verdict": "qualified",
        }

    import backend.ai as backend_ai

    monkeypatch.setattr(backend_ai, "analyze_cv", fake_analyze_cv)

    first = _do_upload(client, auth_headers)
    assert first.status_code == 200
    first_payload = first.json()
    assert first_payload["success"] is True
    assert first_payload["status"] == "analyzed"

    db_session.refresh(profile)
    assert profile.candidate_cv_uploads_this_month == 1
    assert profile.candidate_ai_analyses_this_month == 1

    second = _do_upload(client, auth_headers)
    assert second.status_code == 200
    second_payload = second.json()
    assert second_payload["success"] is True
    assert second_payload["analysis_status"] == "quota_blocked"
    assert second_payload["status"] == "analyzing"
    assert second_payload["application_id"] == first_payload["application_id"] + 1
    assert second_payload["cv_document_id"] is not None

    db_session.refresh(profile)
    assert profile.candidate_cv_uploads_this_month == 2
    assert profile.candidate_ai_analyses_this_month == 1

    from backend.database import Application

    apps = (
        db_session.query(Application)
        .filter(Application.user_id == user.id)
        .order_by(Application.id)
        .all()
    )
    assert len(apps) == 2
    assert apps[0].status == "analyzed"
    assert apps[0].cv_document.analysis_json is not None
    assert apps[1].status == "analyzing"
    assert apps[1].cv_document.analysis_json is None


def test_third_upload_blocked_by_cv_quota(
    client, auth_headers, db_session, monkeypatch, free_plan_setup
):
    """With cv=2/ai=1, the third upload is blocked by the CV quota, not the AI one."""
    user, profile, plan = free_plan_setup

    async def fake_analyze_cv(text, role):
        return {
            "score": 70,
            "detected_role": "Python Developer",
            "verdict": "qualified",
        }

    import backend.ai as backend_ai

    monkeypatch.setattr(backend_ai, "analyze_cv", fake_analyze_cv)

    first = _do_upload(client, auth_headers)
    assert first.status_code == 200

    second = _do_upload(client, auth_headers)
    assert second.status_code == 200
    assert second.json()["analysis_status"] == "quota_blocked"

    third = _do_upload(client, auth_headers)
    assert third.status_code == 403
    assert "CV upload limit" in third.json()["detail"]

    db_session.refresh(profile)
    assert profile.candidate_cv_uploads_this_month == 2
    assert profile.candidate_ai_analyses_this_month == 1


def test_cv_upload_never_blocked_by_ai_with_unlimited_ai_plan(
    client, auth_headers, db_session, monkeypatch, cv_upload_setup
):
    """candidate_ai_analyses_limit=-1 never blocks and never increments the AI counter."""
    user, profile, plan = cv_upload_setup
    plan.candidate_cv_uploads_limit = -1
    plan.candidate_ai_analyses_limit = -1
    db_session.commit()

    async def fake_analyze_cv(text, role):
        return {"score": 70, "detected_role": "Python Developer"}

    import backend.ai as backend_ai

    monkeypatch.setattr(backend_ai, "analyze_cv", fake_analyze_cv)

    for _ in range(3):
        resp = _do_upload(client, auth_headers)
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        assert resp.json().get("analysis_status") is None

    db_session.refresh(profile)
    assert profile.candidate_cv_uploads_this_month == 3
    assert profile.candidate_ai_analyses_this_month == 0


def test_upload_cv_without_auth_returns_401(
    client, db_session, monkeypatch, cv_upload_setup
):
    """Auth/CSRF untouched: an unauthenticated upload still returns 401."""
    resp = client.post(
        "/api/v1/candidate/upload-cv",
        files={"file": ("resume.txt", b"fake CV content", "text/plain")},
        data={"declared_role": "Python Developer"},
    )
    assert resp.status_code == 401
