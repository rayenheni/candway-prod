"""Tests for AI audit hash-chaining immutability (C4)."""
import hashlib
import json
from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session

from backend.ai_audit import (
    _compute_record_hash,
    detect_tampering,
    get_audit_detail,
    log_ai_call,
    verify_audit_chain,
)
from backend.database import AIAuditLog, SessionLocal, engine


def _ensure_table():
    """Create only the AIAuditLog table without affecting other tables."""
    AIAuditLog.__table__.create(bind=engine, checkfirst=True)


def _drop_table():
    """Drop only the AIAuditLog table."""
    AIAuditLog.__table__.drop(bind=engine, checkfirst=True)


class TestAuditHashChain:
    def setup_method(self):
        _ensure_table()

    def teardown_method(self):
        _drop_table()

    # -----------------------------------------------------------------
    # Happy path
    # -----------------------------------------------------------------

    def test_empty_chain_is_valid(self):
        """Edge case: an empty chain should be valid."""
        session = SessionLocal()
        try:
            is_valid, errors = verify_audit_chain(session)
            assert is_valid is True
            assert errors == []
        finally:
            session.close()

    def test_single_record_chain(self):
        """A single audit record with a valid hash."""
        log_ai_call(action="test_action", model_version="test-model", success=True, application_id=1, company_id=1)
        session = SessionLocal()
        try:
            is_valid, errors = verify_audit_chain(session)
            assert is_valid is True, f"Errors: {errors}"
        finally:
            session.close()

    def test_three_record_chain_integrity(self):
        """Three records in sequence — all hashes must link."""
        log_ai_call(action="first", model_version="m1", success=True, application_id=1, company_id=1)
        log_ai_call(action="second", model_version="m2", success=True, application_id=1, company_id=1)
        log_ai_call(action="third", model_version="m3", success=True, application_id=1, company_id=1)

        session = SessionLocal()
        try:
            is_valid, errors = verify_audit_chain(session)
            assert is_valid is True, f"Chain verification failed: {errors}"

            records = (
                session.query(AIAuditLog)
                .order_by(AIAuditLog.created_at.asc())
                .all()
            )
            assert len(records) == 3
            assert records[0].previous_hash is None
            assert records[1].previous_hash == records[0].record_hash
            assert records[2].previous_hash == records[1].record_hash
        finally:
            session.close()

    def test_hash_is_deterministic(self):
        """Same inputs produce the same hash."""
        h1 = _compute_record_hash(None, "test", "v1", "hello", "2025-01-01")
        h2 = _compute_record_hash(None, "test", "v1", "hello", "2025-01-01")
        assert h1 == h2

    # -----------------------------------------------------------------
    # Tamper detection
    # -----------------------------------------------------------------

    def test_detect_content_tampering(self):
        """Modifying a record's content must break its hash."""
        log_ai_call(action="first", model_version="m1", prompt="original prompt", success=True, application_id=1, company_id=1)

        session = SessionLocal()
        try:
            r = session.query(AIAuditLog).first()
            r.prompt_used = "TAMPERED CONTENT"
            session.commit()
        finally:
            session.close()

        tampers = detect_tampering()
        assert len(tampers) >= 1
        assert any("CRITICAL" in str(t.get("severity", "")) for t in tampers)

    def test_detect_reordering(self):
        """Reordering records must break the chain."""
        log_ai_call(action="record_a", model_version="m1", success=True, application_id=1, company_id=1)
        log_ai_call(action="record_b", model_version="m2", success=True, application_id=1, company_id=1)

        session = SessionLocal()
        try:
            records = (
                session.query(AIAuditLog)
                .order_by(AIAuditLog.created_at.asc())
                .all()
            )
            records[0].action, records[1].action = (
                records[1].action,
                records[0].action,
            )
            session.commit()
        finally:
            session.close()

        is_valid, errors = verify_audit_chain()
        assert is_valid is False

    def test_detect_new_record_in_middle(self):
        """Inserting an unlinked record must be detected."""
        log_ai_call(action="first", model_version="m1", success=True, application_id=1, company_id=1)
        log_ai_call(action="third", model_version="m3", success=True, application_id=1, company_id=1)

        session = SessionLocal()
        try:
            first = session.query(AIAuditLog).order_by(AIAuditLog.created_at.asc()).first()
            now = datetime.now(UTC).replace(tzinfo=None)
            fake = AIAuditLog(
                application_id=1,
                company_id=1,
                action="injected",
                model_version="fake",
                record_hash="injected_hash",
                previous_hash=first.record_hash,
                created_at=now,
            )
            session.add(fake)
            session.commit()
        finally:
            session.close()

        tampers = detect_tampering()
        assert len(tampers) >= 1

    # -----------------------------------------------------------------
    # Hash format
    # -----------------------------------------------------------------

    def test_hash_format(self):
        """record_hash must be a 64-character hex string (SHA-256)."""
        log_ai_call(action="fmt_test", model_version="v1", success=True, application_id=1, company_id=1)
        session = SessionLocal()
        try:
            r = session.query(AIAuditLog).first()
            assert r.record_hash is not None
            assert len(r.record_hash) == 64
            int(r.record_hash, 16)  # must be valid hex
        finally:
            session.close()

    def test_previous_hash_none_for_first(self):
        """The very first record must have previous_hash = None."""
        log_ai_call(action="first_ever", model_version="v1", success=True, application_id=1, company_id=1)
        session = SessionLocal()
        try:
            r = session.query(AIAuditLog).first()
            assert r.previous_hash is None
        finally:
            session.close()
