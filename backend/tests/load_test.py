"""
Candway Load Tests (Locust)
============================
Simulates realistic user behavior for performance testing.

Usage:
    locust -f backend/tests/load_test.py --headless -u 50 -r 5 --run-time 60s --host http://localhost:8002
    locust -f backend/tests/load_test.py --web-host 127.0.0.1  # Web UI at http://127.0.0.1:8089

Candidate-specific scenarios test:
- Dashboard with eager-loaded applications (N+1 fix)
- Application history with batch-loaded jobs
- Profile comprehensive endpoint
- Interview time sync endpoint
"""

import requests
from locust import HttpUser, between, events, tag, task

TEST_EMAIL = "candidate@test.com"
TEST_PASSWORD = "testpass123"
RECRUITER_EMAIL = "recruiter@techcorp.com"
RECRUITER_PASSWORD = "recruiter123"
# Application owned by TEST_EMAIL, created by scripts/perf_seed.py.
INTERVIEW_APP_ID = 900001

# CI quality gate (see the quitting listener). Locust's default is "exit 1 on
# any failure"; expected statuses are accepted explicitly per request instead.
MAX_FAIL_RATIO = 0.01
MAX_P95_MS = 5000

# One login per role, done once before users spawn. /api/v1/auth/login is
# rate-limited per IP (10/min) and every simulated user shares one IP, so
# per-user logins (and the anonymous login attempts below) would exhaust the
# budget and turn every authenticated scenario into 401s.
_TOKENS: dict[str, str] = {}


def _login(host: str, email: str, password: str) -> str:
    resp = requests.post(
        f"{host}/api/v1/auth/login",
        json={"email": email, "password": password},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


@events.test_start.add_listener
def _login_once(environment, **kwargs):
    host = environment.host
    _TOKENS["candidate"] = _login(host, TEST_EMAIL, TEST_PASSWORD)
    _TOKENS["recruiter"] = _login(host, RECRUITER_EMAIL, RECRUITER_PASSWORD)


@events.quitting.add_listener
def _quality_gate(environment, **kwargs):
    total = environment.stats.total
    p95 = total.get_response_time_percentile(0.95) or 0
    failed = total.fail_ratio > MAX_FAIL_RATIO or p95 > MAX_P95_MS
    print(
        f"[perf-gate] requests={total.num_requests} "
        f"fail_ratio={total.fail_ratio:.4f} (max {MAX_FAIL_RATIO}) "
        f"p95={p95}ms (max {MAX_P95_MS}) -> {'FAIL' if failed else 'PASS'}"
    )
    environment.process_exit_code = 1 if failed else 0


def _use_token(user: HttpUser, role: str) -> None:
    user.client.headers.update({"Authorization": f"Bearer {_TOKENS[role]}"})
    # Mutating requests need the double-submit CSRF token, obtained the same
    # way the SPA gets it (see backend/tests/conftest.py).
    resp = user.client.get("/login", name="csrf bootstrap")
    csrf = resp.headers.get("X-CSRF-Token") or user.client.cookies.get("csrf_token")
    if csrf:
        user.client.headers.update({"X-CSRF-Token": csrf})


def _expect(user: HttpUser, method: str, path: str, ok: tuple, **kwargs) -> None:
    """Request whose non-2xx status is an expected, correct answer."""
    with user.client.request(method, path, catch_response=True, **kwargs) as r:
        if r.status_code in ok:
            r.success()
        else:
            r.failure(f"unexpected status {r.status_code}")


class AnonymousUser(HttpUser):
    """Simulates unauthenticated visitors browsing public pages."""

    wait_time = between(1, 5)
    weight = 3

    @tag("public")
    @task(10)
    def view_homepage(self):
        self.client.get("/")

    @tag("public")
    @task(5)
    def view_public_jobs(self):
        self.client.get("/api/v1/jobs/public")

    @tag("public")
    @task(5)
    def view_public_courses(self):
        self.client.get("/api/v1/courses/public")

    @tag("public")
    @task(3)
    def view_pricing(self):
        self.client.get("/pricing.html")

    @tag("auth")
    @task(2)
    def view_login_page(self):
        self.client.get("/login.html")

    @tag("auth")
    @task(1)
    def attempt_login(self):
        # Wrong password on purpose: exercises the login path and its per-IP
        # limiter without locking the shared test account.
        _expect(
            self,
            "POST",
            "/api/v1/auth/login",
            (401, 429),
            json={"email": "nobody@test.com", "password": "wrong-password"},
        )


class AuthenticatedCandidate(HttpUser):
    """Simulates logged-in candidates browsing and taking interviews."""

    wait_time = between(2, 8)
    weight = 2

    def on_start(self):
        _use_token(self, "candidate")

    @tag("candidate")
    @task(8)
    def view_dashboard(self):
        self.client.get("/candidate/dashboard.html")

    @tag("api")
    @task(6)
    def api_dashboard_data(self):
        self.client.get("/api/v1/candidate/dashboard")

    @tag("api")
    @task(4)
    def api_profile(self):
        self.client.get("/api/v1/auth/me")

    @tag("api")
    @task(3)
    def api_jobs(self):
        self.client.get("/api/v1/jobs/public")

    @tag("api")
    @task(2)
    def api_learning(self):
        self.client.get("/api/v1/courses/public")

    @tag("api")
    @task(1)
    def update_profile(self):
        self.client.put(
            "/api/v1/auth/me",
            json={
                "name": "Load Test User",
                "headline": "Performance Engineer",
                "bio": "Testing system limits",
            },
        )


class AuthenticatedRecruiter(HttpUser):
    """Simulates recruiters managing candidates and jobs."""

    wait_time = between(3, 10)
    weight = 2

    def on_start(self):
        _use_token(self, "recruiter")

    @tag("recruiter")
    @task(8)
    def view_dashboard(self):
        self.client.get("/recruiter/dashboard.html")

    @tag("api")
    @task(6)
    def api_dashboard(self):
        self.client.get("/api/v1/recruiter/dashboard/stats")

    @tag("api")
    @task(5)
    def api_jobs(self):
        self.client.get("/api/v1/recruiter/jobs/my")

    @tag("api")
    @task(4)
    def api_candidates(self):
        self.client.get("/api/v1/recruiter/candidates")

    @tag("api")
    @task(3)
    def api_pipeline(self):
        self.client.get("/api/v1/analytics/pipeline")

    @tag("api")
    @task(2)
    def api_analytics(self):
        self.client.get("/api/v1/analytics/dashboard")


class CandidateHeavyUser(HttpUser):
    """
    Stress-tests candidate-specific endpoints.
    Focuses on the N+1 fixed endpoints and timer sync.
    """

    wait_time = between(0.5, 2)
    weight = 1

    def on_start(self):
        _use_token(self, "candidate")

    @tag("stress", "candidate")
    @task(5)
    def stress_dashboard(self):
        self.client.get("/api/v1/candidate/dashboard")

    @tag("stress", "candidate")
    @task(4)
    def stress_application_history(self):
        self.client.get("/api/v1/candidate/applications/me/history")

    @tag("stress", "candidate")
    @task(3)
    def stress_profile_comprehensive(self):
        self.client.get("/api/v1/candidate/profile/comprehensive")

    @tag("stress", "candidate")
    @task(3)
    def stress_interview_time_sync(self):
        self.client.get(
            f"/api/v1/ai/interview/time?app_id={INTERVIEW_APP_ID}",
            name="/api/v1/ai/interview/time",
        )

    @tag("stress", "candidate")
    @task(2)
    def stress_talent_graph(self):
        self.client.get("/api/v1/candidate/talent-graph")

    @tag("stress", "candidate")
    @task(2)
    def stress_job_matches(self):
        self.client.get("/api/v1/candidate/jobs/matches")


class ApiHeavyUser(HttpUser):
    """Stress-tests API endpoints with rapid requests."""

    wait_time = between(0.1, 0.5)
    weight = 1

    @tag("stress")
    @task(5)
    def stress_auth_me(self):
        token = "eyJhbGciOiJIUzI1NiJ9.dG9rZW4.QWxhZGRpbk9wZW5TZXNhbWU"
        _expect(
            self,
            "GET",
            "/api/v1/auth/me",
            (401,),
            headers={"Authorization": f"Bearer {token}"},
        )

    @tag("stress")
    @task(5)
    def stress_public_jobs(self):
        self.client.get("/api/v1/jobs/public")

    @tag("stress")
    @task(3)
    def stress_public_courses(self):
        self.client.get("/api/v1/courses/public")

    @tag("health")
    @task(2)
    def health_check(self):
        self.client.get("/api/v1/monitoring/health")
