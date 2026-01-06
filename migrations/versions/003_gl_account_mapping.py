"""Add GL account mapping tables

Revision ID: 003
Revises: 002
Create Date: 2025-12-23
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade():
    # GL Account Mapping table
    op.create_table(
        'gl_account_mappings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('gl_account', sa.String(50), nullable=False),
        sa.Column('company_code', sa.String(10), nullable=True),
        sa.Column('plant_code', sa.String(5), nullable=True),
        sa.Column('entity_code', sa.String(10), nullable=True),
        sa.Column('account_type', sa.String(10), nullable=True),
        sa.Column('cost_type_code', sa.String(10), nullable=True),
        sa.Column('department_code', sa.String(10), nullable=True),
        sa.Column('ferc_account', sa.String(10), nullable=True),
        sa.Column('sub_account', sa.String(10), nullable=True),
        sa.Column('labor_indicator', sa.String(5), nullable=True),
        sa.Column('plant_id', sa.Integer(), nullable=True),
        sa.Column('cost_category_id', sa.Integer(), nullable=True),
        sa.Column('account_description', sa.String(200), nullable=True),
        sa.Column('is_energy_account', sa.Boolean(), default=False),
        sa.Column('is_labor', sa.Boolean(), default=False),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['plant_id'], ['plants.id']),
        sa.ForeignKeyConstraint(['cost_category_id'], ['cost_categories.id']),
    )
    op.create_index('ix_gl_account_mappings_gl_account', 'gl_account_mappings', ['gl_account'], unique=True)
    op.create_index('ix_gl_account_mappings_ferc_account', 'gl_account_mappings', ['ferc_account'])
    op.create_index('ix_gl_account_mappings_plant_id', 'gl_account_mappings', ['plant_id'])

    # FERC Account Mapping table
    op.create_table(
        'ferc_account_mappings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('ferc_code', sa.String(10), nullable=False),
        sa.Column('description', sa.String(200), nullable=False),
        sa.Column('cost_category_id', sa.Integer(), nullable=True),
        sa.Column('is_fuel_related', sa.Boolean(), default=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['cost_category_id'], ['cost_categories.id']),
    )
    op.create_index('ix_ferc_account_mappings_ferc_code', 'ferc_account_mappings', ['ferc_code'], unique=True)

    # Department Mapping table
    op.create_table(
        'department_mappings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('dept_code', sa.String(10), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('short_name', sa.String(20), nullable=True),
        sa.Column('is_outage', sa.Boolean(), default=False),
        sa.Column('unit_number', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_department_mappings_dept_code', 'department_mappings', ['dept_code'], unique=True)


def downgrade():
    op.drop_table('department_mappings')
    op.drop_table('ferc_account_mappings')
    op.drop_table('gl_account_mappings')

