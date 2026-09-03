"""Phase 2 — Interview Session Ownership: EvaluationSession is single source of truth

Makes EvaluationSession the single source of truth for interview execution
state by backfilling any Application without an EvaluationSession.

Application interview columns are marked deprecated (not dropped) — a
future migration will drop them.

Migration ID: m14_phase2_interview_session_ownership
Revises: m13_phase1_entity_ownership
"""
import json
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "m14_phase2_interview_session_ownership"
down_revision: Union[str, None] = "m13_phase1_entity_ownership"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

app_cols = sa.table(
    "applications",
    sa.column("id", sa.Integer),
    sa.column("company_id", sa.Integer),
    sa.column("interview_state", sa.String),
    sa.column("interview_progress", sa.Integer),
    sa.column("interview_time_left", sa.Integer),
    sa.column("interview_last_saved", sa.DateTime),
    sa.column("interview_turn_seq", sa.Integer),
    sa.column("interview_reset_count", sa.Integer),
    sa.column("interview_last_reset_at", sa.DateTime),
    sa.column("calibration_json", sa.Text),
)

es_cols = sa.table(
    "evaluation_sessions",
    sa.column("application_id", sa.Integer),
    sa.column("company_id", sa.Integer),
    sa.column("status", sa.String),
    sa.column("interview_state", sa.String),
    sa.column("interview_progress", sa.Integer),
    sa.column("interview_time_left", sa.Integer),
    sa.column("interview_last_saved", sa.DateTime),
    sa.column("interview_log", sa.JSON),
    sa.column("interview_questions", sa.JSON),
    sa.column("interview_turn_seq", sa.Integer),
    sa.column("interview_reset_count", sa.Integer),
    sa.column("interview_last_reset_at", sa.DateTime),
    sa.column("video_file_path", sa.String),
    sa.column("calibration_json", sa.Text),
)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    app_existing_cols = {c["name"] for c in inspector.get_columns("applications")}
    if "interview_time_left" not in app_existing_cols or "interview_state" not in app_existing_cols:
        print("[m14] Skipped backfill: interview columns already dropped from applications table.")
        return

    status_map = {
        "not_started": "created",
        "in_progress": "in_progress",
        "completed": "completed",
        "expired": "completed",
        "flagged": "flagged",
        "paused": "paused",
    }

    rows = bind.execute(
        sa.select(
            app_cols.c.id,
            app_cols.c.company_id,
            app_cols.c.interview_state,
            app_cols.c.interview_progress,
            app_cols.c.interview_time_left,
            app_cols.c.interview_last_saved,
            app_cols.c.interview_turn_seq,
            app_cols.c.interview_reset_count,
            app_cols.c.interview_last_reset_at,
            app_cols.c.calibration_json,
        )
        .where(
            ~sa.exists(
                sa.select(es_cols.c.application_id).where(
                    es_cols.c.application_id == app_cols.c.id
                )
            )
        )
        .where(app_cols.c.interview_state.isnot(None))
    ).fetchall()

    count = 0
    for row in rows:
        interview_state_val = row.interview_state
        if not interview_state_val or interview_state_val == "not_started":
            continue

        interview_log_val = None
        interview_questions_val = None
        video_file_path_val = None

        calibration_json_val = None
        try:
            raw = row.calibration_json
            if raw and isinstance(raw, str) and raw not in ("{}", "null"):
                calibration_json_val = json.loads(raw) if raw.startswith(("{", "[")) else raw
        except Exception:
            pass

        bind.execute(
            es_cols.insert().values(
                application_id=row.id,
                company_id=row.company_id,
                status=status_map.get(interview_state_val, "created"),
                interview_state=interview_state_val,
                interview_progress=row.interview_progress or 0,
                interview_time_left=row.interview_time_left or 1800,
                interview_last_saved=row.interview_last_saved,
                interview_log=interview_log_val or [],
                interview_questions=interview_questions_val or [],
                interview_turn_seq=row.interview_turn_seq or 0,
                interview_reset_count=row.interview_reset_count or 0,
                interview_last_reset_at=row.interview_last_reset_at,
                video_file_path=video_file_path_val,
                calibration_json=calibration_json_val,
            )
        )
        count += 1

    print(f"[m14] Backfilled {count} EvaluationSession rows from Application interview data")


def downgrade() -> None:
    pass
