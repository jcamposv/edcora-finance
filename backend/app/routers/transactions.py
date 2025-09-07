from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date

from app.core.database import get_db
from app.core.schemas import Transaction, TransactionCreate, TransactionUpdate
from app.models.transaction import TransactionType
from app.services.transaction_service import TransactionService
from app.services.user_service import UserService

router = APIRouter(prefix="/transactions", tags=["transactions"])

@router.post("/", response_model=Transaction)
def create_transaction(transaction: TransactionCreate, db: Session = Depends(get_db)):
    # Check if user can add more transactions
    if not UserService.can_add_transaction(db, str(transaction.user_id)):
        raise HTTPException(
            status_code=403, 
            detail="Transaction limit reached for free plan. Upgrade to premium for unlimited transactions."
        )
    
    return TransactionService.create_transaction(db=db, transaction=transaction)

@router.get("/{transaction_id}", response_model=Transaction)
def read_transaction(transaction_id: str, db: Session = Depends(get_db)):
    db_transaction = TransactionService.get_transaction(db, transaction_id=transaction_id)
    if db_transaction is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return db_transaction

@router.get("/user/{user_id}", response_model=List[Transaction])
def read_user_transactions(
    user_id: str,
    skip: int = 0,
    limit: int = 100,
    category: Optional[str] = Query(None),
    transaction_type: Optional[TransactionType] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    db: Session = Depends(get_db)
):
    return TransactionService.get_user_transactions(
        db, user_id=user_id, skip=skip, limit=limit,
        category=category, transaction_type=transaction_type,
        start_date=start_date, end_date=end_date
    )

@router.put("/{transaction_id}", response_model=Transaction)
def update_transaction(transaction_id: str, transaction: TransactionUpdate, db: Session = Depends(get_db)):
    db_transaction = TransactionService.update_transaction(db, transaction_id=transaction_id, transaction_update=transaction)
    if db_transaction is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return db_transaction

@router.delete("/{transaction_id}")
def delete_transaction(transaction_id: str, db: Session = Depends(get_db)):
    if not TransactionService.delete_transaction(db, transaction_id=transaction_id):
        raise HTTPException(status_code=404, detail="Transaction not found")
    return {"message": "Transaction deleted successfully"}

@router.get("/user/{user_id}/balance")
def get_user_balance(user_id: str, db: Session = Depends(get_db)):
    return TransactionService.get_user_balance(db, user_id=user_id)

@router.get("/user/{user_id}/expenses-by-category")
def get_expenses_by_category(
    user_id: str,
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    db: Session = Depends(get_db)
):
    return TransactionService.get_expenses_by_category(db, user_id=user_id, start_date=start_date, end_date=end_date)