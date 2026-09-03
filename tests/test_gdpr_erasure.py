"""P1-06 FIX tests: GDPR Article 17 erasure.

These tests stub out the SQLAlchemy model layer in ``sys.modules``
so the SQLAlchemy mapper configuration does not run (the
``User.enrollments`` relationship has multiple FK paths and
SQLite-in-memory trips the mapper). Once the stub is in place,
``backend.gdpr_erasure`` resolves ``User``/``AuditLog``/
``ConsentLog`` to MagicMock classes and the behaviour tests run
without a real DB.
"""
from __future__ import annotations

import importlib
import sys
import types
from unittest.mock import MagicMock


def _install_db_stubs(monkeypatch):
    """Replace the SQLAlchemy-heavy imports in ``backend.gdpr_erasure``
    with MagicMock classes so we can test the erasure logic
    without spinning up a real DB.

    Idempotent: safe to call multiple times in a session.
    """
    db_stub = types.ModuleType("backend.database")

    class _User:
        # SQLAlchemy-like class attributes so the call sites
        # ``User.id``, ``User.email`` etc. resolve to the column
        # descriptor rather than an instance attribute.
        id = None
        email = None
        name = None
        hashed_password = None
        temp_password = None
        phone = None
        avatar_url = None
        deleted_at = None
        candidate_profile = None
        recruiter_profile = None

        def __init__(self, **kwargs):
            self.id = kwargs.get("id", 0)
            self.email = kwargs.get("email", "")
            self.name = kwargs.get("name", "")
            self.hashed_password = kwargs.get("hashed_password")
            self.temp_password = kwargs.get("temp_password")
            self.phone = kwargs.get("phone")
            self.avatar_url = kwargs.get("avatar_url")
            self.deleted_at = None

    class _AuditLog:
        user_id = None
        action = None
        target_id = None
        details = None

        def __init__(self, **kwargs):
            self.user_id = kwargs.get("user_id")
            self.action = kwargs.get("action")
            self.target_id = kwargs.get("target_id")
            self.details = kwargs.get("details")

    class _ConsentLog:
        user_id = None
        agreement_type = None
        version = None

        def __init__(self, **kwargs):
            self.user_id = kwargs.get("user_id")
            self.agreement_type = kwargs.get("agreement_type")
            self.version = kwargs.get("version")

    class _Application:
        id = None
        user_id = None

        def __init__(self, **kwargs):
            self.id = kwargs.get("id", 0)
            self.user_id = kwargs.get("user_id", 0)

    db_stub.User = _User
    db_stub.AuditLog = _AuditLog
    db_stub.ConsentLog = _ConsentLog
    db_stub.Application = _Application
    monkeypatch.setitem(sys.modules, "backend.database", db_stub)

    # Force gdpr_erasure to re-resolve its imports so it picks up
    # the stubbed User/AuditLog/ConsentLog.
    sys.modules.pop("backend.gdpr_erasure", None)
    return importlib.import_module("backend.gdpr_erasure")


def test_module_exports_public_api(monkeypatch):
    ge = _install_db_stubs(monkeypatch)
    assert callable(ge.request_erasure)
    assert ge.ERASED_PLACEHOLDER == "[ERASED]"
    assert hasattr(ge, "ErasureReport")


def test_erasure_returns_error_when_user_missing(monkeypatch):
    ge = _install_db_stubs(monkeypatch)
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None

    report = ge.request_erasure(
        db, user_id=999, requester_id=1, requester_role="admin"
    )

    assert report.error == "user not found"
    assert report.completed_at is None
    # No side effects when there is no user to erase.
    assert not db.add.called


def test_erasure_anonymises_user(monkeypatch):
    ge = _install_db_stubs(monkeypatch)
    user = ge.User(
        id=42,
        email="alice@example.com",
        name="Alice",
        hashed_password="h",
        temp_password="t",
        phone="+216 12 345 678",
        avatar_url="https://cdn.example.com/avatars/42.png",
    )
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = user
    db.execute.return_value.scalar.return_value = 0

    report = ge.request_erasure(
        db,
        user_id=42,
        requester_id=1,
        requester_role="admin",
        reason="user_request",
    )

    assert report.error is None
    assert report.completed_at is not None
    assert user.email == "erased+42@candway.invalid"
    assert user.name == "[ERASED]"
    assert user.hashed_password is None
    assert user.temp_password is None
    assert user.phone is None
    assert user.avatar_url is None
    assert user.deleted_at is not None


def test_erasure_writes_audit_log_and_consent_log(monkeypatch):
    ge = _install_db_stubs(monkeypatch)
    user = ge.User(id=5, email="x@y.com", name="X")
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = user
    db.execute.return_value.scalar.return_value = 0

    ge.request_erasure(
        db, user_id=5, requester_id=1, requester_role="admin"
    )

    actions = []
    for c in db.add.call_args_list:
        obj = c[0][0]
        if hasattr(obj, "action"):
            actions.append(("audit", obj.action))
        if hasattr(obj, "agreement_type"):
            actions.append(("consent", obj.agreement_type))
    assert ("audit", "gdpr_erasure_request") in actions
    assert ("consent", "gdpr_erasure") in actions
    assert db.commit.called


def test_erasure_hard_delete_removes_user(monkeypatch):
    ge = _install_db_stubs(monkeypatch)
    user = ge.User(id=7, email="b@e.com", name="Bob")
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = user
    db.execute.return_value.scalar.return_value = 0

    report = ge.request_erasure(
        db,
        user_id=7,
        requester_id=1,
        requester_role="admin",
        hard_delete=True,
    )

    assert db.delete.called
    assert db.delete.call_args[0][0] is user
    assert report.rows_erased == 1
    assert report.error is None


def test_erasure_hard_delete_refused_for_non_admin(monkeypatch):
    ge = _install_db_stubs(monkeypatch)
    user = ge.User(id=8, email="c@e.com", name="Carol")
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = user
    db.execute.return_value.scalar.return_value = 0

    report = ge.request_erasure(
        db,
        user_id=8,
        requester_id=8,
        requester_role="candidate",
        hard_delete=True,
    )

    assert not db.delete.called
    assert report.rows_erased == 0


def test_erasure_audit_log_includes_requester_id(monkeypatch):
    ge = _install_db_stubs(monkeypatch)
    user = ge.User(id=99, email="d@e.com", name="D")
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = user
    db.execute.return_value.scalar.return_value = 0

    ge.request_erasure(
        db,
        user_id=99,
        requester_id=11,
        requester_role="admin",
        reason="legal_hold_release",
    )

    audit_rows = [
        c[0][0]
        for c in db.add.call_args_list
        if hasattr(c[0][0], "action")
    ]
    assert audit_rows, "No AuditLog was added"
    audit = audit_rows[0]
    assert audit.user_id == 11  # the requester
    assert audit.target_id == "99"
    assert "legal_hold_release" in audit.details


def test_erasure_completes_when_extra_columns_missing(monkeypatch):
    """Old DBs may not have ``phone`` or ``avatar_url`` columns.
    Erasure must still complete (the code uses ``hasattr``)."""
    ge = _install_db_stubs(monkeypatch)
    user = ge.User(id=13, email="e@e.com", name="E")

    # Strip the optional attributes before the function runs.
    del user.phone
    del user.avatar_url

    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = user
    db.execute.return_value.scalar.return_value = 0

    report = ge.request_erasure(
        db, user_id=13, requester_id=13, requester_role="candidate"
    )
    assert report.error is None
    assert user.email == "erased+13@candway.invalid"
    assert user.name == "[ERASED]"


def test_erasure_report_serialises_to_dict(monkeypatch):
    ge = _install_db_stubs(monkeypatch)
    user = ge.User(id=1, email="a@e.com", name="A")
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = user
    # Make db.execute(...).scalar() return 0 so verification passes.
    db.execute.return_value.scalar.return_value = 0

    report = ge.request_erasure(
        db, user_id=1, requester_id=1, requester_role="admin"
    )
    d = report.to_dict()
    assert d["user_id"] == 1
    assert d["error"] is None
    assert isinstance(d["requested_at"], str)
    assert isinstance(d["completed_at"], str)
    assert isinstance(d["tables_touched"], list)
    assert d["verification_warnings"] == []
