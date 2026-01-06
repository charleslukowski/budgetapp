"""Add coal starting inventory table

Revision ID: 009
Revises: 008
Create Date: 2025-12-27
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = '009'
down_revision = '008'
branch_labels = None
depends_on = None


def upgrade():
    # Coal Starting Inventory table - stores January 1st beginning inventory
    op.create_table(
        'coal_starting_inventory',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('plant_id', sa.Integer(), nullable=False),
        sa.Column('beginning_inventory_tons', sa.Numeric(18, 2), nullable=False),
        sa.Column('source', sa.String(100), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['plant_id'], ['plants.id']),
    )
    op.create_index('ix_coal_starting_inventory_year', 'coal_starting_inventory', ['year'])
    op.create_index('ix_coal_starting_inventory_plant_id', 'coal_starting_inventory', ['plant_id'])


def downgrade():
    op.drop_table('coal_starting_inventory')
