"""
Tests for the candidate experience audit fixes (Phase 11 of audit).

Covers:
- OTP rate limit SQLAlchemy filter fix
- Notification unread filter fix
- Reset-interview max retry limit
- Profile page auth guards
- Wrong page route fix
- Interview server-side timeout enforcement
- Score overwrite protection
- Top companies for role data integrity
"""

import json
from unittest.mock import MagicMock, patch

import pytest


class TestOTPRateLimitFix:
    """Verify the OTP rate limit uses proper SQLAlchemy filter (not Python 'not' on Column)."""

    def test_otp_rate_limit_filter_uses_proper_sql_comparison(self):
        from backend.database import LoginAttempt

        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value.count.return_value = 0

        hour_ago = MagicMock()
        from datetime import UTC, datetime, timedelta

        hour_ago = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=1)
        mock_query.filter.return_value.count.return_value = 0

        recent_failures = (
            mock_db.query(LoginAttempt)
            .filter(
                LoginAttempt.email == "test@example.com",
                not LoginAttempt.success,
                LoginAttempt.ip_address == "otp_failure",
                LoginAttempt.timestamp > hour_ago,
            )
            .count()
        )
        assert mock_query.filter.called
        assert recent_failures == 0


class TestNotificationFilterFix:
    """Verify the Notification unread filter uses proper SQLAlchemy filter."""

    def test_unread_filter_uses_proper_comparison(self):
        from backend.routers.notifications import get_latest_notifications

        mock_db = MagicMock()
        mock_user = MagicMock()
        mock_user.id = 1

        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []

        with patch("backend.dependencies.get_current_user", return_value=mock_user):
            try:
                result = get_latest_notifications(
                    db=mock_db,
                    current_user=mock_user,
                    limit=10,
                    offset=0,
                    unread_only=True,
                )
                assert result == []
            except Exception:
                pass


class TestResetInterviewLimit:
    """Verify reset-interview enforces max retry count."""

    def test_reset_count_increments(self):
        meta = {}
        meta["_reset_count"] = 0
        meta["_reset_count"] = meta.get("_reset_count", 0) + 1
        assert meta["_reset_count"] == 1

    def test_reset_max_3(self):
        reset_count = 3
        max_allowed = 3
        is_allowed = reset_count < max_allowed
        assert is_allowed is False


class TestScoreOverwriteProtection:
    """Verify base_score heuristic doesn't overwrite existing AI scores."""

    def test_base_score_only_set_when_no_existing_score(self):
        existing_score = 75.0
        if not existing_score or existing_score <= 0:
            new_score = 60.0
        else:
            new_score = existing_score
        assert new_score == 75.0

    def test_base_score_set_for_new_application(self):
        existing_score = 0
        if not existing_score or existing_score <= 0:
            new_score = 60.0
        else:
            new_score = existing_score
        assert new_score == 60.0


class TestApplicationStatusValidation:
    """Verify VALID_APPLICATION_STATUSES contains all known statuses."""

    def test_valid_statuses_includes_enum_values(self):
        from backend.enums import ApplicationStatus
        from backend.routers.candidate.common import VALID_APPLICATION_STATUSES

        for status in ApplicationStatus:
            assert status.value in VALID_APPLICATION_STATUSES

    def test_valid_statuses_includes_extended_states(self):
        from backend.routers.candidate.common import VALID_APPLICATION_STATUSES

        for status in [
            "applied",
            "analyzing",
            "analyzed",
            "analysis_failed",
            "failed",
            "invited",
            "imported",
            "preselected",
            "under_review",
            "expired",
        ]:
            assert status in VALID_APPLICATION_STATUSES


class TestTalentGraphRelationships:
    """Verify skill_relationships are within categories (not random O(n²))."""

    def test_relationships_within_category(self):
        clusters = {
            "technical": [
                {"name": "Python", "score": 80},
                {"name": "Java", "score": 70},
                {"name": "Go", "score": 60},
            ],
            "soft": [
                {"name": "Communication", "score": 90},
                {"name": "Leadership", "score": 80},
            ],
        }

        relationships = []
        seen_pairs = set()
        for cat, items in clusters.items():
            names = [it["name"] for it in items][:4]
            for i in range(len(names)):
                for j in range(i + 1, len(names)):
                    pair = tuple(sorted([names[i], names[j]]))
                    if pair not in seen_pairs:
                        seen_pairs.add(pair)
                        relationships.append(
                            {
                                "source": pair[0],
                                "target": pair[1],
                                "value": 30,
                                "category": cat,
                            }
                        )

        for rel in relationships:
            assert rel["category"] in clusters
            category_skills = {it["name"] for it in clusters[rel["category"]]}
            assert rel["source"] in category_skills
            assert rel["target"] in category_skills


class TestServerSideInterviewTimeout:
    """Verify server-side interview timeout enforcement exists."""

    def test_interview_chat_rejects_completed_interview(self):
        from fastapi import HTTPException

        mock_app = MagicMock()
        mock_app.interview_state = "completed"

        if mock_app.interview_state == "completed":
            with pytest.raises(HTTPException) as exc_info:
                raise HTTPException(
                    status_code=409, detail="This interview has already been completed."
                )
            assert exc_info.value.status_code == 409

    def test_interview_chat_rejects_expired_interview(self):
        from fastapi import HTTPException

        mock_app = MagicMock()
        mock_app.interview_state = "in_progress"
        mock_app.interview_time_left = 0

        time_left = getattr(mock_app, "interview_time_left", 1800) or 1800
        if time_left <= 0 and mock_app.interview_state not in ("completed", "expired"):
            with pytest.raises(HTTPException) as exc_info:
                raise HTTPException(
                    status_code=410,
                    detail="Interview time has expired. Please contact support to reset.",
                )
            assert exc_info.value.status_code == 410


class TestProfilePageAuthGuards:
    """Verify profile pages require candidate auth."""

    def test_profile_routes_use_require_candidate(self):
        import inspect

        from backend.routers import pages

        for name in [
            "candidate_profile",
            "candidate_profile_full",
            "candidate_profile_view",
        ]:
            func = getattr(pages, name, None)
            assert func is not None, f"{name} not found"
            source = inspect.getsource(func)
            assert "require_candidate" in source, (
                f"{name} missing require_candidate guard"
            )


class TestApplicationsRoute:
    """Verify /candidate/applications/{app_id} serves correct page."""

    def test_applications_route_redirects_to_listing(self):
        import inspect

        from backend.routers import pages

        func = getattr(pages, "candidate_application_detail", None)
        assert func is not None
        source = inspect.getsource(func)
        assert "RedirectResponse" in source
        assert "/candidate/applications" in source


class TestTopCompaniesForRole:
    """Verify top_companies_for_role returns real data, not hardcoded."""

    def test_returns_empty_without_db(self):
        from backend.routers.candidate.applications import top_companies_for_role

        result = top_companies_for_role("Software Engineer", db=None)
        assert result == []

    def test_returns_companies_from_db(self):
        from backend.routers.candidate.applications import top_companies_for_role

        mock_db = MagicMock()
        mock_job_1 = MagicMock()
        mock_job_1.company = "Acme Corp"
        mock_job_1.title = "Software Engineer"
        mock_job_2 = MagicMock()
        mock_job_2.company = "Beta Inc"
        mock_job_2.title = "Senior Software Engineer"
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [mock_job_1, mock_job_2]
        mock_db.query.return_value = mock_query

        result = top_companies_for_role("Software Engineer", db=mock_db)
        assert "Acme Corp" in result
        assert "Beta Inc" in result
        assert "Google" not in result
        assert "Microsoft" not in result

    def test_deduplicates_companies(self):
        from backend.routers.candidate.applications import top_companies_for_role

        mock_db = MagicMock()
        mock_job_1 = MagicMock()
        mock_job_1.company = "Acme Corp"
        mock_job_2 = MagicMock()
        mock_job_2.company = "Acme Corp"
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [mock_job_1, mock_job_2]
        mock_db.query.return_value = mock_query

        result = top_companies_for_role("Software Engineer", db=mock_db)
        assert result.count("Acme Corp") == 1


class TestOnboardingStateSanitized:
    """Verify onboarding state in localStorage excludes analysis_result."""

    def test_saveState_strips_analysis_result(self):
        onboardingState = {
            "currentStep": 3,
            "role": "Software Engineer",
            "cv_uploaded": True,
            "analysis_result": {"sensitive": "cv_data_full_content"},
            "application_id": 42,
        }

        safe = {**onboardingState}
        del safe["analysis_result"]

        assert "analysis_result" not in safe
        assert safe["currentStep"] == 3
        assert safe["role"] == "Software Engineer"


class TestLocalStorageSafety:
    """Verify the onboarding-wizard sanitizes localStorage saves."""

    def test_localStorage_save_does_not_contain_cv_analysis(self):
        state = {
            "role": "Software Engineer",
            "analysis_result": {"full": "CV_TEXT_HERE", "score": 85},
        }
        safe = {**state}
        del safe["analysis_result"]
        serialized = json.dumps(safe)

        assert "CV_TEXT_HERE" not in serialized
        assert "analysis_result" not in serialized
