from pydantic import BaseModel, validator
from typing import Optional, List
from datetime import datetime, date
from decimal import Decimal
from uuid import UUID
from app.models.transaction import TransactionType

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