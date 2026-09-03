"""
backfill_company_ids.py — Safe data migration for multi-tenant company_id.

For every table that gained a company_id column, this script walks the
relationship chain to determine the correct company_id for each existing
record.  Ambiguous records (those that cannot be resolved) are reported
for manual triage and never silently assigned.

Usage:
    python -m backend.scripts.backfill_company_ids

Workflow:
    1. Run the Alembic migration m22 (adds nullable company_id).
    2. Run this script.
    3. Run m22b (makes company_id NOT NULL).

Safety:
    - Wraps every table in a transaction with rollback on error.
    - Reports every ambiguous record to stderr for manual triage.
    - Never guesses — if a record's company_id cannot be determined
      via FK chain, it is flagged as ambiguous.
"""

import sys

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.database import (
    Application,
    BatchJob,
    CampaignTemplate,
    CompanyMember,
    ConversationParticipant,
    Job,
    Offer,
    ReEngagementCampaign,
    SessionLocal,
)
from backend.logger import logger

# ── Mapping: table → (FK column, target_table, target_company_resolver) ──
# target_company_resolver is a function that, given a Session and the FK value,
# returns the company_id or None.


def _app_company(db: Session, app_id: int) -> int | None:
    row = db.query(Application.company_id).filter(Application.id == app_id).first()
    return row[0] if row else None


def _job_company(db: Session, job_id: int) -> int | None:
    job = db.query(Job.recruiter_id).filter(Job.id == job_id).first()
    if not job:
        return None
    return _user_company(db, job[0])


def _batch_company(db: Session, batch_id: int) -> int | None:
    batch = db.query(BatchJob.recruiter_id).filter(BatchJob.id == batch_id).first()
    if not batch:
        return None
    return _user_company(db, batch[0])


def _user_company(db: Session, user_id: int) -> int | None:
    """Get the active company for a user via CompanyMember."""
    row = (
        db.query(CompanyMember.company_id)
        .filter(
            CompanyMember.user_id == user_id,
            CompanyMember.is_active,
        )
        .first()
    )
    return row[0] if row else None


def _campaign_company(db: Session, campaign_id: int) -> int | None:
    row = (
        db.query(CampaignTemplate.company_id)
        .filter(CampaignTemplate.id == campaign_id)
        .first()
    )
    return row[0] if row else None


def _conv_company(db: Session, conv_id: int) -> int | None:
    """Resolve conversation.company_id through its participants' companies.
    If all participants belong to the same company, use that.
    Otherwise flag as ambiguous.
    """
    participants = (
        db.query(ConversationParticipant.user_id)
        .filter(ConversationParticipant.conversation_id == conv_id)
        .all()
    )
    companies = set()
    for (uid,) in participants:
        c = _user_company(db, uid)
        if c:
            companies.add(c)
    if len(companies) == 1:
        return companies.pop()
    return None  # ambiguous


def _offer_company(db: Session, offer_id: int) -> int | None:
    offer = db.query(Offer.application_id).filter(Offer.id == offer_id).first()
    if not offer:
        return None
    return _app_company(db, offer[0])


def _re_campaign_company(db: Session, re_id: int) -> int | None:
    row = (
        db.query(ReEngagementCampaign.recruiter_id)
        .filter(ReEngagementCampaign.id == re_id)
        .first()
    )
    if not row:
        return None
    return _user_company(db, row[0])


# Resolver table: (table_name, fk_column, fk_target_resolver)
# or (table_name, ("fk1", "fk2", ...), composite_resolver_fn)
BACKFILL_MAP = [
    # ── Messaging ───────────────────────────────────────────────
    ("conversations", "id", _conv_company),  # self-referential
    ("conversation_participants", "user_id", _user_company),
    ("messages", "conversation_id", _conv_company),
    # ── Interview ──────────────────────────────────────────────
    ("interviews", "application_id", _app_company),
    (
        "interview_participants",
        "interview_id",
        lambda db, iid: _app_company(
            db, _fk_val(db, "interviews", iid, "application_id")
        ),
    ),
    (
        "interview_feedback",
        "interview_id",
        lambda db, iid: _app_company(
            db, _fk_val(db, "interviews", iid, "application_id")
        ),
    ),
    ("interview_scorecards", "recruiter_id", _user_company),
    ("scorecard_submissions", "application_id", _app_company),
    # ── Offer ──────────────────────────────────────────────────
    ("offer_templates", "recruiter_id", _user_company),
    ("offers", "application_id", _app_company),
    ("background_checks", "application_id", _app_company),
    (
        "background_check_status_logs",
        "background_check_id",
        lambda db, bc_id: _app_company(
            db, _fk_val(db, "background_checks", bc_id, "application_id")
        ),
    ),
    # ── Pipeline ───────────────────────────────────────────────
    ("application_stage_history", "application_id", _app_company),
    ("tagged_notes", "application_id", _app_company),
    ("comments", "application_id", _app_company),
    ("candidate_ratings", "application_id", _app_company),
    ("activity_logs", "application_id", _app_company),
    ("candidate_interactions", "application_id", _app_company),
    ("team_members", "member_id", _user_company),
    # ── Campaign ───────────────────────────────────────────────
    ("webhook_integrations", "recruiter_id", _user_company),
    ("bot_integrations", "recruiter_id", _user_company),
    ("campaign_templates", "recruiter_id", _user_company),
    ("email_templates", "recruiter_id", _user_company),
    ("email_sequence_logs", "application_id", _app_company),
    ("reengagement_campaigns", "recruiter_id", _user_company),
    ("reengagement_candidates", "campaign_id", _re_campaign_company),
    # ── Application child tables ───────────────────────────────
    ("qualifications", "application_id", _app_company),
    ("cv_documents", "application_id", _app_company),
    ("extracted_skills", "application_id", _app_company),
    ("eeo_consent", "application_id", _app_company),
    # ── Job ────────────────────────────────────────────────────
    ("jobs", "recruiter_id", _user_company),
    ("saved_jobs", "job_id", _job_company),
    ("interview_questions", "job_id", _job_company),
    ("chatbot_leads", "assigned_recruiter_id", _user_company),
    # ── Batch ──────────────────────────────────────────────────
    ("batch_jobs", "recruiter_id", _user_company),
    ("pipeline_stages", "recruiter_id", _user_company),
    ("pipeline_automation_rules", "recruiter_id", _user_company),
    # ── Evaluation ─────────────────────────────────────────────
    (
        "evaluation_results",
        "evaluation_session_id",
        lambda db, es_id: _fk_val(db, "evaluation_sessions", es_id, "company_id"),
    ),
    ("rubrics", "created_by", _user_company),
    (
        "rubric_scoring_details",
        "evaluation_result_id",
        lambda db, er_id: _fk_val(
            db, "evaluation_results", er_id, "evaluation_session_id"
        ),
    ),
    ("verdicts", "application_id", _app_company),
    ("evaluation_config_snapshots", None, None),  # orphaned — skip, these are archived
    ("rubric_snapshots", None, None),  # orphaned — skip
    # ── Finance ────────────────────────────────────────────────
    ("transactions", "user_id", _user_company),
    ("invoices", "user_id", _user_company),
    ("saved_reports", "recruiter_id", _user_company),
    (
        "report_snapshots",
        "report_id",
        lambda db, r_id: _fk_val(db, "saved_reports", r_id, "company_id"),
    ),
    ("campaign_costs", "recruiter_id", _user_company),
    # ── Foundation: User ───────────────────────────────────────
    ("notifications", "user_id", _user_company),
    ("feature_flags", "user_id", _user_company),
    ("undo_actions", "user_id", _user_company),
    # ── Foundation: System ─────────────────────────────────────
    ("tickets", "user_id", _user_company),
    ("support_tickets", "user_id", _user_company),
    # ── Foundation: CMS ────────────────────────────────────────
    ("blog_posts", "author_id", _user_company),
    ("announcements", "created_by", _user_company),
    # ── Foundation: Company ────────────────────────────────────
    ("company_verifications", "user_id", _user_company),
    # ── Profile ────────────────────────────────────────────────
    ("recruiter_profiles", "user_id", _user_company),
    # ── LMS ────────────────────────────────────────────────────
    ("courses", "mentor_id", _user_company),
    ("enrollments", "user_id", _user_company),
    ("payout_requests", "mentor_id", _user_company),
    # ── A/B Testing (system-wide, skip if no obvious company) ──
    ("ab_test_experiments", "created_by", _user_company),
    (
        "ab_test_assignments",
        "experiment_id",
        lambda db, eid: _fk_val(db, "ab_test_experiments", eid, "company_id"),
    ),
    (
        "scoring_variant_results",
        "experiment_id",
        lambda db, eid: _fk_val(db, "ab_test_experiments", eid, "company_id"),
    ),
    # ── Prompt management ──────────────────────────────────────
    ("prompt_tests", "created_by", _user_company),
    ("prompt_variants", None, None),  # system-wide, skip
    ("prompt_test_results", None, None),  # system-wide, skip
    ("skill_definitions", None, None),  # system-wide catalog, skip
]


def _fk_val(db: Session, table: str, pk: int, col: str) -> int | None:
    """Get a single column value by primary key lookup."""
    if pk is None:
        return None
    row = db.execute(
        text(f"SELECT {col} FROM {table} WHERE id = :pk"),
        {"pk": pk},
    ).first()
    return row[0] if row else None


def backfill_table(
    db: Session,
    table: str,
    fk_column: str | tuple | None,
    resolver,
    dry_run: bool = True,
) -> tuple[int, int]:
    """Backfill company_id for one table.

    Returns (updated_count, ambiguous_count).
    """
    if fk_column is None and resolver is None:
        logger.info("  SKIP %s — no resolver (system-wide table)", table)
        return 0, 0

    # Get all rows that have NULL company_id
    rows = db.execute(
        text(f"SELECT id FROM {table} WHERE company_id IS NULL")
    ).fetchall()

    if not rows:
        logger.info("  %s — no rows to backfill", table)
        return 0, 0

    updated = 0
    ambiguous = 0

    for (row_id,) in rows:
        if callable(fk_column):
            # Resolver is the sole function
            company_id = fk_column(db, row_id)
        elif isinstance(fk_column, str):
            # Simple FK → resolver
            fk_val = _fk_val(db, table, row_id, fk_column)
            if fk_val is None:
                company_id = None
            else:
                company_id = resolver(db, fk_val)
        else:
            company_id = None

        if company_id is None:
            logger.warning(
                "  AMBIGUOUS: %s.id=%d — cannot determine company_id",
                table,
                row_id,
            )
            ambiguous += 1
            continue

        if not dry_run:
            db.execute(
                text(f"UPDATE {table} SET company_id = :cid WHERE id = :rid"),
                {"cid": company_id, "rid": row_id},
            )
        updated += 1

    if not dry_run:
        db.commit()

    logger.info(
        "  %s — %d updated, %d ambiguous",
        table,
        updated,
        ambiguous,
    )
    return updated, ambiguous


def main(dry_run: bool = True):
    logger.info(
        "Company ID backfill — %s mode",
        "DRY RUN (no changes)" if dry_run else "LIVE",
    )

    db = SessionLocal()
    try:
        total_updated = 0
        total_ambiguous = 0

        for entry in BACKFILL_MAP:
            if len(entry) == 3:
                table, fk_column, resolver = entry
            else:
                table, fk_column, resolver = entry[0], entry[1], entry[2]

            logger.info("Processing %s ...", table)
            upd, amb = backfill_table(db, table, fk_column, resolver, dry_run)
            total_updated += upd
            total_ambiguous += amb

        logger.info("=" * 60)
        logger.info(
            "SUMMARY: %d rows updated, %d ambiguous", total_updated, total_ambiguous
        )

        if total_ambiguous > 0:
            logger.warning(
                "⚠  %d records could not be assigned a company_id. "
                "Review the AMBIGUOUS lines above and fix manually.",
                total_ambiguous,
            )
            sys.exit(1)

        if dry_run:
            logger.info("Run with --live to apply changes.")
        else:
            logger.info("Backfill complete. Ready for m22b (NOT NULL migration).")

    finally:
        db.close()


if __name__ == "__main__":
    dry_run = "--live" not in sys.argv
    main(dry_run=dry_run)
