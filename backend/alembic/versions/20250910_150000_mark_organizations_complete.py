"""Mark organizations migration as complete and add missing column

Revision ID: 20250910_150000
Revises: 20250909_201123
Create Date: 2025-09-10 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20250910_150000'
down_revision = '20250909_201123'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Check if organization_id column exists, if not add it
    op.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT 1 
                FROM information_schema.columns 
                WHERE table_name = 'transactions' 
                AND column_name = 'organization_id'
            ) THEN
                ALTER TABLE transactions ADD COLUMN organization_id UUID REFERENCES organizations(id);
                CREATE INDEX IF NOT EXISTS idx_transactions_organization_id ON transactions(organization_id);
                CREATE INDEX IF NOT EXISTS idx_transactions_user_org ON transactions(user_id, organization_id);
            END IF;
        END $$;
    """)


def downgrade() -> None:
    # Remove organization_id column and indexes if they exist
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (
                SELECT 1 
                FROM information_schema.columns 
                WHERE table_name = 'transactions' 
                AND column_name = 'organization_id'
            ) THEN
                DROP INDEX IF EXISTS idx_transactions_user_org;
                DROP INDEX IF EXISTS idx_transactions_organization_id;
                ALTER TABLE transactions DROP COLUMN organization_id;
            END IF;
        END $$;
    """)