"""Add organizations system with hierarchy support

Revision ID: 20250909_201123
Revises: 
Create Date: 2025-09-09 20:11:23.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20250909_201123'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create organization_type enum (skip if exists)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE organization_type AS ENUM ('family', 'team', 'department', 'company');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    # Create organization_role enum (skip if exists)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE organization_role AS ENUM ('owner', 'admin', 'manager', 'member', 'viewer', 'accountant');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    # Create organizations table
    op.create_table('organizations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=sa.text('gen_random_uuid()')),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('type', postgresql.ENUM(name='organization_type'), nullable=False),
        sa.Column('parent_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('owner_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('currency', sa.String(3), default='USD'),
        sa.Column('plan_type', sa.String(50), default='free'),
        sa.Column('settings', postgresql.JSONB, default={}),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('is_active', sa.Boolean, default=True),
        sa.ForeignKeyConstraint(['parent_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id']),
        sa.CheckConstraint('id != parent_id', name='no_self_parent')
    )
    
    # Create organization_members table
    op.create_table('organization_members',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=sa.text('gen_random_uuid()')),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('role', postgresql.ENUM(name='organization_role'), nullable=False, default='member'),
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
        sa.Column('role', postgresql.ENUM(name='organization_role'), default='member'),
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
    
    # Add organization_id to transactions table
    op.add_column('transactions', sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key('fk_transactions_organization_id', 'transactions', 'organizations', ['organization_id'], ['id'])
    
    # Create indexes for performance
    op.create_index('idx_organizations_parent_id', 'organizations', ['parent_id'])
    op.create_index('idx_organizations_owner_id', 'organizations', ['owner_id'])
    op.create_index('idx_org_members_user_id', 'organization_members', ['user_id'])
    op.create_index('idx_org_members_organization_id', 'organization_members', ['organization_id'])
    op.create_index('idx_org_invitations_phone', 'organization_invitations', ['invited_phone'])
    op.create_index('idx_transactions_organization_id', 'transactions', ['organization_id'])
    op.create_index('idx_transactions_user_org', 'transactions', ['user_id', 'organization_id'])
    
    # Migrate existing families to organizations
    op.execute("""
        INSERT INTO organizations (id, name, type, owner_id, currency, created_at)
        SELECT id, name, 'family'::organization_type, created_by, currency, created_at 
        FROM families
        WHERE EXISTS (SELECT 1 FROM families)
    """)
    
    # Migrate family_members to organization_members
    op.execute("""
        INSERT INTO organization_members (organization_id, user_id, role, nickname, joined_at)
        SELECT family_id, user_id, 
               CASE 
                 WHEN role = 'admin' THEN 'admin'::organization_role
                 WHEN role = 'member' THEN 'member'::organization_role  
                 WHEN role = 'viewer' THEN 'viewer'::organization_role
                 ELSE 'member'::organization_role
               END,
               nickname, joined_at
        FROM family_members
        WHERE EXISTS (SELECT 1 FROM family_members)
    """)
    
    # Migrate family_invitations to organization_invitations  
    op.execute("""
        INSERT INTO organization_invitations (organization_id, invited_phone, invited_by, role, message, expires_at, created_at)
        SELECT family_id, invited_phone, invited_by,
               CASE 
                 WHEN role = 'admin' THEN 'admin'::organization_role
                 WHEN role = 'member' THEN 'member'::organization_role
                 WHEN role = 'viewer' THEN 'viewer'::organization_role  
                 ELSE 'member'::organization_role
               END,
               message, expires_at, created_at
        FROM family_invitations
        WHERE EXISTS (SELECT 1 FROM family_invitations)
    """)


def downgrade() -> None:
    # Remove indexes
    op.drop_index('idx_transactions_user_org', 'transactions')
    op.drop_index('idx_transactions_organization_id', 'transactions')
    op.drop_index('idx_org_invitations_phone', 'organization_invitations')
    op.drop_index('idx_org_members_organization_id', 'organization_members')
    op.drop_index('idx_org_members_user_id', 'organization_members')
    op.drop_index('idx_organizations_owner_id', 'organizations')
    op.drop_index('idx_organizations_parent_id', 'organizations')
    
    # Remove organization_id from transactions
    op.drop_constraint('fk_transactions_organization_id', 'transactions', type_='foreignkey')
    op.drop_column('transactions', 'organization_id')
    
    # Drop tables
    op.drop_table('organization_invitations')
    op.drop_table('organization_members')
    op.drop_table('organizations')
    
    # Drop enums
    op.execute('DROP TYPE IF EXISTS organization_role')
    op.execute('DROP TYPE IF EXISTS organization_type')