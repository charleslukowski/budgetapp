"""Add budget submissions and budget entries tables

Revision ID: 007
Revises: 006
Create Date: 2025-12-24
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = '007'
down_revision = '006'
branch_labels = None
depends_on = None


def upgrade():
    # Budget Submissions table - tracks status of budget entry per department
    op.create_table(
        'budget_submissions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('plant_code', sa.String(10), nullable=False),
        sa.Column('dept_code', sa.String(30), nullable=False),
        sa.Column('budget_year', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='draft'),  # draft, submitted, approved, rejected
        sa.Column('submitted_at', sa.DateTime(), nullable=True),
        sa.Column('submitted_by', sa.String(100), nullable=True),
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        sa.Column('approved_by', sa.String(100), nullable=True),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('plant_code', 'dept_code', 'budget_year', name='uq_budget_submission'),
    )
    op.create_index('ix_budget_submissions_plant_year', 'budget_submissions', ['plant_code', 'budget_year'])
    op.create_index('ix_budget_submissions_status', 'budget_submissions', ['status'])
    op.create_index('ix_budget_submissions_dept', 'budget_submissions', ['dept_code'])

    # Budget Entries table - stores monthly budget values during entry phase
    op.create_table(
        'budget_entries',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('submission_id', sa.Integer(), sa.ForeignKey('budget_submissions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('plant_code', sa.String(10), nullable=False),
        sa.Column('dept_code', sa.String(30), nullable=False),
        sa.Column('budget_year', sa.Integer(), nullable=False),
        sa.Column('account_code', sa.String(50), nullable=True),
        sa.Column('account_name', sa.String(100), nullable=True),
        sa.Column('line_description', sa.String(500), nullable=True),
        # Monthly amounts
        sa.Column('jan', sa.Numeric(18, 2), server_default='0'),
        sa.Column('feb', sa.Numeric(18, 2), server_default='0'),
        sa.Column('mar', sa.Numeric(18, 2), server_default='0'),
        sa.Column('apr', sa.Numeric(18, 2), server_default='0'),
        sa.Column('may', sa.Numeric(18, 2), server_default='0'),
        sa.Column('jun', sa.Numeric(18, 2), server_default='0'),
        sa.Column('jul', sa.Numeric(18, 2), server_default='0'),
        sa.Column('aug', sa.Numeric(18, 2), server_default='0'),
        sa.Column('sep', sa.Numeric(18, 2), server_default='0'),
        sa.Column('oct', sa.Numeric(18, 2), server_default='0'),
        sa.Column('nov', sa.Numeric(18, 2), server_default='0'),
        sa.Column('dec', sa.Numeric(18, 2), server_default='0'),
        sa.Column('total', sa.Numeric(18, 2), server_default='0'),
        # Notes
        sa.Column('notes', sa.Text(), nullable=True),
        # Audit
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_budget_entries_submission', 'budget_entries', ['submission_id'])
    op.create_index('ix_budget_entries_plant_year', 'budget_entries', ['plant_code', 'budget_year'])
    op.create_index('ix_budget_entries_dept', 'budget_entries', ['dept_code'])


def downgrade():
    op.drop_table('budget_entries')
    op.drop_table('budget_submissions')

