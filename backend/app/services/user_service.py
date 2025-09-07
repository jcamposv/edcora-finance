from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.user import User
from app.models.transaction import Transaction, TransactionType
from app.core.schemas import UserCreate, UserUpdate
from datetime import datetime, timedelta
from typing import Optional

class UserService:
    @staticmethod
    def create_user(db: Session, user: UserCreate) -> User:
        db_user = User(**user.dict())
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        return db_user

    @staticmethod
    def get_user_by_phone(db: Session, phone_number: str) -> Optional[User]:
        return db.query(User).filter(User.phone_number == phone_number).first()

    @staticmethod
    def get_user(db: Session, user_id: str) -> Optional[User]:
        return db.query(User).filter(User.id == user_id).first()

    @staticmethod
    def update_user(db: Session, user_id: str, user_update: UserUpdate) -> Optional[User]:
        db_user = db.query(User).filter(User.id == user_id).first()
        if db_user:
            update_data = user_update.dict(exclude_unset=True)
            for key, value in update_data.items():
                setattr(db_user, key, value)
            db.commit()
            db.refresh(db_user)
        return db_user

    @staticmethod
    def get_user_transaction_count_this_month(db: Session, user_id: str) -> int:
        start_of_month = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end_of_month = (start_of_month + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        
        return db.query(Transaction).filter(
            Transaction.user_id == user_id,
            Transaction.date >= start_of_month,
            Transaction.date <= end_of_month
        ).count()

    @staticmethod
    def can_add_transaction(db: Session, user_id: str) -> bool:
        user = UserService.get_user(db, user_id)
        if user.plan_type == "premium":
            return True
        
        count = UserService.get_user_transaction_count_this_month(db, user_id)
        return count < 50