from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app.core.database import get_db
from app.core.schemas import (
    Budget, BudgetCreate, BudgetUpdate, BudgetStatusResponse,
    BudgetAlert
)
from app.services.budget_service import BudgetService

router = APIRouter(prefix="/budgets", tags=["budgets"])

def get_budget_service(db: Session = Depends(get_db)) -> BudgetService:
    return BudgetService(db)

@router.post("/", response_model=Budget)
def create_budget(
    budget: BudgetCreate,
    budget_service: BudgetService = Depends(get_budget_service)
):
    """Crear un nuevo presupuesto"""
    return budget_service.create_budget(budget)

@router.get("/user/{user_id}", response_model=List[Budget])
def get_user_budgets(
    user_id: UUID,
    active_only: bool = True,
    budget_service: BudgetService = Depends(get_budget_service)
):
    """Obtener presupuestos de un usuario"""
    return budget_service.get_user_budgets(user_id, active_only)

@router.get("/{budget_id}", response_model=Budget)
def get_budget(
    budget_id: UUID,
    budget_service: BudgetService = Depends(get_budget_service)
):
    """Obtener presupuesto por ID"""
    budget = budget_service.get_budget_by_id(budget_id)
    if not budget:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Presupuesto no encontrado"
        )
    return budget

@router.put("/{budget_id}", response_model=Budget)
def update_budget(
    budget_id: UUID,
    budget_update: BudgetUpdate,
    budget_service: BudgetService = Depends(get_budget_service)
):
    """Actualizar presupuesto"""
    budget = budget_service.update_budget(budget_id, budget_update)
    if not budget:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Presupuesto no encontrado"
        )
    return budget

@router.delete("/{budget_id}")
def delete_budget(
    budget_id: UUID,
    budget_service: BudgetService = Depends(get_budget_service)
):
    """Eliminar presupuesto"""
    success = budget_service.delete_budget(budget_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Presupuesto no encontrado"
        )
    return {"message": "Presupuesto eliminado exitosamente"}

@router.get("/{budget_id}/status", response_model=BudgetStatusResponse)
def get_budget_status(
    budget_id: UUID,
    budget_service: BudgetService = Depends(get_budget_service)
):
    """Obtener estado actual de un presupuesto"""
    status_info = budget_service.get_budget_status(budget_id)
    if not status_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Presupuesto no encontrado"
        )
    return status_info

@router.get("/user/{user_id}/category/{category}", response_model=Budget)
def get_budget_by_category(
    user_id: UUID,
    category: str,
    budget_service: BudgetService = Depends(get_budget_service)
):
    """Obtener presupuesto activo por categoría"""
    budget = budget_service.get_budget_by_category(user_id, category)
    if not budget:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No hay presupuesto activo para la categoría {category}"
        )
    return budget

@router.post("/user/{user_id}/monthly", response_model=Budget)
def create_monthly_budget(
    user_id: UUID,
    category: str,
    amount: float,
    name: str = None,
    budget_service: BudgetService = Depends(get_budget_service)
):
    """Crear presupuesto mensual rápido (para WhatsApp)"""
    from decimal import Decimal
    
    # Verificar si ya existe presupuesto activo para esta categoría
    existing = budget_service.get_budget_by_category(user_id, category)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ya existe un presupuesto activo para {category}"
        )
    
    return budget_service.create_monthly_budget(
        user_id=user_id,
        category=category,
        amount=Decimal(str(amount)),
        name=name
    )