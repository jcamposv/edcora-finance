from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from app.models.transaction import Transaction, TransactionType
from app.core.schemas import TransactionCreate, TransactionUpdate
from datetime import datetime, date
from typing import Optional, List
from decimal import Decimal

class TransactionService:
    @staticmethod
    def create_transaction(db: Session, transaction: TransactionCreate) -> Transaction:
        db_transaction = Transaction(**transaction.dict())
        db.add(db_transaction)
        db.commit()
        db.refresh(db_transaction)
        
        # Verificar alertas de presupuesto para gastos
        if db_transaction.type == TransactionType.expense:
            from app.services.budget_service import BudgetService
            budget_service = BudgetService(db)
            budget_service.check_budget_alerts(
                user_id=db_transaction.user_id,
                transaction_amount=db_transaction.amount,
                category=db_transaction.category
            )
        
        return db_transaction

    @staticmethod
    def get_transaction(db: Session, transaction_id: str) -> Optional[Transaction]:
        return db.query(Transaction).filter(Transaction.id == transaction_id).first()

    @staticmethod
    def get_user_transactions(
        db: Session, 
        user_id: str, 
        skip: int = 0, 
        limit: int = 100,
        category: Optional[str] = None,
        transaction_type: Optional[TransactionType] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> List[Transaction]:
        query = db.query(Transaction).filter(Transaction.user_id == user_id)
        
        if category:
            query = query.filter(Transaction.category == category)
        if transaction_type:
            query = query.filter(Transaction.type == transaction_type)
        if start_date:
            query = query.filter(Transaction.date >= start_date)
        if end_date:
            query = query.filter(Transaction.date <= end_date)
            
        return query.order_by(Transaction.date.desc()).offset(skip).limit(limit).all()

    @staticmethod
    def update_transaction(db: Session, transaction_id: str, transaction_update: TransactionUpdate) -> Optional[Transaction]:
        db_transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
        if db_transaction:
            update_data = transaction_update.dict(exclude_unset=True)
            for key, value in update_data.items():
                setattr(db_transaction, key, value)
            db.commit()
            db.refresh(db_transaction)
        return db_transaction

    @staticmethod
    def delete_transaction(db: Session, transaction_id: str) -> bool:
        db_transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
        if db_transaction:
            db.delete(db_transaction)
            db.commit()
            return True
        return False

    @staticmethod
    def get_user_balance(db: Session, user_id: str) -> dict:
        income_sum = db.query(func.coalesce(func.sum(Transaction.amount), 0)).filter(
            and_(Transaction.user_id == user_id, Transaction.type == TransactionType.income)
        ).scalar()
        
        expense_sum = db.query(func.coalesce(func.sum(Transaction.amount), 0)).filter(
            and_(Transaction.user_id == user_id, Transaction.type == TransactionType.expense)
        ).scalar()
        
        return {
            "income": float(income_sum),
            "expenses": float(expense_sum),
            "balance": float(income_sum - expense_sum)
        }
    
    @staticmethod
    def get_transactions_by_date_range(db: Session, user_id: str, start_date: date, end_date: date) -> List[Transaction]:
        """Get all transactions for a user within a specific date range."""
        # Convert dates to datetime for proper comparison with timezone-aware DateTime column
        from datetime import datetime, time
        
        start_datetime = datetime.combine(start_date, time.min)  # 00:00:00
        end_datetime = datetime.combine(end_date, time.max)      # 23:59:59.999999
        
        print(f"DEBUG: Searching with datetime range: {start_datetime} to {end_datetime}")
        
        transactions = db.query(Transaction).filter(
            and_(
                Transaction.user_id == user_id,
                Transaction.date >= start_datetime,
                Transaction.date <= end_datetime
            )
        ).order_by(Transaction.date.desc()).all()
        
        print(f"DEBUG: Query returned {len(transactions)} transactions")
        return transactions

    @staticmethod
    def get_expenses_by_category(db: Session, user_id: str, start_date: Optional[date] = None, end_date: Optional[date] = None) -> List[dict]:
        query = db.query(
            Transaction.category,
            func.sum(Transaction.amount).label('total')
        ).filter(
            and_(Transaction.user_id == user_id, Transaction.type == TransactionType.expense)
        )
        
        if start_date:
            query = query.filter(Transaction.date >= start_date)
        if end_date:
            query = query.filter(Transaction.date <= end_date)
            
        result = query.group_by(Transaction.category).all()
        
        return [{"category": cat, "amount": float(total)} for cat, total in result]
    
    @staticmethod
    def can_user_create_transaction(db: Session, user_id: str) -> bool:
        """Check if user has permission to create transactions (individual or organization)."""
        # For individual transactions, users can always create their own
        # For organization contexts, check if user has member+ role
        from app.models.organization import OrganizationMember, OrganizationRole
        
        user_memberships = db.query(OrganizationMember).filter(
            OrganizationMember.user_id == user_id,
            OrganizationMember.is_active == True
        ).all()
        
        # If user has no organizations, they can create individual transactions
        if not user_memberships:
            return True
        
        # If user is a member+ in at least one organization, they can create transactions
        for membership in user_memberships:
            if membership.role in [OrganizationRole.owner, OrganizationRole.admin, OrganizationRole.manager, OrganizationRole.member]:
                return True
        
        return False  # Only viewers cannot create transactions