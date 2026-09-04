"""
Test configuration and fixtures for Candway Intelligence Platform
"""

import os

import pytest
import pytest_asyncio
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Mock environment variables for testing - MUST BE DONE BEFORE ANY BACKEND IMPORTS
_TEST_DATABASE_URL = os.environ.get(
    "CANDWAY_TEST_DATABASE_URL",
    "sqlite:///file:test_db?mode=memory&cache=shared&uri=true",
)
os.environ["DATABASE_URL"] = _TEST_DATABASE_URL
os.environ["SECRET_KEY"] = "test_secret_key_for_jwt_encoding_12345"
os.environ["ALGORITHM"] = "HS256"
os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = "30"
os.environ["DEBUG"] = "false"
os.environ["TESTING"] = "true"  # Disables RateLimitMiddleware during test runs
os.environ["ALLOWED_HOSTS"] = "testserver,localhost,127.0.0.1"

# Now we can import the app and models
from fastapi.testclient import TestClient  # noqa: E402

import backend.database  # noqa: E402
import backend.dependencies  # noqa: E402
import backend.models  # noqa: E402

# Import all models to ensure they are registered with Base.metadata
from backend.database import (  # noqa: E402
    Base,
    Company,
    CompanyMember,
    User,
)
from backend.dependencies import get_current_user, pwd_context  # noqa: E402
from backend.main import app  # noqa: E402
from backend.simple_rate_limiter import interview_rate_limiter  # noqa: E402

# Test database setup (SQLite in-memory by default; MySQL via CANDWAY_TEST_DATABASE_URL)
if _TEST_DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        _TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
else:
    engine = create_engine(_TEST_DATABASE_URL, pool_pre_ping=True)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# FORCED OVERRIDE: Ensure backend.database AND backend.dependencies use the test engine and session
backend.database.engine = engine
backend.database.SessionLocal = TestingSessionLocal
backend.dependencies.SessionLocal = TestingSessionLocal

# Some service modules imported SessionLocal at import time; re-bind them
# to the test session so their ad-hoc queries hit the same in-memory DB.
import backend.email_service as _email_service  # noqa: E402
_email_service.SessionLocal = TestingSessionLocal


def _fetch_csrf_token(client):
    """Get a valid CSRF token from a safe GET request.
    Falls back to generating one directly for test compatibility."""
    import hashlib
    import hmac
    import secrets
    import time

    from backend.dependencies import SECRET_KEY

    resp = client.get("/login")
    token = resp.headers.get("X-CSRF-Token") or resp.cookies.get("csrf_token")
    if token:
        return token
    session_id = secrets.token_urlsafe(32)
    expires_at = int(time.time()) + 86400
    message = f"{session_id}:{expires_at}"
    token_hash = hmac.new(
        SECRET_KEY.encode(), message.encode(), hashlib.sha256
    ).hexdigest()
    return f"{session_id}.{expires_at}.{token_hash}"


@pytest.fixture(scope="function")
def db_session():
    """Create a truly isolated database for each test.

    The SQLite test engine uses StaticPool, so an in-memory database
    persists across connections.  create_all() alone therefore does
    NOT reset data between tests and causes UNIQUE constraint failures
    when fixtures reuse stable slugs/emails.
    """
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    # Re-seed the minimal admin account required by admin route tests.
    db = TestingSessionLocal()
    try:
        admin = db.query(User).filter(
            User.email == "admin@test.local"
        ).first()

        if not admin:
            db.add(
                User(
                    email="admin@test.local",
                    name="Test Admin",
                    role="admin",
                    is_super_admin=True,
                )
            )
            db.commit()

        yield db

    finally:
        try:
            db.close()
        except Exception:
            pass

        # Remove all test data so the next test starts clean.
        try:
            Base.metadata.drop_all(bind=engine)
        except Exception:
            pass


@pytest_asyncio.fixture(autouse=True)
async def cleanup_redis_manager():
    """Close the shared async Redis client before pytest closes the loop."""
    yield

    from backend.redis_manager import redis_manager

    try:
        await redis_manager.close()
    except Exception:
        pass


@pytest.fixture(autouse=True)
def reset_interview_rate_limiter():
    """Prevent global in-memory limiter state from leaking across tests."""
    interview_rate_limiter.reset()
    yield
    interview_rate_limiter.reset()


@pytest.fixture(scope="function")
def client(db_session):
    """Create a test client with database override"""

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    # Override get_db in BOTH locations where it might be defined/imported
    from backend.database import get_db as get_db_db
    from backend.dependencies import get_db as get_db_dep

    app.dependency_overrides[get_db_db] = override_get_db
    app.dependency_overrides[get_db_dep] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def test_company(db_session):
    """Create a default test company"""
    company = Company(name="Test Company", slug="test-company")
    db_session.add(company)
    db_session.commit()
    db_session.refresh(company)
    return company


@pytest.fixture
def test_company_id(test_company):
    return test_company.id


@pytest.fixture
def test_user(db_session, test_company):
    """Create a test user with company membership"""

    user = User(
        email="test@example.com",
        name="Test User",
        phone="+15555550100",
        hashed_password=pwd_context.hash("testpassword123"),
        role="candidate",
        email_verified=True,
    )
    db_session.add(user)
    db_session.flush()
    membership = CompanyMember(
        company_id=test_company.id, user_id=user.id, role="member", is_active=True
    )
    db_session.add(membership)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_company_b(db_session):
    """Create a second test company for cross-company tests"""
    company = Company(name="Evil Corp", slug="evil-corp")
    db_session.add(company)
    db_session.commit()
    db_session.refresh(company)
    return company


@pytest.fixture
def test_recruiter(db_session, test_company):
    """Create a test recruiter with company membership"""

    user = User(
        email="recruiter@example.com",
        name="Test Recruiter",
        hashed_password=pwd_context.hash("recruiterpass123"),
        role="recruiter",
        email_verified=True,
        company_name="Test Company",
    )
    db_session.add(user)
    db_session.flush()
    membership = CompanyMember(
        company_id=test_company.id, user_id=user.id, role="admin", is_active=True
    )
    db_session.add(membership)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_recruiter_b(db_session, test_company_b):
    """Create a test recruiter for Company B (cross-company access)"""

    user = User(
        email="attacker@evilcorp.com",
        name="Evil Recruiter",
        hashed_password=pwd_context.hash("attackerpass123"),
        role="recruiter",
        email_verified=True,
        company_name="Evil Corp",
    )
    db_session.add(user)
    db_session.flush()
    membership = CompanyMember(
        company_id=test_company_b.id, user_id=user.id, role="admin", is_active=True
    )
    db_session.add(membership)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def auth_headers(client, test_user):
    """Get authentication headers for test user"""
    csrf_token = _fetch_csrf_token(client)
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "test@example.com", "password": "testpassword123"},
        headers={"X-CSRF-Token": csrf_token},
    )
    data = response.json()
    print(f"DEBUG: Login Response: {data}")
    token = data["access_token"]
    return {"Authorization": f"Bearer {token}", "X-CSRF-Token": csrf_token}


@pytest.fixture
def recruiter_headers(client, test_recruiter):
    """Get authentication headers for test recruiter"""
    csrf_token = _fetch_csrf_token(client)
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "recruiter@example.com", "password": "recruiterpass123"},
        headers={"X-CSRF-Token": csrf_token},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}", "X-CSRF-Token": csrf_token}


@pytest.fixture
def recruiter_headers_b(client, test_recruiter_b):
    """Get authentication headers for attacker recruiter (Company B)"""
    csrf_token = _fetch_csrf_token(client)
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "attacker@evilcorp.com", "password": "attackerpass123"},
        headers={"X-CSRF-Token": csrf_token},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}", "X-CSRF-Token": csrf_token}


@pytest.fixture
def mock_current_user(test_user):
    """Mock the get_current_user dependency"""

    def override_get_current_user():
        return test_user

    app.dependency_overrides[get_current_user] = override_get_current_user
    yield test_user
    app.dependency_overrides.clear()
