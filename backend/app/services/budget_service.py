from sqlalchemy.orm import Session
from sqlalchemy import and_, func, extract, or_
from typing import List, Optional
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID

from app.models.budget import Budget, BudgetAlert, BudgetPeriod, BudgetStatus
from app.models.transaction import Transaction, TransactionType
from app.core.schemas import BudgetCreate, BudgetUpdate, BudgetStatusResponse
from app.services.whatsapp_service import WhatsAppService

class BudgetService:
    def __init__(self, db: Session):
        self.db = db
        self.whatsapp_service = WhatsAppService()

    def create_budget(self, budget_data: BudgetCreate) -> Budget:
        """Crear un nuevo presupuesto"""
        budget = Budget(**budget_data.dict())
        self.db.add(budget)
        self.db.commit()
        self.db.refresh(budget)
        return budget

    def get_user_budgets(self, user_id: UUID, active_only: bool = True) -> List[Budget]:
        """Obtener presupuestos de un usuario"""
        query = self.db.query(Budget).filter(Budget.user_id == user_id)
        
        if active_only:
            query = query.filter(Budget.status == BudgetStatus.active)
            
        return query.order_by(Budget.created_at.desc()).all()

    def get_budget_by_id(self, budget_id: UUID) -> Optional[Budget]:
        """Obtener presupuesto por ID"""
        return self.db.query(Budget).filter(Budget.id == budget_id).first()

    def update_budget(self, budget_id: UUID, budget_update: BudgetUpdate) -> Optional[Budget]:
        """Actualizar presupuesto"""
        budget = self.get_budget_by_id(budget_id)
        if not budget:
            return None
            
        for field, value in budget_update.dict(exclude_unset=True).items():
            setattr(budget, field, value)
            
        self.db.commit()
        self.db.refresh(budget)
        return budget

    def delete_budget(self, budget_id: UUID) -> bool:
        """Eliminar presupuesto"""
        budget = self.get_budget_by_id(budget_id)
        if not budget:
            return False
            
        self.db.delete(budget)
        self.db.commit()
        return True

    def get_budget_status(self, budget_id: UUID) -> Optional[BudgetStatusResponse]:
        """Obtener estado actual de un presupuesto"""
        budget = self.get_budget_by_id(budget_id)
        if not budget:
            return None

        # Calcular gasto actual en el período del presupuesto
        spent_amount = self._calculate_spent_amount(budget)
        
        # Calcular valores derivados
        remaining_amount = budget.amount - spent_amount
        percentage_spent = (spent_amount / budget.amount * 100) if budget.amount > 0 else 0
        is_over_budget = spent_amount > budget.amount
        
        # Calcular días restantes
        days_remaining = (budget.end_date - datetime.now()).days
        if days_remaining < 0:
            days_remaining = 0

        return BudgetStatusResponse(
            budget=budget,
            spent_amount=spent_amount,
            remaining_amount=remaining_amount,
            percentage_spent=percentage_spent,
            is_over_budget=is_over_budget,
            days_remaining=days_remaining
        )

    def check_budget_alerts(self, user_id: UUID, transaction_amount: Decimal, category: str):
        """Verificar si una nueva transacción dispara alertas de presupuesto"""
        # Obtener presupuestos activos que apliquen a esta categoría
        budgets = self.db.query(Budget).filter(
            and_(
                Budget.user_id == user_id,
                Budget.status == BudgetStatus.active,
                Budget.start_date <= datetime.now(),
                Budget.end_date >= datetime.now(),
                # Flexible category matching
                or_(
                    Budget.category.ilike(f"%{category}%"),
                    Budget.category.ilike("general"),
                    Budget.category.ilike("todos")
                )
            )
        ).all()

        for budget in budgets:
            # Calcular nuevo gasto total
            current_spent = self._calculate_spent_amount(budget)
            new_spent = current_spent + transaction_amount
            new_percentage = (new_spent / budget.amount * 100) if budget.amount > 0 else 0

            # Verificar si se superó el umbral de alerta
            if new_percentage >= budget.alert_percentage:
                # Verificar si ya se envió alerta para este porcentaje
                existing_alert = self.db.query(BudgetAlert).filter(
                    and_(
                        BudgetAlert.budget_id == budget.id,
                        BudgetAlert.percentage_spent >= budget.alert_percentage
                    )
                ).first()

                if not existing_alert:
                    self._create_budget_alert(budget, new_spent, new_percentage)

    def _calculate_spent_amount(self, budget: Budget) -> Decimal:
        """Calcular monto gastado en un presupuesto"""
        query = self.db.query(func.sum(Transaction.amount)).filter(
            and_(
                Transaction.user_id == budget.user_id,
                Transaction.type == TransactionType.expense,
                Transaction.date >= budget.start_date,
                Transaction.date <= budget.end_date
            )
        )

        # Filtrar por categoría si no es presupuesto general
        if budget.category.lower() not in ["general", "todos"]:
            # Use case-insensitive and flexible category matching
            query = query.filter(Transaction.category.ilike(f"%{budget.category}%"))

        result = query.scalar()
        return result if result else Decimal("0.00")

    def _create_budget_alert(self, budget: Budget, spent_amount: Decimal, percentage_spent: Decimal):
        """Crear alerta de presupuesto y enviar por WhatsApp"""
        # Crear registro de alerta
        alert = BudgetAlert(
            budget_id=budget.id,
            percentage_spent=percentage_spent,
            amount_spent=spent_amount,
            message_sent=False
        )
        self.db.add(alert)

        # Obtener información del usuario para moneda
        from app.models.user import User
        user = self.db.query(User).filter(User.id == budget.user_id).first()
        currency_symbol = "₡" if user and user.currency == "CRC" else "$"

        # Preparar mensaje para WhatsApp
        if percentage_spent >= 100:
            emoji = "🚨"
            status = "LÍMITE SUPERADO"
            over_amount = spent_amount - budget.amount
            message = f"{emoji} **{status}**\n\n"
            message += f"💸 Gastado: {currency_symbol}{spent_amount:,.0f}\n"
            message += f"💰 Límite: {currency_symbol}{budget.amount:,.0f}\n"
            message += f"❌ Excedido: {currency_symbol}{over_amount:,.0f}\n\n"
            message += f"📊 Presupuesto: {budget.category}"
        else:
            emoji = "⚠️"
            status = "ALERTA DE PRESUPUESTO"
            remaining = budget.amount - spent_amount
            message = f"{emoji} **{status}**\n\n"
            message += f"💸 Gastado: {currency_symbol}{spent_amount:,.0f} ({percentage_spent:.0f}%)\n"
            message += f"💰 Límite: {currency_symbol}{budget.amount:,.0f}\n"
            message += f"✅ Disponible: {currency_symbol}{remaining:,.0f}\n\n"
            message += f"📊 Presupuesto: {budget.category}"

        # Enviar mensaje por WhatsApp
        try:
            if user:
                self.whatsapp_service.send_message(user.phone_number, message)
                alert.message_sent = True
        except Exception as e:
            print(f"Error enviando alerta de presupuesto: {e}")

        self.db.commit()

    def get_budget_by_category(self, user_id: UUID, category: str) -> Optional[Budget]:
        """Obtener presupuesto activo por categoría"""
        return self.db.query(Budget).filter(
            and_(
                Budget.user_id == user_id,
                Budget.category == category,
                Budget.status == BudgetStatus.active,
                Budget.start_date <= datetime.now(),
                Budget.end_date >= datetime.now()
            )
        ).first()

    def create_monthly_budget(self, user_id: UUID, category: str, amount: Decimal, name: str = None) -> Budget:
        """Crear presupuesto mensual (helper para WhatsApp)"""
        now = datetime.now()
        start_date = datetime(now.year, now.month, 1)
        
        # Calcular último día del mes
        if now.month == 12:
            end_date = datetime(now.year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = datetime(now.year, now.month + 1, 1) - timedelta(days=1)
        
        # Establecer hora al final del día
        end_date = end_date.replace(hour=23, minute=59, second=59)

        budget_data = BudgetCreate(
            user_id=user_id,
            name=name or f"{category.title()} - {now.strftime('%B %Y')}",
            category=category,
            amount=amount,
            period=BudgetPeriod.monthly,
            start_date=start_date,
            end_date=end_date
        )

        return self.create_budget(budget_data)

    def auto_renew_budgets(self):
        """Renovar automáticamente presupuestos que han expirado"""
        expired_budgets = self.db.query(Budget).filter(
            and_(
                Budget.auto_renew == True,
                Budget.status == BudgetStatus.active,
                Budget.end_date < datetime.now()
            )
        ).all()

        for budget in expired_budgets:
            # Marcar presupuesto actual como completado
            budget.status = BudgetStatus.completed
            
            # Crear nuevo presupuesto para el siguiente período
            if budget.period == BudgetPeriod.monthly:
                new_start = budget.end_date + timedelta(days=1)
                new_end = new_start.replace(day=1) + timedelta(days=32)
                new_end = new_end.replace(day=1) - timedelta(days=1)
                new_end = new_end.replace(hour=23, minute=59, second=59)
            elif budget.period == BudgetPeriod.weekly:
                new_start = budget.end_date + timedelta(days=1)
                new_end = new_start + timedelta(days=6)
                new_end = new_end.replace(hour=23, minute=59, second=59)
            else:  # yearly
                new_start = budget.end_date + timedelta(days=1)
                new_end = new_start.replace(year=new_start.year + 1) - timedelta(days=1)
                new_end = new_end.replace(hour=23, minute=59, second=59)

            new_budget = Budget(
                user_id=budget.user_id,
                name=f"{budget.name.split(' - ')[0]} - {new_start.strftime('%B %Y') if budget.period == BudgetPeriod.monthly else new_start.strftime('%Y')}",
                category=budget.category,
                amount=budget.amount,
                period=budget.period,
                start_date=new_start,
                end_date=new_end,
                alert_percentage=budget.alert_percentage,
                auto_renew=budget.auto_renew,
                status=BudgetStatus.active
            )
            
            self.db.add(new_budget)

        self.db.commit()