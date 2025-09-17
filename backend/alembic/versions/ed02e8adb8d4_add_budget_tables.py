"""add_budget_tables

Revision ID: ed02e8adb8d4
Revises: a02fbd5a58e0
Create Date: 2025-09-17 02:59:34.813432

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'ed02e8adb8d4'
down_revision: Union[str, None] = 'a02fbd5a58e0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create BudgetPeriod enum if it doesn't exist
    op.execute("DO $$ BEGIN CREATE TYPE budgetperiod AS ENUM ('weekly', 'monthly', 'yearly'); EXCEPTION WHEN duplicate_object THEN null; END $$;")
    
    # Create BudgetStatus enum if it doesn't exist  
    op.execute("DO $$ BEGIN CREATE TYPE budgetstatus AS ENUM ('active', 'paused', 'completed'); EXCEPTION WHEN duplicate_object THEN null; END $$;")
    
    # Create budgets table
    op.create_table('budgets',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('category', sa.String(), nullable=False),
        sa.Column('amount', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('period', sa.String(), nullable=True),
        sa.Column('start_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('end_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('status', sa.String(), nullable=True),
        sa.Column('alert_percentage', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('auto_renew', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create budget_alerts table
    op.create_table('budget_alerts',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('budget_id', sa.UUID(), nullable=False),
        sa.Column('percentage_spent', sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column('amount_spent', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('message_sent', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['budget_id'], ['budgets.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create reminders table
    op.create_table('reminders',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('message', sa.String(), nullable=False),
        sa.Column('category', sa.String(), nullable=True),
        sa.Column('amount', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('next_trigger', sa.DateTime(timezone=True), nullable=False),
        sa.Column('frequency', sa.String(), nullable=False),
        sa.Column('day_of_week', sa.String(), nullable=True),
        sa.Column('day_of_month', sa.String(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('last_sent', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    # Drop tables
    op.drop_table('reminders')
    op.drop_table('budget_alerts')
    op.drop_table('budgets')
    
    # Drop enums if they exist
    op.execute("DROP TYPE IF EXISTS budgetstatus")
    op.execute("DROP TYPE IF EXISTS budgetperiod")