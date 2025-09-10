"""Initial migration

Revision ID: a02fbd5a58e0
Revises: 
Create Date: 2025-09-10 15:39:03.538828

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'a02fbd5a58e0'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create ENUMs with protection
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE organization_type AS ENUM ('family', 'team', 'department', 'company');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE organization_role AS ENUM ('owner', 'admin', 'manager', 'member', 'viewer', 'accountant');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE transactiontype AS ENUM ('income', 'expense');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    # Create users table
    op.create_table('users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=sa.text('gen_random_uuid()')),
        sa.Column('phone_number', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('currency', sa.String(), nullable=False, default='CRC'),
        sa.Column('plan_type', sa.String(), nullable=False, default='free'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint('phone_number')
    )
    op.create_index('ix_users_phone_number', 'users', ['phone_number'])

    # Create organizations table
    op.create_table('organizations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=sa.text('gen_random_uuid()')),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('type', sa.String(), nullable=False),
        sa.Column('parent_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('owner_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('currency', sa.String(3), default='USD'),
        sa.Column('plan_type', sa.String(50), default='free'),
        sa.Column('settings', postgresql.JSONB, default={}),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('is_active', sa.Boolean, default=True),
        sa.ForeignKeyConstraint(['parent_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id'])
    )

    # Create organization_members table
    op.create_table('organization_members',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=sa.text('gen_random_uuid()')),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('role', sa.String(), nullable=False, default='member'),
        sa.Column('department', sa.String(255), nullable=True),
        sa.Column('permissions', postgresql.JSONB, default={}),
        sa.Column('nickname', sa.String(100), nullable=True),
        sa.Column('joined_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('is_active', sa.Boolean, default=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.UniqueConstraint('organization_id', 'user_id', name='unique_user_per_organization')
    )

    # Create organization_invitations table
    op.create_table('organization_invitations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=sa.text('gen_random_uuid()')),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('invited_phone', sa.String(20), nullable=False),
        sa.Column('invited_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('role', sa.String(), default='member'),
        sa.Column('message', sa.Text, nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), server_default=sa.text("NOW() + INTERVAL '7 days'")),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('accepted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('accepted_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('is_active', sa.Boolean, default=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['invited_by'], ['users.id']),
        sa.ForeignKeyConstraint(['accepted_by'], ['users.id'])
    )

    # Create transactions table
    op.create_table('transactions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('amount', sa.Numeric(10, 2), nullable=False),
        sa.Column('type', sa.String(), nullable=False),
        sa.Column('category', sa.String(), nullable=False),
        sa.Column('description', sa.Text),
        sa.Column('date', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'])
    )

    # Create reports table
    op.create_table('reports',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('period', sa.String(), nullable=False),
        sa.Column('start_date', sa.Date, nullable=False),
        sa.Column('end_date', sa.Date, nullable=False),
        sa.Column('summary', postgresql.JSONB, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'])
    )

    # Create indexes
    op.create_index('idx_organizations_parent_id', 'organizations', ['parent_id'])
    op.create_index('idx_organizations_owner_id', 'organizations', ['owner_id'])
    op.create_index('idx_org_members_user_id', 'organization_members', ['user_id'])
    op.create_index('idx_org_members_organization_id', 'organization_members', ['organization_id'])
    op.create_index('idx_org_invitations_phone', 'organization_invitations', ['invited_phone'])
    op.create_index('idx_transactions_user_id', 'transactions', ['user_id'])
    op.create_index('idx_transactions_organization_id', 'transactions', ['organization_id'])
    op.create_index('idx_transactions_user_org', 'transactions', ['user_id', 'organization_id'])


def downgrade() -> None:
    # Drop tables
    op.drop_table('reports')
    op.drop_table('transactions')
    op.drop_table('organization_invitations')
    op.drop_table('organization_members')
    op.drop_table('organizations')
    op.drop_table('users')
    
    # Drop ENUMs
    op.execute('DROP TYPE IF EXISTS transactiontype')
    op.execute('DROP TYPE IF EXISTS organization_role')
    op.execute('DROP TYPE IF EXISTS organization_type')