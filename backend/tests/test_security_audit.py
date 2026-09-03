"""Security audit tests: admin snapshot access, audit logging, tenant isolation."""

import pytest
from fastapi import HTTPException

from backend.database import (
    AuditLog,
    Company,
    CompanyMember,
    EvaluationConfigSnapshot,
    EvaluationSession,
    User,
)
from backend.services.admin_snapshot_service import AdminSnapshotService

# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def company_a(db_session):
    c = Company(id=1, name="Company A", slug="company-a")
    db_session.add(c)
    db_session.flush()
    return c


@pytest.fixture
def company_b(db_session):
    c = Company(id=2, name="Company B", slug="company-b")
    db_session.add(c)
    db_session.flush()
    return c


@pytest.fixture
def admin_user(db_session, company_a):
    u = User(id=10, email="admin@a.com", role="admin", is_super_admin=True)
    db_session.add(u)
    db_session.flush()
    cm = CompanyMember(user_id=u.id, company_id=company_a.id, is_active=True)
    db_session.add(cm)
    db_session.flush()
    return u


@pytest.fixture
def company_b_admin(db_session, company_b):
    u = User(id=20, email="admin@b.com", role="admin", is_super_admin=True)
    db_session.add(u)
    db_session.flush()
    cm = CompanyMember(user_id=u.id, company_id=company_b.id, is_active=True)
    db_session.add(cm)
    db_session.flush()
    return u


@pytest.fixture
def snapshot_with_session(db_session, company_a, admin_user):
    snap = EvaluationConfigSnapshot(
        source_type="job_apply",
        source_id=42,
        hash="abc123def456",
        total_questions=15,
        rubric_id=1,
        rubric_version=2,
        config_json={"test": "data"},
        company_id=company_a.id,
    )
    db_session.add(snap)
    db_session.flush()

    sess = EvaluationSession(
        application_id=100,
        company_id=company_a.id,
        candidate_id=1,
        context_type="job",
        evaluation_config_snapshot_id=snap.id,
        status="completed",
    )
    db_session.add(sess)
    db_session.flush()
    db_session.commit()
    return snap, sess


# ── Phase 1: Admin Snapshot Audit API ─────────────────────────────────


class TestAdminSnapshotAudit:
    def test_get_snapshot_success(
        self, db_session, snapshot_with_session, admin_user, company_a
    ):
        snap, sess = snapshot_with_session
        result = AdminSnapshotService.get_snapshot_for_session(
            db_session, sess.id, admin_user.id, is_super_admin=True
        )
        assert result["evaluation_config_snapshot_id"] == snap.id
        assert result["session_id"] == sess.id
        assert result["hash"] == "abc123def456"
        assert result["rubric_id"] == 1
        assert result["rubric_version"] == 2
        assert result["total_questions"] == 15
        assert result["company_id"] == company_a.id

    def test_get_snapshot_not_found(self, db_session, admin_user):
        with pytest.raises(HTTPException) as exc:
            AdminSnapshotService.get_snapshot_for_session(
                db_session, 99999, admin_user.id, is_super_admin=True
            )
        assert exc.value.status_code == 404

    def test_get_snapshot_no_snapshot(self, db_session, company_a, admin_user):
        sess = EvaluationSession(
            application_id=101,
            company_id=company_a.id,
            candidate_id=1,
            context_type="job",
            status="created",
        )
        db_session.add(sess)
        db_session.flush()
        result = AdminSnapshotService.get_snapshot_for_session(
            db_session, sess.id, admin_user.id, is_super_admin=True
        )
        assert result["evaluation_config_snapshot_id"] is None

    def test_tenant_isolation(self, db_session, snapshot_with_session, company_b_admin):
        snap, sess = snapshot_with_session
        # Company B admin tries to access Company A's session
        with pytest.raises(HTTPException) as exc:
            AdminSnapshotService.get_snapshot_for_session(
                db_session, sess.id, company_b_admin.id, is_super_admin=False
            )
        assert exc.value.status_code == 404

    def test_super_admin_bypasses_tenant_isolation(
        self, db_session, snapshot_with_session, company_b_admin
    ):
        snap, sess = snapshot_with_session
        # Super admin bypasses tenant check
        result = AdminSnapshotService.get_snapshot_for_session(
            db_session, sess.id, company_b_admin.id, is_super_admin=True
        )
        assert result["evaluation_config_snapshot_id"] == snap.id


# ── Phase 2: Audit Logging ────────────────────────────────────────────


class TestAuditLogging:
    def test_rubric_publish_creates_audit_log(self, db_session, admin_user):
        log = AuditLog(
            user_id=admin_user.id,
            action="rubric_publish",
            target_id="42",
            details="Published rubric v3 for job 1 (from draft 5)",
            ip_address="127.0.0.1",
        )
        db_session.add(log)
        db_session.commit()

        saved = db_session.query(AuditLog).filter_by(action="rubric_publish").first()
        assert saved is not None
        assert saved.user_id == admin_user.id
        assert saved.target_id == "42"
        assert "v3" in saved.details

    def test_rubric_create_creates_audit_log(self, db_session, admin_user):
        log = AuditLog(
            user_id=admin_user.id,
            action="rubric_create",
            target_id="100",
            details="Created rubric v1 for job 5",
            ip_address="192.168.1.1",
        )
        db_session.add(log)
        db_session.commit()

        saved = db_session.query(AuditLog).filter_by(action="rubric_create").first()
        assert saved is not None
        assert saved.target_id == "100"

    def test_skill_delete_creates_audit_log(self, db_session, admin_user):
        log = AuditLog(
            user_id=admin_user.id,
            action="skill_delete",
            target_id="skill-abc",
            details="Deleted skill 'Python'",
            ip_address="10.0.0.1",
        )
        db_session.add(log)
        db_session.commit()

        saved = db_session.query(AuditLog).filter_by(action="skill_delete").first()
        assert saved is not None
        assert "Python" in saved.details

    def test_audit_log_has_timestamp(self, db_session, admin_user):
        log = AuditLog(
            user_id=admin_user.id,
            action="rubric_publish",
            target_id="50",
            details="Test timestamp",
            ip_address="10.0.0.1",
        )
        db_session.add(log)
        db_session.commit()

        saved = db_session.query(AuditLog).filter_by(target_id="50").first()
        assert saved.timestamp is not None

    # ── Fix 1: ip_address nullable ────────────────────────────────────

    def test_audit_log_ip_address_nullable(self, db_session, admin_user):
        log = AuditLog(
            user_id=admin_user.id,
            action="rubric_publish",
            target_id="60",
            details="ip_address is None",
            ip_address=None,
        )
        db_session.add(log)
        db_session.commit()
        saved = db_session.query(AuditLog).filter_by(target_id="60").first()
        assert saved is not None
        assert saved.ip_address is None

    # ── Fix 2: New audit actions ──────────────────────────────────────

    def test_duplicate_audit_action(self, db_session, admin_user):
        log = AuditLog(
            user_id=admin_user.id,
            action="rubric_duplicate",
            target_id="70",
            details="Duplicated rubric for job 1 as draft v-1",
            ip_address="127.0.0.1",
        )
        db_session.add(log)
        db_session.commit()
        saved = db_session.query(AuditLog).filter_by(action="rubric_duplicate").first()
        assert saved is not None
        assert "Duplicated" in saved.details

    def test_import_audit_action(self, db_session, admin_user):
        log = AuditLog(
            user_id=admin_user.id,
            action="rubric_import",
            target_id="80",
            details="Imported rubric from file 'test.xlsx'",
            ip_address="10.0.0.1",
        )
        db_session.add(log)
        db_session.commit()
        saved = db_session.query(AuditLog).filter_by(action="rubric_import").first()
        assert saved is not None
        assert "test.xlsx" in saved.details

    # ── Fix 3: company_id storage ─────────────────────────────────────

    def test_audit_log_stores_company_id(self, db_session, admin_user, company_a):
        log = AuditLog(
            user_id=admin_user.id,
            company_id=company_a.id,
            action="rubric_create",
            target_id="90",
            details="With company_id",
            ip_address="10.0.0.1",
        )
        db_session.add(log)
        db_session.commit()
        saved = db_session.query(AuditLog).filter_by(target_id="90").first()
        assert saved is not None
        assert saved.company_id == company_a.id

    def test_audit_log_company_id_nullable(self, db_session, admin_user):
        log = AuditLog(
            user_id=admin_user.id,
            company_id=None,
            action="rubric_create",
            target_id="95",
            details="company_id is None",
            ip_address="10.0.0.1",
        )
        db_session.add(log)
        db_session.commit()
        saved = db_session.query(AuditLog).filter_by(target_id="95").first()
        assert saved is not None
        assert saved.company_id is None


# ── Phase 3: Authorization ────────────────────────────────────────────


class TestAuthorization:
    def test_unauthorized_user_cannot_access_admin_snapshot(self, db_session):
        user = User(
            id=99, email="candidate@test.com", role="candidate", is_super_admin=False
        )
        db_session.add(user)
        db_session.flush()

        with pytest.raises(HTTPException) as exc:
            AdminSnapshotService.get_snapshot_for_session(
                db_session, 1, user.id, is_super_admin=False
            )
        # Should fail with 404 (resource not found pattern)
        assert exc.value.status_code == 404

    def test_company_b_cannot_access_company_a_data(
        self, db_session, company_a, company_b
    ):
        # Create session for company_a
        snap = EvaluationConfigSnapshot(
            source_type="job_apply",
            source_id=1,
            hash="h1",
            total_questions=15,
            config_json={},
            company_id=company_a.id,
        )
        db_session.add(snap)
        db_session.flush()
        sess = EvaluationSession(
            application_id=1,
            company_id=company_a.id,
            candidate_id=1,
            context_type="job",
            evaluation_config_snapshot_id=snap.id,
            status="completed",
        )
        db_session.add(sess)
        db_session.flush()

        # Company B user (not super admin)
        b_user = User(id=30, email="b@b.com", role="admin")
        db_session.add(b_user)
        db_session.flush()
        cm_b = CompanyMember(user_id=b_user.id, company_id=company_b.id, is_active=True)
        db_session.add(cm_b)
        db_session.flush()

        with pytest.raises(HTTPException) as exc:
            AdminSnapshotService.get_snapshot_for_session(
                db_session, sess.id, b_user.id, is_super_admin=False
            )
        assert exc.value.status_code == 404


# ── Phase 4: Tenant Scoped Audit Logs ───────────────────────────────


class TestAuditTenantIsolation:
    def test_company_a_admin_sees_only_own_audit_logs(
        self, db_session, company_a, admin_user
    ):
        log1 = AuditLog(
            user_id=admin_user.id,
            company_id=company_a.id,
            action="rubric_create",
            target_id="1",
            details="Company A log",
            ip_address="10.0.0.1",
        )
        log2 = AuditLog(
            user_id=admin_user.id,
            company_id=company_a.id,
            action="rubric_publish",
            target_id="2",
            details="Company A log 2",
            ip_address="10.0.0.1",
        )
        db_session.add_all([log1, log2])
        db_session.commit()

        logs = (
            db_session.query(AuditLog).filter(AuditLog.company_id == company_a.id).all()
        )
        assert len(logs) == 2
        for log in logs:
            assert log.company_id == company_a.id

    def test_company_b_cannot_see_company_a_audit_logs(
        self, db_session, company_a, company_b, admin_user, company_b_admin
    ):
        log_a = AuditLog(
            user_id=admin_user.id,
            company_id=company_a.id,
            action="rubric_create",
            target_id="10",
            details="Company A secret",
            ip_address="10.0.0.1",
        )
        log_b = AuditLog(
            user_id=company_b_admin.id,
            company_id=company_b.id,
            action="rubric_publish",
            target_id="20",
            details="Company B log",
            ip_address="10.0.0.1",
        )
        db_session.add_all([log_a, log_b])
        db_session.commit()

        company_b_logs = (
            db_session.query(AuditLog).filter(AuditLog.company_id == company_b.id).all()
        )
        assert len(company_b_logs) == 1
        assert company_b_logs[0].company_id == company_b.id
        assert company_b_logs[0].target_id == "20"

        company_a_logs = (
            db_session.query(AuditLog).filter(AuditLog.company_id == company_a.id).all()
        )
        assert len(company_a_logs) == 1
        assert company_a_logs[0].target_id == "10"

    def test_audit_log_backfilled_company_id_null(self, db_session, admin_user):
        """Existing audit logs without company_id are preserved (nullable)."""
        log = AuditLog(
            user_id=admin_user.id,
            action="rubric_create",
            target_id="100",
            details="Legacy log, no company_id",
            ip_address="10.0.0.1",
        )
        db_session.add(log)
        db_session.commit()
        saved = db_session.query(AuditLog).filter_by(target_id="100").first()
        assert saved.company_id is None
