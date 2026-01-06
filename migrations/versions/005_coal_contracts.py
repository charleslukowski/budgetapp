"""Add coal contract tables

Revision ID: 005
Revises: 004
Create Date: 2025-12-23
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade():
    # Coal Contracts table
    op.create_table(
        'coal_contracts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('contract_id', sa.String(50), nullable=False),
        sa.Column('supplier', sa.String(100), nullable=False),
        sa.Column('plant_id', sa.Integer(), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('annual_tons', sa.Numeric(18, 2), nullable=False),
        sa.Column('min_tons', sa.Numeric(18, 2), nullable=True),
        sa.Column('max_tons', sa.Numeric(18, 2), nullable=True),
        sa.Column('btu_per_lb', sa.Numeric(10, 2), nullable=False),
        sa.Column('so2_lb_per_mmbtu', sa.Numeric(8, 4), nullable=True),
        sa.Column('ash_pct', sa.Numeric(6, 4), nullable=True),
        sa.Column('moisture_pct', sa.Numeric(6, 4), nullable=True),
        sa.Column('coal_price_per_ton', sa.Numeric(10, 2), nullable=False),
        sa.Column('barge_price_per_ton', sa.Numeric(10, 2), default=0),
        sa.Column('coal_region', sa.String(50), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['plant_id'], ['plants.id']),
    )
    op.create_index('ix_coal_contracts_contract_id', 'coal_contracts', ['contract_id'], unique=True)
    op.create_index('ix_coal_contracts_plant_id', 'coal_contracts', ['plant_id'])

    # Coal Deliveries table
    op.create_table(
        'coal_deliveries',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('contract_id', sa.Integer(), nullable=False),
        sa.Column('period_id', sa.Integer(), nullable=True),
        sa.Column('period_yyyymm', sa.String(6), nullable=False),
        sa.Column('scheduled_tons', sa.Numeric(18, 2), default=0),
        sa.Column('actual_tons', sa.Numeric(18, 2), default=0),
        sa.Column('actual_btu_per_lb', sa.Numeric(10, 2), nullable=True),
        sa.Column('actual_so2', sa.Numeric(8, 4), nullable=True),
        sa.Column('actual_ash', sa.Numeric(6, 4), nullable=True),
        sa.Column('actual_coal_price', sa.Numeric(10, 2), nullable=True),
        sa.Column('actual_barge_price', sa.Numeric(10, 2), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['contract_id'], ['coal_contracts.id']),
        sa.ForeignKeyConstraint(['period_id'], ['periods.id']),
    )
    op.create_index('ix_coal_deliveries_period_yyyymm', 'coal_deliveries', ['period_yyyymm'])
    op.create_index('ix_coal_deliveries_contract_id', 'coal_deliveries', ['contract_id'])

    # Uncommitted Coal table
    op.create_table(
        'uncommitted_coal',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('plant_id', sa.Integer(), nullable=False),
        sa.Column('period_yyyymm', sa.String(6), nullable=False),
        sa.Column('period_id', sa.Integer(), nullable=True),
        sa.Column('tons', sa.Numeric(18, 2), default=0),
        sa.Column('btu_per_lb', sa.Numeric(10, 2), nullable=False),
        sa.Column('so2_lb_per_mmbtu', sa.Numeric(8, 4), nullable=True),
        sa.Column('market_price_per_ton', sa.Numeric(10, 2), nullable=False),
        sa.Column('barge_price_per_ton', sa.Numeric(10, 2), default=0),
        sa.Column('coal_region', sa.String(50), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['plant_id'], ['plants.id']),
        sa.ForeignKeyConstraint(['period_id'], ['periods.id']),
    )
    op.create_index('ix_uncommitted_coal_period_yyyymm', 'uncommitted_coal', ['period_yyyymm'])
    op.create_index('ix_uncommitted_coal_plant_id', 'uncommitted_coal', ['plant_id'])


def downgrade():
    op.drop_table('uncommitted_coal')
    op.drop_table('coal_deliveries')
    op.drop_table('coal_contracts')

