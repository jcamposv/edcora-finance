"""
CrewAI Tools for Financial Management
Properly designed tools for expense tracking, reporting, and organization management
"""

from crewai.tools import BaseTool
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from decimal import Decimal
import json


class AddExpenseInput(BaseModel):
    """Input schema for adding expenses"""
    amount: float = Field(..., description="The expense amount")
    description: str = Field(..., description="Description of the expense")
    organization_context: Optional[str] = Field(None, description="Organization context (personal, family, empresa, etc.)")


class AddExpenseTool(BaseTool):
    """Tool for adding financial expenses with intelligent organization handling"""
    
    name: str = "add_expense"
    description: str = """Add a financial expense to the system. 
    Handles organization selection intelligently and creates the transaction.
    Use this when user wants to record spending like 'Gasto 500 comida' or 'Gasté 40000 gasolina familia'."""
    
    args_schema = AddExpenseInput
    
    def __init__(self, db: Session, user_id: str):
        super().__init__()
        self.db = db
        self.user_id = user_id
    
    def _run(self, amount: float, description: str, organization_context: Optional[str] = None) -> str:
        """Execute expense addition with smart organization handling"""
        try:
            from app.services.transaction_service import TransactionService
            from app.services.organization_service import OrganizationService
            from app.services.user_service import UserService
            from app.core.schemas import TransactionCreate
            from app.models.transaction import TransactionType
            from uuid import UUID
            
            # Get user and organizations
            user = UserService.get_user(self.db, self.user_id)
            user_organizations = OrganizationService.get_user_organizations(self.db, self.user_id)
            
            # Smart organization selection
            target_organization_id = None
            organization_name = "Personal"
            
            if organization_context:
                # Handle explicit organization context
                if organization_context.lower() in ["personal", "mío", "mio", "propio"]:
                    target_organization_id = None
                    organization_name = "Personal"
                else:
                    # Try to match organization by name
                    for org in user_organizations:
                        if organization_context.lower() in org.name.lower():
                            target_organization_id = org.id
                            organization_name = org.name
                            break
            
            # If no explicit context and user has organizations, need clarification
            if not organization_context and len(user_organizations) > 0:
                # Return request for clarification
                org_options = []
                for i, org in enumerate(user_organizations, 1):
                    emoji = "👨‍👩‍👧‍👦" if org.type.value == "family" else "🏢"
                    org_options.append(f"{i}. {emoji} {org.name}")
                
                org_list = "\n".join(org_options)
                personal_option = f"{len(user_organizations) + 1}. 👤 Personal"
                
                # Save pending transaction for follow-up
                from app.services.conversation_state import conversation_state
                conversation_state.set_pending_transaction(
                    user_id=self.user_id,
                    transaction_data={
                        "amount": amount,
                        "description": description,
                        "type": "expense"
                    },
                    available_contexts=[{"id": str(org.id), "name": org.name, "type": org.type.value} for org in user_organizations]
                )
                
                currency = "₡" if user and user.currency == "CRC" else "$"
                return f"💸 **Gasto de {currency}{amount:,.0f} en {description}**\n\n🏷️ **¿Dónde quieres registrarlo?**\n\n{org_list}\n{personal_option}\n\n📝 Responde con el número o nombre:\n• \"1\" o \"{user_organizations[0].name if user_organizations else 'Mi Hogar'}\"\n• \"Personal\""
            
            # Create the transaction
            transaction_data = TransactionCreate(
                user_id=UUID(self.user_id) if isinstance(self.user_id, str) else self.user_id,
                organization_id=target_organization_id,
                amount=Decimal(str(amount)),
                type=TransactionType.expense,
                category=self._categorize_expense(description),
                description=description
            )
            
            transaction = TransactionService.create_transaction(self.db, transaction_data)
            
            currency = "₡" if user and user.currency == "CRC" else "$"
            return f"✅ **Gasto registrado**\n\n💸 {currency}{amount:,.0f} en {description}\n🏷️ Organización: {organization_name}\n📅 {transaction.date.strftime('%d/%m/%Y')}"
            
        except Exception as e:
            return f"❌ Error al registrar gasto: {str(e)}"
    
    def _categorize_expense(self, description: str) -> str:
        """Simple expense categorization"""
        description_lower = description.lower()
        
        if any(word in description_lower for word in ["gasolina", "combustible", "gas"]):
            return "Gasolina"
        elif any(word in description_lower for word in ["comida", "almuerzo", "cena", "desayuno", "restaurant", "soda"]):
            return "Comida"
        elif any(word in description_lower for word in ["supermercado", "super", "compras"]):
            return "Supermercado"
        elif any(word in description_lower for word in ["transporte", "taxi", "uber", "bus"]):
            return "Transporte"
        else:
            return "General"


class GenerateReportInput(BaseModel):
    """Input schema for generating reports"""
    period: str = Field(..., description="Time period (hoy, esta semana, este mes, etc.)")
    organization: Optional[str] = Field(None, description="Organization filter (personal, familia, empresa)")


class GenerateReportTool(BaseTool):
    """Tool for generating financial reports and summaries"""
    
    name: str = "generate_report"
    description: str = """Generate financial reports and summaries for different time periods and organizations.
    Use this when user asks for 'resumen', 'gastos', 'balance', 'reporte', or specific queries like 'resumen personal', 'gastos familia'."""
    
    args_schema = GenerateReportInput
    
    def __init__(self, db: Session, user_id: str):
        super().__init__()
        self.db = db
        self.user_id = user_id
    
    def _run(self, period: str, organization: Optional[str] = None) -> str:
        """Generate financial report"""
        try:
            from app.agents.report_agent import ReportAgent
            
            # Construct query message
            query_parts = ["resumen"]
            if organization:
                query_parts.append(organization)
            if period and period != "este mes":
                query_parts.append(period)
            
            query_message = " ".join(query_parts)
            
            # Use existing report agent
            report_agent = ReportAgent()
            if report_agent.is_report_request(query_message):
                result = report_agent.generate_report(query_message, self.user_id, self.db)
                
                if result.get("success"):
                    return result["report"]
                else:
                    return "❌ Error generando reporte"
            else:
                return "❌ No se pudo procesar la solicitud de reporte"
                
        except Exception as e:
            return f"❌ Error generando reporte: {str(e)}"


class OrganizationManagementInput(BaseModel):
    """Input schema for organization management"""
    action: str = Field(..., description="Action to perform (list, create, join)")
    organization_name: Optional[str] = Field(None, description="Organization name for create action")


class OrganizationManagementTool(BaseTool):
    """Tool for managing organizations and family groups"""
    
    name: str = "manage_organizations"
    description: str = """Manage user organizations, families, and groups.
    Use this when user wants to 'crear familia', 'en qué familias estoy', 'listar organizaciones', etc."""
    
    args_schema = OrganizationManagementInput
    
    def __init__(self, db: Session, user_id: str):
        super().__init__()
        self.db = db
        self.user_id = user_id
    
    def _run(self, action: str, organization_name: Optional[str] = None) -> str:
        """Execute organization management action"""
        try:
            from app.services.organization_service import OrganizationService
            from app.services.user_service import UserService
            
            if action == "list":
                # List user organizations
                organizations = OrganizationService.get_user_organizations(self.db, self.user_id)
                
                if not organizations:
                    return "📝 No perteneces a ninguna organización aún.\n\n💡 Puedes crear una nueva familia diciendo:\n'Crear familia Mi Hogar'"
                
                org_list = []
                for org in organizations:
                    emoji = "👨‍👩‍👧‍👦" if org.type.value == "family" else "🏢"
                    role_emoji = "👑" if org.owner_id == self.user_id else "👤"
                    org_list.append(f"{emoji} **{org.name}** {role_emoji}")
                
                return f"🏷️ **Tus organizaciones:**\n\n" + "\n".join(org_list)
            
            elif action == "create" and organization_name:
                # Create new organization
                from app.models.organization import OrganizationType
                
                organization = OrganizationService.create_organization(
                    db=self.db,
                    name=organization_name,
                    created_by=self.user_id,
                    organization_type=OrganizationType.family
                )
                
                return f"✅ **Familia creada**\n\n👨‍👩‍👧‍👦 {organization_name}\n👑 Eres el administrador\n\n💡 Ahora puedes invitar miembros o registrar gastos familiares."
            
            else:
                return "❌ Acción no válida. Usa 'list' para ver organizaciones o 'create' con un nombre para crear una nueva."
                
        except Exception as e:
            return f"❌ Error en gestión de organizaciones: {str(e)}"