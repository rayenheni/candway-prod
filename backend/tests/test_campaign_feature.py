"""Tests for the recruiter campaign feature (list/create/detail/stats/analytics/candidates).

Covers:
- GET  /recruiter/campaigns (list, plain array)
- POST /recruiter/campaigns/ (create)
- GET  /recruiter/campaigns/{batch_id} (detail — new endpoint)
- GET  /recruiter/campaigns/{batch_id}/stats
- GET  /recruiter/campaigns/{batch_id}/analytics
- GET  /recruiter/campaigns/{batch_id}/candidates
- Cross-company 404 isolation
- PATCH /recruiter/campaigns/{batch_id} update (PATCH not PUT)

Follows the module-scoped TestClient pattern from test_org_portal.py
to avoid the alembic auto-upgrade startup interfering with per-test sessions.
"""

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
def test_company(client):
    db = backend.database.SessionLocal()
    company = Company(name="Campaign Co", slug="campaign-co", is_active=True)
    db.add(company)
    db.commit()
    db.refresh(company)
    cid = company.id
    db.close()
    db2 = backend.database.SessionLocal()
    fresh = db2.query(Company).filter(Company.id == cid).first()
    yield fresh
    db2.close()


@pytest.fixture(scope="module")
def test_company_b(client):
    db = backend.database.SessionLocal()
    company = Company(name="Evil Co", slug="evil-co", is_active=True)
    db.add(company)
    db.commit()
    db.refresh(company)
    cid = company.id
    db.close()
    db2 = backend.database.SessionLocal()
    fresh = db2.query(Company).filter(Company.id == cid).first()
    yield fresh
    db2.close()


def _make_recruiter(db, email, name, company, role="admin"):
    user = User(
        email=email,
        name=name,
        hashed_password=pwd_context.hash("recruitpass123"),
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
    db.refresh(user)
    uid = user.id
    db.close()
    db2 = backend.database.SessionLocal()
    fresh = db2.query(User).filter(User.id == uid).first()
    db2.close()
    return fresh


@pytest.fixture(scope="module")
def recruiter(client, test_company):
    db = backend.database.SessionLocal()
    return _make_recruiter(db, "camp_recruiter@test.tn", "Camp Recruiter", test_company)


@pytest.fixture(scope="module")
def recruiter_b(client, test_company_b):
    db = backend.database.SessionLocal()
    return _make_recruiter(
        db, "evil_recruiter@test.tn", "Evil Recruiter", test_company_b
    )


@pytest.fixture(scope="module")
def recruiter_headers(client, recruiter):
    return _login(client, "camp_recruiter@test.tn", "recruitpass123")


@pytest.fixture(scope="module")
def recruiter_headers_b(client, recruiter_b):
    return _login(client, "evil_recruiter@test.tn", "recruitpass123")


@pytest.fixture(scope="module")
def campaign_fixture(client, recruiter, test_company):
    """Job + BatchJob + Application used by all tests."""
    db = backend.database.SessionLocal()

    job = Job(
        title="Senior Frontend Engineer",
        recruiter_id=recruiter.id,
        company_id=test_company.id,
        company_name="Campaign Co",
        location="Tunis",
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    batch = BatchJob(
        recruiter_id=recruiter.id,
        job_id=job.id,
        company_id=test_company.id,
        title="Frontend Hiring Q3",
        status="active",
        worker_status="completed",
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)

    app = Application(
        user_id=recruiter.id,
        batch_id=batch.id,
        job_id=job.id,
        company_id=test_company.id,
        full_name="Jane Doe",
        email="jane@example.com",
        status="invited",
        declared_role="Frontend Engineer",
    )
    db.add(app)
    db.commit()
    db.refresh(app)

    batch_id = batch.id
    job_id = job.id
    app_id = app.id
    db.close()
    yield {"batch_id": batch_id, "job_id": job_id, "app_id": app_id}


# ── Create ──────────────────────────────────────────────────────


def test_create_campaign_requires_existing_job(client, recruiter_headers):
    resp = client.post(
        "/api/v1/recruiter/campaigns/",
        json={"title": "Ghost Campaign", "job_id": 99999},
        headers=recruiter_headers,
    )
    assert resp.status_code in (404, 422), resp.text


def test_create_campaign_returns_response(client, recruiter_headers, campaign_fixture):
    resp = client.post(
        "/api/v1/recruiter/campaigns/",
        json={"title": "New Campaign", "job_id": campaign_fixture["job_id"]},
        headers=recruiter_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["id"] is not None
    assert data["title"] == "New Campaign"
    assert data["status"] == "active"


# ── List ────────────────────────────────────────────────────────


def test_list_campaigns_returns_plain_array(
    client, recruiter_headers, campaign_fixture
):
    resp = client.get("/api/v1/recruiter/campaigns", headers=recruiter_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert isinstance(data, list)
    match = [c for c in data if c["id"] == campaign_fixture["batch_id"]]
    assert match, "created campaign not present in list"
    assert match[0]["title"] == "Frontend Hiring Q3"
    assert "candidate_count" in match[0]


# ── Detail (new endpoint) ───────────────────────────────────────


def test_get_campaign_detail(client, recruiter_headers, campaign_fixture):
    batch_id = campaign_fixture["batch_id"]
    resp = client.get(
        f"/api/v1/recruiter/campaigns/{batch_id}", headers=recruiter_headers
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["id"] == batch_id
    assert data["title"] == "Frontend Hiring Q3"
    assert data["job_id"] == campaign_fixture["job_id"]
    assert data["stats"]["total_candidates"] >= 1
    assert "emails_sent" in data
    assert "processed_files" in data


def test_get_campaign_detail_404_missing(client, recruiter_headers):
    resp = client.get(
        "/api/v1/recruiter/campaigns/999999", headers=recruiter_headers
    )
    assert resp.status_code == 404, resp.text


# ── Stats ───────────────────────────────────────────────────────


def test_get_campaign_stats(client, recruiter_headers, campaign_fixture):
    batch_id = campaign_fixture["batch_id"]
    resp = client.get(
        f"/api/v1/recruiter/campaigns/{batch_id}/stats", headers=recruiter_headers
    )
    assert resp.status_code == 200, resp.text
    stats = resp.json()["stats"]
    assert stats["total_candidates"] >= 1
    assert stats["invited"] >= 1
    assert "interviewed" in stats
    assert "avg_cv_score" in stats


# ── Analytics ───────────────────────────────────────────────────


def test_get_campaign_analytics(client, recruiter_headers, campaign_fixture):
    batch_id = campaign_fixture["batch_id"]
    resp = client.get(
        f"/api/v1/recruiter/campaigns/{batch_id}/analytics", headers=recruiter_headers
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["campaign_id"] == batch_id
    assert data["total_candidates"] >= 1
    assert "pipeline" in data
    assert "conversion" in data
    assert data["pipeline"]["invited"] >= 1


# ── Candidates ──────────────────────────────────────────────────


def test_get_campaign_candidates(client, recruiter_headers, campaign_fixture):
    batch_id = campaign_fixture["batch_id"]
    resp = client.get(
        f"/api/v1/recruiter/campaigns/{batch_id}/candidates", headers=recruiter_headers
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    items = data["items"] if isinstance(data, dict) and "items" in data else data
    assert isinstance(items, list)
    assert len(items) >= 1
    candidate = items[0]
    assert candidate["id"] == campaign_fixture["app_id"]
    assert candidate["full_name"] == "Jane Doe"
    assert candidate["email"] == "jane@example.com"
    assert "interview_state" in candidate
    assert "interview_progress" in candidate


# ── Update (PATCH) ──────────────────────────────────────────────


def test_update_campaign_uses_patch(client, recruiter_headers, campaign_fixture):
    batch_id = campaign_fixture["batch_id"]
    resp = client.patch(
        f"/api/v1/recruiter/campaigns/{batch_id}",
        json={"title": "Renamed Campaign"},
        headers=recruiter_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["title"] == "Renamed Campaign"


# ── Tenant isolation ────────────────────────────────────────────


def test_cross_company_campaign_is_404(client, recruiter_headers_b, campaign_fixture):
    """Recruiters from another company must get 404 (never 403/200)."""
    batch_id = campaign_fixture["batch_id"]
    resp = client.get(
        f"/api/v1/recruiter/campaigns/{batch_id}", headers=recruiter_headers_b
    )
    assert resp.status_code == 404, resp.text


def test_cross_company_candidates_is_404(
    client, recruiter_headers_b, campaign_fixture
):
    batch_id = campaign_fixture["batch_id"]
    resp = client.get(
        f"/api/v1/recruiter/campaigns/{batch_id}/candidates",
        headers=recruiter_headers_b,
    )
    assert resp.status_code == 404, resp.text
