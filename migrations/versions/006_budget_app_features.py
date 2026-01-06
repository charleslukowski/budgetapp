"""Add department forecasts, variance explanations, and funding changes tables

Revision ID: 006
Revises: 005
Create Date: 2025-12-24
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = '006'
down_revision = '005'
branch_labels = None
depends_on = None


def upgrade():
    # Department Forecasts table - stores user-entered forecast values by department/month
    op.create_table(
        'department_forecasts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('plant_code', sa.String(10), nullable=False),
        sa.Column('dept_code', sa.String(30), nullable=False),
        sa.Column('budget_year', sa.Integer(), nullable=False),
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
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('updated_by', sa.String(100), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('plant_code', 'dept_code', 'budget_year', name='uq_dept_forecast'),
    )
    op.create_index('ix_dept_forecasts_plant_year', 'department_forecasts', ['plant_code', 'budget_year'])
    op.create_index('ix_dept_forecasts_dept', 'department_forecasts', ['dept_code'])

    # Variance Explanations table - stores explanations for budget variances
    op.create_table(
        'variance_explanations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('plant_code', sa.String(10), nullable=False),
        sa.Column('dept_code', sa.String(30), nullable=False),
        sa.Column('budget_year', sa.Integer(), nullable=False),
        sa.Column('period_month', sa.Integer(), nullable=False),  # 1-12 or 0 for YTD
        sa.Column('explanation', sa.Text(), nullable=True),
        sa.Column('variance_amount', sa.Numeric(18, 2), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('created_by', sa.String(100), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('plant_code', 'dept_code', 'budget_year', 'period_month', name='uq_variance_expl'),
    )
    op.create_index('ix_variance_expl_plant_year', 'variance_explanations', ['plant_code', 'budget_year'])
    op.create_index('ix_variance_expl_dept', 'variance_explanations', ['dept_code'])

    # Funding Changes table - stores budget amendments and reallocations
    op.create_table(
        'funding_changes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('plant_code', sa.String(10), nullable=False),
        sa.Column('budget_year', sa.Integer(), nullable=False),
        sa.Column('change_type', sa.String(20), nullable=False),  # 'amendment' or 'reallocation'
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),  # pending, approved, rejected
        # For amendments: single department/account change
        sa.Column('department', sa.String(30), nullable=True),
        sa.Column('account', sa.String(50), nullable=True),
        sa.Column('amount', sa.Numeric(18, 2), nullable=True),
        # For reallocations: from/to details
        sa.Column('from_department', sa.String(30), nullable=True),
        sa.Column('from_account', sa.String(50), nullable=True),
        sa.Column('to_department', sa.String(30), nullable=True),
        sa.Column('to_account', sa.String(50), nullable=True),
        sa.Column('reallocation_amount', sa.Numeric(18, 2), nullable=True),
        # Common fields
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('requested_by', sa.String(100), nullable=True),
        sa.Column('approved_by', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_funding_changes_plant_year', 'funding_changes', ['plant_code', 'budget_year'])
    op.create_index('ix_funding_changes_type', 'funding_changes', ['change_type'])
    op.create_index('ix_funding_changes_status', 'funding_changes', ['status'])


def downgrade():
    op.drop_table('funding_changes')
    op.drop_table('variance_explanations')
    op.drop_table('department_forecasts')

