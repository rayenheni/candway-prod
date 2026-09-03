"""
backfill_user_to_profiles.py — Populate Profile tables from User columns.

For each User with a role that has a corresponding profile table, creates
a profile row if one doesn't exist, copying all deprecated User columns
into the profile.

Target tables:
  - Users with role='candidate'  → candidate_profiles
  - Users with role='recruiter'  → recruiter_profiles
  - Users with role='admin'      → admin_profiles (+ recruiter_profiles)

Usage:
    python -m alembic upgrade m28          # add location column to candidate_profiles
    python -m backend.scripts.backfill_user_to_profiles  # populate profiles

Safety:
    - Single transaction — rolls back on error.
    - Idempotent — skips users that already have a profile.
    - Never deletes User data.
"""

import sys

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.database import SessionLocal
from backend.logger import logger

# Mapping of User columns to CandidateProfile columns
CANDIDATE_FIELDS = [
    "name",
    "phone",
    "email",
    "headline",
    "bio",
    "location",
    "skills",
    "languages",
    "availability",
    "work_preference",
    "salary_expectation_min",
    "salary_expectation_max",
    "linkedin_url",
    "github_url",
    "portfolio_url",
    "avatar_url",
    "profile_views",
    "profile_views_growth",
    "candidate_cv_uploads_this_month",
    "candidate_ai_analyses_this_month",
    "candidate_pdf_downloads_this_month",
    "candidate_usage_reset_date",
]

# Mapping of User columns to RecruiterProfile columns
RECRUITER_FIELDS = [
    "name",
    "phone",
    "email",
    "company_name",
    "company_description",
    "company_logo_url",
    "smtp_host",
    "smtp_port",
    "smtp_user",
    "smtp_password",
    "usage_jobs",
    "usage_cvs",
    "usage_ai_interviews",
    "usage_reset_date",
]

# Mapping of User columns to AdminProfile columns
ADMIN_FIELDS = [
    "is_super_admin",
]


def _build_insert(table: str, user_id: int, field_map: list, user_row: dict) -> tuple:
    """Build column names, placeholders, and values for an INSERT."""
    cols = ["user_id"]
    placeholders = [":user_id"]
    values = {"user_id": user_id}
    for col in field_map:
        if col in user_row and user_row[col] is not None:
            cols.append(col)
            placeholders.append(f":{col}")
            values[col] = user_row[col]
    col_list = ", ".join(cols)
    ph_list = ", ".join(placeholders)
    sql = f"INSERT IGNORE INTO {table} ({col_list}) VALUES ({ph_list})"
    return sql, values


def backfill_profiles(db: Session) -> dict:
    """Populate profile tables from User deprecated columns.

    Returns dict with counts of profiles created per role.
    """
    counts = {"candidate": 0, "recruiter": 0, "admin": 0}

    # Fetch all non-deleted users
    rows = db.execute(
        text(
            "SELECT id, role, "
            + ", ".join(
                f"`{f}`"
                for f in set(
                    CANDIDATE_FIELDS + RECRUITER_FIELDS + ADMIN_FIELDS + ["email"]
                )
            )
            + " FROM users WHERE deleted_at IS NULL"
        )
    ).fetchall()

    if not rows:
        logger.info("No active users found — nothing to backfill")
        return counts

    col_names = ["id", "role"] + [
        f for f in set(CANDIDATE_FIELDS + RECRUITER_FIELDS + ADMIN_FIELDS + ["email"])
    ]

    for row in rows:
        user = dict(zip(col_names, row))
        uid = user["id"]
        role = user["role"]

        if role == "candidate":
            # Check if profile exists
            existing = db.execute(
                text("SELECT id FROM candidate_profiles WHERE user_id = :uid"),
                {"uid": uid},
            ).fetchone()
            if not existing:
                sql, vals = _build_insert(
                    "candidate_profiles", uid, CANDIDATE_FIELDS, user
                )
                db.execute(text(sql), vals)
                counts["candidate"] += 1

        elif role == "recruiter":
            existing = db.execute(
                text("SELECT id FROM recruiter_profiles WHERE user_id = :uid"),
                {"uid": uid},
            ).fetchone()
            if not existing:
                sql, vals = _build_insert(
                    "recruiter_profiles", uid, RECRUITER_FIELDS, user
                )
                db.execute(text(sql), vals)
                counts["recruiter"] += 1

        elif role == "admin":
            # Admin gets both admin_profile and recruiter_profile
            existing_admin = db.execute(
                text("SELECT id FROM admin_profiles WHERE user_id = :uid"),
                {"uid": uid},
            ).fetchone()
            if not existing_admin:
                sql, vals = _build_insert("admin_profiles", uid, ADMIN_FIELDS, user)
                db.execute(text(sql), vals)
                counts["admin"] += 1

            existing_recruiter = db.execute(
                text("SELECT id FROM recruiter_profiles WHERE user_id = :uid"),
                {"uid": uid},
            ).fetchone()
            if not existing_recruiter:
                sql, vals = _build_insert(
                    "recruiter_profiles", uid, RECRUITER_FIELDS, user
                )
                db.execute(text(sql), vals)
                counts["recruiter"] += 1

    return counts


def main():
    db = SessionLocal()
    try:
        counts = backfill_profiles(db)
        db.commit()
        parts = [f"{k}={v}" for k, v in counts.items() if v > 0]
        logger.info(
            "Backfill complete — created: %s",
            ", ".join(parts) if parts else "0 profiles (all up-to-date)",
        )
    except Exception:
        db.rollback()
        logger.exception("Backfill failed — rolling back")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
