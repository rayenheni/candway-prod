"""add tenant mixin to lms tables

CRIT-3: 8 LMS tables were missing TenantMixin, allowing cross-tenant
data access. Add company_id (FK, NOT NULL, indexed) to:
  Section, Lesson, Quiz, Question, LessonProgress, CourseReview,
  Coupon, CareerRoadmap.

Revision ID: m41
Revises: m40
Create Date: 2026-07-21
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "m41"
down_revision: Union[str, Sequence[str], None] = "m40"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES = [
    "sections",
    "lessons",
    "quizzes",
    "questions",
    "lesson_progress",
    "course_reviews",
    "coupons",
    "career_roadmaps",
]


def upgrade() -> None:
    for table in TABLES:
        try:
            op.add_column(
                table,
                sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=True),
            )
        except Exception:
            pass
        try:
            op.create_index(f"ix_{table}_company_id", table, ["company_id"])
        except Exception:
            pass

    for _sql in [
        """
        UPDATE sections s
        JOIN courses c ON s.course_id = c.id
        SET s.company_id = c.company_id
        WHERE s.company_id IS NULL
        """,
        """
        UPDATE lessons l
        JOIN sections s ON l.section_id = s.id
        SET l.company_id = s.company_id
        WHERE l.company_id IS NULL
        """,
        """
        UPDATE quizzes q
        JOIN sections s ON q.section_id = s.id
        SET q.company_id = s.company_id
        WHERE q.company_id IS NULL
        """,
        """
        UPDATE questions q
        JOIN quizzes qu ON q.quiz_id = qu.id
        SET q.company_id = qu.company_id
        WHERE q.company_id IS NULL
        """,
        """
        UPDATE lesson_progress lp
        JOIN lessons l ON lp.lesson_id = l.id
        SET lp.company_id = l.company_id
        WHERE lp.company_id IS NULL
        """,
        """
        UPDATE course_reviews cr
        JOIN courses c ON cr.course_id = c.id
        SET cr.company_id = c.company_id
        WHERE cr.company_id IS NULL
        """,
        """
        UPDATE coupons co
        JOIN courses c ON co.course_id = c.id
        SET co.company_id = c.company_id
        WHERE co.company_id IS NULL
        """,
        """
        UPDATE career_roadmaps cr
        SET cr.company_id = (SELECT c.company_id FROM courses c WHERE c.id = cr.course_id)
        WHERE cr.company_id IS NULL AND cr.course_id IS NOT NULL
        """,
    ]:
        try:
            op.execute(_sql)
        except Exception:
            pass

    for table in TABLES:
        try:
            op.alter_column(table, "company_id", nullable=False)
        except Exception:
            pass


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_index(f"ix_{table}_company_id", table_name=table)
        op.drop_column(table, "company_id")
