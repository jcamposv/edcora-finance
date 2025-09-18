"""
CrewAI Tools for Financial Management
Properly designed tools for expense tracking, reporting, and organization management
"""

from crewai.tools import tool
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from decimal import Decimal
import json


# Global variables to store context for tools
_current_db = None
_current_user_id = None

def set_tool_context(db: Session, user_id: str):
    """Set the database session and user ID for tools to use"""
    global _current_db, _current_user_id
    _current_db = db
    _current_user_id = user_id


@tool("add_expense")
def add_expense_tool(amount: float, description: str, organization_context: str = None) -> str:
    """Add a financial expense to the system. 
    Handles organization selection intelligently and creates the transaction.
    Use this when user wants to record spending like 'Gasto 500 comida' or 'Gasté 40000 gasolina familia'."""
    
    try:
        from app.services.transaction_service import TransactionService
        from app.services.organization_service import OrganizationService
        from app.services.user_service import UserService
        from app.core.schemas import TransactionCreate
        from app.models.transaction import TransactionType
        from uuid import UUID
        
        db = _current_db
        user_id = _current_user_id
        
        if not db or not user_id:
            return "❌ Error: Database session or user ID not provided"
        
        # Get user and organizations
        user = UserService.get_user(db, user_id)
        user_organizations = OrganizationService.get_user_organizations(db, user_id)
        
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
                user_id=user_id,
                transaction_data={
                    "amount": amount,
                    "description": description,
                    "type": "expense"
                },
                available_contexts=[{"id": str(org.id), "name": org.name, "type": org.type.value} for org in user_organizations]
            )
            
            currency = "₡" if user and user.currency == "CRC" else "$"
            return f"💸 **Gasto de {currency}{amount:,.0f} en {description}**\n\n🏷️ **¿Dónde quieres registrarlo?**\n\n{org_list}\n{personal_option}\n\n📝 Responde con el número o nombre:\n• \"1\" o \"{user_organizations[0].name if user_organizations else 'Mi Hogar'}\"\n• \"Personal\""
        
        # Simple expense categorization
        def categorize_expense(description: str) -> str:
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
        
        # Create the transaction
        transaction_data = TransactionCreate(
            user_id=UUID(user_id) if isinstance(user_id, str) else user_id,
            organization_id=target_organization_id,
            amount=Decimal(str(amount)),
            type=TransactionType.expense,
            category=categorize_expense(description),
            description=description
        )
        
        transaction = TransactionService.create_transaction(db, transaction_data)
        
        currency = "₡" if user and user.currency == "CRC" else "$"
        return f"✅ **Gasto registrado**\n\n💸 {currency}{amount:,.0f} en {description}\n🏷️ Organización: {organization_name}\n📅 {transaction.date.strftime('%d/%m/%Y')}"
        
    except Exception as e:
        return f"❌ Error al registrar gasto: {str(e)}"


@tool("generate_report")
def generate_report_tool(period: str, organization: str = None) -> str:
    """Generate financial reports and summaries for different time periods and organizations.
    Use this when user asks for 'resumen', 'gastos', 'balance', 'reporte', or specific queries like 'resumen personal', 'gastos familia'."""
    
    try:
        from app.agents.report_agent import ReportAgent
        
        db = _current_db
        user_id = _current_user_id
        
        if not db or not user_id:
            return "❌ Error: Database session or user ID not provided"
        
        # Construct query message
        query_parts = ["resumen"]
        if organization:
            query_parts.append(organization)
        if period and period != "este mes":
            query_parts.append(period)
        
        query_message = " ".join(query_parts)
        
        # Use existing report agent
        report_agent = ReportAgent(db)
        if report_agent.is_report_request(query_message):
            result = report_agent.generate_report(query_message, user_id, db)
            
            if result.get("success"):
                return result["report"]
            else:
                return "❌ Error generando reporte"
        else:
            return "❌ No se pudo procesar la solicitud de reporte"
            
    except Exception as e:
        return f"❌ Error generando reporte: {str(e)}"


@tool("manage_organizations")
def manage_organizations_tool(action: str, organization_name: str = None) -> str:
    """Manage user organizations, families, and groups.
    Use this when user wants to 'crear familia', 'en qué familias estoy', 'listar organizaciones', etc."""
    
    try:
        from app.services.organization_service import OrganizationService
        from app.services.user_service import UserService
        
        db = _current_db
        user_id = _current_user_id
        
        if not db or not user_id:
            return "❌ Error: Database session or user ID not provided"
        
        if action == "list":
            # List user organizations
            organizations = OrganizationService.get_user_organizations(db, user_id)
            
            if not organizations:
                return "📝 No perteneces a ninguna organización aún.\n\n💡 Puedes crear una nueva familia diciendo:\n'Crear familia Mi Hogar'"
            
            org_list = []
            for org in organizations:
                emoji = "👨‍👩‍👧‍👦" if org.type.value == "family" else "🏢"
                role_emoji = "👑" if org.owner_id == user_id else "👤"
                org_list.append(f"{emoji} **{org.name}** {role_emoji}")
            
            return f"🏷️ **Tus organizaciones:**\n\n" + "\n".join(org_list)
        
        elif action == "create" and organization_name:
            # Create new organization
            from app.models.organization import OrganizationType
            
            organization = OrganizationService.create_organization(
                db=db,
                name=organization_name,
                created_by=user_id,
                organization_type=OrganizationType.family
            )
            
            return f"✅ **Familia creada**\n\n👨‍👩‍👧‍👦 {organization_name}\n👑 Eres el administrador\n\n💡 Ahora puedes invitar miembros o registrar gastos familiares."
        
        else:
            return "❌ Acción no válida. Usa 'list' para ver organizaciones o 'create' con un nombre para crear una nueva."
            
    except Exception as e:
        return f"❌ Error en gestión de organizaciones: {str(e)}"


# Export tools for easy access
AddExpenseTool = add_expense_tool
GenerateReportTool = generate_report_tool
OrganizationManagementTool = manage_organizations_tool