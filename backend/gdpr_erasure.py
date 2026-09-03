"""GDPR Article 17 — Right to Erasure.

A user (or an admin on a user's behalf) can request permanent
deletion of their data. The platform must:

1. Verify the requester is allowed to act on the user (themselves
   or an admin).
2. Log the erasure request to ``ConsentLog`` for the audit trail.
3. Scrub or hard-delete every row that references ``user_id``,
   except for rows the law requires us to keep (financial
   transactions, audit logs) which are anonymised instead.
4. Honor the request synchronously for the caller's own data and
   via a background worker for the full cleanup.

The implementation is conservative: a soft delete on
``User.deleted_at`` is performed, then every PII-bearing column
is overwritten with the literal string ``"[ERASED]"`` so the
row stays in the database for foreign-key integrity but the
personal data is gone.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Iterable, List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.database import (
    Application,
    AuditLog,
    ConsentLog,
    User,
)
from backend.logger import logger

ERASED_PLACEHOLDER = "[ERASED]"


@dataclass
class ErasureReport:
    user_id: int
    requested_at: datetime
    completed_at: Optional[datetime]
    rows_erased: int
    rows_anonymised: int
    tables_touched: List[str]
    error: Optional[str] = None
    verification_warnings: Optional[List[str]] = None

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "requested_at": self.requested_at.isoformat(),
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
            "rows_erased": self.rows_erased,
            "rows_anonymised": self.rows_anonymised,
            "tables_touched": self.tables_touched,
            "error": self.error,
            "verification_warnings": self.verification_warnings,
        }


def _log_request(
    db: Session,
    user_id: int,
    requester_id: int,
    requester_role: str,
    reason: Optional[str] = None,
) -> None:
    db.add(
        AuditLog(
            user_id=requester_id,
            action="gdpr_erasure_request",
            target_id=str(user_id),
            details=(
                f"GDPR Article 17 erasure requested by {requester_role} "
                f"#{requester_id} for user #{user_id}. "
                f"reason={reason or 'user_initiated'}"
            ),
        )
    )
    db.add(
        ConsentLog(
            user_id=user_id,
            agreement_type="gdpr_erasure",
            version=f"v1|requester={requester_id}|role={requester_role}|ts={int(datetime.now(UTC).timestamp())}",
        )
    )
    db.commit()


def _scrub_table(
    db: Session,
    table_name: str,
    text_columns: Iterable[str],
    user_id: int,
    report: ErasureReport,
    *,
    where_column: str = "user_id",
    where_value: Optional[int] = None,
) -> None:
    """Overwrite every PII text column on ``table_name`` for rows
    matching ``where_column = :uid``.

    By default uses ``WHERE user_id = :uid``. Pass a different
    ``where_column`` (e.g. ``"scheduled_by"``) for tables whose FK
    to users has a non-standard name.

    Does NOT commit — the caller (``request_erasure``) manages the
    transaction boundary so the entire erasure is atomic.
    """
    if not text_columns:
        return
    try:
        uid = where_value if where_value is not None else user_id
        any_updated = False
        for col in text_columns:
            stmt = text(
                f"UPDATE {table_name} SET {col} = :placeholder "
                f"WHERE {where_column} = :uid"
            )
            result = db.execute(
                stmt,
                {"placeholder": ERASED_PLACEHOLDER, "uid": uid},
            )
            if result.rowcount:
                report.rows_anonymised += result.rowcount
                any_updated = True
        if any_updated:
            report.tables_touched.append(table_name)
    except Exception as e:  # noqa: BLE001
        logger.error(
            f"[ERASURE] Failed to scrub {table_name} for "
            f"{where_column}={where_value or user_id}: {e}"
        )
        raise


def _scrub_table_by_email(
    db: Session,
    table_name: str,
    text_columns: Iterable[str],
    email: str,
    report: ErasureReport,
    *,
    email_column: str = "email",
) -> None:
    """Overwrite PII columns on rows keyed by email (no user_id FK).

    Does NOT commit — the caller manages the transaction boundary.
    """
    if not text_columns or not email:
        return
    try:
        any_updated = False
        for col in text_columns:
            stmt = text(
                f"UPDATE {table_name} SET {col} = :placeholder "
                f"WHERE {email_column} = :email"
            )
            result = db.execute(
                stmt,
                {"placeholder": ERASED_PLACEHOLDER, "email": email},
            )
            if result.rowcount:
                report.rows_anonymised += result.rowcount
                any_updated = True
        if any_updated:
            report.tables_touched.append(table_name)
    except Exception as e:  # noqa: BLE001
        logger.error(f"[ERASURE] Failed to scrub {table_name} by email {email}: {e}")
        raise


def _scrub_table_by_application_ids(
    db: Session,
    table_name: str,
    text_columns: Iterable[str],
    application_ids: List[int],
    report: ErasureReport,
    *,
    fk_column: str = "application_id",
) -> None:
    """Overwrite PII columns on rows keyed by application_id
    (no direct user_id FK).  Silently skipped when app_ids is empty.

    Does NOT commit — the caller manages the transaction boundary.
    """
    if not text_columns or not application_ids:
        return
    try:
        ids_str = ",".join(str(aid) for aid in application_ids)
        any_updated = False
        for col in text_columns:
            stmt = text(
                f"UPDATE {table_name} SET {col} = :placeholder "
                f"WHERE {fk_column} IN ({ids_str})"
            )
            result = db.execute(
                stmt,
                {"placeholder": ERASED_PLACEHOLDER},
            )
            if result.rowcount:
                report.rows_anonymised += result.rowcount
                any_updated = True
        if any_updated:
            report.tables_touched.append(table_name)
    except Exception as e:  # noqa: BLE001
        logger.error(f"[ERASURE] Failed to scrub {table_name} by application_ids: {e}")
        raise


# ── Registry: tables with PII, grouped by lookup strategy ──

# 1. Tables with a direct ``user_id`` foreign key.
_PII_TABLES_USER_ID: List[tuple] = [
    ("applications", ["full_name", "email", "phone", "notes"]),
    ("interview_turns", ["question", "answer", "feedback", "reasoning"]),
    ("comments", ["content", "mentions"]),
    ("candidate_interactions", ["subject", "content"]),
    (
        "career_roadmaps",
        ["target_role", "current_skills", "roadmap_json", "progress_json"],
    ),
    ("consent_logs", ["ip_address", "user_agent"]),
    ("support_tickets", ["subject", "description", "admin_response"]),
    ("tagged_notes", ["content", "tags"]),
    ("student_notes", ["content"]),
    ("undo_actions", ["previous_state_json", "new_state_json"]),
    ("quiz_results", ["answers"]),
    ("qualifications", ["title", "filename", "file_url"]),
    ("email_verifications", ["token", "code"]),
    ("password_resets", ["token", "ip_address"]),
    (
        "company_verifications",
        [
            "company_name",
            "matricule_fiscale",
            "registre_commerce_id",
            "address",
            "document_url",
            "admin_notes",
        ],
    ),
    ("transactions", ["description", "proof_url"]),
    ("notifications", ["title", "message", "payload_json"]),
]

# 2. Tables with a non-standard FK column name (e.g. ``scheduled_by``)
#    that still points to ``users.id``.
_PII_TABLES_NONSTANDARD_FK: List[tuple] = [
    # "interviews" uses scheduled_by, not user_id
    (
        "interviews",
        ["meeting_link", "location", "agenda", "internal_notes"],
        "scheduled_by",
    ),
    # "interview_feedback" uses interviewer_id, not user_id
    (
        "interview_feedback",
        ["strengths", "concerns", "additional_notes"],
        "interviewer_id",
    ),
]

# 3. Tables with no ``user_id`` FK — matched by email address.
_PII_TABLES_BY_EMAIL: List[tuple] = [
    ("login_attempts", ["email", "ip_address"]),
    ("chatbot_leads", ["name", "email", "phone", "skills", "message_history"]),
]

# 4. Tables keyed by ``application_id`` that must be reached through
#    ``applications`` → ``user_id`` join.  The column list is per
#    table.
_PII_APPLICATION_COLUMNS: dict = {
    "cv_documents": [
        "cv_text",
        "cv_file_path",
        "cv_text_anonymized",
        "extracted_skills",
        "cv_embedding",
        "analysis_json",
        "cv_review_json",
        "roadmap_json",
    ],
    "evaluation_sessions": [
        "interview_log",
        "interview_questions",
        "generated_questions",
        "proctoring_violations",
        "video_file_path",
        "video_transcript",
        "video_analysis_json",
        "calibration_json",
        "calibration_verified_skills",
    ],
    "evaluation_results": [
        "score_breakdown",
    ],
    "eeo_consent": [
        "gender",
        "race_ethnicity",
        "veteran_status",
        "disability_status",
        "age_group",
    ],
}


# Tables in _PII_APPLICATION_COLUMNS whose FK column is not ``application_id``.
_PII_APPLICATION_FK_OVERRIDES: dict = {
    "evaluation_results": "evaluation_session_id",
}


def _collect_application_ids(db: Session, user_id: int) -> List[int]:
    """Return all ``application.id`` values belonging to this user."""
    rows = db.query(Application.id).filter(Application.user_id == user_id).all()
    return [r[0] for r in rows]


def _scrub_sourced_candidates(
    db: Session,
    email: str,
    report: ErasureReport,
) -> None:
    """Sourced candidates store recruiter_id, not user_id, but may
    have a matching email.  Scrub any rows whose email matches.
    """
    if not email:
        return
    cols = [
        "name",
        "email",
        "headline",
        "location",
        "profile_url",
        "avatar_url",
        "skills",
        "bio",
    ]
    _scrub_table_by_email(
        db,
        "sourced_candidates",
        cols,
        email,
        report,
        email_column="email",
    )


# ── Verification (post-erasure spot check) ──

_VERIFICATION_TABLES: List[dict] = [
    {
        "table": "cv_documents",
        "columns": ["cv_text"],
        "where_column": "application_id",
        "depends_on": "application_id",
    },
    {
        "table": "interview_turns",
        "columns": ["answer"],
        "where_column": "user_id",
        "depends_on": "user_id",
    },
    {
        "table": "evaluation_sessions",
        "columns": ["interview_log"],
        "where_column": "application_id",
        "depends_on": "application_id",
    },
    {
        "table": "notifications",
        "columns": ["message"],
        "where_column": "user_id",
        "depends_on": "user_id",
    },
    {
        "table": "applications",
        "columns": ["email"],
        "where_column": "user_id",
        "depends_on": "user_id",
    },
]


def _verify_erasure(
    db: Session,
    user_id: int,
    application_ids: List[int],
    user_email: str,
) -> List[str]:
    """Post-commit spot-check that the 5 highest-risk tables
    actually have no remaining PII.

    Returns a list of warning messages (empty = all clear).
    Logs each warning.  Does not raise — verification is advisory.
    """
    warnings: List[str] = []
    for spec in _VERIFICATION_TABLES:
        if spec["depends_on"] == "application_id":
            if not application_ids:
                continue
            where_val_str = ",".join(str(aid) for aid in application_ids)
            where_clause = f"{spec['where_column']} IN ({where_val_str})"
        else:
            where_clause = f"{spec['where_column']} = {user_id}"

        for col in spec["columns"]:
            try:
                row = db.execute(
                    text(
                        f"SELECT COUNT(*) FROM {spec['table']} "
                        f"WHERE {where_clause} "
                        f"AND ({col} IS NOT NULL AND {col} != :placeholder)"
                    ),
                    {"placeholder": ERASED_PLACEHOLDER},
                ).scalar()
                if row and row > 0:
                    msg = (
                        f"[ERASURE-VERIFY] {spec['table']}.{col}: "
                        f"{row} row(s) still contain PII for user {user_id}"
                    )
                    warnings.append(msg)
                    logger.warning(msg)
            except Exception as e:  # noqa: BLE001
                msg = f"[ERASURE-VERIFY] Could not check {spec['table']}.{col}: {e}"
                warnings.append(msg)
                logger.warning(msg)
    return warnings


def request_erasure(
    db: Session,
    *,
    user_id: int,
    requester_id: int,
    requester_role: str,
    reason: Optional[str] = None,
    hard_delete: bool = False,
) -> ErasureReport:
    """Process a GDPR Article 17 erasure request.

    If ``hard_delete`` is True, the User row is deleted (use with
    caution — this removes the audit-log foreign key). Default
    is soft-delete + scrub PII columns so the row remains for
    financial / legal retention requirements.

    Transaction semantics:

        1. Audit log is committed IMMEDIATELY (``_log_request``)
           so the erasure attempt is always recorded.
        2. All scrubs (26 tables + User row) are batched into a
           **single** transaction.  If any scrub fails, the
           entire batch is rolled back — no partial erasure.
        3. After commit, a verification SELECT runs (advisory —
           does not rollback on failure).
    """
    report = ErasureReport(
        user_id=user_id,
        requested_at=datetime.now(UTC),
        completed_at=None,
        rows_erased=0,
        rows_anonymised=0,
        tables_touched=[],
    )

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        report.error = "user not found"
        return report

    # Capture the user's email before we scrub the User row.
    user_email = user.email or ""

    # Log the request BEFORE we touch data, so the audit trail
    # survives even if the scrub raises.
    _log_request(db, user_id, requester_id, requester_role, reason)

    try:
        # 1. Scrub tables with direct user_id FK.
        for table, cols in _PII_TABLES_USER_ID:
            _scrub_table(db, table, cols, user_id, report)

        # 2. Scrub tables with non-standard FK column names.
        for table, cols, fk_col in _PII_TABLES_NONSTANDARD_FK:
            _scrub_table(db, table, cols, user_id, report, where_column=fk_col)

        # 3. Scrub tables that can only be reached by email.
        if user_email:
            for table, cols in _PII_TABLES_BY_EMAIL:
                _scrub_table_by_email(db, table, cols, user_email, report)
            _scrub_sourced_candidates(db, user_email, report)

        # 4. Scrub tables keyed by application_id (indirect).
        app_ids = _collect_application_ids(db, user_id)
        # Pre-resolve evaluation_session_ids for tables that use them as FK.
        eval_session_ids: List[int] = []
        if app_ids:
            ids_str = ",".join(str(aid) for aid in app_ids)
            rows = db.execute(
                text(
                    f"SELECT id FROM evaluation_sessions "
                    f"WHERE application_id IN ({ids_str})"
                )
            ).fetchall()
            eval_session_ids = [r[0] for r in rows]
        for table_name, cols in _PII_APPLICATION_COLUMNS.items():
            fk_col = _PII_APPLICATION_FK_OVERRIDES.get(table_name, "application_id")
            ids = eval_session_ids if fk_col == "evaluation_session_id" else app_ids
            _scrub_table_by_application_ids(
                db,
                table_name,
                cols,
                ids,
                report,
                fk_column=fk_col,
            )

        # 5. Anonymise the User row itself (auth-level fields only).
        user.email = f"erased+{user_id}@candway.invalid"
        user.hashed_password = None
        user.temp_password = None
        if hasattr(user, "deleted_at"):
            user.deleted_at = datetime.now(UTC)

        # PII erasure on role-specific profile (SSOT for all profile fields)
        profile = user.candidate_profile or user.recruiter_profile
        if profile:
            profile.email = f"erased+{user_id}@candway.invalid"
            profile.name = ERASED_PLACEHOLDER
            for pii_field in (
                "headline",
                "bio",
                "phone",
                "location",
                "avatar_url",
                "linkedin_url",
                "github_url",
                "portfolio_url",
                "availability",
                "work_preference",
                "salary_expectation_min",
                "salary_expectation_max",
            ):
                if hasattr(profile, pii_field):
                    setattr(profile, pii_field, None)

        # 6. Hard delete if requested (admin override).
        if hard_delete and requester_role == "admin":
            db.delete(user)
            report.rows_erased += 1

        # ── Single atomic commit for ALL scrubs ──
        db.commit()
        report.completed_at = datetime.now(UTC)

        # Verification (advisory — does not rollback).
        report.verification_warnings = _verify_erasure(
            db,
            user_id,
            app_ids,
            user_email,
        )

    except Exception as e:  # noqa: BLE001
        db.rollback()
        report.error = str(e)
        logger.error(f"[ERASURE] Failed for user {user_id}: {e}")

    return report
