"""Public-job apply: company-funded recruiter-side CV analysis (flow="apply").

The redesigned upload/apply pipeline:

  - ``flow="apply"`` uploads consume ONLY the candidate CV upload quota; they
    never consume the candidate AI-analysis quota and never run the generic
    upload-time ``analyze_cv()``. The CV is persisted on a MANUAL Application
    (required by the CvDocument FK) and the response returns
    ``analysis_status="pending_apply"``.
  - The recruiter-side ``run_cv_analysis()`` for accepted JOB applications is
    funded by the hiring company through an atomic, idempotent credit-charge
    inside ``apply_to_job`` (idempotency key ``consume:cv_analysis:{app_id}``).
    Insufficient company credits -> 409, no JOB application committed, no
    charge, no analysis.
  - Refunds only on a genuinely failed analysis (error payload or raised
    exception), never after a successful analysis.
  - ``flow="review"`` (the default) keeps the legacy candidate quota +
    generic-analysis behavior — covered by test_candidate_ai_quota.py.

Fixtures here avoid the pre-existing broken ``seeded_application`` pattern
(the EvaluationResult-without-company_id issue); company_id is set explicitly
and a deterministic billing owner funds the company wallet.
"""

import pytest
from sqlalchemy import event
from sqlalchemy.orm import Session

import backend.ai as backend_ai
import backend.cv_service as cv_service
import backend.file_security as file_security
from backend.credit_service import (
    consume_credits_in_transaction,
    get_user_credit_balance,
    grant_credits,
    record_usage_event_in_transaction,
)
from backend.database import (
    Application,
    CompanyMember,
    CreditTransaction,
    CreditWallet,
    Job,
    UsageEvent,
    User,
)
from backend.dependencies import pwd_context
from backend.models.ats.types import ApplicationType
from backend.models.evaluation.profile import CandidateProfile
from backend.models.foundation.subscription import SubscriptionPlan
from backend.tests.conftest import TestingSessionLocal, _fetch_csrf_token

CV_TEXT = (
    "Experienced Python developer with FastAPI and SQLAlchemy. "
    "Built production APIs, background workers, and automated tests. "
    "Led technical interviews for backend roles."
)


@pytest.fixture
def flow_setup(db_session, test_user, monkeypatch):
    """High-limit candidate plan + deterministic offline file/AI layers."""
    from backend.candidate_subscription_service import CandidateSubscriptionService

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
    profile.phone = test_user.phone
    profile.name = test_user.name

    plan = SubscriptionPlan(
        name="Apply Flow Test",
        slug="apply-flow-test",
        target_audience="candidate",
        candidate_cv_uploads_limit=10,
        candidate_ai_analyses_limit=10,
        is_active=True,
    )
    db_session.add(plan)
    db_session.flush()
    test_user.current_plan_id = plan.id
    db_session.commit()

    monkeypatch.setattr(
        CandidateSubscriptionService,
        "reset_usage_if_needed",
        staticmethod(lambda user, db: None),
    )
    monkeypatch.setattr(
        file_security, "scan_for_malware", lambda content, filename: (True, "clean")
    )
    monkeypatch.setattr(
        cv_service,
        "extract_text_from_file",
        lambda content, filename: CV_TEXT,
    )
    return test_user, profile, plan


@pytest.fixture
def test_job(db_session, test_recruiter, test_company):
    job = Job(
        recruiter_id=test_recruiter.id,
        company_id=test_company.id,
        title="Senior Backend Engineer",
        company_name="Test Company",
        location="Tunis",
        salary_range="4000-6000 TND",
        type="Full-time",
        description="Backend API role using Python/FastAPI/PostgreSQL",
        required_skills="Python,FastAPI,PostgreSQL",
        is_active=True,
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)
    return job


def _upload_apply(client, auth_headers, declared_role="Senior Backend Engineer"):
    return client.post(
        "/api/v1/candidate/upload-cv",
        headers=auth_headers,
        files={"file": ("resume.txt", b"fake CV content", "text/plain")},
        data={"declared_role": declared_role, "flow": "apply"},
    )


def _apply_with_doc(client, auth_headers, job_id, cv_document_id):
    return client.post(
        f"/api/v1/candidate/jobs/{job_id}/apply",
        headers=auth_headers,
        json={"cv_document_id": cv_document_id},
    )


def _make_owner(db_session, company_id, balance):
    """Create a sole billing owner with exactly ``balance`` credits."""
    owner = User(
        email="sole-owner@test.local",
        name="Sole Owner",
        hashed_password=pwd_context.hash("ownerpass123"),
        role="company",
        email_verified=True,
    )
    db_session.add(owner)
    db_session.flush()
    db_session.add(
        CompanyMember(
            company_id=company_id,
            user_id=owner.id,
            role="owner",
            is_active=True,
        )
    )
    db_session.commit()
    if balance:
        grant_credits(
            db_session,
            owner,
            balance,
            provider="test",
            provider_ref=f"sole-owner-{balance}",
        )
    return owner


def _make_candidate_and_login(client, db_session, email):
    user = User(
        email=email,
        name="Second Candidate",
        phone="+15555550200",
        hashed_password=pwd_context.hash("candidate2pass123"),
        role="candidate",
        email_verified=True,
    )
    db_session.add(user)
    db_session.commit()
    profile = (
        db_session.query(CandidateProfile)
        .filter(CandidateProfile.user_id == user.id)
        .first()
    )
    if profile is None:
        profile = CandidateProfile(user_id=user.id)
        db_session.add(profile)
    profile.phone = user.phone
    profile.name = user.name
    db_session.commit()
    csrf = _fetch_csrf_token(client)
    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "candidate2pass123"},
        headers={"X-CSRF-Token": csrf},
    )
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    return user, {"Authorization": f"Bearer {token}", "X-CSRF-Token": csrf}


def _consume_tx(db_session, app_id):
    return (
        db_session.query(CreditTransaction)
        .filter(CreditTransaction.idempotency_key == f"consume:cv_analysis:{app_id}")
        .first()
    )


def _jobs_for(db_session, user_id):
    return (
        db_session.query(Application)
        .filter(
            Application.user_id == user_id,
            Application.application_type == ApplicationType.JOB.value,
        )
        .all()
    )


def _manuals_for(db_session, user_id):
    return (
        db_session.query(Application)
        .filter(
            Application.user_id == user_id,
            Application.application_type == ApplicationType.MANUAL.value,
        )
        .all()
    )


# ---------------------------------------------------------------------------
# 1) flow="apply" upload behavior (candidate side)
# ---------------------------------------------------------------------------


def test_apply_upload_returns_pending_apply_without_ai(
    client, auth_headers, db_session, monkeypatch, flow_setup
):
    user, profile, _plan = flow_setup
    calls = []

    async def fake_analyze_cv(text, role):
        calls.append((text, role))
        return {"score": 70, "detected_role": "Python Developer"}

    monkeypatch.setattr(backend_ai, "analyze_cv", fake_analyze_cv)

    resp = _upload_apply(client, auth_headers)
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["success"] is True
    assert payload["analysis_status"] == "pending_apply"
    assert payload["status"] == "analyzing"
    assert payload["cv_document_id"] is not None

    assert calls == []  # generic upload-time analyze_cv never ran
    db_session.refresh(profile)
    assert profile.candidate_cv_uploads_this_month == 1
    assert profile.candidate_ai_analyses_this_month == 0

    manuals = _manuals_for(db_session, user.id)
    assert len(manuals) == 1
    assert manuals[0].status == "analyzing"
    assert manuals[0].cv_document is not None


def test_apply_upload_quota_respected(
    client, auth_headers, db_session, flow_setup
):
    user, profile, plan = flow_setup
    profile.candidate_cv_uploads_this_month = plan.candidate_cv_uploads_limit
    db_session.commit()

    resp = _upload_apply(client, auth_headers)
    assert resp.status_code == 403
    assert "CV upload limit" in resp.json()["detail"]
    assert _manuals_for(db_session, user.id) == []


# ---------------------------------------------------------------------------
# 2) apply funding gate
# ---------------------------------------------------------------------------


def test_apply_success_funds_company_exactly_once(
    client,
    auth_headers,
    db_session,
    monkeypatch,
    flow_setup,
    test_job,
    company_billing_owner,
):
    user, profile, _plan = flow_setup
    owner = company_billing_owner

    async def fake_analyze_cv(text, role):
        return {
            "score": 70,
            "detected_role": "Python Developer",
            "verdict": "qualified",
            "summary": "Mock CV analysis",
        }

    monkeypatch.setattr(backend_ai, "analyze_cv", fake_analyze_cv)

    up = _upload_apply(client, auth_headers)
    doc_id = up.json()["cv_document_id"]

    resp = _apply_with_doc(client, auth_headers, test_job.id, doc_id)
    assert resp.status_code == 200
    app_id = resp.json()["application_id"]

    app = db_session.query(Application).filter(Application.id == app_id).first()
    assert app is not None
    assert app.application_type == ApplicationType.JOB.value
    assert app.job_id == test_job.id
    # Background recruiter-side analysis completed synchronously (TestClient).
    assert app.status == "screening"

    # Exactly one MANUAL container + one JOB application per successful apply.
    assert len(_manuals_for(db_session, user.id)) == 1
    assert len(_jobs_for(db_session, user.id)) == 1

    # Exactly one company charge with the canonical idempotency key.
    tx = _consume_tx(db_session, app_id)
    assert tx is not None
    assert tx.type == "consume"
    assert tx.amount == -3
    assert tx.resource == "cv_analysis"
    assert tx.status == "succeeded"
    assert (
        db_session.query(CreditTransaction)
        .filter(CreditTransaction.idempotency_key == f"consume:cv_analysis:{app_id}")
        .count()
        == 1
    )

    # Company wallet debited exactly 3; candidate AI quota untouched.
    assert get_user_credit_balance(db_session, owner) == 997.0
    db_session.refresh(profile)
    assert profile.candidate_ai_analyses_this_month == 0
    assert profile.candidate_cv_uploads_this_month == 1

    # Usage metering recorded for the company's spend.
    usage = (
        db_session.query(UsageEvent)
        .filter(
            UsageEvent.reference_type == "application",
            UsageEvent.reference_id == app_id,
            UsageEvent.resource == "cv_analysis",
        )
        .first()
    )
    assert usage is not None
    assert usage.company_id == test_job.company_id
    assert usage.credits == 3


def test_apply_duplicate_never_charges_twice(
    client,
    auth_headers,
    db_session,
    monkeypatch,
    flow_setup,
    test_job,
    company_billing_owner,
):
    owner = company_billing_owner

    async def fake_analyze_cv(text, role):
        return {"score": 70, "detected_role": "Python Developer"}

    monkeypatch.setattr(backend_ai, "analyze_cv", fake_analyze_cv)

    doc_id = _upload_apply(client, auth_headers).json()["cv_document_id"]
    first = _apply_with_doc(client, auth_headers, test_job.id, doc_id)
    assert first.status_code == 200
    app_id = first.json()["application_id"]

    second = _apply_with_doc(client, auth_headers, test_job.id, doc_id)
    assert second.status_code == 200
    assert "Already applied" in second.json()["message"]
    assert second.json()["application_id"] == app_id

    assert len(_jobs_for(db_session, flow_setup[0].id)) == 1
    assert _jobs_for(db_session, flow_setup[0].id)[0].id == app_id
    assert _consume_tx(db_session, app_id) is not None
    assert get_user_credit_balance(db_session, owner) == 997.0


def test_apply_insufficient_company_credits_409_no_commit(
    client, auth_headers, db_session, monkeypatch, flow_setup, test_job
):
    user, _profile, _plan = flow_setup
    owner = _make_owner(db_session, test_job.company_id, 2)

    called = {}

    async def fake_analyze_cv(text, role):
        called["called"] = True
        return {"score": 70}

    async def fake_extract_cv_details(text, role, rubric_context):
        called["called"] = True
        return {"score": 70}

    monkeypatch.setattr(backend_ai, "analyze_cv", fake_analyze_cv)
    monkeypatch.setattr(
        backend_ai, "extract_cv_details", fake_extract_cv_details
    )

    doc_id = _upload_apply(client, auth_headers).json()["cv_document_id"]
    resp = _apply_with_doc(client, auth_headers, test_job.id, doc_id)
    assert resp.status_code == 409
    assert "not accepting new applications" in resp.json()["detail"]

    # No JOB application, no charge, no analysis, wallet untouched.
    assert _jobs_for(db_session, user.id) == []
    assert _consume_tx(db_session, test_job.id) is None
    assert get_user_credit_balance(db_session, owner) == 2.0
    assert called == {}


def test_apply_no_billing_user_409(
    client, auth_headers, db_session, monkeypatch, flow_setup, test_company_b
):
    """A job posted by a company with no members cannot fund analysis."""
    user, _profile, _plan = flow_setup
    orphan_job = Job(
        company_id=test_company_b.id,
        title="Orphan Company Role",
        company_name="Orphan Co",
        location="Remote",
        type="Full-time",
        description="No funding available",
        required_skills="Python",
        is_active=True,
    )
    db_session.add(orphan_job)
    db_session.commit()

    doc_id = _upload_apply(client, auth_headers).json()["cv_document_id"]
    resp = _apply_with_doc(client, auth_headers, orphan_job.id, doc_id)
    assert resp.status_code == 409
    assert _jobs_for(db_session, user.id) == []


def test_apply_concurrent_candidates_cannot_overdraw(
    client, auth_headers, db_session, monkeypatch, flow_setup, test_job
):
    """Wallet sized for one analysis: first apply charges, second is blocked.

    A sequential doubling of the atomic guard — the range-debit UPDATE in
    consume_credits (balance >= credits AND version = v) is what makes the
    same invariant hold under true concurrency.
    """
    user_a, _profile, _plan = flow_setup
    owner = _make_owner(db_session, test_job.company_id, 3)

    async def fake_analyze_cv(text, role):
        return {"score": 70, "detected_role": "Python Developer"}

    monkeypatch.setattr(backend_ai, "analyze_cv", fake_analyze_cv)

    user_b, headers_b = _make_candidate_and_login(
        client, db_session, "candidate-b@example.com"
    )
    doc_a = _upload_apply(client, auth_headers).json()["cv_document_id"]
    doc_b = _upload_apply(client, headers_b).json()["cv_document_id"]

    resp_a = _apply_with_doc(client, auth_headers, test_job.id, doc_a)
    assert resp_a.status_code == 200
    app_a = resp_a.json()["application_id"]
    assert get_user_credit_balance(db_session, owner) == 0.0

    resp_b = _apply_with_doc(client, headers_b, test_job.id, doc_b)
    assert resp_b.status_code == 409

    assert len(_jobs_for(db_session, user_a.id)) == 1
    assert len(_jobs_for(db_session, user_b.id)) == 0
    assert _consume_tx(db_session, app_a) is not None
    assert (
        db_session.query(CreditTransaction)
        .filter(CreditTransaction.resource == "cv_analysis")
        .count()
        == 1
    )
    assert get_user_credit_balance(db_session, owner) == 0.0


def test_apply_ai_failure_refunds_company_funding(
    client,
    auth_headers,
    db_session,
    monkeypatch,
    flow_setup,
    test_job,
    company_billing_owner,
):
    owner = company_billing_owner

    async def fake_analyze_cv(text, role):
        return {"error": "boom", "score": None}

    monkeypatch.setattr(backend_ai, "analyze_cv", fake_analyze_cv)

    doc_id = _upload_apply(client, auth_headers).json()["cv_document_id"]
    resp = _apply_with_doc(client, auth_headers, test_job.id, doc_id)
    assert resp.status_code == 200
    app_id = resp.json()["application_id"]

    app = db_session.query(Application).filter(Application.id == app_id).first()
    assert app.status == "analysis_failed"

    tx = _consume_tx(db_session, app_id)
    assert tx is not None
    assert tx.status == "reversed"
    rollback = (
        db_session.query(CreditTransaction)
        .filter(CreditTransaction.idempotency_key == f"rollback:consume:cv_analysis:{app_id}")
        .first()
    )
    assert rollback is not None
    assert rollback.amount == 3
    assert get_user_credit_balance(db_session, owner) == 1000.0


# ---------------------------------------------------------------------------
# 3) apply security / ownership / gates
# ---------------------------------------------------------------------------


def test_apply_rejects_foreign_cv_document(
    client, auth_headers, db_session, monkeypatch, flow_setup, test_job
):
    user_a, _profile, _plan = flow_setup
    _make_owner(db_session, test_job.company_id, 100)
    user_b, headers_b = _make_candidate_and_login(
        client, db_session, "candidate-foreign@example.com"
    )
    # B uploads flow="apply" so B owns a CV document.
    doc_b = _upload_apply(client, headers_b).json()["cv_document_id"]

    # A passes B's cv_document_id -> 404 (no cross-candidate CV access).
    # Note: the app's 404 handler normalizes every 404 to a generic
    # {"detail": "Not Found"} (anti-enumeration), so only the status is asserted.
    resp = _apply_with_doc(client, auth_headers, test_job.id, doc_b)
    assert resp.status_code == 404
    assert _jobs_for(db_session, user_a.id) == []
    assert _jobs_for(db_session, user_b.id) == []


def test_apply_rejects_inactive_and_deleted_jobs(
    client, auth_headers, db_session, monkeypatch, flow_setup, test_job
):
    user, _profile, _plan = flow_setup

    test_job.is_active = False
    db_session.commit()
    resp = client.post(
        f"/api/v1/candidate/jobs/{test_job.id}/apply", headers=auth_headers
    )
    assert resp.status_code == 404

    test_job.is_active = True
    from datetime import UTC, datetime

    test_job.deleted_at = datetime.now(UTC)
    db_session.commit()
    resp = client.post(
        f"/api/v1/candidate/jobs/{test_job.id}/apply", headers=auth_headers
    )
    assert resp.status_code == 404
    assert _jobs_for(db_session, user.id) == []


def test_apply_without_cv_rejected(
    client, auth_headers, db_session, flow_setup, test_job
):
    user, _profile, _plan = flow_setup
    _make_owner(db_session, test_job.company_id, 100)

    resp = client.post(
        f"/api/v1/candidate/jobs/{test_job.id}/apply", headers=auth_headers
    )
    assert resp.status_code == 400
    assert "upload a CV" in resp.json()["detail"]
    assert _jobs_for(db_session, user.id) == []


# ---------------------------------------------------------------------------
# 4) Transaction boundary — proving the charge is genuinely atomic with the
#    JOB application (not just that the final state looks right)
# ---------------------------------------------------------------------------


@pytest.fixture
def _commit_counter():
    """Count SQLAlchemy commits across sessions during a single test."""
    state = {"n": 0}

    @event.listens_for(Session, "after_commit")
    def _on_commit(_session):
        state["n"] += 1

    state["reset"] = lambda: state.__setitem__("n", 0)
    return state


def _stage_application_in(db, user, job):
    """Mirror ApplicationService.create_application (flush only, no commit)."""
    app = Application(
        company_id=job.company_id,
        application_type=ApplicationType.JOB.value,
        user_id=user.id,
        job_id=job.id,
        status="applied",
        declared_role=job.title,
    )
    db.add(app)
    db.flush()
    return app


def test_funding_failure_transaction_boundary_zero_commits(
    db_session, monkeypatch, flow_setup, test_job, _commit_counter
):
    """A funding failure must never produce a SINGLE commit.

    Through the REAL consume_credits_in_transaction (no monkeypatch): a
    JOB application is staged (flushed), the optimistic-lock UPDATE on a
    2-credit wallet vs a 3-credit analysis is staged alongside it, then
    ValueError is raised and the enclosing transaction is rolled back. The
    SQLAlchemy after_commit counter must stay at zero for the whole
    sequence, and afterwards NO application, NO charge and an untouched
    wallet may exist — that is the actual transaction boundary (the old
    self-committing consume_credits would have already fired commits and
    persisted the application).
    """
    user, _profile, _plan = flow_setup
    owner = _make_owner(db_session, test_job.company_id, 2)

    _commit_counter["reset"]()
    s = TestingSessionLocal()
    try:
        app = _stage_application_in(s, user, test_job)

        # consume_credits_in_transaction must NOT commit on its own — if it
        # did (old behavior), the counter would already have advanced.
        with pytest.raises(ValueError):
            consume_credits_in_transaction(
                s,
                owner,
                3,
                "cv_analysis",
                reference_type="application",
                reference_id=app.id,
            )
        assert _commit_counter["n"] == 0

        s.rollback()

        # The whole staged set (application + pending charge) was discarded
        # by the rollback: zero commits fired and nothing persisted.
        assert _commit_counter["n"] == 0
        r2 = TestingSessionLocal()
        try:
            assert r2.query(Application).filter(Application.id == app.id).first() is None
            assert _consume_tx(r2, app.id) is None
            assert get_user_credit_balance(r2, owner) == 2.0
            wallet = (
                r2.query(CreditWallet)
                .filter(CreditWallet.user_id == owner.id)
                .first()
            )
            assert wallet is not None
            assert wallet.balance == 2
            assert wallet.version == 0
        finally:
            r2.close()
    finally:
        s.close()


def test_funding_success_transaction_boundary_single_commit(
    db_session, monkeypatch, flow_setup, test_job, _commit_counter
):
    """A successful apply persists app + wallet debit + charge + metering in
    EXACTLY ONE commit.

    Through the REAL helper functions: none of them commit on their own (the
    counter does not move while staging), and the application, the wallet
    balance, the consume ledger row and the usage row all become durable the
    moment the SINGLE explicit commit fires.
    """
    user, _profile, _plan = flow_setup
    owner = _make_owner(db_session, test_job.company_id, 1000)

    _commit_counter["reset"]()
    s = TestingSessionLocal()
    try:
        app = _stage_application_in(s, user, test_job)

        funding_tx = consume_credits_in_transaction(
            s,
            owner,
            3,
            "cv_analysis",
            reference_type="application",
            reference_id=app.id,
        )
        assert funding_tx.amount == -3
        record_usage_event_in_transaction(
            s,
            user_id=owner.id,
            company_id=test_job.company_id,
            resource="cv_analysis",
            credits=3,
            reference_type="application",
            reference_id=app.id,
        )

        # Neither helper committed on its own — the charge and the metering
        # stay staged inside the caller's transaction until the single commit.
        assert _commit_counter["n"] == 0

        before = _commit_counter["n"]
        s.commit()
        assert _commit_counter["n"] == before + 1  # exactly ONE commit

        r_after = TestingSessionLocal()
        try:
            assert r_after.query(Application).filter(Application.id == app.id).first() is not None
            assert get_user_credit_balance(r_after, owner) == 997.0
            tx = _consume_tx(r_after, app.id)
            assert tx is not None
            assert tx.amount == -3
            assert tx.status == "succeeded"
            usage = (
                r_after.query(UsageEvent)
                .filter(
                    UsageEvent.reference_type == "application",
                    UsageEvent.reference_id == app.id,
                    UsageEvent.resource == "cv_analysis",
                )
                .first()
            )
            assert usage is not None
            assert usage.credits == 3
        finally:
            r_after.close()
    finally:
        s.close()
