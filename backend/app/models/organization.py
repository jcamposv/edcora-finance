from sqlalchemy import Column, String, DateTime, UUID, ForeignKey, Enum, Boolean, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum
from app.core.database import Base

class OrganizationType(enum.Enum):
    """Types of organizations for different scales and use cases."""
    family = "family"          # Familias/roommates (2-10 personas)
    team = "team"             # Equipos pequeños (5-50 personas)
    department = "department"  # Departamentos (10-200 personas)
    company = "company"        # Empresas completas (50+ personas)

class OrganizationRole(enum.Enum):
    """Roles within an organization with different permission levels."""
    owner = "owner"           # Dueño (familias/empresas) - todos los permisos
    admin = "admin"           # Administrador - puede invitar/remover/gestionar
    manager = "manager"       # Manager (empresas) - puede gestionar equipo/departamento
    member = "member"         # Miembro activo - puede agregar transacciones
    viewer = "viewer"         # Solo lectura - puede ver reportes
    accountant = "accountant" # Contador (empresas) - acceso completo a finanzas

class Organization(Base):
    """
    Universal organization model that supports:
    - Families and roommates (family)
    - Small teams and startups (team) 
    - Company departments (department)
    - Full companies (company)
    """
    __tablename__ = "organizations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    type = Column(Enum(OrganizationType), nullable=False)
    
    # Hierarchical support: companies can have departments, departments can have teams
    parent_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True)
    
    # Who created/owns this organization
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # Financial settings
    currency = Column(String(3), default="USD")
    plan_type = Column(String(50), default="free")  # free, premium, business, enterprise
    
    # Flexible configuration storage
    settings = Column(JSONB, default={})
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    is_active = Column(Boolean, default=True)
    
    # Relationships
    owner = relationship("User", back_populates="owned_organizations")
    members = relationship("OrganizationMember", back_populates="organization", cascade="all, delete-orphan")
    transactions = relationship("Transaction", back_populates="organization")
    invitations = relationship("OrganizationInvitation", back_populates="organization", cascade="all, delete-orphan")
    
    # Self-referential relationship for hierarchy
    parent = relationship("Organization", remote_side=[id], back_populates="children")
    children = relationship("Organization", back_populates="parent")
    
    def __repr__(self):
        return f"<Organization {self.name} ({self.type.value})>"
    
    @property
    def member_count(self):
        """Get total number of active members."""
        return len([m for m in self.members if m.is_active])
    
    @property
    def is_hierarchical(self):
        """Check if this organization supports hierarchies."""
        return self.type in [OrganizationType.department, OrganizationType.company]
    
    def get_admin_members(self):
        """Get all members with admin or owner roles."""
        return [m for m in self.members 
                if m.is_active and m.role in [OrganizationRole.owner, OrganizationRole.admin]]
    
    def can_user_manage(self, user_id: str) -> bool:
        """Check if user can manage this organization."""
        if str(self.owner_id) == user_id:
            return True
        
        member = next((m for m in self.members 
                      if str(m.user_id) == user_id and m.is_active), None)
        
        return member and member.role in [OrganizationRole.admin, OrganizationRole.manager]

class OrganizationMember(Base):
    """
    Membership in an organization with role-based permissions.
    """
    __tablename__ = "organization_members"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # Role and permissions
    role = Column(Enum(OrganizationRole), nullable=False, default=OrganizationRole.member)
    department = Column(String(255), nullable=True)  # For large organizations
    permissions = Column(JSONB, default={})  # Granular custom permissions
    
    # Display name within organization
    nickname = Column(String(100), nullable=True)
    
    # Metadata
    joined_at = Column(DateTime(timezone=True), server_default=func.now())
    is_active = Column(Boolean, default=True)
    
    # Relationships
    organization = relationship("Organization", back_populates="members")
    user = relationship("User", back_populates="organization_memberships")
    
    # Unique constraint: one membership per user per organization
    __table_args__ = (
        {'extend_existing': True},
    )
    
    def __repr__(self):
        return f"<OrganizationMember {self.user_id} in {self.organization_id} as {self.role.value}>"
    
    def can_create_transactions(self) -> bool:
        """Check if this member can create transactions."""
        return self.role in [
            OrganizationRole.owner, 
            OrganizationRole.admin, 
            OrganizationRole.manager,
            OrganizationRole.member
        ]
    
    def can_view_reports(self) -> bool:
        """Check if this member can view organization reports."""
        return True  # All members can view reports
    
    def can_invite_members(self) -> bool:
        """Check if this member can invite new members."""
        return self.role in [
            OrganizationRole.owner,
            OrganizationRole.admin,
            OrganizationRole.manager
        ]

class OrganizationInvitation(Base):
    """
    Pending invitations to join an organization.
    """
    __tablename__ = "organization_invitations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    
    # Invitation details
    invited_phone = Column(String(20), nullable=False)
    invited_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    role = Column(Enum(OrganizationRole), default=OrganizationRole.member)
    message = Column(Text, nullable=True)
    
    # Timing
    expires_at = Column(DateTime(timezone=True), server_default=text("NOW() + INTERVAL '7 days'"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Acceptance tracking
    accepted_at = Column(DateTime(timezone=True), nullable=True)
    accepted_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    
    # Status
    is_active = Column(Boolean, default=True)
    
    # Relationships
    organization = relationship("Organization", back_populates="invitations")
    inviter = relationship("User", foreign_keys=[invited_by], back_populates="sent_invitations")
    accepter = relationship("User", foreign_keys=[accepted_by], back_populates="accepted_invitations")
    
    def __repr__(self):
        return f"<OrganizationInvitation {self.invited_phone} to {self.organization_id}>"
    
    @property
    def is_expired(self) -> bool:
        """Check if invitation has expired."""
        from datetime import datetime
        return datetime.now() > self.expires_at
    
    @property
    def is_pending(self) -> bool:
        """Check if invitation is still pending."""
        return self.is_active and not self.accepted_at and not self.is_expired