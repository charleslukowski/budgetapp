"""Add capital assets and projects tables

Revision ID: 002
Revises: 001
Create Date: 2024-12-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Capital assets table
    op.create_table(
        'capital_assets',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('asset_number', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('plant_id', sa.Integer(), nullable=True),
        sa.Column('original_cost', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('salvage_value', sa.Numeric(precision=18, scale=2), nullable=True, default=0),
        sa.Column('useful_life_years', sa.Integer(), nullable=False),
        sa.Column('in_service_date', sa.Date(), nullable=False),
        sa.Column('retirement_date', sa.Date(), nullable=True),
        sa.Column('depreciation_method', sa.String(length=50), nullable=True, default='straight_line'),
        sa.Column('accumulated_depreciation', sa.Numeric(precision=18, scale=2), nullable=True, default=0),
        sa.Column('status', sa.String(length=50), nullable=True, default='active'),
        sa.ForeignKeyConstraint(['plant_id'], ['plants.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('asset_number')
    )
    op.create_index(op.f('ix_capital_assets_id'), 'capital_assets', ['id'], unique=False)

    # Capital projects table
    op.create_table(
        'capital_projects',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_number', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('plant_id', sa.Integer(), nullable=True),
        sa.Column('estimated_cost', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('contingency_percent', sa.Numeric(precision=5, scale=2), nullable=True, default=10),
        sa.Column('npv', sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column('irr', sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column('payback_years', sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column('proposed_start_date', sa.Date(), nullable=True),
        sa.Column('proposed_in_service_date', sa.Date(), nullable=True),
        sa.Column('estimated_useful_life', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=True, default='proposed'),
        sa.Column('approved_date', sa.Date(), nullable=True),
        sa.Column('approved_by', sa.String(length=100), nullable=True),
        sa.Column('capital_asset_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['plant_id'], ['plants.id'], ),
        sa.ForeignKeyConstraint(['capital_asset_id'], ['capital_assets.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('project_number')
    )
    op.create_index(op.f('ix_capital_projects_id'), 'capital_projects', ['id'], unique=False)


def downgrade() -> None:
    op.drop_table('capital_projects')
    op.drop_table('capital_assets')

