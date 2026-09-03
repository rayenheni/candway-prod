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

from locust import HttpUser, between, tag, task

TEST_EMAIL = "candidate@test.com"
TEST_PASSWORD = "testpass123"


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
        self.client.post(
            "/api/v1/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD, "role": "candidate"},
        )


class AuthenticatedCandidate(HttpUser):
    """Simulates logged-in candidates browsing and taking interviews."""

    wait_time = between(2, 8)
    weight = 2

    def on_start(self):
        response = self.client.post(
            "/api/v1/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD, "role": "candidate"},
        )
        if response.status_code == 200:
            data = response.json()
            self.token = data.get("access_token", "")
            self.client.headers.update({"Authorization": f"Bearer {self.token}"})

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
        response = self.client.post(
            "/api/v1/auth/login",
            json={
                "email": "recruiter@techcorp.com",
                "password": "recruiter123",
                "role": "recruiter",
            },
        )
        if response.status_code == 200:
            data = response.json()
            self.token = data.get("access_token", "")
            self.client.headers.update({"Authorization": f"Bearer {self.token}"})

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
        self.client.get("/api/v1/recruiter/jobs")

    @tag("api")
    @task(4)
    def api_candidates(self):
        self.client.get("/api/v1/recruiter/candidates")

    @tag("api")
    @task(3)
    def api_pipeline(self):
        self.client.get("/api/v1/recruiter/pipeline")

    @tag("api")
    @task(2)
    def api_analytics(self):
        self.client.get("/api/v1/analytics/recruiter/overview")


class CandidateHeavyUser(HttpUser):
    """
    Stress-tests candidate-specific endpoints.
    Focuses on the N+1 fixed endpoints and timer sync.
    """

    wait_time = between(0.5, 2)
    weight = 1

    def on_start(self):
        response = self.client.post(
            "/api/v1/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD, "role": "candidate"},
        )
        if response.status_code == 200:
            data = response.json()
            self.token = data.get("access_token", "")
            self.client.headers.update({"Authorization": f"Bearer {self.token}"})

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
        self.client.get("/api/v1/ai/interview/time")

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
        self.client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})

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
