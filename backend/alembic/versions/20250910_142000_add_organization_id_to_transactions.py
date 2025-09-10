"""Add organization_id to transactions table

Revision ID: 20250910_142000
Revises: 20250909_201123
Create Date: 2025-09-10 14:20:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20250910_142000'
down_revision = '20250909_201123'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add organization_id column to transactions table
    op.add_column('transactions', sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=True))
    
    # Create foreign key constraint
    op.create_foreign_key('fk_transactions_organization_id', 'transactions', 'organizations', ['organization_id'], ['id'])
    
    # Create index for performance
    op.create_index('idx_transactions_organization_id', 'transactions', ['organization_id'])
    op.create_index('idx_transactions_user_org', 'transactions', ['user_id', 'organization_id'])


def downgrade() -> None:
    # Remove indexes
    op.drop_index('idx_transactions_user_org', 'transactions')
    op.drop_index('idx_transactions_organization_id', 'transactions')
    
    # Remove foreign key constraint
    op.drop_constraint('fk_transactions_organization_id', 'transactions', type_='foreignkey')
    
    # Remove column
    op.drop_column('transactions', 'organization_id')