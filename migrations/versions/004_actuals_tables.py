"""Add actuals and budget tables

Revision ID: 004
Revises: 003
Create Date: 2025-12-23
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade():
    # Energy Actuals table
    op.create_table(
        'energy_actuals',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('gl_detail_id', sa.String(20), nullable=True),
        sa.Column('journal', sa.String(20), nullable=True),
        sa.Column('period_yyyymm', sa.String(6), nullable=False),
        sa.Column('period_id', sa.Integer(), nullable=True),
        sa.Column('gl_account', sa.String(50), nullable=False),
        sa.Column('account_description', sa.String(100), nullable=True),
        sa.Column('plant_id', sa.Integer(), nullable=True),
        sa.Column('budget_entity', sa.String(20), nullable=True),
        sa.Column('amount', sa.Numeric(18, 2), nullable=False),
        sa.Column('debit_credit', sa.String(1), nullable=True),
        sa.Column('cost_group', sa.String(20), nullable=True),
        sa.Column('cost_type', sa.String(20), nullable=True),
        sa.Column('labor_nonlabor', sa.String(20), nullable=True),
        sa.Column('description', sa.String(100), nullable=True),
        sa.Column('description2', sa.String(200), nullable=True),
        sa.Column('trans_date', sa.Date(), nullable=True),
        sa.Column('work_order', sa.String(30), nullable=True),
        sa.Column('po_number', sa.String(30), nullable=True),
        sa.Column('project_id', sa.String(30), nullable=True),
        sa.Column('project_desc', sa.String(100), nullable=True),
        sa.Column('vendor_id', sa.String(20), nullable=True),
        sa.Column('vendor_name', sa.String(100), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['period_id'], ['periods.id']),
        sa.ForeignKeyConstraint(['plant_id'], ['plants.id']),
    )
    op.create_index('ix_energy_actuals_period_yyyymm', 'energy_actuals', ['period_yyyymm'])
    op.create_index('ix_energy_actuals_gl_account', 'energy_actuals', ['gl_account'])
    op.create_index('ix_energy_actuals_cost_group', 'energy_actuals', ['cost_group'])

    # Expense Actuals table
    op.create_table(
        'expense_actuals',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('gl_detail_id', sa.String(20), nullable=True),
        sa.Column('journal', sa.String(20), nullable=True),
        sa.Column('period_yyyymm', sa.String(6), nullable=False),
        sa.Column('period_id', sa.Integer(), nullable=True),
        sa.Column('gl_account', sa.String(50), nullable=False),
        sa.Column('account_description', sa.String(100), nullable=True),
        sa.Column('plant_id', sa.Integer(), nullable=True),
        sa.Column('budget_entity', sa.String(20), nullable=True),
        sa.Column('amount', sa.Numeric(18, 2), nullable=False),
        sa.Column('debit_credit', sa.String(1), nullable=True),
        sa.Column('department', sa.String(30), nullable=True),
        sa.Column('cost_type', sa.String(20), nullable=True),
        sa.Column('labor_nonlabor', sa.String(20), nullable=True),
        sa.Column('outage_unit', sa.String(10), nullable=True),
        sa.Column('description', sa.String(100), nullable=True),
        sa.Column('description2', sa.String(200), nullable=True),
        sa.Column('trans_date', sa.Date(), nullable=True),
        sa.Column('work_order', sa.String(30), nullable=True),
        sa.Column('po_number', sa.String(30), nullable=True),
        sa.Column('project_id', sa.String(30), nullable=True),
        sa.Column('project_desc', sa.String(100), nullable=True),
        sa.Column('vendor_id', sa.String(20), nullable=True),
        sa.Column('vendor_name', sa.String(100), nullable=True),
        sa.Column('location', sa.String(30), nullable=True),
        sa.Column('location_desc', sa.String(100), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['period_id'], ['periods.id']),
        sa.ForeignKeyConstraint(['plant_id'], ['plants.id']),
    )
    op.create_index('ix_expense_actuals_period_yyyymm', 'expense_actuals', ['period_yyyymm'])
    op.create_index('ix_expense_actuals_gl_account', 'expense_actuals', ['gl_account'])
    op.create_index('ix_expense_actuals_department', 'expense_actuals', ['department'])

    # Budget Lines table
    op.create_table(
        'budget_lines',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('budget_history_link', sa.String(20), nullable=True),
        sa.Column('budget_key', sa.String(100), nullable=True),
        sa.Column('budget_number', sa.String(20), nullable=True),
        sa.Column('full_account', sa.String(50), nullable=False),
        sa.Column('account_code', sa.String(50), nullable=True),
        sa.Column('account_description', sa.String(100), nullable=True),
        sa.Column('line_description', sa.String(500), nullable=True),
        sa.Column('budget_entity', sa.String(20), nullable=True),
        sa.Column('plant_id', sa.Integer(), nullable=True),
        sa.Column('department', sa.String(30), nullable=True),
        sa.Column('labor_nonlabor', sa.String(5), nullable=True),
        sa.Column('budget_year', sa.Integer(), nullable=False),
        sa.Column('jan', sa.Numeric(18, 2), default=0),
        sa.Column('feb', sa.Numeric(18, 2), default=0),
        sa.Column('mar', sa.Numeric(18, 2), default=0),
        sa.Column('apr', sa.Numeric(18, 2), default=0),
        sa.Column('may', sa.Numeric(18, 2), default=0),
        sa.Column('jun', sa.Numeric(18, 2), default=0),
        sa.Column('jul', sa.Numeric(18, 2), default=0),
        sa.Column('aug', sa.Numeric(18, 2), default=0),
        sa.Column('sep', sa.Numeric(18, 2), default=0),
        sa.Column('oct', sa.Numeric(18, 2), default=0),
        sa.Column('nov', sa.Numeric(18, 2), default=0),
        sa.Column('dec', sa.Numeric(18, 2), default=0),
        sa.Column('total', sa.Numeric(18, 2), default=0),
        sa.Column('year_plus_1', sa.Numeric(18, 2), default=0),
        sa.Column('year_plus_2', sa.Numeric(18, 2), default=0),
        sa.Column('year_plus_3', sa.Numeric(18, 2), default=0),
        sa.Column('year_plus_4', sa.Numeric(18, 2), default=0),
        sa.Column('ranking', sa.String(20), nullable=True),
        sa.Column('ranking_priority', sa.Integer(), nullable=True),
        sa.Column('ranking_category', sa.String(30), nullable=True),
        sa.Column('comments', sa.String(500), nullable=True),
        sa.Column('import_date', sa.Date(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['plant_id'], ['plants.id']),
    )
    op.create_index('ix_budget_lines_full_account', 'budget_lines', ['full_account'])
    op.create_index('ix_budget_lines_budget_entity', 'budget_lines', ['budget_entity'])
    op.create_index('ix_budget_lines_budget_year', 'budget_lines', ['budget_year'])
    op.create_index('ix_budget_lines_department', 'budget_lines', ['department'])
    op.create_index('ix_budget_lines_budget_key', 'budget_lines', ['budget_key'])

    # Coal Inventory table
    op.create_table(
        'coal_inventory',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('period_yyyymm', sa.String(6), nullable=False),
        sa.Column('period_id', sa.Integer(), nullable=True),
        sa.Column('plant_id', sa.Integer(), nullable=False),
        sa.Column('purchased_tons', sa.Numeric(18, 2), default=0),
        sa.Column('consumed_tons', sa.Numeric(18, 2), default=0),
        sa.Column('inventory_adjustment', sa.Numeric(18, 2), default=0),
        sa.Column('ending_inventory_tons', sa.Numeric(18, 2), default=0),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['period_id'], ['periods.id']),
        sa.ForeignKeyConstraint(['plant_id'], ['plants.id']),
    )
    op.create_index('ix_coal_inventory_period_yyyymm', 'coal_inventory', ['period_yyyymm'])
    op.create_index('ix_coal_inventory_plant_id', 'coal_inventory', ['plant_id'])


def downgrade():
    op.drop_table('coal_inventory')
    op.drop_table('budget_lines')
    op.drop_table('expense_actuals')
    op.drop_table('energy_actuals')

