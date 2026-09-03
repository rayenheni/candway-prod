"""
Smoke Tests: Recruiter Platform Enhancements v5.0
====================================================
Tests all 14 enhancement features:
1. Quick Actions (one-click invite/shortlist/reject/archive)
2. Hover Previews (rich candidate preview on hover)
3. Undo System (10-second rollback window)
4. Custom Pipeline Stages (CRUD + defaults)
5. Automation Rules Engine (CRUD + evaluate)
6. Tagged Notes (CRUD + filter)
7. Interview Scorecards (CRUD + submit + view)
8. Webhook Integrations (CRUD - skip live test)
9. Time-in-Stage Analytics
10. Source Attribution Analytics
11. Cost-per-Hire Analytics
12. Campaign Cost Tracking
13. Interview Debrief Auto-Summary
14. Stage Transition Tracking
"""

import os

import pytest

# Mock environment before any backend imports
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["SECRET_KEY"] = "test_secret_key_for_jwt_encoding_12345"
os.environ["ALGORITHM"] = "HS256"
os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = "30"
os.environ["DEBUG"] = "false"

from fastapi.testclient import TestClient

import backend.database
import backend.dependencies
from backend.database import (
    Application,
    Base,
    BatchJob,
    Company,
    CompanyMember,
    Interview,
    Job,
    User,
)
from backend.dependencies import pwd_context
from backend.main import app

# Force test engine
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
    token = resp.headers.get("X-CSRF-Token") or resp.cookies.get("csrf_token")
    if token:
        return token
    return ""


def _login(client, email, password):
    csrf = _get_csrf_token(client)
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
        headers={"X-CSRF-Token": csrf},
    )
    data = resp.json()
    token = data.get("access_token")
    return {
        "Authorization": f"Bearer {token}",
        "X-CSRF-Token": csrf,
    }


@pytest.fixture(scope="module")
def client():
    Base.metadata.create_all(bind=test_engine)
    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="module")
def recruiter(client):
    """Create a tenant-scoped recruiter user for all tests."""
    db = backend.database.SessionLocal()

    # Candway jobs are tenant-scoped: create the company first.
    company = Company(
        name="Smoke Test Co",
        slug="smoke-test-co",
        tier="pro",
    )
    db.add(company)
    db.flush()

    user = User(
        email="smoke_recruiter@test.com",
        name="Smoke Recruiter",
        hashed_password=pwd_context.hash("recruiter123"),
        role="recruiter",
        email_verified=True,
        company_name="Smoke Test Co",
        tier="pro",
    )
    db.add(user)
    db.flush()

    membership = CompanyMember(
        company_id=company.id,
        user_id=user.id,
        role="admin",
        is_active=True,
    )
    db.add(membership)
    db.commit()

    uid = user.id
    db.close()

    # Fetch fresh objects to avoid detached-session issues.
    db2 = backend.database.SessionLocal()
    fresh = db2.query(User).filter(User.id == uid).first()

    yield fresh

    db2.close()


@pytest.fixture(scope="module")
def auth(client, recruiter):
    return _login(client, "smoke_recruiter@test.com", "recruiter123")


@pytest.fixture(scope="module")
def job(client, auth, recruiter):
    db = backend.database.SessionLocal()

    membership = (
        db.query(CompanyMember)
        .filter(
            CompanyMember.user_id == recruiter.id,
            CompanyMember.is_active.is_(True),
        )
        .first()
    )

    assert membership is not None, "Recruiter must have an active company membership"

    j = Job(
        title="Smoke Test Engineer",
        description="Test job",
        recruiter_id=recruiter.id,
        company_id=membership.company_id,
        is_active=True,
    )
    db.add(j)
    db.commit()
    db.refresh(j)
    jid = j.id
    db.close()
    db2 = backend.database.SessionLocal()
    fresh = db2.query(Job).filter(Job.id == jid).first()
    yield fresh
    db2.close()


@pytest.fixture(scope="module")
def batch(client, auth, recruiter):
    db = backend.database.SessionLocal()

    membership = (
        db.query(CompanyMember)
        .filter(
            CompanyMember.user_id == recruiter.id,
            CompanyMember.is_active.is_(True),
        )
        .first()
    )

    assert membership is not None, "Recruiter must have an active company membership"

    b = BatchJob(
        title="Smoke Test Batch",
        recruiter_id=recruiter.id,
        company_id=membership.company_id,
        status="active",
    )
    db.add(b)
    db.commit()
    db.refresh(b)
    bid = b.id
    db.close()
    db2 = backend.database.SessionLocal()
    fresh = db2.query(BatchJob).filter(BatchJob.id == bid).first()
    yield fresh
    db2.close()


@pytest.fixture(scope="module")
def application(client, auth, recruiter, job, batch):
    db = backend.database.SessionLocal()
    a = Application(
        full_name="Smoke Candidate",
        email="smoke_candidate@test.com",
        declared_role="Engineer",
        status="applied",
        job_id=job.id,
        batch_id=batch.id,
        assigned_to=recruiter.id,
        source="LinkedIn",
        interview_state="not_started",
        interview_progress=0,
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    aid = a.id
    db.close()
    db2 = backend.database.SessionLocal()
    fresh = db2.query(Application).filter(Application.id == aid).first()
    yield fresh
    db2.close()


@pytest.fixture
def interview(client, auth, application, recruiter):
    db = backend.database.SessionLocal()
    i = Interview(
        application_id=application.id,
        type="technical",
        status="scheduled",
        scheduled_time=None,
    )
    db.add(i)
    db.commit()
    db.refresh(i)
    iid = i.id
    db.close()
    db2 = backend.database.SessionLocal()
    fresh = db2.query(Interview).filter(Interview.id == iid).first()
    yield fresh
    db2.close()


# ============================================================================
# 1. QUICK ACTIONS
# ============================================================================


class TestQuickActions:
    def test_shortlist_action(self, client, auth, application):
        resp = client.post(
            "/api/v1/recruiter/enhancements/quick-action",
            json={"action": "shortlist", "app_id": application.id},
            headers=auth,
        )
        print("DEBUG STATUS:", resp.status_code)
        print("DEBUG BODY:", resp.text)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["action"] == "shortlist"
        assert data["new_status"] == "interviewing"
        assert "undo_id" in data

    def test_reject_action(self, client, auth, application):
        resp = client.post(
            "/api/v1/recruiter/enhancements/quick-action",
            json={"action": "reject", "app_id": application.id},
            headers=auth,
        )
        assert resp.status_code == 200
        assert resp.json()["action"] == "reject"
        assert resp.json()["new_status"] == "rejected"

    def test_archive_action(self, client, auth, application):
        resp = client.post(
            "/api/v1/recruiter/enhancements/quick-action",
            json={"action": "archive", "app_id": application.id},
            headers=auth,
        )
        assert resp.status_code == 200
        assert resp.json()["action"] == "archive"
        assert resp.json()["new_status"] == "archived"

    def test_invalid_action(self, client, auth, application):
        resp = client.post(
            "/api/v1/recruiter/enhancements/quick-action",
            json={"action": "teleport", "app_id": application.id},
            headers=auth,
        )
        assert resp.status_code == 400

    def test_missing_app(self, client, auth):
        resp = client.post(
            "/api/v1/recruiter/enhancements/quick-action",
            json={"action": "shortlist", "app_id": 999999},
            headers=auth,
        )
        assert resp.status_code == 404


# ============================================================================
# 2. UNDO SYSTEM
# ============================================================================


class TestUndoSystem:
    def test_pending_undos(self, client, auth):
        resp = client.get("/api/v1/recruiter/enhancements/undo/pending", headers=auth)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_undo_not_found(self, client, auth):
        resp = client.post("/api/v1/recruiter/enhancements/undo/999999", headers=auth)
        assert resp.status_code == 404


# ============================================================================
# 3. HOVER PREVIEW
# ============================================================================


class TestHoverPreview:
    def test_hover_preview(self, client, auth, application):
        resp = client.get(
            f"/api/v1/recruiter/enhancements/hover-preview/{application.id}",
            headers=auth,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "candidate_name" in data
        assert "overall_score" in data
        assert "cv_score" in data
        assert "trust_score" in data
        assert "skills" in data
        assert "strengths" in data
        assert "weaknesses" in data
        assert "notes_count" in data
        assert "comments_count" in data

    def test_hover_preview_missing(self, client, auth):
        resp = client.get(
            "/api/v1/recruiter/enhancements/hover-preview/999999", headers=auth
        )
        assert resp.status_code == 404


# ============================================================================
# 4. CUSTOM PIPELINE STAGES
# ============================================================================


class TestCustomPipelineStages:
    def test_get_defaults(self, client, auth):
        resp = client.get("/api/v1/recruiter/enhancements/stages", headers=auth)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        if data and "slug" in data[0]:
            slugs = [s["slug"] for s in data]
            assert "applied" in slugs

    def test_create_stage(self, client, auth):
        resp = client.post(
            "/api/v1/recruiter/enhancements/stages",
            json={
                "name": "Technical Review",
                "slug": "tech_review",
                "color": "#ff5722",
            },
            headers=auth,
        )
        assert resp.status_code == 201
        assert resp.json()["success"] is True
        assert resp.json()["stage"]["name"] == "Technical Review"

    def test_duplicate_slug(self, client, auth):
        resp = client.post(
            "/api/v1/recruiter/enhancements/stages",
            json={"name": "Duplicate", "slug": "tech_review", "color": "#000"},
            headers=auth,
        )
        assert resp.status_code == 400

    def test_update_stage(self, client, auth):
        # Create first
        resp = client.post(
            "/api/v1/recruiter/enhancements/stages",
            json={"name": "Update Me", "slug": "update_me", "color": "#000"},
            headers=auth,
        )
        stage_id = resp.json()["stage"]["id"]
        # Update
        resp = client.patch(
            f"/api/v1/recruiter/enhancements/stages/{stage_id}",
            json={"name": "Updated Stage", "color": "#10b981"},
            headers=auth,
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_delete_stage(self, client, auth):
        resp = client.post(
            "/api/v1/recruiter/enhancements/stages",
            json={"name": "Delete Me", "slug": "delete_me"},
            headers=auth,
        )
        stage_id = resp.json()["stage"]["id"]
        resp = client.delete(
            f"/api/v1/recruiter/enhancements/stages/{stage_id}", headers=auth
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True


# ============================================================================
# 5. AUTOMATION RULES
# ============================================================================


class TestAutomationRules:
    def test_create_rule(self, client, auth):
        resp = client.post(
            "/api/v1/recruiter/enhancements/automation-rules",
            json={
                "name": "Auto Shortlist High Scorers",
                "description": "Move to interviewing if score >= 80",
                "trigger_json": {
                    "type": "score_threshold",
                    "field": "overall_score",
                    "operator": ">=",
                    "value": 80,
                },
                "action_json": {"type": "move_stage", "target_stage": "interviewing"},
            },
            headers=auth,
        )
        assert resp.status_code == 201
        assert resp.json()["success"] is True
        assert "rule_id" in resp.json()

    def test_get_rules(self, client, auth):
        # Create one first
        client.post(
            "/api/v1/recruiter/enhancements/automation-rules",
            json={
                "name": "Test Rule",
                "trigger_json": {"type": "status_change", "status": "applied"},
                "action_json": {"type": "move_stage", "target_stage": "invited"},
            },
            headers=auth,
        )
        resp = client.get(
            "/api/v1/recruiter/enhancements/automation-rules", headers=auth
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
        assert len(resp.json()) > 0

    def test_update_rule(self, client, auth):
        resp = client.post(
            "/api/v1/recruiter/enhancements/automation-rules",
            json={
                "name": "Update Rule",
                "trigger_json": {"type": "status_change", "status": "new"},
                "action_json": {"type": "move_stage", "target_stage": "review"},
            },
            headers=auth,
        )
        rule_id = resp.json()["rule_id"]
        resp = client.patch(
            f"/api/v1/recruiter/enhancements/automation-rules/{rule_id}",
            json={"name": "Updated Rule", "is_active": False},
            headers=auth,
        )
        assert resp.status_code == 200

    def test_delete_rule(self, client, auth):
        resp = client.post(
            "/api/v1/recruiter/enhancements/automation-rules",
            json={
                "name": "Delete Rule",
                "trigger_json": {"type": "status_change", "status": "x"},
                "action_json": {"type": "move_stage", "target_stage": "y"},
            },
            headers=auth,
        )
        rule_id = resp.json()["rule_id"]
        resp = client.delete(
            f"/api/v1/recruiter/enhancements/automation-rules/{rule_id}", headers=auth
        )
        assert resp.status_code == 200

    def test_evaluate_rules(self, client, auth, application):
        # Create a matching rule
        client.post(
            "/api/v1/recruiter/enhancements/automation-rules",
            json={
                "name": "Score Rule",
                "trigger_json": {
                    "type": "score_threshold",
                    "field": "overall_score",
                    "operator": ">=",
                    "value": 50,
                },
                "action_json": {"type": "move_stage", "target_stage": "shortlisted"},
            },
            headers=auth,
        )
        resp = client.post(
            f"/api/v1/recruiter/enhancements/automation-rules/evaluate?app_id={application.id}",
            headers=auth,
        )
        assert resp.status_code == 200
        assert "triggered_rules" in resp.json()


# ============================================================================
# 6. TAGGED NOTES
# ============================================================================


class TestTaggedNotes:
    def test_create_note(self, client, auth, application):
        resp = client.post(
            "/api/v1/recruiter/enhancements/notes",
            json={
                "application_id": application.id,
                "content": "Strong communication skills, good culture fit",
                "tags": ["communication", "culture-fit"],
                "priority": "high",
            },
            headers=auth,
        )
        assert resp.status_code == 201
        assert resp.json()["success"] is True
        assert "note_id" in resp.json()

    def test_get_notes(self, client, auth, application):
        # Create one first
        client.post(
            "/api/v1/recruiter/enhancements/notes",
            json={
                "application_id": application.id,
                "content": "Test note",
                "tags": ["test"],
                "priority": "normal",
            },
            headers=auth,
        )
        resp = client.get(
            f"/api/v1/recruiter/enhancements/notes/{application.id}",
            headers=auth,
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
        assert len(resp.json()) > 0
        note = resp.json()[0]
        assert "content" in note
        assert "tags" in note
        assert "priority" in note
        assert "is_pinned" in note

    def test_update_note(self, client, auth, application):
        resp = client.post(
            "/api/v1/recruiter/enhancements/notes",
            json={
                "application_id": application.id,
                "content": "Update me",
                "tags": ["old"],
            },
            headers=auth,
        )
        note_id = resp.json()["note_id"]
        resp = client.patch(
            f"/api/v1/recruiter/enhancements/notes/{note_id}",
            json={
                "content": "Updated content",
                "tags": ["new", "important"],
                "is_pinned": True,
            },
            headers=auth,
        )
        assert resp.status_code == 200

    def test_resolve_note(self, client, auth, application):
        resp = client.post(
            "/api/v1/recruiter/enhancements/notes",
            json={
                "application_id": application.id,
                "content": "Resolve me",
                "tags": [],
            },
            headers=auth,
        )
        note_id = resp.json()["note_id"]
        resp = client.patch(
            f"/api/v1/recruiter/enhancements/notes/{note_id}",
            json={"is_resolved": True},
            headers=auth,
        )
        assert resp.status_code == 200

    def test_delete_note(self, client, auth, application):
        resp = client.post(
            "/api/v1/recruiter/enhancements/notes",
            json={"application_id": application.id, "content": "Delete me", "tags": []},
            headers=auth,
        )
        note_id = resp.json()["note_id"]
        resp = client.delete(
            f"/api/v1/recruiter/enhancements/notes/{note_id}", headers=auth
        )
        assert resp.status_code == 200


# ============================================================================
# 7. INTERVIEW SCORECARDS
# ============================================================================


class TestInterviewScorecards:
    def test_create_scorecard(self, client, auth):
        resp = client.post(
            "/api/v1/recruiter/enhancements/scorecards",
            json={
                "role_type": "engineer",
                "name": "Technical Assessment",
                "description": "Core engineering skills",
                "criteria_json": [
                    {"name": "coding", "weight": 3, "max_score": 5},
                    {"name": "system_design", "weight": 2, "max_score": 5},
                    {"name": "communication", "weight": 1, "max_score": 5},
                ],
            },
            headers=auth,
        )
        assert resp.status_code == 201
        assert resp.json()["success"] is True
        assert "scorecard_id" in resp.json()

    def test_get_scorecards(self, client, auth):
        # Create one first
        client.post(
            "/api/v1/recruiter/enhancements/scorecards",
            json={
                "role_type": "designer",
                "name": "Design Review",
                "criteria_json": [{"name": "portfolio", "weight": 1, "max_score": 5}],
            },
            headers=auth,
        )
        resp = client.get("/api/v1/recruiter/enhancements/scorecards", headers=auth)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
        assert len(resp.json()) > 0

    def test_get_scorecards_by_role(self, client, auth):
        resp = client.get(
            "/api/v1/recruiter/enhancements/scorecards?role_type=engineer", headers=auth
        )
        assert resp.status_code == 200

    def test_submit_scorecard(self, client, auth, application):
        # Create scorecard first
        resp = client.post(
            "/api/v1/recruiter/enhancements/scorecards",
            json={
                "role_type": "engineer",
                "name": "Submit Test",
                "criteria_json": [
                    {"name": "coding", "weight": 2, "max_score": 5},
                    {"name": "communication", "weight": 1, "max_score": 5},
                ],
            },
            headers=auth,
        )
        scorecard_id = resp.json()["scorecard_id"]

        # Submit
        resp = client.post(
            "/api/v1/recruiter/enhancements/scorecards/submit",
            json={
                "scorecard_id": scorecard_id,
                "application_id": application.id,
                "scores_json": {"coding": 4, "communication": 5},
                "recommendation": "yes",
                "notes": "Great candidate",
            },
            headers=auth,
        )
        assert resp.status_code == 201
        assert resp.json()["success"] is True
        assert "overall_score" in resp.json()
        assert "submission_id" in resp.json()

    def test_get_submissions(self, client, auth, application):
        resp = client.get(
            f"/api/v1/recruiter/enhancements/scorecards/submissions/{application.id}",
            headers=auth,
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


# ============================================================================
# 8. WEBHOOK INTEGRATIONS
# ============================================================================


class TestWebhookIntegrations:
    def test_get_webhooks_empty(self, client, auth):
        resp = client.get("/api/v1/recruiter/enhancements/webhooks", headers=auth)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_create_webhook_invalid_url(self, client, auth):
        """Webhook creation tests a live URL; invalid URL should return 400"""
        resp = client.post(
            "/api/v1/recruiter/enhancements/webhooks",
            json={
                "name": "Test Webhook",
                "provider": "slack",
                "webhook_url": "https://nonexistent.invalid.webhook.url/test",
                "events_json": ["application.created", "application.updated"],
            },
            headers=auth,
        )
        # Should fail because URL is unreachable
        assert resp.status_code == 400

    def test_update_webhook_not_found(self, client, auth):
        resp = client.patch(
            "/api/v1/recruiter/enhancements/webhooks/999999",
            json={"name": "Updated"},
            headers=auth,
        )
        assert resp.status_code == 404

    def test_delete_webhook_not_found(self, client, auth):
        resp = client.delete(
            "/api/v1/recruiter/enhancements/webhooks/999999", headers=auth
        )
        assert resp.status_code == 404


# ============================================================================
# 9. TIME-IN-STAGE ANALYTICS
# ============================================================================


class TestTimeInStageAnalytics:
    def test_time_in_stage(self, client, auth):
        resp = client.get(
            "/api/v1/recruiter/enhancements/analytics/time-in-stage?days=30",
            headers=auth,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "period_days" in data
        assert "stages" in data
        assert "total_transitions" in data
        assert data["period_days"] == 30


# ============================================================================
# 10. SOURCE ATTRIBUTION ANALYTICS
# ============================================================================


class TestSourceAttribution:
    def test_source_attribution(self, client, auth):
        resp = client.get(
            "/api/v1/recruiter/enhancements/analytics/source-attribution?days=90",
            headers=auth,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "period_days" in data
        assert "sources" in data
        assert "total_applications" in data
        assert data["period_days"] == 90


# ============================================================================
# 11. COST-PER-HIRE ANALYTICS
# ============================================================================


class TestCostPerHire:
    def test_cost_per_hire_empty(self, client, auth):
        resp = client.get(
            "/api/v1/recruiter/enhancements/analytics/cost-per-hire?days=90",
            headers=auth,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "total_cost" in data
        assert "total_hires" in data
        assert "cost_per_hire" in data
        assert "cost_by_type" in data
        assert data["cost_per_hire"] == 0  # No hires yet


# ============================================================================
# 12. CAMPAIGN COST TRACKING
# ============================================================================


class TestCampaignCostTracking:
    def test_add_cost(self, client, auth, batch):
        resp = client.post(
            "/api/v1/recruiter/enhancements/analytics/costs",
            json={
                "batch_id": batch.id,
                "cost_type": "job_board",
                "amount": 500.0,
                "currency": "TND",
                "description": "LinkedIn posting",
            },
            headers=auth,
        )
        assert resp.status_code == 201
        assert resp.json()["success"] is True
        assert "cost_id" in resp.json()

    def test_add_cost_invalid_batch(self, client, auth):
        resp = client.post(
            "/api/v1/recruiter/enhancements/analytics/costs",
            json={"batch_id": 999999, "cost_type": "ads", "amount": 100},
            headers=auth,
        )
        assert resp.status_code == 404

    def test_cost_reflects_in_analytics(self, client, auth, batch):
        # Add a cost
        client.post(
            "/api/v1/recruiter/enhancements/analytics/costs",
            json={"batch_id": batch.id, "cost_type": "ads", "amount": 200},
            headers=auth,
        )
        # Check analytics
        resp = client.get(
            "/api/v1/recruiter/enhancements/analytics/cost-per-hire?days=90",
            headers=auth,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_cost"] >= 200


# ============================================================================
# 13. INTERVIEW DEBRIEF AUTO-SUMMARY
# ============================================================================


class TestInterviewDebrief:
    def test_debrief_not_found(self, client, auth):
        resp = client.post(
            "/api/v1/recruiter/enhancements/debrief/999999", headers=auth
        )
        assert resp.status_code == 404

    def test_debrief_generates(self, client, auth, interview):
        resp = client.post(
            f"/api/v1/recruiter/enhancements/debrief/{interview.id}",
            headers=auth,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "candidate_name" in data
        assert "role" in data
        assert "interview_type" in data
        assert "overall_score" in data
        assert "interview_feedback" in data
        assert "scorecard_results" in data
        assert "strengths" in data
        assert "concerns" in data
        assert "recommendations" in data


# ============================================================================
# 14. STAGE TRANSITION TRACKING
# ============================================================================


class TestStageTransitionTracking:
    def test_record_transition(self, client, auth, application):
        # Reset status first
        db = backend.database.SessionLocal()
        app_obj = db.query(Application).filter(Application.id == application.id).first()
        app_obj.status = "applied"
        db.commit()
        db.close()

        resp = client.post(
            "/api/v1/recruiter/enhancements/stage-transition",
            json={
                "app_id": application.id,
                "new_stage": "invited",
                "trigger_type": "manual",
            },
            headers=auth,
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        assert resp.json()["new_status"] == "invited"

    def test_get_stage_history(self, client, auth, application):
        resp = client.get(
            f"/api/v1/recruiter/enhancements/stage-history/{application.id}",
            headers=auth,
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


# ============================================================================
# RUN ALL TESTS
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
