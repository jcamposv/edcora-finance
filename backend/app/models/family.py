from sqlalchemy import Column, String, DateTime, UUID, Boolean, ForeignKey, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum
from app.core.database import Base

class FamilyRole(enum.Enum):
    admin = "admin"      # Puede invitar/remover miembros, cambiar configuraciones
    member = "member"    # Puede ver y agregar transacciones
    viewer = "viewer"    # Solo puede ver transacciones

class Family(Base):
    __tablename__ = "families"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)  # "Familia García", "Los Pérez", etc.
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # Configuraciones familiares
    shared_budget = Column(Boolean, default=True)  # Si comparten presupuesto
    currency = Column(String, default="USD")       # Moneda principal de la familia
    
    # Relaciones
    members = relationship("FamilyMember", back_populates="family", cascade="all, delete-orphan")
    creator = relationship("User", foreign_keys=[created_by])

class FamilyMember(Base):
    __tablename__ = "family_members"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    family_id = Column(UUID(as_uuid=True), ForeignKey("families.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    role = Column(Enum(FamilyRole), default=FamilyRole.member)
    
    # Status
    is_active = Column(Boolean, default=True)
    joined_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Configuraciones personales dentro de la familia
    nickname = Column(String)  # "Papá", "Mamá", "Hijo mayor", etc.
    
    # Relaciones
    family = relationship("Family", back_populates="members")
    user = relationship("User")
    
    # Índices únicos: un usuario solo puede estar una vez por familia
    __table_args__ = (
        {'extend_existing': True}
    )

class FamilyInvitation(Base):
    __tablename__ = "family_invitations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    family_id = Column(UUID(as_uuid=True), ForeignKey("families.id"), nullable=False)
    invited_phone = Column(String, nullable=False)  # Número de teléfono invitado
    invited_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # Configuración de la invitación
    role = Column(Enum(FamilyRole), default=FamilyRole.member)
    message = Column(String)  # Mensaje personalizado de invitación
    
    # Status
    is_accepted = Column(Boolean, default=False)
    is_expired = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    accepted_at = Column(DateTime(timezone=True))
    expires_at = Column(DateTime(timezone=True))  # Invitaciones expiran en 7 días
    
    # Relaciones
    family = relationship("Family")
    inviter = relationship("User", foreign_keys=[invited_by])