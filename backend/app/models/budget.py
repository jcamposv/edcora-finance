from sqlalchemy import Column, String, DateTime, UUID, Numeric, Boolean, ForeignKey, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum
from app.core.database import Base

class BudgetPeriod(enum.Enum):
    weekly = "weekly"
    monthly = "monthly"
    yearly = "yearly"

class BudgetStatus(enum.Enum):
    active = "active"
    paused = "paused"
    completed = "completed"

class Budget(Base):
    __tablename__ = "budgets"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True)
    
    # Configuración del presupuesto
    name = Column(String, nullable=False)  # "Alimentación Octubre", "Gastos Mensuales"
    category = Column(String, nullable=False)  # Categoría específica o "general"
    amount = Column(Numeric(10, 2), nullable=False)  # Monto límite
    period = Column(Enum(BudgetPeriod), default=BudgetPeriod.monthly)
    
    # Fechas
    start_date = Column(DateTime(timezone=True), nullable=False)
    end_date = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Estado y configuración
    status = Column(Enum(BudgetStatus), default=BudgetStatus.active)
    alert_percentage = Column(Numeric(5, 2), default=80.0)  # Alerta al 80%
    auto_renew = Column(Boolean, default=False)  # Renovar automáticamente
    
    # Relaciones
    user = relationship("User", back_populates="budgets")
    organization = relationship("Organization", back_populates="budgets")
    alerts = relationship("BudgetAlert", back_populates="budget", cascade="all, delete-orphan")

class BudgetAlert(Base):
    __tablename__ = "budget_alerts"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    budget_id = Column(UUID(as_uuid=True), ForeignKey("budgets.id"), nullable=False)
    
    # Información de la alerta
    percentage_spent = Column(Numeric(5, 2), nullable=False)  # % gastado cuando se disparó
    amount_spent = Column(Numeric(10, 2), nullable=False)     # Monto gastado
    message_sent = Column(Boolean, default=False)             # Si se envió mensaje por WhatsApp
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relaciones
    budget = relationship("Budget", back_populates="alerts")

class Reminder(Base):
    __tablename__ = "reminders"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # Configuración del recordatorio
    title = Column(String, nullable=False)  # "Pago de electricidad", "Revisión semanal"
    message = Column(String, nullable=False)  # Mensaje a enviar
    category = Column(String)  # Categoría relacionada (opcional)
    amount = Column(Numeric(10, 2))  # Monto estimado (opcional)
    
    # Programación
    next_trigger = Column(DateTime(timezone=True), nullable=False)
    frequency = Column(String, nullable=False)  # "daily", "weekly", "monthly", "yearly", "once"
    day_of_week = Column(String)  # Para frecuencia semanal: "monday", "friday"
    day_of_month = Column(String)  # Para frecuencia mensual: "1", "15", "last"
    
    # Estado
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_sent = Column(DateTime(timezone=True))
    
    # Relaciones
    user = relationship("User", back_populates="reminders")