"""Tests for RubricSnapshot immutability and scoring integration."""

import json

import pytest

from backend.database import (
    Company,
    EvaluationResult,
    EvaluationSession,
)
from backend.database import (
    Rubric as RubricDB,
)
from backend.rubric.rubric_snapshotter import RubricSnapshotter


@pytest.fixture
def rubric_record(db_session):
    company = Company(name="Rubric Snapshot Co", slug="rubric-snapshot-co")
    db_session.add(company)
    db_session.flush()
    rec = RubricDB(
        job_id=1,
        company_id=company.id,
        version=1,
        title="Test Rubric",
        criteria_json=json.dumps(
            {"categories": [{"name": "Technical", "weight": 0.6}]}
        ),
        skill_weights=json.dumps({"Python": 0.8, "SQL": 0.2}),
        passing_score=60.0,
        max_score=100.0,
    )
    db_session.add(rec)
    db_session.flush()
    return rec


class TestRubricSnapshotModel:
    def test_create_snapshot(self, db_session, rubric_record):
        snapshot = RubricSnapshotter.create_from_rubric_record(
            db_session, rubric_record
        )
        assert snapshot.id is not None
        assert snapshot.original_rubric_id == rubric_record.id
        assert snapshot.version == 1
        assert snapshot.criteria_json is not None
        assert snapshot.rubric_title == "Test Rubric"
        assert snapshot.passing_score == 60.0

    def test_snapshot_is_immutable(self, db_session, rubric_record):
        snapshot = RubricSnapshotter.create_from_rubric_record(
            db_session, rubric_record
        )
        db_session.commit()

        rubric_record.passing_score = 80.0
        db_session.flush()

        db_session.refresh(snapshot)
        assert snapshot.passing_score == 60.0

    def test_create_snapshot_from_scratch(self, db_session):
        company = Company(name="Manual Snapshot Co", slug="manual-snapshot-co")
        db_session.add(company)
        db_session.flush()
        snapshot = RubricSnapshotter.create_snapshot(
            db_session,
            rubric_id=42,
            company_id=company.id,
            job_id=1,
            version=2,
            criteria_json={"test": "data"},
            rubric_title="Manual Snapshot",
            passing_score=75.0,
        )
        assert snapshot.id is not None
        assert snapshot.rubric_title == "Manual Snapshot"
        assert snapshot.criteria_json == {"test": "data"}


class TestRubricSnapshotScoringIntegration:
    def test_evaluation_session_links_snapshot(self, db_session, rubric_record):
        snapshot = RubricSnapshotter.create_from_rubric_record(
            db_session, rubric_record
        )
        session = EvaluationSession(
            application_id=1,
            company_id=rubric_record.company_id,
            rubric_id=rubric_record.id,
            rubric_snapshot_id=snapshot.id,
            status="completed",
        )
        db_session.add(session)
        db_session.flush()

        assert session.rubric_snapshot_id == snapshot.id
        assert session.rubric_snapshot.original_rubric_id == rubric_record.id

    def test_evaluation_result_links_snapshot(self, db_session, rubric_record):
        snapshot = RubricSnapshotter.create_from_rubric_record(
            db_session, rubric_record
        )
        session = EvaluationSession(
            application_id=1,
            company_id=rubric_record.company_id,
            rubric_id=rubric_record.id,
            status="completed",
        )
        db_session.add(session)
        db_session.flush()

        result = EvaluationResult(
            evaluation_session_id=session.id,
            rubric_snapshot_id=snapshot.id,
            scoring_status="SCORED",
            final_score=85.0,
        )
        db_session.add(result)
        db_session.flush()

        assert result.rubric_snapshot_id == snapshot.id

    def test_editing_rubric_does_not_affect_snapshot(self, db_session, rubric_record):
        snapshot = RubricSnapshotter.create_from_rubric_record(
            db_session, rubric_record
        )
        original_criteria = snapshot.criteria_json

        rubric_record.criteria_json = json.dumps(
            {"categories": [{"name": "Modified", "weight": 1.0}]}
        )
        db_session.flush()

        db_session.refresh(snapshot)
        assert snapshot.criteria_json == original_criteria
