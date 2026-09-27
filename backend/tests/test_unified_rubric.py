"""Tests for the unified rubric model (``rubrics`` table as single source of truth).

The rubric table stores both published rubrics and recruiter drafts:

* published rubric  -> ``is_active=1``, ``version >= 1``
* draft             -> ``is_active=0``, ``version <= 0`` (0, -1, -2, ...)
* ``criteria_json`` -> JSON text of a ``JobRubric``

These tests exercise the real helpers (``_next_draft_version``,
``load_current_rubric_record``, ``load_rubric_by_id``) against that contract,
including tenant scoping.

(The earlier version of this file targeted a pre-migration schema with
``status`` / ``is_current`` / ``rubric_json`` / ``user_id`` columns that no
longer exist; the draft endpoints themselves are covered by
``test_rubric_draft_persistence.py``.)
"""

import json
import uuid

import pytest

from backend.database import Company, Job, User
from backend.database import Rubric as RubricDB
from backend.rubric.rubric_loader import (
    invalidate_cache,
    load_current_rubric_record,
    load_rubric_by_id,
)
from backend.rubric.rubric_router import _next_draft_version
from backend.rubric.rubric_schema import JobRubric


def _company(db):
    slug = f"rubric-co-{uuid.uuid4().hex[:8]}"
    c = Company(name=slug, slug=slug)
    db.add(c)
    db.flush()
    return c


def _job(db, company, title="Engineer"):
    user = User(
        email=f"{uuid.uuid4().hex[:8]}@test.com",
        hashed_password="x",
        name="Recruiter",
        role="recruiter",
    )
    db.add(user)
    db.flush()
    job = Job(title=title, recruiter_id=user.id, company_id=company.id)
    db.add(job)
    db.flush()
    return job


def _rubric(db, job, version, is_active, company_id=None, seniority="mid"):
    body = JobRubric(job_id=job.id, version=max(version, 1), categories=[])
    data = body.model_dump(mode="json")
    data["seniority"] = seniority
    r = RubricDB(
        job_id=job.id,
        version=version,
        is_active=is_active,
        criteria_json=json.dumps(data),
        company_id=company_id or job.company_id,
    )
    db.add(r)
    db.flush()
    return r


@pytest.fixture
def db(db_session):
    yield db_session


class TestNextDraftVersion:
    def test_empty_returns_zero(self, db):
        job = _job(db, _company(db))
        assert _next_draft_version(db, job.id) == 0

    def test_existing_drafts_go_more_negative(self, db):
        job = _job(db, _company(db))
        _rubric(db, job, 0, is_active=0)
        _rubric(db, job, -1, is_active=0)
        assert _next_draft_version(db, job.id) == -2

    def test_published_versions_are_ignored(self, db):
        job = _job(db, _company(db))
        _rubric(db, job, 1, is_active=1)
        _rubric(db, job, 2, is_active=1)
        assert _next_draft_version(db, job.id) == 0

    def test_scoped_per_job(self, db):
        company = _company(db)
        job_a, job_b = _job(db, company, "A"), _job(db, company, "B")
        _rubric(db, job_a, 0, is_active=0)
        assert _next_draft_version(db, job_a.id) == -1
        assert _next_draft_version(db, job_b.id) == 0


class TestRubricLoading:
    def test_current_record_is_highest_active_version_not_draft(self, db):
        job = _job(db, _company(db))
        _rubric(db, job, 1, is_active=1, seniority="junior")
        v2 = _rubric(db, job, 2, is_active=1, seniority="senior")
        _rubric(db, job, 0, is_active=0, seniority="lead")  # draft
        db.commit()
        invalidate_cache(job.id)

        rubric, record_id = load_current_rubric_record(job.id)
        assert record_id == v2.id
        assert rubric.seniority == "senior"

    def test_current_record_is_tenant_scoped(self, db):
        company = _company(db)
        other = _company(db)
        job = _job(db, company)
        foreign = _rubric(db, job, 1, is_active=1, company_id=other.id)
        db.commit()

        _, record_id = load_current_rubric_record(
            job.id, rubric_id=foreign.id, company_id=company.id
        )
        assert record_id != foreign.id

    def test_load_by_id_resolves_and_respects_tenant(self, db):
        company = _company(db)
        other = _company(db)
        job = _job(db, company)
        r = _rubric(db, job, 1, is_active=1, seniority="senior")
        db.commit()

        loaded = load_rubric_by_id(r.id, db=db)
        assert loaded is not None
        assert loaded.job_id == job.id
        assert loaded.seniority == "senior"

        assert load_rubric_by_id(r.id, db=db, company_id=company.id) is not None
        assert load_rubric_by_id(r.id, db=db, company_id=other.id) is None
