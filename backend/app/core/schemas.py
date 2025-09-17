from pydantic import BaseModel, validator
from typing import Optional, List
from datetime import datetime, date
from decimal import Decimal
from uuid import UUID
from app.models.transaction import TransactionType
from app.models.family import FamilyRole
from app.models.organization import OrganizationType, OrganizationRole
from app.models.budget import BudgetPeriod, BudgetStatus

class UserBase(BaseModel):
    phone_number: str
    name: str
    currency: str = "CRC"
    plan_type: str = "free"

class UserCreate(UserBase):
    pass

class UserUpdate(BaseModel):
    name: Optional[str] = None
    currency: Optional[str] = None
    plan_type: Optional[str] = None

class User(UserBase):
    id: UUID
    created_at: datetime
    
    class Config:
        from_attributes = True

class TransactionBase(BaseModel):
    amount: Decimal
    type: TransactionType
    category: str
    description: Optional[str] = None

class TransactionCreate(TransactionBase):
    user_id: UUID
    organization_id: Optional[UUID] = None  # NULL = personal, UUID = organization transaction

class TransactionUpdate(BaseModel):
    amount: Optional[Decimal] = None
    type: Optional[TransactionType] = None
    category: Optional[str] = None
    description: Optional[str] = None

class Transaction(TransactionBase):
    id: UUID
    user_id: UUID
    organization_id: Optional[UUID] = None
    date: datetime
    
    class Config:
        from_attributes = True

class ReportBase(BaseModel):
    period: str
    start_date: date
    end_date: date
    summary: dict

class ReportCreate(ReportBase):
    user_id: UUID

class Report(ReportBase):
    id: UUID
    user_id: UUID
    created_at: datetime
    
    class Config:
        from_attributes = True

class WhatsAppMessage(BaseModel):
    From: str
    Body: str
    
class OTPRequest(BaseModel):
    phone_number: str

class OTPVerify(BaseModel):
    phone_number: str
    code: str

# Family Schemas
class FamilyBase(BaseModel):
    name: str
    shared_budget: bool = True
    currency: str = "USD"

class FamilyCreate(FamilyBase):
    pass

class FamilyUpdate(BaseModel):
    name: Optional[str] = None
    shared_budget: Optional[bool] = None
    currency: Optional[str] = None

class Family(FamilyBase):
    id: UUID
    created_by: UUID
    created_at: datetime
    
    class Config:
        from_attributes = True

class FamilyMemberBase(BaseModel):
    role: FamilyRole = FamilyRole.member
    nickname: Optional[str] = None

class FamilyMemberCreate(FamilyMemberBase):
    family_id: UUID
    user_id: UUID

class FamilyMemberUpdate(BaseModel):
    role: Optional[FamilyRole] = None
    nickname: Optional[str] = None

class FamilyMember(FamilyMemberBase):
    id: UUID
    family_id: UUID
    user_id: UUID
    is_active: bool
    joined_at: datetime
    
    class Config:
        from_attributes = True

class FamilyInvitationBase(BaseModel):
    invited_phone: str
    role: FamilyRole = FamilyRole.member
    message: Optional[str] = None

class FamilyInvitationCreate(FamilyInvitationBase):
    family_id: UUID

class FamilyInvitation(FamilyInvitationBase):
    id: UUID
    family_id: UUID
    invited_by: UUID
    is_accepted: bool
    is_expired: bool
    created_at: datetime
    accepted_at: Optional[datetime] = None
    expires_at: datetime
    
    class Config:
        from_attributes = True


# Organization Schemas
class OrganizationBase(BaseModel):
    name: str
    type: OrganizationType
    currency: str = "USD"
    plan_type: str = "free"

class OrganizationCreate(OrganizationBase):
    parent_id: Optional[UUID] = None

class OrganizationUpdate(BaseModel):
    name: Optional[str] = None
    currency: Optional[str] = None
    plan_type: Optional[str] = None
    settings: Optional[dict] = None

class Organization(OrganizationBase):
    id: UUID
    parent_id: Optional[UUID] = None
    owner_id: UUID
    settings: dict
    created_at: datetime
    updated_at: datetime
    is_active: bool
    
    class Config:
        from_attributes = True

class OrganizationMemberBase(BaseModel):
    role: OrganizationRole = OrganizationRole.member
    department: Optional[str] = None
    nickname: Optional[str] = None

class OrganizationMemberCreate(OrganizationMemberBase):
    organization_id: UUID
    user_id: UUID

class OrganizationMemberUpdate(BaseModel):
    role: Optional[OrganizationRole] = None
    department: Optional[str] = None
    nickname: Optional[str] = None
    permissions: Optional[dict] = None

class OrganizationMember(OrganizationMemberBase):
    id: UUID
    organization_id: UUID
    user_id: UUID
    permissions: dict
    joined_at: datetime
    is_active: bool
    
    class Config:
        from_attributes = True

class OrganizationInvitationBase(BaseModel):
    invited_phone: str
    role: OrganizationRole = OrganizationRole.member
    message: Optional[str] = None

class OrganizationInvitationCreate(OrganizationInvitationBase):
    organization_id: UUID

class OrganizationInvitation(OrganizationInvitationBase):
    id: UUID
    organization_id: UUID
    invited_by: UUID
    expires_at: datetime
    created_at: datetime
    accepted_at: Optional[datetime] = None
    accepted_by: Optional[UUID] = None
    is_active: bool
    
    class Config:
        from_attributes = True

# Budget Schemas
class BudgetBase(BaseModel):
    name: str
    category: str
    amount: Decimal
    period: BudgetPeriod = BudgetPeriod.monthly
    alert_percentage: Decimal = Decimal("80.0")
    auto_renew: bool = False

class BudgetCreate(BudgetBase):
    user_id: UUID
    start_date: datetime
    end_date: datetime

class BudgetUpdate(BaseModel):
    name: Optional[str] = None
    amount: Optional[Decimal] = None
    alert_percentage: Optional[Decimal] = None
    status: Optional[BudgetStatus] = None
    auto_renew: Optional[bool] = None

class Budget(BudgetBase):
    id: UUID
    user_id: UUID
    start_date: datetime
    end_date: datetime
    status: BudgetStatus
    created_at: datetime
    
    class Config:
        from_attributes = True

class BudgetAlert(BaseModel):
    id: UUID
    budget_id: UUID
    percentage_spent: Decimal
    amount_spent: Decimal
    message_sent: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

class BudgetStatusResponse(BaseModel):
    budget: Budget
    spent_amount: Decimal
    remaining_amount: Decimal
    percentage_spent: Decimal
    is_over_budget: bool
    days_remaining: int

# Reminder Schemas
class ReminderBase(BaseModel):
    title: str
    message: str
    category: Optional[str] = None
    amount: Optional[Decimal] = None
    frequency: str
    day_of_week: Optional[str] = None
    day_of_month: Optional[str] = None

class ReminderCreate(ReminderBase):
    user_id: UUID
    next_trigger: datetime

class ReminderUpdate(BaseModel):
    title: Optional[str] = None
    message: Optional[str] = None
    next_trigger: Optional[datetime] = None
    frequency: Optional[str] = None
    day_of_week: Optional[str] = None
    day_of_month: Optional[str] = None
    is_active: Optional[bool] = None

class Reminder(ReminderBase):
    id: UUID
    user_id: UUID
    next_trigger: datetime
    is_active: bool
    created_at: datetime
    last_sent: Optional[datetime] = None
    
    class Config:
        from_attributes = True