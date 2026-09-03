"""add_enterprise_tables (Company, CompanyMember, CalibrationSample, DriftSnapshot, ABExperiment, AIAuditLog)

Revision ID: d8fefe0773fd
Revises: 77bc00a1531c
Create Date: 2026-06-01 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd8fefe0773fd'
down_revision: Union[str, Sequence[str], None] = '77bc00a1531c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Company ---
    op.create_table(
        'companies',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('slug', sa.String(100), nullable=False, unique=True),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default=sa.text('1')),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # --- CompanyMember ---
    op.create_table(
        'company_members',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer, sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('company_id', sa.Integer, sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False),
        sa.Column('role', sa.String(50), nullable=False, server_default='recruiter'),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default=sa.text('1')),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('user_id', 'company_id', name='uq_user_company'),
    )

    # --- CalibrationSample ---
    op.create_table(
        'calibration_samples',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('application_id', sa.Integer, sa.ForeignKey('applications.id', ondelete='CASCADE'), nullable=False),
        sa.Column('company_id', sa.Integer, sa.ForeignKey('companies.id', ondelete='SET NULL'), nullable=True),
        sa.Column('ai_score', sa.Float, nullable=True),
        sa.Column('ai_breakdown', sa.Text, nullable=True),
        sa.Column('human_rating', sa.Float, nullable=True),
        sa.Column('human_breakdown', sa.Text, nullable=True),
        sa.Column('human_evaluator_id', sa.Integer, sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('calibrated_at', sa.DateTime, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    # --- DriftSnapshot ---
    op.create_table(
        'drift_snapshots',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('company_id', sa.Integer, sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=True),
        sa.Column('metric_name', sa.String(100), nullable=False),
        sa.Column('metric_value', sa.Float, nullable=False),
        sa.Column('baseline_value', sa.Float, nullable=True),
        sa.Column('drift_score', sa.Float, nullable=True),
        sa.Column('sample_size', sa.Integer, nullable=True),
        sa.Column('snapshot_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    # --- ABExperiment ---
    op.create_table(
        'ab_experiments',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('company_id', sa.Integer, sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('model_a', sa.String(100), nullable=False),
        sa.Column('model_b', sa.String(100), nullable=False),
        sa.Column('sample_size_a', sa.Integer, nullable=False, server_default=sa.text('0')),
        sa.Column('sample_size_b', sa.Integer, nullable=False, server_default=sa.text('0')),
        sa.Column('avg_score_a', sa.Float, nullable=True),
        sa.Column('avg_score_b', sa.Float, nullable=True),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default=sa.text('1')),
        sa.Column('conclusion', sa.Text, nullable=True),
        sa.Column('started_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('ended_at', sa.DateTime, nullable=True),
    )

    # --- AIAuditLog ---
    op.create_table(
        'ai_audit_logs',
        sa.Column('id', sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column('application_id', sa.Integer, sa.ForeignKey('applications.id', ondelete='SET NULL'), nullable=True),
        sa.Column('company_id', sa.Integer, sa.ForeignKey('companies.id', ondelete='SET NULL'), nullable=True),
        sa.Column('turn_number', sa.Integer, nullable=True),
        sa.Column('action', sa.String(100), nullable=False, server_default='llm_call'),
        sa.Column('prompt_used', sa.Text, nullable=True),
        sa.Column('model_version', sa.String(100), nullable=True),
        sa.Column('response_content', sa.Text, nullable=True),
        sa.Column('scoring_breakdown', sa.Text, nullable=True),
        sa.Column('input_snapshot', sa.Text, nullable=True),
        sa.Column('duration_ms', sa.Integer, nullable=True),
        sa.Column('success', sa.Boolean, nullable=False, server_default=sa.text('1')),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    # --- Indexes ---
    op.create_index('ix_ai_audit_application', 'ai_audit_logs', ['application_id'])
    op.create_index('ix_ai_audit_company', 'ai_audit_logs', ['company_id'])
    op.create_index('ix_ai_audit_created', 'ai_audit_logs', ['created_at'])
    op.create_index('ix_company_member_user', 'company_members', ['user_id'])
    op.create_index('ix_company_member_company', 'company_members', ['company_id'])
    op.create_index('ix_calibration_application', 'calibration_samples', ['application_id'])
    op.create_index('ix_drift_snapshot_company', 'drift_snapshots', ['company_id'])
    op.create_index('ix_drift_snapshot_metric', 'drift_snapshots', ['metric_name'])
    op.create_index('ix_drift_snapshot_time', 'drift_snapshots', ['snapshot_at'])
    op.create_index('ix_ab_experiment_company', 'ab_experiments', ['company_id'])


def downgrade() -> None:
    op.drop_table('ai_audit_logs')
    op.drop_table('ab_experiments')
    op.drop_table('drift_snapshots')
    op.drop_table('calibration_samples')
    op.drop_table('company_members')
    op.drop_table('companies')
