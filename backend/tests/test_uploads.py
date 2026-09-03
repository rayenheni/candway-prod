"""C-1 regression tests: serve_uploaded_file must inject its db session.

Covers the owner-encoding patterns and the two DB-backed branches
(video_<appid> resolution and company-shared avatars) that previously
raised NameError because ``db`` was undefined in the route signature.
Also verifies the route is registered before the SPA catch-all so it is
actually reachable.

Follows the module-level engine + TestClient pattern of test_org_billing.py
to avoid the pre-existing conftest closed-database teardown bug.
"""

import os

import pytest

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["SECRET_KEY"] = "test_secret_key_for_jwt_encoding_12345"
os.environ["ALGORITHM"] = "HS256"
os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = "30"
os.environ["DEBUG"] = "false"

from fastapi.testclient import TestClient  # noqa: E402

import backend.app as app_module  # noqa: E402
import backend.database  # noqa: E402
import backend.dependencies  # noqa: E402
from backend.database import (  # noqa: E402
    Application,
    Base,
    Company,
    CompanyMember,
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


def _login(client, email, password):
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
        headers={"X-CSRF-Token": "test"},
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.fixture(scope="module")
def client():
    Base.metadata.create_all(bind=test_engine)

    # app.py's serve_uploaded_file imports get_db from backend.database
    # (defined in models/base.py), which is NOT the same object as
    # backend.dependencies.get_db. Override it so the route reads from the
    # same in-memory engine the seeded fixtures write to.
    def override_get_db():
        db = backend.database.SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[backend.database.get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="module")
def seeded(client):
    """Company, owner candidate, recruiter member, one Application."""
    db = backend.database.SessionLocal()

    company = Company(name="Uploads Co", slug="uploads-co", is_active=True)
    db.add(company)
    db.flush()
    cid = company.id

    candidate = User(
        email="owner@test.tn",
        name="Owner",
        hashed_password=pwd_context.hash("ownerpass123"),
        role="candidate",
        email_verified=True,
    )
    db.add(candidate)
    db.flush()
    db.add(
        CompanyMember(
            company_id=cid,
            user_id=candidate.id,
            role="member",
            is_active=True,
        )
    )

    recruiter = User(
        email="recruiter@test.tn",
        name="Recruiter",
        hashed_password=pwd_context.hash("recruiterpass123"),
        role="recruiter",
        email_verified=True,
    )
    db.add(recruiter)
    db.flush()
    db.add(
        CompanyMember(
            company_id=cid,
            user_id=recruiter.id,
            role="admin",
            is_active=True,
        )
    )

    app_row = Application(
        id=555001,
        company_id=cid,
        user_id=candidate.id,
        email=candidate.email,
        status="pending",
    )
    db.add(app_row)
    db.commit()

    result = {
        "company_id": cid,
        "candidate_id": candidate.id,
        "recruiter_id": recruiter.id,
    }
    db.close()
    return result


@pytest.fixture(scope="module")
def owner_headers(client, seeded):
    return _login(client, "owner@test.tn", "ownerpass123")


@pytest.fixture(scope="module")
def recruiter_headers(client, seeded):
    return _login(client, "recruiter@test.tn", "recruiterpass123")


@pytest.fixture
def fake_upload_dir(monkeypatch, tmp_path):
    """Redirect UPLOAD_DIR to a temp directory for the test."""
    monkeypatch.setattr(app_module, "UPLOAD_DIR", str(tmp_path))
    return tmp_path


def _write(upload_dir, rel_path, content=b"fake-file-content"):
    full = os.path.join(str(upload_dir), rel_path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "wb") as f:
        f.write(content)
    return full


class TestUploadAccessControl:
    def test_owner_can_access_authorized_upload(
        self, client, seeded, owner_headers, fake_upload_dir
    ):
        _write(fake_upload_dir, f"upload_{seeded['candidate_id']}_cv.pdf")
        resp = client.get(
            f"/uploads/upload_{seeded['candidate_id']}_cv.pdf",
            headers=owner_headers,
        )
        assert resp.status_code == 200
        assert resp.content == b"fake-file-content"

    def test_unauthorized_user_cannot_access_private_upload(
        self, client, seeded, owner_headers, recruiter_headers, fake_upload_dir
    ):
        _write(fake_upload_dir, f"upload_{seeded['candidate_id']}_cv.pdf")
        resp = client.get(
            f"/uploads/upload_{seeded['candidate_id']}_cv.pdf",
            headers=recruiter_headers,
        )
        assert resp.status_code == 403

    def test_unauthenticated_upload_requires_login(
        self, client, seeded, fake_upload_dir
    ):
        client.cookies.clear()
        _write(fake_upload_dir, f"upload_{seeded['candidate_id']}_cv.pdf")
        resp = client.get(f"/uploads/upload_{seeded['candidate_id']}_cv.pdf")
        assert resp.status_code == 401

    def test_missing_file_returns_404(
        self, client, seeded, owner_headers, fake_upload_dir
    ):
        resp = client.get(
            f"/uploads/upload_{seeded['candidate_id']}_nonexistent.pdf",
            headers=owner_headers,
        )
        assert resp.status_code == 404

    def test_path_traversal_denied(
        self, client, seeded, owner_headers, fake_upload_dir
    ):
        _write(fake_upload_dir, "secret.txt", b"top-secret")
        resp = client.get("/uploads/..%2F..%2Fetc%2Fpasswd", headers=owner_headers)
        assert resp.status_code in (403, 404)


class TestVideoUploadRetrieval:
    def test_video_upload_retrieval_works_for_owner(
        self, client, seeded, owner_headers, fake_upload_dir
    ):
        _write(fake_upload_dir, "videos/video_555001_abc123.webm", b"webm-bytes")
        resp = client.get(
            "/uploads/videos/video_555001_abc123.webm", headers=owner_headers
        )
        assert resp.status_code == 200
        assert resp.content == b"webm-bytes"

    def test_video_upload_denied_to_non_owner(
        self, client, seeded, recruiter_headers, fake_upload_dir
    ):
        _write(fake_upload_dir, "videos/video_555001_abc123.webm", b"webm-bytes")
        resp = client.get(
            "/uploads/videos/video_555001_abc123.webm", headers=recruiter_headers
        )
        assert resp.status_code == 403

    def test_video_upload_missing_application_denied(
        self, client, seeded, owner_headers, fake_upload_dir
    ):
        _write(fake_upload_dir, "videos/video_999999_abc123.webm", b"webm-bytes")
        resp = client.get(
            "/uploads/videos/video_999999_abc123.webm", headers=owner_headers
        )
        assert resp.status_code == 403


class TestAvatarCompanyShare:
    def test_avatar_retrieval_works_for_same_company_recruiter(
        self, client, seeded, recruiter_headers, fake_upload_dir
    ):
        # Candidate avatar shared with a recruiter in the same company.
        _write(
            fake_upload_dir,
            f"avatars/upload_{seeded['candidate_id']}_avatar.png",
        )
        resp = client.get(
            f"/uploads/avatars/upload_{seeded['candidate_id']}_avatar.png",
            headers=recruiter_headers,
        )
        assert resp.status_code == 200
        assert resp.content == b"fake-file-content"
