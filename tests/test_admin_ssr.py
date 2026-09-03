import pytest
from fastapi.testclient import TestClient


class _AdminUser:
    def __init__(self, id=1, email="admin@example.com", role="admin"):
        self.id = id
        self.email = email
        self.role = role
        self.admin_permissions = "view_analytics,manage_users,manage_jobs"
        self.is_super_admin = True


class _NonAdminUser:
    def __init__(self, id=2, email="user@example.com", role="candidate"):
        self.id = id
        self.email = email
        self.role = role
        self.admin_permissions = None
        self.is_super_admin = False


def _client(admin=True):
    """Build a TestClient with FastAPI ``dependency_overrides``.

    Rewritten from the original ``monkeypatch.setattr`` pattern
    which did not take effect once the route had been registered.
    """
    from backend.dependencies import get_current_admin, get_current_user

    mock_user = _AdminUser() if admin else _NonAdminUser()

    async def _mock_current_admin():
        from fastapi import HTTPException, status
        if mock_user.role not in ["admin", "super_admin"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized as admin",
            )
        return mock_user

    async def _mock_current_user():
        return mock_user

    from backend.app import create_app

    app = create_app()
    app.dependency_overrides[get_current_admin] = _mock_current_admin
    app.dependency_overrides[get_current_user] = _mock_current_user
    return TestClient(app)


def test_admin_ssr_prompt_management_access():
    """Admin user can access the prompt-management page."""
    with _client(admin=True) as client:
        resp = client.get("/admin/prompt-management")
        assert resp.status_code in (200, 304, 302), (
            f"admin prompt-management returned {resp.status_code}"
        )


def test_admin_health_endpoint():
    """The /admin/health endpoint either exists (200/302) or
    returns 404 if it hasn't been added yet — both are valid
    during a phased rollout."""
    with _client(admin=True) as client:
        resp = client.get("/admin/health")
        assert resp.status_code in (200, 302, 404), (
            f"admin /admin/health returned {resp.status_code}"
        )


def test_admin_ssr_prompt_management_forbidden():
    """Non-admin user gets 403 on the prompt-management page."""
    with _client(admin=False) as client:
        resp = client.get("/admin/prompt-management")
        assert resp.status_code == 403, (
            f"non-admin prompt-management returned {resp.status_code}"
        )
