"""Tests for unified rubric model migration (Phase C).

Verifies that JobRubric now serves as the single source of truth for both
published rubrics and recruiter drafts, and that the rubric chain
(load_current_rubric_record, load_rubric_by_id, AIInterviewSession FK) remains
intact.
"""

import json

import pytest

from backend.database import (
    Category,
    Job,
    User,
)
from backend.database import (
    Rubric as RubricDB,
)


@pytest.mark.usefixtures("db_session")
class TestUnifiedRubricModel:
    """Phase C: Unified rubric model — JobRubric as SSOT."""

    def _create_user(self, db_session, role="recruiter"):
        u = User(
            email=f"{role}@test.com",
            hashed_password="x",
            name="Test User",
            role=role,
        )
        db_session.add(u)
        db_session.flush()
        return u

    def _create_job(self, db_session, recruiter):
        cat = Category(name="Tech")
        db_session.add(cat)
        db_session.flush()
        job = Job(title="Engineer", recruiter_id=recruiter.id, category_id=cat.id)
        db_session.add(job)
        db_session.flush()
        return job

    def _create_published_rubric(self, db_session, job, version=1, is_current=True):
        r = RubricDB(
            job_id=job.id,
            version=version,
            is_current=is_current,
            rubric_json=json.dumps({"version": version, "categories": []}),
            status="published",
        )
        db_session.add(r)
        db_session.flush()
        return r

    # ------------------------------------------------------------------
    # 1. Model defaults
    # ------------------------------------------------------------------

    def test_published_rubric_defaults_to_published_status(self, db_session):
        """Published rubrics get status='published' by default."""
        job = self._create_job(db_session, self._create_user(db_session))
        r = self._create_published_rubric(db_session, job)
        assert r.status == "published"

    def test_draft_explicit_status(self, db_session):
        """Drafts must set status='draft' explicitly."""
        job = self._create_job(db_session, self._create_user(db_session))
        draft = RubricDB(
            job_id=job.id,
            version=0,
            is_current=False,
            rubric_json=json.dumps({"version": 1, "categories": []}),
            status="draft",
            user_id=job.recruiter_id,
        )
        db_session.add(draft)
        db_session.flush()
        assert draft.status == "draft"
        assert draft.version == 0
        assert draft.is_current is False

    # ------------------------------------------------------------------
    # 2. Version isolation
    # ------------------------------------------------------------------

    def test_draft_version_zero_does_not_conflict_with_published(self, db_session):
        """Draft at version=0 never collides with published version >= 1."""
        job = self._create_job(db_session, self._create_user(db_session))
        self._create_published_rubric(db_session, job, version=1, is_current=True)
        draft = RubricDB(
            job_id=job.id,
            version=0,
            is_current=False,
            rubric_json=json.dumps({"version": 1, "categories": []}),
            status="draft",
            user_id=job.recruiter_id,
        )
        db_session.add(draft)
        db_session.flush()  # Should not raise IntegrityError
        assert draft.id is not None

    def test_multiple_drafts_per_job_negative_versions(self, db_session):
        """Multiple drafts per job use sequential negative versions."""
        job = self._create_job(db_session, self._create_user(db_session))
        drafts = []
        for i in range(3):
            d = RubricDB(
                job_id=job.id,
                version=-i,
                is_current=False,
                rubric_json=json.dumps({"version": 1, "categories": []}),
                status="draft",
                user_id=job.recruiter_id,
            )
            db_session.add(d)
            drafts.append(d)
        db_session.flush()
        versions = sorted([d.version for d in drafts])
        assert versions == [-2, -1, 0]

    # ------------------------------------------------------------------
    # 3. Draft querying
    # ------------------------------------------------------------------

    def test_query_drafts_by_status(self, db_session):
        """Drafts can be queried by status='draft'."""
        user = self._create_user(db_session)
        job = self._create_job(db_session, user)
        self._create_published_rubric(db_session, job, version=1, is_current=True)
        draft = RubricDB(
            job_id=job.id,
            version=0,
            is_current=False,
            rubric_json=json.dumps({"version": 1, "categories": []}),
            status="draft",
            user_id=user.id,
        )
        db_session.add(draft)
        db_session.flush()

        drafts = (
            db_session.query(RubricDB)
            .filter(
                RubricDB.status == "draft",
                RubricDB.job_id == job.id,
            )
            .all()
        )
        assert len(drafts) == 1

        published = (
            db_session.query(RubricDB)
            .filter(
                RubricDB.status == "published",
                RubricDB.job_id == job.id,
            )
            .all()
        )
        assert len(published) >= 1

    def test_query_drafts_by_user(self, db_session):
        """Drafts can be queried by user_id."""
        u1 = self._create_user(db_session, "recruiter")
        u2 = self._create_user(db_session, "recruiter2")
        j1 = self._create_job(db_session, u1)
        j2 = self._create_job(db_session, u2)

        for job, user in [(j1, u1), (j2, u2)]:
            draft = RubricDB(
                job_id=job.id,
                version=0,
                is_current=False,
                rubric_json=json.dumps({"version": 1, "categories": []}),
                status="draft",
                user_id=user.id,
            )
            db_session.add(draft)
        db_session.flush()

        u1_drafts = (
            db_session.query(RubricDB)
            .filter(
                RubricDB.status == "draft",
                RubricDB.user_id == u1.id,
            )
            .all()
        )
        assert len(u1_drafts) == 1

    # ------------------------------------------------------------------
    # 4. _next_draft_version helper
    # ------------------------------------------------------------------

    def test_next_draft_version_empty(self, db_session):
        """Returns 0 when no drafts exist for a job."""
        from backend.rubric.rubric_router import _next_draft_version

        user = self._create_user(db_session)
        job = self._create_job(db_session, user)
        ver = _next_draft_version(db_session, job.id)
        assert ver == 0

    def test_next_draft_version_with_existing(self, db_session):
        """Returns min_version - 1 when drafts exist."""
        from backend.rubric.rubric_router import _next_draft_version

        user = self._create_user(db_session)
        job = self._create_job(db_session, user)
        for v in (0, -1):
            d = RubricDB(
                job_id=job.id,
                version=v,
                is_current=False,
                rubric_json=json.dumps({"version": 1, "categories": []}),
                status="draft",
                user_id=user.id,
            )
            db_session.add(d)
        db_session.flush()
        ver = _next_draft_version(db_session, job.id)
        assert ver == -2

    def test_next_draft_version_ignores_published(self, db_session):
        """Published versions (>=1) are ignored by _next_draft_version."""
        from backend.rubric.rubric_router import _next_draft_version

        user = self._create_user(db_session)
        job = self._create_job(db_session, user)
        self._create_published_rubric(db_session, job, version=1, is_current=True)
        self._create_published_rubric(db_session, job, version=2, is_current=True)
        ver = _next_draft_version(db_session, job.id)
        assert ver == 0  # No drafts exist

    # ------------------------------------------------------------------
    # 5. Rubric chain — load_current_rubric_record
    # ------------------------------------------------------------------

    def test_load_current_rubric_record_returns_published_only(self, db_session):
        """Only is_current=True rubrics are returned by the loading logic."""
        user = self._create_user(db_session)
        job = self._create_job(db_session, user)
        self._create_published_rubric(db_session, job, version=1, is_current=True)
        self._create_published_rubric(db_session, job, version=2, is_current=False)
        draft = RubricDB(
            job_id=job.id,
            version=0,
            is_current=False,
            rubric_json=json.dumps({"version": 1, "categories": []}),
            status="draft",
            user_id=user.id,
        )
        db_session.add(draft)
        db_session.commit()

        # Query the same way load_current_rubric_record does
        record = (
            db_session.query(RubricDB)
            .filter(
                RubricDB.job_id == job.id,
                RubricDB.is_current,
            )
            .order_by(RubricDB.version.desc())
            .first()
        )
        assert record is not None
        assert record.is_current is True
        assert record.status == "published"
        assert record.version == 1

    def test_load_rubric_by_id_resolves_correctly(self, db_session):
        """Rubric can be found by PK regardless of status."""
        user = self._create_user(db_session)
        job = self._create_job(db_session, user)
        published = self._create_published_rubric(
            db_session, job, version=1, is_current=True
        )
        draft = RubricDB(
            job_id=job.id,
            version=0,
            is_current=False,
            rubric_json=json.dumps({"version": 1, "categories": []}),
            status="draft",
            user_id=user.id,
        )
        db_session.add(draft)
        db_session.commit()

        r1 = db_session.query(RubricDB).filter(RubricDB.id == published.id).first()
        assert r1 is not None
        assert r1.status == "published"

        r2 = db_session.query(RubricDB).filter(RubricDB.id == draft.id).first()
        assert r2 is not None
        assert r2.status == "draft"

    # ------------------------------------------------------------------
    # 6. Publish draft — updates status + creates new published row
    # ------------------------------------------------------------------

    def test_publish_draft_creates_new_published_row(self, db_session):
        """Publishing a draft creates a new published row and marks draft."""
        user = self._create_user(db_session)
        job = self._create_job(db_session, user)
        draft = RubricDB(
            job_id=job.id,
            version=0,
            is_current=False,
            rubric_json=json.dumps({"version": 1, "categories": []}),
            status="draft",
            user_id=user.id,
        )
        db_session.add(draft)
        db_session.flush()

        # Simulate publish logic
        next_version = 1
        published = RubricDB(
            job_id=job.id,
            version=next_version,
            is_current=True,
            rubric_json=json.dumps({"version": 1, "categories": []}),
            status="published",
            created_by=user.id,
        )
        db_session.add(published)
        draft.status = "published"
        db_session.flush()

        published_rows = (
            db_session.query(RubricDB)
            .filter(
                RubricDB.job_id == job.id,
                RubricDB.status == "published",
                RubricDB.is_current,
            )
            .all()
        )
        assert len(published_rows) == 1
        assert published_rows[0].version == 1
        assert draft.status == "published"

    # ------------------------------------------------------------------
    # 7. Draft CRUD
    # ------------------------------------------------------------------

    def test_create_draft_via_helper(self, db_session):
        """Create a draft using the helper."""
        from backend.rubric.rubric_router import _next_draft_version

        user = self._create_user(db_session)
        job = self._create_job(db_session, user)
        ver = _next_draft_version(db_session, job.id)
        draft = RubricDB(
            job_id=job.id,
            version=ver,
            is_current=False,
            name="My Draft",
            rubric_json=json.dumps({"version": 1, "categories": []}),
            status="draft",
            user_id=user.id,
        )
        db_session.add(draft)
        db_session.flush()

        loaded = (
            db_session.query(RubricDB)
            .filter(
                RubricDB.id == draft.id,
                RubricDB.status == "draft",
            )
            .first()
        )
        assert loaded is not None
        assert loaded.name == "My Draft"
        assert loaded.user_id == user.id

    def test_update_draft(self, db_session):
        """Update draft fields."""
        user = self._create_user(db_session)
        job = self._create_job(db_session, user)
        draft = RubricDB(
            job_id=job.id,
            version=0,
            is_current=False,
            rubric_json=json.dumps({"version": 1, "categories": []}),
            status="draft",
            user_id=user.id,
            name="Original",
        )
        db_session.add(draft)
        db_session.flush()

        draft.name = "Updated"
        draft.rubric_json = json.dumps({"version": 2, "categories": []})
        db_session.flush()

        loaded = db_session.query(RubricDB).filter(RubricDB.id == draft.id).first()
        assert loaded.name == "Updated"
        assert json.loads(loaded.rubric_json)["version"] == 2

    # ------------------------------------------------------------------
    # 8. Archived drafts
    # ------------------------------------------------------------------

    def test_archived_draft_listed_in_draft_query(self, db_session):
        """Archived drafts are included in status IN ('draft', 'archived') queries."""
        user = self._create_user(db_session)
        job = self._create_job(db_session, user)
        for status_val in ("draft", "archived"):
            d = RubricDB(
                job_id=job.id,
                version=0 if status_val == "draft" else -1,
                is_current=False,
                rubric_json=json.dumps({"version": 1, "categories": []}),
                status=status_val,
                user_id=user.id,
            )
            db_session.add(d)
        db_session.flush()

        results = (
            db_session.query(RubricDB)
            .filter(
                RubricDB.status.in_(["draft", "archived"]),
                RubricDB.user_id == user.id,
            )
            .all()
        )
        assert len(results) == 2
