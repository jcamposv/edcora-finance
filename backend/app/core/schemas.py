from pydantic import BaseModel, validator
from typing import Optional, List
from datetime import datetime, date
from decimal import Decimal
from uuid import UUID
from app.models.transaction import TransactionType
from app.models.family import FamilyRole

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

class TransactionUpdate(BaseModel):
    amount: Optional[Decimal] = None
    type: Optional[TransactionType] = None
    category: Optional[str] = None
    description: Optional[str] = None

class Transaction(TransactionBase):
    id: UUID
    user_id: UUID
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