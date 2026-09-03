"""Tests for EvaluationConfigSnapshot determinism, isolation, and resolution."""

import json

from backend.models.evaluation.config_snapshot import (
    EntryPoint,
    EvaluationConfigSnapshot,
    ResolvedEvaluationConfig,
)
from backend.rubric.config_resolver import ConfigurationResolver

# ── Helpers ──────────────────────────────────────────────────────────


class FakeRubric:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class FakeJob:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


# ── Hash determinism ─────────────────────────────────────────────────


class TestHashDeterminism:
    def test_same_config_same_hash(self):
        c1 = ResolvedEvaluationConfig(
            source_type="job_apply", total_questions=10, language="en"
        )
        c2 = ResolvedEvaluationConfig(
            source_type="job_apply", total_questions=10, language="en"
        )
        assert c1.compute_hash() == c2.compute_hash()

    def test_diff_config_diff_hash(self):
        c1 = ResolvedEvaluationConfig(source_type="job_apply", total_questions=10)
        c2 = ResolvedEvaluationConfig(source_type="job_apply", total_questions=15)
        assert c1.compute_hash() != c2.compute_hash()

    def test_hash_independent_of_order(self):
        c1 = ResolvedEvaluationConfig(
            source_type="campaign",
            total_questions=10,
            scoring_weights={"technical": 0.5, "soft": 0.5},
        )
        c2 = ResolvedEvaluationConfig(
            source_type="campaign",
            total_questions=10,
            scoring_weights={"soft": 0.5, "technical": 0.5},
        )
        assert c1.compute_hash() == c2.compute_hash()


# ── Resolution hierarchy ─────────────────────────────────────────────


class TestResolutionHierarchy:
    def test_rubric_defaults_applied(self, db_session):
        ep = EntryPoint(source_type="individual_audit")
        rubric = FakeRubric(
            id=5,
            version=2,
            passing_score=70.0,
            max_score=100.0,
            criteria_json=json.dumps({"skills": ["python"]}),
        )
        snap = ConfigurationResolver.resolve(db_session, ep, rubric_record=rubric)
        assert snap.rubric_id == 5
        assert snap.rubric_version == 2
        assert snap.passing_score == 70.0
        assert snap.max_score == 100.0
        assert snap.total_questions == 15  # system default
        assert snap.language == "en"  # system default

    def test_job_overrides_rubric(self, db_session):
        ep = EntryPoint(source_type="job_apply", source_id=42)
        rubric = FakeRubric(id=1, version=1, passing_score=50.0, max_score=100.0)
        job = FakeJob(interview_instructions="Follow the rules", language="fr")
        snap = ConfigurationResolver.resolve(
            db_session, ep, rubric_record=rubric, job=job
        )
        assert snap.rubric_id == 1  # from rubric
        assert snap.interview_instructions == "Follow the rules"  # from job
        assert snap.language == "fr"  # from job
        assert snap.passing_score == 50.0  # from rubric

    def test_campaign_overrides_job(self, db_session):
        ep = EntryPoint(source_type="campaign", source_id=99)
        rubric = FakeRubric(id=2, version=1, passing_score=60.0, max_score=100.0)
        job = FakeJob(interview_instructions="Job instructions", language="en")
        campaign = {
            "interview_instructions": "Campaign instructions",
            "total_questions": 20,
        }
        snap = ConfigurationResolver.resolve(
            db_session,
            ep,
            rubric_record=rubric,
            job=job,
            campaign_config=campaign,
        )
        assert snap.interview_instructions == "Campaign instructions"
        assert snap.total_questions == 20

    def test_explicit_overrides_highest_priority(self, db_session):
        ep = EntryPoint(source_type="campaign", source_id=99)
        rubric = FakeRubric(id=2, version=1, passing_score=60.0, max_score=100.0)
        job = FakeJob(interview_instructions="Job instructions")
        campaign = {
            "interview_instructions": "Campaign instructions",
            "total_questions": 20,
        }
        overrides = {"interview_instructions": "Override!", "total_questions": 5}
        snap = ConfigurationResolver.resolve(
            db_session,
            ep,
            rubric_record=rubric,
            job=job,
            campaign_config=campaign,
            explicit_overrides=overrides,
        )
        assert snap.interview_instructions == "Override!"
        assert snap.total_questions == 5

    def test_empty_overrides_dont_override_with_none(self, db_session):
        ep = EntryPoint(source_type="job_apply")
        rubric = FakeRubric(id=1, version=2, passing_score=70.0, max_score=100.0)
        job = FakeJob(interview_instructions="Keep me")
        overrides = {"total_questions": None, "language": None}
        snap = ConfigurationResolver.resolve(
            db_session,
            ep,
            rubric_record=rubric,
            job=job,
            explicit_overrides=overrides,
        )
        # None values in overrides should be ignored
        assert snap.interview_instructions == "Keep me"
        assert snap.total_questions == 15  # system default
        assert snap.language == "en"


# ── Deduplication ────────────────────────────────────────────────────


class TestDeduplication:
    def test_same_config_reuses_snapshot(self, db_session):
        ep = EntryPoint(source_type="job_apply", source_id=1)
        rubric = FakeRubric(id=10, version=1, passing_score=0.0, max_score=100.0)
        snap1 = ConfigurationResolver.resolve(db_session, ep, rubric_record=rubric)
        snap2 = ConfigurationResolver.resolve(db_session, ep, rubric_record=rubric)
        assert snap2.id == snap1.id

    def test_diff_config_diff_snapshot(self, db_session):
        ep1 = EntryPoint(source_type="job_apply", source_id=1)
        ep2 = EntryPoint(source_type="campaign", source_id=2)
        rubric = FakeRubric(id=10, version=1, passing_score=0.0, max_score=100.0)
        snap1 = ConfigurationResolver.resolve(db_session, ep1, rubric_record=rubric)
        snap2 = ConfigurationResolver.resolve(db_session, ep2, rubric_record=rubric)
        assert snap2.id != snap1.id


# ── Entry point agnostic ─────────────────────────────────────────────


class TestEntryPointAgnostic:
    def test_multiple_source_types_produce_valid_snapshots(self, db_session):
        rubric = FakeRubric(id=1, version=1, passing_score=0.0, max_score=100.0)
        for source_type in (
            "job_apply",
            "campaign",
            "individual_audit",
            "api",
            "certification",
        ):
            ep = EntryPoint(source_type=source_type, source_id=hash(source_type) % 1000)
            snap = ConfigurationResolver.resolve(db_session, ep, rubric_record=rubric)
            assert snap.source_type == source_type
            assert snap.id is not None

    def test_minimal_entry_point(self, db_session):
        ep = EntryPoint(source_type="individual_audit")
        snap = ConfigurationResolver.resolve(db_session, ep)
        assert snap.source_type == "individual_audit"
        assert snap.source_id is None
        assert snap.total_questions == 15
        assert snap.passing_score == 0.0
        assert snap.language == "en"


# ── Immutability ─────────────────────────────────────────────────────


class TestSnapshotImmutability:
    def test_snapshot_content_does_not_change(self, db_session):
        ep = EntryPoint(source_type="job_apply", source_id=42)
        rubric = FakeRubric(id=1, version=2, passing_score=75.0, max_score=100.0)
        job = FakeJob(interview_instructions="Do your best", language="en")
        snap = ConfigurationResolver.resolve(
            db_session, ep, rubric_record=rubric, job=job
        )
        stored = (
            db_session.query(EvaluationConfigSnapshot).filter_by(id=snap.id).first()
        )
        assert stored.total_questions == 15
        assert stored.passing_score == 75.0
        assert stored.rubric_id == 1
        assert stored.rubric_version == 2
        assert stored.interview_instructions == "Do your best"
        assert stored.config_json is not None

    def test_config_json_matches_denormalized(self, db_session):
        ep = EntryPoint(source_type="job_apply", source_id=42)
        rubric = FakeRubric(id=1, version=2, passing_score=75.0, max_score=100.0)
        snap = ConfigurationResolver.resolve(db_session, ep, rubric_record=rubric)
        stored = (
            db_session.query(EvaluationConfigSnapshot).filter_by(id=snap.id).first()
        )
        cfg = stored.config_json
        assert cfg["rubric_id"] == 1
        assert cfg["rubric_version"] == 2
        assert cfg["passing_score"] == 75.0
        assert cfg["total_questions"] == 15
        assert cfg["language"] == "en"
        assert cfg["source_type"] == "job_apply"
