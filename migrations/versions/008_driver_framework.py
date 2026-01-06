"""Add driver framework tables for driver-based forecasting

Revision ID: 008
Revises: 007
Create Date: 2025-12-24
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = '008'
down_revision = '007'
branch_labels = None
depends_on = None


def upgrade():
    # Create enum types for PostgreSQL
    driver_type_enum = sa.Enum(
        'input', 'price_index', 'rate', 'volume', 'percentage', 'calculated', 'toggle',
        name='driver_type_enum'
    )
    driver_category_enum = sa.Enum(
        'coal_price', 'transportation', 'heat_rate', 'generation', 
        'inventory', 'escalation', 'consumables', 'byproducts', 'other',
        name='driver_category_enum'
    )
    
    # Driver Definitions table - stores metadata about each driver
    op.create_table(
        'driver_definitions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('driver_type', driver_type_enum, nullable=False, server_default='input'),
        sa.Column('category', driver_category_enum, nullable=False, server_default='other'),
        sa.Column('unit', sa.String(50), nullable=False, server_default=''),
        sa.Column('default_value', sa.Numeric(18, 6), server_default='0'),
        sa.Column('min_value', sa.Numeric(18, 6), nullable=True),
        sa.Column('max_value', sa.Numeric(18, 6), nullable=True),
        sa.Column('step', sa.Numeric(18, 6), server_default='1'),
        sa.Column('depends_on', sa.Text(), nullable=True),  # JSON array of driver names
        sa.Column('calculation_formula', sa.Text(), nullable=True),
        sa.Column('is_plant_specific', sa.Boolean(), server_default='false'),
        sa.Column('display_order', sa.Integer(), server_default='0'),
        sa.Column('is_active', sa.Boolean(), server_default='true'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name', name='uq_driver_definition_name'),
    )
    op.create_index('ix_driver_definitions_name', 'driver_definitions', ['name'])
    op.create_index('ix_driver_definitions_category', 'driver_definitions', ['category'])
    op.create_index('ix_driver_definitions_type', 'driver_definitions', ['driver_type'])

    # Driver Values table - stores values for each driver/scenario/period combination
    op.create_table(
        'driver_values',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('scenario_id', sa.Integer(), sa.ForeignKey('scenarios.id', ondelete='CASCADE'), nullable=False),
        sa.Column('driver_id', sa.Integer(), sa.ForeignKey('driver_definitions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('plant_id', sa.Integer(), sa.ForeignKey('plants.id', ondelete='SET NULL'), nullable=True),
        sa.Column('period_yyyymm', sa.String(6), nullable=False),  # YYYYMM for monthly, YYYY for annual
        sa.Column('value', sa.Numeric(18, 6), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('updated_by', sa.String(100), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        # Unique constraint: one value per driver/scenario/plant/period combination
        sa.UniqueConstraint('scenario_id', 'driver_id', 'plant_id', 'period_yyyymm', name='uq_driver_value'),
    )
    op.create_index('ix_driver_values_scenario', 'driver_values', ['scenario_id'])
    op.create_index('ix_driver_values_driver', 'driver_values', ['driver_id'])
    op.create_index('ix_driver_values_period', 'driver_values', ['period_yyyymm'])
    op.create_index('ix_driver_value_lookup', 'driver_values', ['scenario_id', 'driver_id', 'period_yyyymm'])
    op.create_index('ix_driver_value_full', 'driver_values', ['scenario_id', 'driver_id', 'plant_id', 'period_yyyymm'])
    op.create_index('ix_driver_value_scenario_period', 'driver_values', ['scenario_id', 'period_yyyymm'])

    # Driver Value History table - audit trail for changes
    op.create_table(
        'driver_value_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('driver_value_id', sa.Integer(), nullable=True),  # Not FK to allow deletion
        sa.Column('scenario_id', sa.Integer(), nullable=False),
        sa.Column('driver_id', sa.Integer(), nullable=False),
        sa.Column('plant_id', sa.Integer(), nullable=True),
        sa.Column('period_yyyymm', sa.String(6), nullable=False),
        sa.Column('old_value', sa.Numeric(18, 6), nullable=True),
        sa.Column('new_value', sa.Numeric(18, 6), nullable=True),
        sa.Column('change_type', sa.String(20), nullable=False),  # 'create', 'update', 'delete'
        sa.Column('changed_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('changed_by', sa.String(100), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_driver_history_lookup', 'driver_value_history', ['scenario_id', 'driver_id', 'period_yyyymm'])
    op.create_index('ix_driver_history_changed', 'driver_value_history', ['changed_at'])


def downgrade():
    # Drop tables in reverse order
    op.drop_table('driver_value_history')
    op.drop_table('driver_values')
    op.drop_table('driver_definitions')
    
    # Drop enum types
    op.execute('DROP TYPE IF EXISTS driver_type_enum')
    op.execute('DROP TYPE IF EXISTS driver_category_enum')

