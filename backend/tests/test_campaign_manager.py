"""
Campaign Manager Feature Tests
Tests the recruiter campaign management functionality
"""


class TestCampaignManager:
    """Test suite for Campaign Manager feature"""

    def test_create_campaign_model(self, db_session):
        """Test creating a new campaign (model only)"""
        from backend.database import BatchJob, Company, CompanyMember, Job, User

        recruiter = db_session.query(User).filter(User.role == "recruiter").first()
        if not recruiter:
            company = Company(name="Test Company", slug="test-company")
            db_session.add(company)
            db_session.flush()

            recruiter = User(
                email="recruiter@test.com",
                name="Test Recruiter",
                hashed_password="hashed",
                role="recruiter",
            )
            db_session.add(recruiter)
            db_session.flush()

            db_session.add(
                CompanyMember(
                    company_id=company.id,
                    user_id=recruiter.id,
                    role="admin",
                    is_active=True,
                )
            )
            db_session.commit()
            db_session.refresh(recruiter)

        job = Job(
            title="Test Job",
            recruiter_id=recruiter.id,
            company_id=company.id,
        )
        db_session.add(job)
        db_session.commit()
        db_session.refresh(job)

        batch = BatchJob(
            recruiter_id=recruiter.id,
            job_id=job.id,
            company_id=job.company_id,
            title="Test Campaign",
            status="active",
        )
        db_session.add(batch)
        db_session.commit()
        db_session.refresh(batch)

        assert batch.id is not None
        assert batch.title == "Test Campaign"
        assert batch.status == "active"

    def test_soft_delete_preserves_data(self, db_session):
        """Test soft delete preserves data"""
        from datetime import datetime

        from backend.database import BatchJob, Company, CompanyMember, Job, User

        recruiter = db_session.query(User).filter(User.role == "recruiter").first()
        if not recruiter:
            company = Company(name="Test Company", slug="test-company")
            db_session.add(company)
            db_session.flush()

            recruiter = User(
                email="recruiter@test.com",
                name="Test Recruiter",
                hashed_password="hashed",
                role="recruiter",
            )
            db_session.add(recruiter)
            db_session.flush()

            db_session.add(
                CompanyMember(
                    company_id=company.id,
                    user_id=recruiter.id,
                    role="admin",
                    is_active=True,
                )
            )
            db_session.commit()
            db_session.refresh(recruiter)

        job = Job(
            title="Test Job",
            recruiter_id=recruiter.id,
            company_id=company.id,
        )
        db_session.add(job)
        db_session.commit()
        db_session.refresh(job)

        batch = BatchJob(
            recruiter_id=recruiter.id,
            job_id=job.id,
            company_id=job.company_id,
            title="Test Campaign",
            status="active",
        )
        db_session.add(batch)
        db_session.commit()
        db_session.refresh(batch)

        # Soft delete
        batch.status = "archived"
        batch.deleted_at = datetime.now()
        db_session.commit()

        # Verify soft delete preserves data
        archived = db_session.query(BatchJob).filter(BatchJob.id == batch.id).first()
        assert archived.status == "archived"
        assert archived.title == "Test Campaign"  # Data preserved

    def test_interview_progress_tracking(self, db_session):
        """Test interview progress is tracked in Application"""

        from backend.database import Application, BatchJob, Company, CompanyMember, Job, User

        # Create recruiter and candidate
        recruiter = db_session.query(User).filter(User.role == "recruiter").first()
        if not recruiter:
            company = Company(name="Test Company", slug="test-company")
            db_session.add(company)
            db_session.flush()

            recruiter = User(
                email="recruiter@test.com",
                name="Test Recruiter",
                hashed_password="hashed",
                role="recruiter",
            )
            db_session.add(recruiter)
            db_session.flush()

            db_session.add(
                CompanyMember(
                    company_id=company.id,
                    user_id=recruiter.id,
                    role="admin",
                    is_active=True,
                )
            )
            db_session.commit()
            db_session.refresh(recruiter)

        candidate = db_session.query(User).filter(User.role == "candidate").first()
        if not candidate:
            candidate = User(
                email="candidate@test.com",
                name="Test Candidate",
                hashed_password="hashed",
                role="candidate",
            )
            db_session.add(candidate)
            db_session.commit()
            db_session.refresh(candidate)

        job = Job(
            title="Test Job",
            recruiter_id=recruiter.id,
            company_id=company.id,
        )
        db_session.add(job)
        db_session.commit()
        db_session.refresh(job)

        # Create campaign
        batch = BatchJob(
            recruiter_id=recruiter.id,
            job_id=job.id,
            company_id=job.company_id,
            title="Test Campaign",
            status="active",
        )
        db_session.add(batch)
        db_session.commit()
        db_session.refresh(batch)

        # Create application
        app = Application(
            user_id=candidate.id,
            batch_id=batch.id,
            full_name=candidate.name,
            email=candidate.email,
        )
        db_session.add(app)
        db_session.commit()
        db_session.refresh(app)

        # Set interview state via evaluation session
        from backend.entity_writer import sync_ai_interview_session

        sync_ai_interview_session(
            db_session,
            app,
            interview_state="in_progress",
            interview_progress=7,
        )

        # Verify tracking
        assert app.interview_state == "in_progress"
        assert app.interview_progress == 7

    def test_score_delta_calculation(self, db_session):
        """Test CV to Interview score delta is calculated"""

        from backend.database import (
            Application,
            BatchJob,
            Company,
            CompanyMember,
            EvaluationResult,
            EvaluationSession,
            Job,
            User,
        )

        # Setup
        recruiter = db_session.query(User).filter(User.role == "recruiter").first()
        if not recruiter:
            company = Company(name="Test Company", slug="test-company")
            db_session.add(company)
            db_session.flush()

            recruiter = User(
                email="recruiter@test.com",
                name="Test Recruiter",
                hashed_password="hashed",
                role="recruiter",
            )
            db_session.add(recruiter)
            db_session.flush()

            db_session.add(
                CompanyMember(
                    company_id=company.id,
                    user_id=recruiter.id,
                    role="admin",
                    is_active=True,
                )
            )
            db_session.commit()
            db_session.refresh(recruiter)

        candidate = db_session.query(User).filter(User.role == "candidate").first()
        if not candidate:
            candidate = User(
                email="candidate@test.com",
                name="Test Candidate",
                hashed_password="hashed",
                role="candidate",
            )
            db_session.add(candidate)
            db_session.commit()
            db_session.refresh(candidate)

        job = Job(
            title="Test Job",
            recruiter_id=recruiter.id,
            company_id=company.id,
        )
        db_session.add(job)
        db_session.commit()
        db_session.refresh(job)

        batch = BatchJob(
            recruiter_id=recruiter.id,
            job_id=job.id,
            company_id=job.company_id,
            title="Test Campaign",
            status="active",
        )
        db_session.add(batch)
        db_session.commit()
        db_session.refresh(batch)

        app = Application(
            user_id=candidate.id,
            batch_id=batch.id,
            full_name=candidate.name,
            email=candidate.email,
            interview_state="completed",
        )
        db_session.add(app)
        db_session.flush()

        _es = EvaluationSession(application_id=app.id)
        db_session.add(_es)
        db_session.flush()
        _er = EvaluationResult(
            evaluation_session_id=_es.id,
            scoring_status="SCORED",
            final_score=80,
            cv_score=60,
        )
        db_session.add(_er)
        db_session.commit()
        db_session.refresh(app)

        # Calculate delta
        _er_check = (
            app.evaluation_sessions[0].evaluation_result
            if app.evaluation_sessions and app.evaluation_sessions[0].evaluation_result
            else None
        )
        delta = (_er_check.final_score if _er_check else 0) - (
            _er_check.cv_score if _er_check else 0 or 0
        )
        assert delta == 20

    def test_batch_job_has_required_fields(self, db_session):
        """Test BatchJob model has all required fields"""
        from backend.database import BatchJob, Company, CompanyMember, Job, User

        recruiter = db_session.query(User).filter(User.role == "recruiter").first()
        if not recruiter:
            company = Company(name="Test Company", slug="test-company")
            db_session.add(company)
            db_session.flush()

            recruiter = User(
                email="recruiter@test.com",
                name="Test Recruiter",
                hashed_password="hashed",
                role="recruiter",
            )
            db_session.add(recruiter)
            db_session.flush()

            db_session.add(
                CompanyMember(
                    company_id=company.id,
                    user_id=recruiter.id,
                    role="admin",
                    is_active=True,
                )
            )
            db_session.commit()
            db_session.refresh(recruiter)

        job = Job(
            title="Test Job",
            recruiter_id=recruiter.id,
            company_id=company.id,
        )
        db_session.add(job)
        db_session.commit()
        db_session.refresh(job)

        # Test creation with various fields
        batch = BatchJob(
            recruiter_id=recruiter.id,
            job_id=job.id,
            company_id=job.company_id,
            title="Test Campaign",
            target_role="Python Developer",
            description="Test job description",
            interview_instructions="Focus on Python and API development",
            language="English",
            status="active",
        )
        db_session.add(batch)
        db_session.commit()

        # Verify fields
        assert batch.title == "Test Campaign"
        assert batch.target_role == "Python Developer"
        assert batch.description == "Test job description"
        assert batch.interview_instructions == "Focus on Python and API development"
        assert batch.language == "English"
