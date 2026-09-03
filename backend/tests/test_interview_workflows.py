"""
Interview 3 Workflows Integration Tests
Tests the 3 ways a candidate can start an AI interview:
1. From Onboarding/Audit (no job, no campaign)
2. From Job Application (with job_id)
3. From Campaign Invitation (with batch_id)
"""

import os

import pytest
from fastapi import status

from backend.database import Application, BatchJob


class TestWorkflow1OnboardingAudit:
    """Workflow 1: New audit from onboarding (no job, no campaign)"""

    def test_audit_application_has_no_job_or_batch(
        self, client, db_session, test_user, auth_headers
    ):
        """Audit created from onboarding should have job_id=None and batch_id=None"""
        if not os.environ.get("GROQ_API_KEY"):
            pytest.skip(
                "GROQ_API_KEY not set — requires a real API key for AI analysis"
            )
        import base64

        cv_bytes = b"Experienced Python Developer with 5 years of professional experience building web applications using FastAPI, Django, PostgreSQL, and Docker. Skilled in REST API design, microservices architecture, and CI/CD pipelines."
        headers = {**auth_headers, "Content-Type": "application/json"}
        response = client.post(
            "/api/v1/onboarding/analyze-cv-json",
            headers=headers,
            json={
                "declared_role": "Python Developer",
                "file_content": base64.b64encode(cv_bytes).decode(),
                "file_name": "resume.txt",
            },
        )

        assert response.status_code == status.HTTP_200_OK, (
            f"Expected 200, got {response.status_code}: {response.text[:200]}"
        )
        data = response.json()
        app_id = data.get("application_id") or data.get("id")
        assert app_id is not None

        app = db_session.query(Application).filter(Application.id == app_id).first()
        assert app is not None
        assert app.job_id is None
        assert app.batch_id is None

    def test_audit_interview_starts_with_audit_context(
        self, client, auth_headers, db_session, test_user
    ):
        """Interview from audit should have is_audit=True"""
        app = Application(
            user_id=test_user.id,
            declared_role="Python Developer",
            full_name=test_user.name,
            email=test_user.email,
            status="analyzed",
            cv_text_anonymized="Python developer experience",
            job_id=None,
            batch_id=None,
        )
        db_session.add(app)
        db_session.commit()
        db_session.refresh(app)

        response = client.post(
            "/api/v1/ai/interview/chat",
            headers=auth_headers,
            json={"candidate_id": app.id, "message": "ready"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        # Audit interviews have no job_title or campaign_title
        assert not data.get("job_title")
        assert not data.get("campaign_title")


class TestWorkflow2JobApplication:
    """Workflow 2: From job application (with job_id)"""

    def test_application_has_job_id(
        self, client, db_session, test_user, test_recruiter
    ):
        """Application to job should have job_id set"""
        from backend.database import Job

        job = Job(
            recruiter_id=test_recruiter.id,
            title="Senior Python Developer",
            location="Remote",
        )
        db_session.add(job)
        db_session.commit()
        db_session.refresh(job)

        app = Application(
            user_id=test_user.id,
            declared_role="Python Developer",
            full_name=test_user.name,
            email=test_user.email,
            status="invited",
            cv_text_anonymized="Python developer",
            job_id=job.id,
            batch_id=None,
        )
        db_session.add(app)
        db_session.commit()
        db_session.refresh(app)

        assert app.job_id == job.id
        assert app.batch_id is None

    def test_interview_with_job_context(
        self, client, auth_headers, db_session, test_user, test_recruiter
    ):
        """Interview from job should have job context"""
        if not os.environ.get("GROQ_API_KEY"):
            pytest.skip("GROQ_API_KEY not set — requires a real API key")
        from backend.database import Job

        job = Job(
            recruiter_id=test_recruiter.id, title="Backend Engineer", location="Remote"
        )
        db_session.add(job)
        db_session.commit()

        app = Application(
            user_id=test_user.id,
            declared_role="Backend Engineer",
            full_name=test_user.name,
            email=test_user.email,
            status="invited",
            job_id=job.id,
            batch_id=None,
        )
        db_session.add(app)
        db_session.commit()
        db_session.refresh(app)

        response = client.post(
            "/api/v1/ai/interview/chat",
            headers=auth_headers,
            json={"candidate_id": app.id, "message": "ready"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        # Job interviews should have a job_title
        assert data.get("job_title") is not None


class TestWorkflow3CampaignInvite:
    """Workflow 3: From campaign invitation (with batch_id)"""

    def test_invited_application_has_batch_id(
        self, client, db_session, test_user, test_recruiter
    ):
        """Invited application should have batch_id set"""
        batch = BatchJob(
            recruiter_id=test_recruiter.id, title="Q2 2024 Hiring", status="active"
        )
        db_session.add(batch)
        db_session.commit()
        db_session.refresh(batch)

        app = Application(
            user_id=test_user.id,
            declared_role="Data Scientist",
            full_name=test_user.name,
            email=test_user.email,
            status="invited",
            cv_text_anonymized="Data science experience",
            job_id=None,
            batch_id=batch.id,
        )
        db_session.add(app)
        db_session.commit()
        db_session.refresh(app)

        assert app.batch_id == batch.id
        assert app.job_id is None
        assert app.status == "invited"

    def test_interview_with_campaign_context(
        self, client, auth_headers, db_session, test_user, test_recruiter
    ):
        """Interview from campaign should have campaign/batch context"""
        if not os.environ.get("GROQ_API_KEY"):
            pytest.skip("GROQ_API_KEY not set — requires a real API key")
        batch = BatchJob(
            recruiter_id=test_recruiter.id, title="Summer Campaign", status="active"
        )
        db_session.add(batch)
        db_session.commit()

        app = Application(
            user_id=test_user.id,
            declared_role="Marketing Manager",
            full_name=test_user.name,
            email=test_user.email,
            status="invited",
            batch_id=batch.id,
        )
        db_session.add(app)
        db_session.commit()
        db_session.refresh(app)

        response = client.post(
            "/api/v1/ai/interview/chat",
            headers=auth_headers,
            json={"candidate_id": app.id, "message": "ready"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        # Campaign interviews should have a campaign_title or batch context
        assert (
            data.get("campaign_title") is not None or data.get("job_title") is not None
        )


class TestWorkflowTransitions:
    """Test status transitions across all 3 workflows"""

    def test_audit_status_transition(self, client, auth_headers, db_session, test_user):
        """Audit: pending -> analyzed -> interviewing"""
        app = Application(
            user_id=test_user.id, status="pending", job_id=None, batch_id=None
        )
        db_session.add(app)
        db_session.commit()

        app.status = "analyzed"
        db_session.commit()

        response = client.post(
            "/api/v1/ai/interview/chat",
            headers=auth_headers,
            json={"candidate_id": app.id, "message": "ready"},
        )
        assert response.status_code == status.HTTP_200_OK

        db_session.refresh(app)
        assert app.interview_state in ["IN_PROGRESS", "in_progress", "completed"]

    def test_apply_status_transition(
        self, client, auth_headers, db_session, test_user, test_recruiter
    ):
        """Apply: applied -> interviewing"""
        from backend.database import Job

        job = Job(recruiter_id=test_recruiter.id, title="Dev", location="Remote")
        db_session.add(job)
        db_session.commit()

        app = Application(user_id=test_user.id, status="invited", job_id=job.id)
        db_session.add(app)
        db_session.commit()

        response = client.post(
            "/api/v1/ai/interview/chat",
            headers=auth_headers,
            json={"candidate_id": app.id, "message": "ready"},
        )
        assert response.status_code == status.HTTP_200_OK

        db_session.refresh(app)
        assert app.interview_state in ["IN_PROGRESS", "in_progress", "completed"]

    def test_invited_status_transition(
        self, client, auth_headers, db_session, test_user, test_recruiter
    ):
        """Invite: invited -> interviewing"""
        batch = BatchJob(recruiter_id=test_recruiter.id, title="Test", status="active")
        db_session.add(batch)
        db_session.commit()

        app = Application(user_id=test_user.id, status="invited", batch_id=batch.id)
        db_session.add(app)
        db_session.commit()

        response = client.post(
            "/api/v1/ai/interview/chat",
            headers=auth_headers,
            json={"candidate_id": app.id, "message": "ready"},
        )
        assert response.status_code == status.HTTP_200_OK

        db_session.refresh(app)
        assert app.interview_state in ["IN_PROGRESS", "in_progress", "completed"]
