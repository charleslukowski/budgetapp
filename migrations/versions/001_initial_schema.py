"""Initial schema for OVEC Budget System

Revision ID: 001
Revises: 
Create Date: 2024-12-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Plants table
    op.create_table(
        'plants',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('short_name', sa.String(length=20), nullable=False),
        sa.Column('capacity_mw', sa.Integer(), nullable=False),
        sa.Column('unit_count', sa.Integer(), nullable=False),
        sa.Column('unit_capacity_mw', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=True, default=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )
    op.create_index(op.f('ix_plants_id'), 'plants', ['id'], unique=False)

    # Periods table
    op.create_table(
        'periods',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('month', sa.Integer(), nullable=True),
        sa.Column('quarter', sa.Integer(), nullable=True),
        sa.Column('granularity', sa.Enum('MONTHLY', 'QUARTERLY', 'ANNUAL', name='granularity'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_periods_id'), 'periods', ['id'], unique=False)
    op.create_index(op.f('ix_periods_year'), 'periods', ['year'], unique=False)

    # Cost categories table
    op.create_table(
        'cost_categories',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('short_name', sa.String(length=50), nullable=False),
        sa.Column('section', sa.Enum('FUEL', 'OPERATING', 'NON_OPERATING', 'CAPITAL', name='costsection'), nullable=False),
        sa.Column('parent_id', sa.Integer(), nullable=True),
        sa.Column('sort_order', sa.Integer(), nullable=True, default=0),
        sa.Column('is_subtotal', sa.Boolean(), nullable=True, default=False),
        sa.Column('is_active', sa.Boolean(), nullable=True, default=True),
        sa.ForeignKeyConstraint(['parent_id'], ['cost_categories.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_cost_categories_id'), 'cost_categories', ['id'], unique=False)
    op.create_index(op.f('ix_cost_categories_section'), 'cost_categories', ['section'], unique=False)

    # Scenarios table
    op.create_table(
        'scenarios',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('scenario_type', sa.Enum('BUDGET', 'INTERNAL_FORECAST', 'EXTERNAL_FORECAST', name='scenariotype'), nullable=False),
        sa.Column('status', sa.Enum('DRAFT', 'REVIEW', 'PUBLISHED', 'ARCHIVED', name='scenariostatus'), nullable=True, default='DRAFT'),
        sa.Column('version', sa.Integer(), nullable=True, default=1),
        sa.Column('parent_scenario_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('created_by', sa.String(length=100), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, default=True),
        sa.Column('is_locked', sa.Boolean(), nullable=True, default=False),
        sa.ForeignKeyConstraint(['parent_scenario_id'], ['scenarios.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_scenarios_id'), 'scenarios', ['id'], unique=False)
    op.create_index(op.f('ix_scenarios_scenario_type'), 'scenarios', ['scenario_type'], unique=False)

    # Forecasts table
    op.create_table(
        'forecasts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('scenario_id', sa.Integer(), nullable=False),
        sa.Column('plant_id', sa.Integer(), nullable=True),
        sa.Column('category_id', sa.Integer(), nullable=False),
        sa.Column('period_id', sa.Integer(), nullable=False),
        sa.Column('generation_mwh', sa.Numeric(precision=18, scale=4), nullable=True),
        sa.Column('cost_dollars', sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('updated_by', sa.String(length=100), nullable=True),
        sa.ForeignKeyConstraint(['category_id'], ['cost_categories.id'], ),
        sa.ForeignKeyConstraint(['period_id'], ['periods.id'], ),
        sa.ForeignKeyConstraint(['plant_id'], ['plants.id'], ),
        sa.ForeignKeyConstraint(['scenario_id'], ['scenarios.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_forecasts_id'), 'forecasts', ['id'], unique=False)
    op.create_index(op.f('ix_forecasts_scenario_id'), 'forecasts', ['scenario_id'], unique=False)
    op.create_index(op.f('ix_forecasts_plant_id'), 'forecasts', ['plant_id'], unique=False)
    op.create_index(op.f('ix_forecasts_category_id'), 'forecasts', ['category_id'], unique=False)
    op.create_index(op.f('ix_forecasts_period_id'), 'forecasts', ['period_id'], unique=False)
    op.create_index('ix_forecast_scenario_period', 'forecasts', ['scenario_id', 'period_id'], unique=False)
    op.create_index('ix_forecast_scenario_plant', 'forecasts', ['scenario_id', 'plant_id'], unique=False)
    op.create_index('ix_forecast_full', 'forecasts', ['scenario_id', 'plant_id', 'category_id', 'period_id'], unique=False)


def downgrade() -> None:
    op.drop_table('forecasts')
    op.drop_table('scenarios')
    op.drop_table('cost_categories')
    op.drop_table('periods')
    op.drop_table('plants')
    
    # Drop enums
    op.execute("DROP TYPE IF EXISTS granularity")
    op.execute("DROP TYPE IF EXISTS costsection")
    op.execute("DROP TYPE IF EXISTS scenariotype")
    op.execute("DROP TYPE IF EXISTS scenariostatus")

