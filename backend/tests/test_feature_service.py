"""Tests for the feature evaluation service (Monetization S7).

Covers: flag row precedence, kill switches, maintenance mode, internal
visibility, audience gating, plan restrictions, rollout percentage, per-user
unlocks, company override and legacy plan-matrix fallback.
"""

from datetime import UTC, datetime, timedelta

import pytest

from backend.database import FeatureFlag
from backend.services import feature_service as fs
from backend.subscription_service import SubscriptionService


@pytest.fixture
def flag(db_session, test_company, **kwargs):
    data = {
        "flag_key": "test_flag",
        "company_id": test_company.id,
        "enabled": True,
        "rollout_percentage": 100,
        "visibility": "public",
        "audiences": "all",
    }
    data.update(kwargs)
    f = FeatureFlag(**data)
    db_session.add(f)
    db_session.commit()
    db_session.refresh(f)
    return f


def test_enabled_returns_true(db_session, test_recruiter, test_company, flag):
    test_recruiter._company_id = test_company.id
    enabled, reason = fs.feature_enabled(
        db_session, "test_flag", test_recruiter, test_company.id
    )
    assert enabled is True
    assert reason == "flag"


def test_kill_switch_disables(db_session, test_recruiter, test_company):
    from backend.database import FeatureFlag as FF

    f = FF(
        flag_key="killed_flag",
        company_id=test_company.id,
        enabled=True,
        rollout_percentage=100,
        kill_switch=True,
    )
    db_session.add(f)
    db_session.commit()
    test_recruiter._company_id = test_company.id
    enabled, reason = fs.feature_enabled(
        db_session, "killed_flag", test_recruiter, test_company.id
    )
    assert enabled is False
    assert reason == "maintenance"


def test_maintenance_mode_disables(db_session, test_recruiter, test_company):
    f = FeatureFlag(
        flag_key="maint_flag",
        company_id=test_company.id,
        enabled=True,
        rollout_percentage=100,
        maintenance_mode=True,
    )
    db_session.add(f)
    db_session.commit()
    test_recruiter._company_id = test_company.id
    enabled, reason = fs.feature_enabled(
        db_session, "maint_flag", test_recruiter, test_company.id
    )
    assert enabled is False
    assert reason == "maintenance"


def test_internal_visibility_admin_only(db_session, test_recruiter, test_company):
    f = FeatureFlag(
        flag_key="internal_flag",
        company_id=test_company.id,
        enabled=True,
        rollout_percentage=100,
        visibility="internal",
    )
    db_session.add(f)
    db_session.commit()
    test_recruiter._company_id = test_company.id
    enabled, reason = fs.feature_enabled(
        db_session, "internal_flag", test_recruiter, test_company.id
    )
    assert enabled is False
    assert reason == "admin_only"


def test_audience_gating(db_session, test_recruiter, test_company):
    f = FeatureFlag(
        flag_key="aud_flag",
        company_id=test_company.id,
        enabled=True,
        rollout_percentage=100,
        audiences="candidate",
    )
    db_session.add(f)
    db_session.commit()
    test_recruiter._company_id = test_company.id
    enabled, reason = fs.feature_enabled(
        db_session, "aud_flag", test_recruiter, test_company.id
    )
    assert enabled is False
    assert reason == "audience"


def test_plan_restrictions_block(db_session, test_recruiter, test_company):
    f = FeatureFlag(
        flag_key="plan_flag",
        company_id=test_company.id,
        enabled=True,
        rollout_percentage=100,
        plan_restrictions="recruiter-enterprise",
    )
    db_session.add(f)
    db_session.commit()
    test_recruiter._company_id = test_company.id
    enabled, reason = fs.feature_enabled(
        db_session, "plan_flag", test_recruiter, test_company.id
    )
    # free_recruiter default plan is not in the restriction list
    assert enabled is False
    assert reason == "plan"


def test_rollout_percentage_zero_blocks(db_session, test_recruiter, test_company):
    f = FeatureFlag(
        flag_key="rollout_flag",
        company_id=test_company.id,
        enabled=True,
        rollout_percentage=0,
    )
    db_session.add(f)
    db_session.commit()
    test_recruiter._company_id = test_company.id
    enabled, reason = fs.feature_enabled(
        db_session, "rollout_flag", test_recruiter, test_company.id
    )
    assert enabled is False
    assert reason == "rollout"


def test_permanent_unlock_overrides_disabled_flag(
    db_session, test_recruiter, test_company
):
    f = FeatureFlag(
        flag_key="unlock_flag",
        company_id=test_company.id,
        enabled=False,
        rollout_percentage=0,
        permanent_unlock_user_id=test_recruiter.id,
    )
    db_session.add(f)
    db_session.commit()
    test_recruiter._company_id = test_company.id
    enabled, reason = fs.feature_enabled(
        db_session, "unlock_flag", test_recruiter, test_company.id
    )
    assert enabled is True
    assert reason == "override"


def test_temp_unlock_expired_does_not_override(
    db_session, test_recruiter, test_company
):
    past = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=1)
    f = FeatureFlag(
        flag_key="temp_unlock_flag",
        company_id=test_company.id,
        enabled=False,
        rollout_percentage=0,
        temp_unlock_user_id=test_recruiter.id,
        temp_unlock_until=past,
    )
    db_session.add(f)
    db_session.commit()
    test_recruiter._company_id = test_company.id
    enabled, reason = fs.feature_enabled(
        db_session, "temp_unlock_flag", test_recruiter, test_company.id
    )
    assert enabled is False
    assert reason == "rollout"


def test_company_override_flag(db_session, test_recruiter, test_company):
    # The override flag row keyed by company_override_key; disabled globally
    # but enabled for this company via the override row.
    f = FeatureFlag(
        flag_key="company_flag",
        company_id=test_company.id,
        enabled=False,
        rollout_percentage=0,
        company_override_key="company_flag_override",
    )
    override = FeatureFlag(
        flag_key="company_flag_override",
        company_id=test_company.id,
        enabled=True,
        rollout_percentage=100,
    )
    db_session.add_all([f, override])
    db_session.commit()
    test_recruiter._company_id = test_company.id
    enabled, reason = fs.feature_enabled(
        db_session, "company_flag", test_recruiter, test_company.id
    )
    assert enabled is True
    assert reason == "company_override"


def test_missing_flag_falls_back_to_plan_matrix(
    db_session, test_recruiter, test_company
):
    test_recruiter._company_id = test_company.id
    # No flag row for "ghost_report" in this test company; legacy matrix has
    # no permissions key → disabled.
    enabled, reason = fs.feature_enabled(
        db_session, "ghost_report", test_recruiter, test_company.id
    )
    assert enabled is False
    assert reason in ("plan_matrix", "missing")


def test_legacy_subscription_service_has_feature_consults_flags(
    db_session, test_recruiter, test_company, flag
):
    test_recruiter._company_id = test_company.id
    # has_feature should route through feature_service (flag enabled=True)
    assert (
        SubscriptionService.has_feature(test_recruiter, "test_flag", db_session) is True
    )


def test_company_isolation(db_session, test_company, test_company_b, test_recruiter_b):
    f = FeatureFlag(
        flag_key="iso_flag",
        company_id=test_company.id,
        enabled=True,
        rollout_percentage=100,
    )
    db_session.add(f)
    db_session.commit()
    test_recruiter_b._company_id = test_company_b.id
    enabled, reason = fs.feature_enabled(
        db_session, "iso_flag", test_recruiter_b, test_company_b.id
    )
    # Flag exists only in company A → company B sees no row → disabled
    assert enabled is False
    assert reason in ("plan_matrix", "missing")
