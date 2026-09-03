import pytest
from fastapi.testclient import TestClient


class _AdminUser:
    def __init__(self, id=1, email="admin@masar.com", role="admin"):
        self.id = id
        self.email = email
        self.role = role
        # Granting super_admin short-circuits route-level
        # ``check_permission`` so the SSR surface test asserts
        # the page is reachable, not the RBAC matrix.
        self.admin_permissions = "view_analytics,manage_users,manage_jobs"
        self.is_super_admin = True


class _NonAdminUser:
    def __init__(self, id=99, email="user@example.com", role="candidate"):
        self.id = id
        self.email = email
        self.role = role
        self.admin_permissions = None
        self.is_super_admin = False


def _make_app():
    from backend.app import create_app
    return create_app()


def _client(admin=True):
    """Build a TestClient with the admin dependency properly overridden.

    Uses FastAPI's dependency_overrides (the only correct mechanism for
    overriding Depends()-wired functions after router registration).
    Monkeypatching the module attribute has NO effect on already-wired deps.
    """
    from backend.dependencies import get_current_admin, get_current_user

    mock_user = _AdminUser() if admin else _NonAdminUser()

    async def _mock_current_admin():
        if mock_user.role not in ["admin", "super_admin"]:
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized as admin",
            )
        return mock_user

    async def _mock_current_user():
        return mock_user

    app = _make_app()
    app.dependency_overrides[get_current_admin] = _mock_current_admin
    app.dependency_overrides[get_current_user] = _mock_current_user
    return TestClient(app)


class TestAdminAPIRBAC:
    @pytest.fixture
    def admin_client(self):
        return _client(admin=True)

    @pytest.fixture
    def non_admin_client(self):
        return _client(admin=False)

    def test_admin_analytics_overview_access(self, admin_client):
        resp = admin_client.get("/api/v1/admin/analytics/overview")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"

    def test_admin_analytics_overview_forbidden(self, non_admin_client):
        resp = non_admin_client.get("/api/v1/admin/analytics/overview")
        assert resp.status_code == 403

    def test_admin_users_access(self, admin_client):
        resp = admin_client.get("/api/v1/admin/users")
        assert resp.status_code == 200

    def test_admin_users_forbidden(self, non_admin_client):
        resp = non_admin_client.get("/api/v1/admin/users")
        assert resp.status_code == 403

    def test_admin_jobs_access(self, admin_client):
        resp = admin_client.get("/api/v1/admin/jobs")
        assert resp.status_code == 200

    def test_admin_jobs_forbidden(self, non_admin_client):
        resp = non_admin_client.get("/api/v1/admin/jobs")
        assert resp.status_code == 403

    def test_admin_health_access(self, admin_client):
        resp = admin_client.get("/api/v1/admin/health")
        assert resp.status_code == 200

    def test_admin_health_forbidden(self, non_admin_client):
        resp = non_admin_client.get("/api/v1/admin/health")
        assert resp.status_code == 403

    def test_admin_stats_access(self, admin_client):
        resp = admin_client.get("/api/v1/admin/stats")
        assert resp.status_code == 200

    def test_admin_stats_forbidden(self, non_admin_client):
        resp = non_admin_client.get("/api/v1/admin/stats")
        assert resp.status_code == 403

    def test_admin_payments_access(self, admin_client):
        resp = admin_client.get("/api/v1/admin/payments")
        assert resp.status_code == 200

    def test_admin_payments_forbidden(self, non_admin_client):
        resp = non_admin_client.get("/api/v1/admin/payments")
        assert resp.status_code == 403

    def test_admin_subscriptions_access(self, admin_client):
        resp = admin_client.get("/api/v1/admin/subscriptions")
        assert resp.status_code == 200

    def test_admin_subscriptions_forbidden(self, non_admin_client):
        resp = non_admin_client.get("/api/v1/admin/subscriptions")
        assert resp.status_code == 403

    def test_admin_courses_access(self, admin_client):
        resp = admin_client.get("/api/v1/admin/courses")
        assert resp.status_code == 200

    def test_admin_courses_forbidden(self, non_admin_client):
        resp = non_admin_client.get("/api/v1/admin/courses")
        assert resp.status_code == 403

    def test_admin_logs_access(self, admin_client):
        resp = admin_client.get("/api/v1/admin/logs")
        assert resp.status_code == 200

    def test_admin_logs_forbidden(self, non_admin_client):
        resp = non_admin_client.get("/api/v1/admin/logs")
        assert resp.status_code == 403

    def test_admin_settings_access(self, admin_client):
        resp = admin_client.get("/api/v1/admin/settings")
        assert resp.status_code == 200

    def test_admin_settings_forbidden(self, non_admin_client):
        resp = non_admin_client.get("/api/v1/admin/settings")
        assert resp.status_code == 403

    def test_admin_prompts_access(self, admin_client):
        resp = admin_client.get("/api/v1/admin/prompts")
        assert resp.status_code == 200

    def test_admin_prompts_forbidden(self, non_admin_client):
        resp = non_admin_client.get("/api/v1/admin/prompts")
        assert resp.status_code == 403

    def test_admin_tickets_access(self, admin_client):
        resp = admin_client.get("/api/v1/admin/tickets")
        assert resp.status_code == 200

    def test_admin_tickets_forbidden(self, non_admin_client):
        resp = non_admin_client.get("/api/v1/admin/tickets")
        assert resp.status_code == 403

    def test_admin_verifications_access(self, admin_client):
        resp = admin_client.get("/api/v1/admin/verifications")
        assert resp.status_code == 200

    def test_admin_verifications_forbidden(self, non_admin_client):
        resp = non_admin_client.get("/api/v1/admin/verifications")
        assert resp.status_code == 403

    def test_admin_announcements_access(self, admin_client):
        resp = admin_client.get("/api/v1/admin/announcements/active")
        assert resp.status_code == 200

    def test_admin_announcements_forbidden(self, non_admin_client):
        # /api/v1/admin/announcements/active is intentionally a
        # public endpoint (powers the public landing-page
        # banner). A non-admin must be able to read it.
        resp = non_admin_client.get("/api/v1/admin/announcements/active")
        assert resp.status_code == 200

    def test_admin_marketing_leads_access(self, admin_client):
        resp = admin_client.get("/api/v1/admin/marketing/leads")
        assert resp.status_code == 200

    def test_admin_marketing_leads_forbidden(self, non_admin_client):
        resp = non_admin_client.get("/api/v1/admin/marketing/leads")
        assert resp.status_code == 403

    def test_admin_payouts_access(self, admin_client):
        resp = admin_client.get("/api/v1/admin/payouts")
        assert resp.status_code == 200

    def test_admin_payouts_forbidden(self, non_admin_client):
        resp = non_admin_client.get("/api/v1/admin/payouts")
        assert resp.status_code == 403

    def test_admin_plans_access(self, admin_client):
        resp = admin_client.get("/api/v1/admin/plans")
        assert resp.status_code == 200

    def test_admin_plans_forbidden(self, non_admin_client):
        resp = non_admin_client.get("/api/v1/admin/plans")
        assert resp.status_code == 403

    def test_admin_upgrade_requests_access(self, admin_client):
        resp = admin_client.get("/api/v1/admin/upgrade-requests")
        assert resp.status_code == 200

    def test_admin_upgrade_requests_forbidden(self, non_admin_client):
        resp = non_admin_client.get("/api/v1/admin/upgrade-requests")
        assert resp.status_code == 403

    def test_admin_coupons_access(self, admin_client):
        resp = admin_client.get("/api/v1/admin/coupons")
        assert resp.status_code == 200

    def test_admin_coupons_forbidden(self, non_admin_client):
        resp = non_admin_client.get("/api/v1/admin/coupons")
        assert resp.status_code == 403

    def test_admin_ab_testing_access(self, admin_client):
        resp = admin_client.get("/api/v1/admin/ab-testing/config")
        assert resp.status_code == 200

    def test_admin_ab_testing_forbidden(self, non_admin_client):
        resp = non_admin_client.get("/api/v1/admin/ab-testing/config")
        assert resp.status_code == 403

    def test_admin_blogs_access(self, admin_client):
        resp = admin_client.get("/api/v1/admin/blogs")
        assert resp.status_code == 200

    def test_admin_blogs_forbidden(self, non_admin_client):
        resp = non_admin_client.get("/api/v1/admin/blogs")
        assert resp.status_code == 403

    def test_admin_invoices_access(self, admin_client):
        resp = admin_client.get("/api/v1/admin/invoices")
        assert resp.status_code == 200

    def test_admin_invoices_forbidden(self, non_admin_client):
        resp = non_admin_client.get("/api/v1/admin/invoices")
        assert resp.status_code == 403

    def test_admin_user_usage_access(self, admin_client):
        resp = admin_client.get("/api/v1/admin/users/usage")
        assert resp.status_code == 200

    def test_admin_user_usage_forbidden(self, non_admin_client):
        resp = non_admin_client.get("/api/v1/admin/users/usage")
        assert resp.status_code == 403

    def test_admin_opportunities_access(self, admin_client):
        resp = admin_client.get("/api/v1/admin/opportunities")
        assert resp.status_code == 200

    def test_admin_opportunities_forbidden(self, non_admin_client):
        resp = non_admin_client.get("/api/v1/admin/opportunities")
        assert resp.status_code == 403

    def test_admin_pages_access(self, admin_client):
        resp = admin_client.get("/api/v1/admin/pages/home")
        assert resp.status_code in (200, 404)

    def test_admin_pages_forbidden(self, non_admin_client):
        resp = non_admin_client.get("/api/v1/admin/pages/home")
        assert resp.status_code == 403

    def test_admin_background_jobs_access(self, admin_client):
        resp = admin_client.get("/api/v1/admin/background-jobs")
        assert resp.status_code == 200

    def test_admin_background_jobs_forbidden(self, non_admin_client):
        resp = non_admin_client.get("/api/v1/admin/background-jobs")
        assert resp.status_code == 403


class TestAdminSSR:
    @pytest.fixture
    def admin_client(self):
        return _client(admin=True)

    @pytest.fixture
    def non_admin_client(self):
        return _client(admin=False)

    _ADMIN_PAGES = [
        "/admin/dashboard",
        "/admin/ai-sales",
        "/admin/analytics",
        "/admin/announcements",
        "/admin/categories",
        "/admin/content",
        "/admin/invoices",
        "/admin/jobs",
        "/admin/marketing",
        "/admin/opportunities",
        "/admin/recruiter-usage",
        "/admin/support",
        "/admin/technical",
        "/admin/users",
        "/admin/verifications",
        "/admin/prompt-management",
        "/admin/subscriptions",
        "/admin/courses",
        "/admin/settings",
        "/admin/payments",
    ]

    _AUTH_PAGES = ["/login", "/register", "/forgot-password", "/reset-password"]

    @pytest.mark.parametrize("page", _ADMIN_PAGES)
    def test_admin_ssr_pages_require_admin(self, non_admin_client, page):
        resp = non_admin_client.get(page, follow_redirects=False)
        assert resp.status_code == 403, f"{page} returned {resp.status_code}"

    @pytest.mark.parametrize("page", _ADMIN_PAGES)
    def test_admin_ssr_pages_accessible_to_admin(self, admin_client, page):
        resp = admin_client.get(page, follow_redirects=False)
        assert resp.status_code in (200, 302), f"{page} returned {resp.status_code}"