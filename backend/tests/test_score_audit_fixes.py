"""Tests for score consistency, campaign upload, and rubric cache."""

from datetime import datetime
from unittest.mock import MagicMock

from backend.rubric.rubric_loader import _CACHE, _CACHE_MAX_ENTRIES, _prune_cache
from backend.score_drift_monitor import (
    check_population_health,
    find_divergent_scores,
)


class TestScoreDriftMonitor:
    def test_find_divergent_scores_returns_empty(self, db_session):
        divergent = find_divergent_scores(db_session, limit=10)
        assert divergent == []

    def test_health_stats_counts_correctly(self, db_session):
        from backend.database import Application, User

        user = User(email="health1@test.com", name="Health 1", role="candidate")
        db_session.add(user)
        db_session.flush()

        app_no_score = Application(
            user_id=user.id,
            email="health1@test.com",
            full_name="Health 1",
            status="pending",
        )
        db_session.add(app_no_score)
        db_session.flush()

        health = check_population_health(db_session)
        assert health["total_applications"] >= 1
        assert health["has_application_score"] == 0


class TestRubricCache:
    def test_cache_prune_removes_expired(self):
        from datetime import timedelta

        from backend.rubric.rubric_loader import CachedRubric

        now = datetime.utcnow()
        _CACHE["old"] = CachedRubric(
            rubric=MagicMock(), expires_at=now - timedelta(minutes=1)
        )
        _CACHE["fresh"] = CachedRubric(
            rubric=MagicMock(), expires_at=now + timedelta(minutes=5)
        )

        _prune_cache()

        assert "old" not in _CACHE
        assert "fresh" in _CACHE

    def test_cache_prune_enforces_max_entries(self):
        from datetime import timedelta

        from backend.rubric.rubric_loader import CachedRubric

        for i in range(_CACHE_MAX_ENTRIES):
            _CACHE[f"item_{i}"] = CachedRubric(
                rubric=MagicMock(),
                expires_at=datetime.utcnow() + timedelta(minutes=5),
            )

        assert len(_CACHE) >= _CACHE_MAX_ENTRIES
        _prune_cache()
        assert len(_CACHE) <= _CACHE_MAX_ENTRIES

    def teardown_method(self):
        _CACHE.clear()
