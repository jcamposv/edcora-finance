from sqlalchemy import Column, String, DateTime, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from app.core.database import Base

class User(Base):
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    phone_number = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    currency = Column(String, default="CRC", nullable=False)
    plan_type = Column(String, default="free", nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Existing relationships
    transactions = relationship("Transaction", back_populates="user")
    reports = relationship("Report", back_populates="user")
    budgets = relationship("Budget", back_populates="user")
    reminders = relationship("Reminder", back_populates="user")
    
    # Organization relationships
    owned_organizations = relationship("Organization", back_populates="owner")
    organization_memberships = relationship("OrganizationMember", back_populates="user")
    sent_invitations = relationship("OrganizationInvitation", foreign_keys="OrganizationInvitation.invited_by", back_populates="inviter")
    accepted_invitations = relationship("OrganizationInvitation", foreign_keys="OrganizationInvitation.accepted_by", back_populates="accepter")