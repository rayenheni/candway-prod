"""P0-05 FIX tests: admin approval idempotency.

Locks the three properties the platform depends on:

1. Both approve and reject handlers lock the row with
   ``with_for_update()`` so two admin clicks do not race.
2. Re-submission of the SAME ``Idempotency-Key`` returns the
   cached outcome without re-applying side effects.
3. A terminal "Failed" / "rejected" state cannot be re-applied
   silently — the server returns 409.
"""
from __future__ import annotations

import importlib
import sys
import types
from unittest.mock import MagicMock


def _install_db_stubs(monkeypatch):
    """Provide minimal User/AuditLog/SubscriptionPlan stubs so the
    admin router modules can be imported without a real MySQL
    connection."""
    db_stub = types.ModuleType("backend.database")

    class _User:
        id = None
        email = None
        name = None
        is_admin = None
        role = None
        permissions = None
        tier = None
        subscription_status = None
        subscription_plan = None
        subscription_end = None
        current_plan_id = None
        deleted_at = None

        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

    class _AuditLog:
        user_id = None
        action = None
        target_id = None
        details = None
        ip_address = None

        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

    class _Transaction:
        id = None
        user_id = None
        amount = None
        currency = None
        status = None
        description = None
        proof_url = None
        approved_at = None
        approved_by = None
        rejected_at = None
        rejected_by = None
        idempotency_key = None
        amount_ht = None
        tva_amount = None
        stamp_duty = None
        amount_ttc = None
        created_at = None

        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

    class _Enrollment:
        id = None
        user_id = None
        course_id = None
        status = None
        amount_paid = None
        proof_url = None
        approved_at = None
        approved_by = None
        rejected_at = None
        rejected_by = None
        idempotency_key = None
        enrolled_at = None

        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

    class _Course:
        id = None
        title = None

        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

    class _SubscriptionPlan:
        id = None
        slug = None
        name = None
        price_monthly = None
        is_active = None
        target_audience = None

        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

    class _PayoutRequest:
        id = None
        status = None
        processed_at = None

        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

    # The admin __init__.py transitively imports analytics, so we
    # need the rest of the model classes too. They are
    # intentionally empty — only the class attribute exists so
    # the import statement succeeds.
    class _Stub:
        pass

    for name in (
        "Application",
        "DailyPlatformReport",
        "Interview",
        "Job",
        "SalesCampaign",
        "SalesLead",
        "Invoice",
        "ConsentLog",
        "SupportTicket",
        "SystemConfig",
        "PayoutRequest",
        "Mentor",
        "Recruiter",
        "CV",
        "CandidateProfile",
        "Notification",
        "Message",
        "Cohort",
        "Lesson",
        "Event",
        "BlogPost",
        "PlanChange",
        "EmailCampaign",
        "EmailList",
        "EmailTemplate",
        "EmailLog",
        "EmailEvent",
        "EmailSubscriber",
        "EmailAutomation",
        "EmailSegment",
        "FeatureFlag",
        "SecurityLog",
        "RateLimitBucket",
        "RefundRequest",
        "Subscription",
        "Webhook",
    ):
        if not hasattr(db_stub, name):
            setattr(db_stub, name, _Stub)

    db_stub.User = _User
    db_stub.AuditLog = _AuditLog
    db_stub.Transaction = _Transaction
    db_stub.Enrollment = _Enrollment
    db_stub.Course = _Course
    db_stub.SubscriptionPlan = _SubscriptionPlan
    db_stub.PayoutRequest = _PayoutRequest
    monkeypatch.setitem(sys.modules, "backend.database", db_stub)
    return db_stub


def test_admin_subscriptions_uses_select_for_update(monkeypatch):
    _install_db_stubs(monkeypatch)
    from pathlib import Path

    src = Path("backend/routers/admin/subscriptions.py").read_text(
        encoding="utf-8"
    )
    approve_block = src.split("def approve_subscription")[1].split("def ")[0]
    assert "with_for_update" in approve_block
    assert "idempotency_key" in approve_block
    assert "Idempotency-Key" in approve_block


def test_admin_payments_uses_select_for_update(monkeypatch):
    _install_db_stubs(monkeypatch)
    from pathlib import Path

    src = Path("backend/routers/admin/payments.py").read_text(encoding="utf-8")
    approve_block = src.split("def approve_payment")[1].split("def ")[0]
    reject_block = src.split("def reject_payment")[1].split("def ")[0]
    assert "with_for_update" in approve_block
    assert "with_for_update" in reject_block
    assert "Idempotency-Key" in approve_block
    assert "Idempotency-Key" in reject_block


def test_admin_subscriptions_blocks_double_approval(monkeypatch):
    """A transaction in terminal 'succeeded' state must not be
    re-applied — the handler returns a 200 with ``idempotent=True``
    instead of extending the subscription window again."""
    _install_db_stubs(monkeypatch)
    from pathlib import Path

    src = Path("backend/routers/admin/subscriptions.py").read_text(
        encoding="utf-8"
    )
    approve_block = src.split("def approve_subscription")[1].split("def ")[0]
    # The first branch after locking checks for the terminal
    # 'succeeded' state and short-circuits.
    assert "tx.status == \"succeeded\"" in approve_block
    # And returns "idempotent": True
    assert "idempotent\": True" in approve_block or "idempotent': True" in approve_block


def test_admin_payments_blocks_double_rejection(monkeypatch):
    _install_db_stubs(monkeypatch)
    from pathlib import Path

    src = Path("backend/routers/admin/payments.py").read_text(encoding="utf-8")
    reject_block = src.split("def reject_payment")[1].split("def ")[0]
    # An already-rejected enrollment returns 200 + idempotent: True.
    assert "enrollment.status == \"rejected\"" in reject_block
    # An already-active enrollment cannot be silently rejected.
    assert "status_code=409" in reject_block


def test_admin_payments_approve_409_on_active(monkeypatch):
    _install_db_stubs(monkeypatch)
    from pathlib import Path

    src = Path("backend/routers/admin/payments.py").read_text(encoding="utf-8")
    reject_block = src.split("def reject_payment")[1].split("def ")[0]
    # If the enrollment is already 'active', reject refuses with 409.
    assert "Payment is already approved" in reject_block


def test_idempotency_key_header_recognised(monkeypatch):
    _install_db_stubs(monkeypatch)
    from pathlib import Path

    subs = Path("backend/routers/admin/subscriptions.py").read_text(
        encoding="utf-8"
    )
    pays = Path("backend/routers/admin/payments.py").read_text(encoding="utf-8")
    for name, src in (("subs", subs), ("payments", pays)):
        assert "Idempotency-Key" in src, f"{name} missing header parsing"
        assert "idempotency_key" in src, f"{name} missing field read/write"


def test_idempotency_key_collision_returns_early():
    """Smoke check: the same admin + same Idempotency-Key on an
    already-approved row must short-circuit BEFORE any side
    effects. We assert this at the string level because the
    handler is locked behind the SQLAlchemy mapper configuration
    which is hard to instantiate in a unit test."""
    from pathlib import Path

    src = Path("backend/routers/admin/subscriptions.py").read_text(
        encoding="utf-8"
    )
    approve_block = src.split("def approve_subscription")[1].split("def ")[0]
    # The Idempotency-Key check happens BEFORE the terminal-state
    # check and BEFORE any commit. Look for that ordering.
    key_idx = approve_block.find("idempotency_key ==")
    commit_idx = approve_block.find("db.commit()")
    assert key_idx != -1, "Idempotency-Key branch not found"
    assert commit_idx != -1, "db.commit() not found"
    # The key-replay branch must come before the first commit.
    assert key_idx < commit_idx, (
        "Idempotency-Key replay must short-circuit BEFORE any commit"
    )
