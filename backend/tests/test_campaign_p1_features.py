"""Tests for Campaign Manager P1 improvements.

Covers:
- PATCH /recruiter/campaigns/{batch_id}/candidates/{app_id}/shortlist
- GET   /recruiter/campaigns/{batch_id}/export/csv (all and shortlisted scopes)
- GET   /recruiter/campaigns/{batch_id}/export/pdf
- GET   /recruiter/campaigns/{batch_id}/analytics (avg_cv_score, qualified_count, real response_rate)
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
def p1_company(client):
    db = backend.database.SessionLocal()
    c = Company(name="P1 Co", slug="p1-co", is_active=True)
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
def p1_recruiter(client, p1_company):
    db = backend.database.SessionLocal()
    user = User(
        email="p1_recruiter@test.tn",
        name="P1 Recruiter",
        hashed_password=pwd_context.hash("pass123!"),
        role="recruiter",
        email_verified=True,
        company_name=p1_company.name,
    )
    db.add(user)
    db.flush()
    db.add(
        CompanyMember(
            company_id=p1_company.id,
            user_id=user.id,
            role="admin",
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
def p1_headers(client, p1_recruiter):
    return _login(client, "p1_recruiter@test.tn", "pass123!")


@pytest.fixture(scope="module")
def p1_fixture(client, p1_recruiter, p1_company):
    db = backend.database.SessionLocal()

    job = Job(
        title="P1 Backend Role",
        recruiter_id=p1_recruiter.id,
        company_id=p1_company.id,
        company_name="P1 Co",
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    batch = BatchJob(
        recruiter_id=p1_recruiter.id,
        job_id=job.id,
        company_id=p1_company.id,
        title="P1 Campaign Test",
        status="active",
        worker_status="completed",
        email_sequence_enabled=True,
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)

    candidates = [
        ("Candidate One", "one@p1.tn", "screening", 85.0),
        ("Candidate Two", "two@p1.tn", "shortlisted", 72.0),
        ("Candidate Three", "three@p1.tn", "screening", 55.0),
    ]
    app_ids = []
    for full_name, email, status, score in candidates:
        a = Application(
            user_id=None,
            batch_id=batch.id,
            job_id=job.id,
            company_id=p1_company.id,
            full_name=full_name,
            email=email,
            status=status,
            declared_role="Backend Role",
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


# ── 1. Shortlist Action ──────────────────────────────────────────


def test_shortlist_candidate_updates_status(client, p1_headers, p1_fixture):
    batch_id = p1_fixture["batch_id"]
    app_id = p1_fixture["app_ids"][0]
    resp = client.patch(
        f"/api/v1/recruiter/campaigns/{batch_id}/candidates/{app_id}/shortlist",
        headers=p1_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["success"] is True
    assert data["status"] == "shortlisted"


# ── 2. CSV Export ─────────────────────────────────────────────────


def test_export_csv_all(client, p1_headers, p1_fixture):
    batch_id = p1_fixture["batch_id"]
    resp = client.get(
        f"/api/v1/recruiter/campaigns/{batch_id}/export/csv",
        params={"scope": "all"},
        headers=p1_headers,
    )
    assert resp.status_code == 200, resp.text
    assert "text/csv" in resp.headers["content-type"]
    body = resp.text
    assert "name,email,status" in body
    assert "Candidate One" in body


def test_export_csv_shortlisted(client, p1_headers, p1_fixture):
    batch_id = p1_fixture["batch_id"]
    resp = client.get(
        f"/api/v1/recruiter/campaigns/{batch_id}/export/csv",
        params={"scope": "shortlisted"},
        headers=p1_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.text
    assert "name,email,status" in body
    # Candidate One was shortlisted in test 1, Candidate Two was shortlisted in fixture
    assert "shortlisted" in body


# ── 3. PDF Export ─────────────────────────────────────────────────


def test_export_pdf_report(client, p1_headers, p1_fixture):
    batch_id = p1_fixture["batch_id"]
    resp = client.get(
        f"/api/v1/recruiter/campaigns/{batch_id}/export/pdf",
        params={"scope": "shortlisted"},
        headers=p1_headers,
    )
    assert resp.status_code == 200, resp.text
    assert "application/pdf" in resp.headers["content-type"]
    assert len(resp.content) > 100  # Non-empty PDF bytes


# ── 4. Analytics P1 Metrics ──────────────────────────────────────


def test_analytics_p1_metrics(client, p1_headers, p1_fixture):
    batch_id = p1_fixture["batch_id"]
    resp = client.get(
        f"/api/v1/recruiter/campaigns/{batch_id}/analytics",
        params={"threshold": 70},
        headers=p1_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "avg_cv_score" in data
    assert data["avg_cv_score"] == 70.7  # (85 + 72 + 55) / 3 = 70.666 -> 70.7
    assert "qualified_count" in data
    assert data["qualified_count"] == 2  # 85 and 72 >= 70
    assert "response_rate" in data
