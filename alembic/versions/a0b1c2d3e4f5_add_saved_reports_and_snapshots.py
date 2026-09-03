"""Add saved_reports and report_snapshots tables

Revision ID: a0b1c2d3e4f5
Revises: f4a5b6c7d8e9
Create Date: 2026-06-06 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a0b1c2d3e4f5'
down_revision: Union[str, Sequence[str], None] = '7f6a7b8c9d0e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('saved_reports',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('recruiter_id', sa.Integer(), nullable=True),
        sa.Column('name', sa.String(length=255), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('config', sa.Text(), nullable=True),
        sa.Column('is_scheduled', sa.Boolean(), nullable=True, default=False),
        sa.Column('schedule_frequency', sa.String(length=50), nullable=True),
        sa.Column('schedule_recipients', sa.Text(), nullable=True),
        sa.Column('last_generated_at', sa.DateTime(), nullable=True),
        sa.Column('next_scheduled_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['recruiter_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_saved_reports_id'), 'saved_reports', ['id'], unique=False)
    op.create_index(op.f('ix_saved_reports_recruiter_id'), 'saved_reports', ['recruiter_id'], unique=False)

    op.create_table('report_snapshots',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('report_id', sa.Integer(), nullable=True),
        sa.Column('report_data', sa.Text(), nullable=True),
        sa.Column('generated_at', sa.DateTime(), nullable=True),
        sa.Column('file_path', sa.String(length=500), nullable=True),
        sa.ForeignKeyConstraint(['report_id'], ['saved_reports.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_report_snapshots_id'), 'report_snapshots', ['id'], unique=False)
    op.create_index(op.f('ix_report_snapshots_report_id'), 'report_snapshots', ['report_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_report_snapshots_report_id'), table_name='report_snapshots')
    op.drop_index(op.f('ix_report_snapshots_id'), table_name='report_snapshots')
    op.drop_table('report_snapshots')
    op.drop_index(op.f('ix_saved_reports_recruiter_id'), table_name='saved_reports')
    op.drop_index(op.f('ix_saved_reports_id'), table_name='saved_reports')
    op.drop_table('saved_reports')
