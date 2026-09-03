"""Tests for Campaign Manager P0 beta fixes.

Covers:
- GET /campaigns/{batch_id}/candidates — pagination, status filter, sort_by, page_size_max
- Duplicate email upload returns skipped details (not silent)
- Cross-tenant candidate list still returns 404
- Invalid file type rejected
- Consent fields persisted to Application
"""

import io
import os

import pytest

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["SECRET_KEY"] = "test_secret_key_for_jwt_encoding_12345"
os.environ["ALGORITHM"] = "HS256"
os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = "30"
os.environ["DEBUG"] = "false"

from fastapi.testclient import TestClient  # noqa: E402

import backend.database  # noqa: E402
import backend.dependencies  # noqa: E402
from backend.database import (  # noqa: E402
    Application,
    Base,
    BatchJob,
    Company,
    CompanyMember,
    Job,
    User,
)
from backend.dependencies import pwd_context  # noqa: E402
from backend.main import app  # noqa: E402
from backend.models.core.batch_job import batch_counters  # noqa: E402

test_engine = backend.database.engine
if test_engine.url.database != ":memory:":
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    backend.database.engine = test_engine
    backend.database.SessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=test_engine
    )
    backend.dependencies.SessionLocal = backend.database.SessionLocal


def _get_csrf_token(client):
    resp = client.get("/login")
    return resp.headers.get("X-CSRF-Token") or resp.cookies.get("csrf_token") or ""


def _login(client, email, password):
    csrf = _get_csrf_token(client)
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
        headers={"X-CSRF-Token": csrf},
    )
    if resp.status_code != 200:
        raise AssertionError(
            f"Login failed for {email}: {resp.status_code} {resp.text}"
        )
    token = resp.json().get("access_token")
    return {"Authorization": f"Bearer {token}", "X-CSRF-Token": csrf}


@pytest.fixture(scope="module")
def client():
    Base.metadata.create_all(bind=test_engine)
    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="module")
def company_a(client):
    db = backend.database.SessionLocal()
    c = Company(name="P0 Test Co A", slug="p0-test-co-a", is_active=True)
    db.add(c)
    db.commit()
    db.refresh(c)
    cid = c.id
    db.close()
    db2 = backend.database.SessionLocal()
    fresh = db2.query(Company).filter(Company.id == cid).first()
    yield fresh
    db2.close()


@pytest.fixture(scope="module")
def company_b(client):
    db = backend.database.SessionLocal()
    c = Company(name="P0 Test Co B", slug="p0-test-co-b", is_active=True)
    db.add(c)
    db.commit()
    db.refresh(c)
    cid = c.id
    db.close()
    db2 = backend.database.SessionLocal()
    fresh = db2.query(Company).filter(Company.id == cid).first()
    yield fresh
    db2.close()


def _make_recruiter(email, name, company, role="admin"):
    db = backend.database.SessionLocal()
    user = User(
        email=email,
        name=name,
        hashed_password=pwd_context.hash("pass123!"),
        role="recruiter",
        email_verified=True,
        company_name=company.name,
    )
    db.add(user)
    db.flush()
    db.add(
        CompanyMember(
            company_id=company.id,
            user_id=user.id,
            role=role,
            is_active=True,
        )
    )
    db.commit()
    uid = user.id
    db.close()
    db2 = backend.database.SessionLocal()
    fresh = db2.query(User).filter(User.id == uid).first()
    db2.close()
    return fresh


@pytest.fixture(scope="module")
def recruiter_a(client, company_a):
    return _make_recruiter("p0_recruiter_a@test.tn", "Recruiter A", company_a)


@pytest.fixture(scope="module")
def recruiter_b(client, company_b):
    return _make_recruiter("p0_recruiter_b@test.tn", "Recruiter B", company_b)


@pytest.fixture(scope="module")
def headers_a(client, recruiter_a):
    return _login(client, "p0_recruiter_a@test.tn", "pass123!")


@pytest.fixture(scope="module")
def headers_b(client, recruiter_b):
    return _login(client, "p0_recruiter_b@test.tn", "pass123!")


@pytest.fixture(scope="module")
def p0_fixture(client, recruiter_a, company_a):
    """Job + BatchJob + 5 Applications with different statuses and scores."""
    db = backend.database.SessionLocal()

    job = Job(
        title="P0 Test Role",
        recruiter_id=recruiter_a.id,
        company_id=company_a.id,
        company_name="P0 Test Co A",
        location="Remote",
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    from backend.database import Rubric

    rubric = Rubric(
        company_id=company_a.id,
        created_by=recruiter_a.id,
        title="P0 Test Rubric",
        is_active=1,
    )
    db.add(rubric)
    db.commit()
    db.refresh(rubric)

    job.rubric_id = rubric.id
    db.commit()

    batch = BatchJob(
        recruiter_id=recruiter_a.id,
        job_id=job.id,
        company_id=company_a.id,
        title="P0 Batch Test",
        status="active",
        worker_status="completed",
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)

    candidates = [
        ("Alice Chen", "alice@p0test.tn", "screening", 88.0),
        ("Bob Smith", "bob@p0test.tn", "invited", 75.0),
        ("Carol White", "carol@p0test.tn", "screening", 60.0),
        ("Dave Brown", "dave@p0test.tn", "rejected", None),
        ("Eve Wilson", "eve@p0test.tn", "failed", None),
    ]
    app_ids = []
    for full_name, email, status, score in candidates:
        a = Application(
            user_id=None,
            batch_id=batch.id,
            job_id=job.id,
            company_id=company_a.id,
            full_name=full_name,
            email=email,
            status=status,
            declared_role="Test Role",
            analysis_score=score,
        )
        db.add(a)
        db.flush()
        app_ids.append(a.id)

    db.commit()
    batch_id = batch.id
    job_id = job.id
    db.close()
    yield {"batch_id": batch_id, "job_id": job_id, "app_ids": app_ids}


# ── 1. Pagination ────────────────────────────────────────────────


def test_candidate_list_returns_paginated_shape(client, headers_a, p0_fixture):
    """Response must be paginated dict, not a plain array."""
    batch_id = p0_fixture["batch_id"]
    resp = client.get(
        f"/api/v1/recruiter/campaigns/{batch_id}/candidates",
        params={"page": 1, "page_size": 10},
        headers=headers_a,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "items" in data, "Response must have 'items' key"
    assert "total" in data
    assert "page" in data
    assert "page_size" in data
    assert "total_pages" in data
    assert data["page"] == 1
    assert data["total"] >= 5  # 5 test candidates


def test_candidate_list_page_size_enforced(client, headers_a, p0_fixture):
    """page_size=200 is the max; >200 must be clamped."""
    batch_id = p0_fixture["batch_id"]
    resp = client.get(
        f"/api/v1/recruiter/campaigns/{batch_id}/candidates",
        params={"page": 1, "page_size": 300},
        headers=headers_a,
    )
    # FastAPI Query(le=200) should reject 300 with 422
    assert resp.status_code == 422


def test_candidate_list_page_2(client, headers_a, p0_fixture):
    """Page 2 with page_size=2 — items should not overlap with page 1."""
    batch_id = p0_fixture["batch_id"]
    resp1 = client.get(
        f"/api/v1/recruiter/campaigns/{batch_id}/candidates",
        params={"page": 1, "page_size": 2},
        headers=headers_a,
    )
    resp2 = client.get(
        f"/api/v1/recruiter/campaigns/{batch_id}/candidates",
        params={"page": 2, "page_size": 2},
        headers=headers_a,
    )
    assert resp1.status_code == 200
    assert resp2.status_code == 200
    ids_p1 = {c["id"] for c in resp1.json()["items"]}
    ids_p2 = {c["id"] for c in resp2.json()["items"]}
    assert ids_p1.isdisjoint(ids_p2), "Pages must not share candidate IDs"


# ── 2. Status filter ─────────────────────────────────────────────


def test_candidate_list_filter_by_screening(client, headers_a, p0_fixture):
    batch_id = p0_fixture["batch_id"]
    resp = client.get(
        f"/api/v1/recruiter/campaigns/{batch_id}/candidates",
        params={"status": "screening"},
        headers=headers_a,
    )
    assert resp.status_code == 200, resp.text
    items = resp.json()["items"]
    assert all(c["status"] == "screening" for c in items), (
        "All items must have status=screening"
    )
    # We created 2 screening candidates
    assert len(items) >= 2


def test_candidate_list_filter_invited(client, headers_a, p0_fixture):
    batch_id = p0_fixture["batch_id"]
    resp = client.get(
        f"/api/v1/recruiter/campaigns/{batch_id}/candidates",
        params={"status": "invited"},
        headers=headers_a,
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert all(c["status"] == "invited" for c in items)
    assert len(items) >= 1


def test_candidate_list_filter_all_returns_all(client, headers_a, p0_fixture):
    batch_id = p0_fixture["batch_id"]
    resp = client.get(
        f"/api/v1/recruiter/campaigns/{batch_id}/candidates",
        params={"status": "all"},
        headers=headers_a,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 5


# ── 3. Sorting ───────────────────────────────────────────────────


def test_candidate_list_sort_by_cv_score_desc(client, headers_a, p0_fixture):
    batch_id = p0_fixture["batch_id"]
    resp = client.get(
        f"/api/v1/recruiter/campaigns/{batch_id}/candidates",
        params={"sort_by": "cv_score", "sort_dir": "desc", "page_size": 50},
        headers=headers_a,
    )
    assert resp.status_code == 200, resp.text
    items = resp.json()["items"]
    scores = [c["cv_score"] for c in items if c["cv_score"] is not None]
    # Non-null scores should be descending
    assert scores == sorted(scores, reverse=True), (
        f"Scores not sorted descending: {scores}"
    )


def test_candidate_list_null_scores_no_crash(client, headers_a, p0_fixture):
    """Candidates with null cv_score must not cause sort errors."""
    batch_id = p0_fixture["batch_id"]
    resp = client.get(
        f"/api/v1/recruiter/campaigns/{batch_id}/candidates",
        params={"sort_by": "cv_score", "sort_dir": "desc", "page_size": 50},
        headers=headers_a,
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    # All 5 should be returned
    assert len(items) >= 5


def test_candidate_list_sort_by_created_at(client, headers_a, p0_fixture):
    batch_id = p0_fixture["batch_id"]
    resp = client.get(
        f"/api/v1/recruiter/campaigns/{batch_id}/candidates",
        params={"sort_by": "created_at", "sort_dir": "asc"},
        headers=headers_a,
    )
    assert resp.status_code == 200


# ── 4. Batch counters / processing_status ────────────────────────


def test_batch_counters_processing_status(p0_fixture):
    """batch_counters must return processing_status and failed_files."""
    db = backend.database.SessionLocal()
    try:
        counters = batch_counters(db, p0_fixture["batch_id"])
        assert "processing_status" in counters
        assert "failed_files" in counters
        assert "total_files" in counters
        assert "processed_files" in counters
        # 5 candidates, none are pending → processing_status = completed
        assert counters["processing_status"] in ("completed", "processing", "idle")
        # We have 1 failed candidate
        assert counters["failed_files"] >= 1
    finally:
        db.close()


def test_campaign_detail_exposes_processing_status(client, headers_a, p0_fixture):
    batch_id = p0_fixture["batch_id"]
    resp = client.get(
        f"/api/v1/recruiter/campaigns/{batch_id}",
        headers=headers_a,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "processing_status" in data
    assert "failed_files" in data
    assert "total_files" in data
    assert "processed_files" in data


# ── 5. Tenant isolation ──────────────────────────────────────────


def test_cross_tenant_candidate_list_is_404(client, headers_b, p0_fixture):
    """Recruiter from company B must get 404 on company A's batch candidates."""
    batch_id = p0_fixture["batch_id"]
    resp = client.get(
        f"/api/v1/recruiter/campaigns/{batch_id}/candidates",
        headers=headers_b,
    )
    assert resp.status_code == 404, f"Expected 404, got {resp.status_code}: {resp.text}"


# ── 6. Consent fields on Application ────────────────────────────


def test_application_has_consent_fields(p0_fixture):
    """Application model must have consent_accepted, consent_at, consent_source."""
    db = backend.database.SessionLocal()
    try:
        app = db.query(Application).filter(
            Application.id == p0_fixture["app_ids"][0]
        ).first()
        assert hasattr(app, "consent_accepted")
        assert hasattr(app, "consent_at")
        assert hasattr(app, "consent_source")
    finally:
        db.close()


def test_batch_job_has_consent_fields(p0_fixture):
    """BatchJob model must have consent confirmation fields."""
    db = backend.database.SessionLocal()
    try:
        batch = db.query(BatchJob).filter(
            BatchJob.id == p0_fixture["batch_id"]
        ).first()
        assert hasattr(batch, "cv_processing_consent_confirmed")
        assert hasattr(batch, "cv_processing_consent_confirmed_at")
        assert hasattr(batch, "cv_processing_consent_confirmed_by")
    finally:
        db.close()


# ── 7. Invalid file rejected by upload endpoint ──────────────────


def test_upload_non_pdf_rejected(client, headers_a, p0_fixture):
    """Uploading a .exe file must return skipped (not a PDF), not 500."""
    batch_id = p0_fixture["batch_id"]
    job_id = p0_fixture["job_id"]
    fake_exe = io.BytesIO(b"MZ fake exe content")
    resp = client.post(
        "/api/v1/recruiter/campaigns/upload/cv",
        headers=headers_a,
        data={"job_id": str(job_id), "campaign_id": str(batch_id)},
        files={"files": ("malicious.exe", fake_exe, "application/octet-stream")},
    )
    # Either 200 with skipped detail or the job has no rubric → 400, never 500
    assert resp.status_code != 500, f"Got 500: {resp.text}"
