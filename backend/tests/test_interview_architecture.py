"""
Integration tests for the Interview Architecture.

Verifies:
 1. InterviewStarter.start() creates a snapshot and links it to the session.
 2. A second call to start() with identical config reuses the same snapshot (dedup by hash).
 3. Campaign pre-generated snapshot is reused when batch_job.active_snapshot_id is set.
 4. EvaluationConfigReader raises ConfigurationMissingError when no snapshot is linked.
 5. Deleting Job / Rubric rows after the interview has started does NOT affect EvaluationConfigReader.
 6. The config hash is deterministic for identical inputs.
"""

# ── In-memory DB setup ────────────────────────────────────────────────────────
import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test_secret_key")
os.environ.setdefault("ALGORITHM", "HS256")

from backend.database import (
    Application,
    Base,
    Company,
    CompanyMember,
    EvaluationSession,
    Job,
    User,
)

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db():
    session = TestSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def base_entities(db):
    """Create minimal Company, User, Job, and Application for tests."""
    company = Company(name="Acme Corp", slug="acme")
    db.add(company)
    db.flush()

    user = User(
        email="candidate@acme.com",
        name="Candidate",
        hashed_password="hashed",
        role="candidate",
        email_verified=True,
    )
    db.add(user)
    db.flush()

    member = CompanyMember(
        company_id=company.id, user_id=user.id, role="member", is_active=True
    )
    db.add(member)

    job = Job(
        title="Software Engineer",
        company_name="Acme",
        company_id=company.id,
        recruiter_id=user.id,
        is_active=True,
    )
    db.add(job)
    db.flush()

    app = Application(
        user_id=user.id,
        company_id=company.id,
        job_id=job.id,
        status="applied",
        interview_state="not_started",
    )
    db.add(app)
    db.commit()
    db.refresh(app)
    db.refresh(job)
    return {"db": db, "app": app, "job": job, "user": user, "company": company}


# ── Test 1: InterviewStarter creates snapshot ─────────────────────────────────


def test_start_creates_snapshot_and_links_session(base_entities):
    """InterviewStarter.start() must create an EvaluationConfigSnapshot and link it."""
    db = base_entities["db"]
    app = base_entities["app"]

    from backend.rubric.interview_starter import InterviewStarter

    session = InterviewStarter.start(db, app, source_type="job_apply")

    db.refresh(app)
    assert session is not None, "start() must return an EvaluationSession"
    assert session.evaluation_config_snapshot_id is not None, (
        "EvaluationSession must have evaluation_config_snapshot_id after start()"
    )
    assert app.interview_state == "in_progress", (
        "Application interview_state must be in_progress"
    )


# ── Test 2: Snapshot deduplication ───────────────────────────────────────────


def test_start_reuses_snapshot_on_identical_config(base_entities):
    """Two calls to start() with identical config must produce the same snapshot (dedup)."""
    db = base_entities["db"]
    app = base_entities["app"]

    from backend.rubric.interview_starter import InterviewStarter

    s1 = InterviewStarter.start(db, app, source_type="job_apply")
    snap_id_1 = s1.evaluation_config_snapshot_id

    # Reset interview state to allow a second start
    app.interview_state = "not_started"
    db.commit()

    s2 = InterviewStarter.start(db, app, source_type="job_apply")
    snap_id_2 = s2.evaluation_config_snapshot_id

    assert snap_id_1 == snap_id_2, (
        f"Identical config must reuse the same snapshot. Got {snap_id_1} vs {snap_id_2}"
    )


# ── Test 3: EvaluationConfigReader without snapshot raises ───────────────────


def test_config_reader_raises_when_no_snapshot(base_entities):
    """EvaluationConfigReader must raise ConfigurationMissingError when session has no snapshot."""
    db = base_entities["db"]
    app = base_entities["app"]

    # Create a session but do NOT link a snapshot
    es = EvaluationSession(
        application_id=app.id, company_id=app.company_id, status="created"
    )
    db.add(es)
    db.commit()
    db.refresh(es)

    from backend.rubric.config_reader import (
        ConfigurationMissingError,
        EvaluationConfigReader,
    )

    reader = EvaluationConfigReader(es)
    with pytest.raises(ConfigurationMissingError):
        reader.get_rubric()


# ── Test 4: EvaluationConfigReader reads from snapshot ───────────────────────


def test_config_reader_reads_from_snapshot(base_entities):
    """After start(), EvaluationConfigReader must return settings from the snapshot."""
    db = base_entities["db"]
    app = base_entities["app"]

    from backend.rubric.interview_starter import InterviewStarter

    session = InterviewStarter.start(db, app, source_type="job_apply")

    db.refresh(session)

    from backend.rubric.config_reader import EvaluationConfigReader

    reader = EvaluationConfigReader(session)

    settings = reader.get_interview_settings()
    assert "max_questions" in settings
    assert "language" in settings
    assert settings["max_questions"] > 0


# ── Test 5: Deleting Job after start does not break reader ────────────────────


def test_reader_survives_job_deletion(base_entities):
    """Deleting the Job row after interview start must not affect EvaluationConfigReader."""
    db = base_entities["db"]
    app = base_entities["app"]
    job = base_entities["job"]

    from backend.rubric.interview_starter import InterviewStarter

    session = InterviewStarter.start(db, app, source_type="job_apply")
    db.refresh(session)

    # Delete the Job from the database
    app.job_id = None
    db.flush()
    db.delete(job)
    db.commit()

    # The reader should still work using the snapshot
    from backend.rubric.config_reader import EvaluationConfigReader

    reader = EvaluationConfigReader(session)
    settings = reader.get_interview_settings()
    assert settings["max_questions"] > 0, "Reader must work even if Job is deleted"


# ── Test 6: Hash determinism ──────────────────────────────────────────────────


def test_snapshot_hash_is_deterministic(base_entities):
    """ResolvedEvaluationConfig must produce the same hash for identical inputs."""
    from backend.models.evaluation.config_snapshot import ResolvedEvaluationConfig

    cfg = ResolvedEvaluationConfig(
        source_type="job_apply",
        source_id=1,
        rubric_id=None,
        rubric_version=None,
        total_questions=15,
        time_limit_seconds=1800,
        passing_score=0.0,
        max_score=100.0,
        interview_instructions="Be professional.",
        language="en",
        question_generation_prompt=None,
        evaluation_criteria=None,
        scoring_weights=None,
        source_metadata=None,
    )
    h1 = cfg.compute_hash()
    h2 = cfg.compute_hash()
    assert h1 == h2, "compute_hash() must be deterministic"


# ── Test 7: Campaign snapshot reuse ──────────────────────────────────────────


def test_start_reuses_campaign_active_snapshot(base_entities):
    """If batch_job.active_snapshot_id is set, InterviewStarter must reuse that snapshot."""
    db = base_entities["db"]
    app = base_entities["app"]

    from backend.models.evaluation.config_snapshot import (
        EntryPoint,
    )
    from backend.rubric.config_resolver import ConfigurationResolver
    from backend.rubric.interview_starter import InterviewStarter

    # Pre-generate a snapshot (simulating campaign pre-generation)
    entry_point = EntryPoint(
        source_type="campaign", source_id=app.job_id, application_id=app.id
    )
    pre_snap = ConfigurationResolver.resolve(
        db, entry_point, company_id=base_entities["company"].id, job=base_entities["job"]
    )

    # Create a fake BatchJob with active_snapshot_id
    from backend.database import BatchJob

    bj = BatchJob(
        company_id=base_entities["company"].id,
        recruiter_id=base_entities["user"].id,
        job_id=base_entities["job"].id,
        title="Campaign A",
        status="active",
        active_snapshot_id=pre_snap.id,
    )
    db.add(bj)
    db.commit()
    db.refresh(bj)

    app.batch_id = bj.id
    # Monkey-patch app.batch_job for the test since SQLite may not have lazy-loading
    app.batch_job = bj
    db.commit()

    session = InterviewStarter.start(db, app, source_type="campaign")
    assert session.evaluation_config_snapshot_id == pre_snap.id, (
        "InterviewStarter must reuse campaign's active_snapshot_id"
    )


# ── Test 8: Job time limit resolution ───────────────────────────────────────


def test_job_time_limit_resolution(base_entities):
    """ConfigurationResolver must resolve time_limit_seconds from Job duration settings."""
    db = base_entities["db"]
    job = base_entities["job"]
    job.duration_minutes = 45
    db.commit()

    from backend.models.evaluation.config_snapshot import EntryPoint
    from backend.rubric.config_resolver import ConfigurationResolver

    entry_point = EntryPoint(
        source_type="job_apply", source_id=job.id, application_id=base_entities["app"].id
    )
    snapshot = ConfigurationResolver.resolve(
        db, entry_point, company_id=base_entities["company"].id, job=job
    )

    assert snapshot.time_limit_seconds == 2700, (
        f"Expected 2700 seconds (45 min), got {snapshot.time_limit_seconds}"
    )
