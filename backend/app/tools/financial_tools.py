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
            context_lower = organization_context.lower().strip()
            
            # Handle explicit "personal" keywords
            if context_lower in ["personal", "mío", "mio", "propio"]:
                target_organization_id = None
                organization_name = "Personal"
            else:
                # Search user's organizations by name or type (same logic as income)
                found_org = None
                
                # First, try exact name match (case insensitive)
                for org in user_organizations:
                    if org.name.lower() == context_lower:
                        found_org = org
                        break
                
                # If not found, try partial name match
                if not found_org:
                    for org in user_organizations:
                        if context_lower in org.name.lower() or org.name.lower() in context_lower:
                            found_org = org
                            break
                
                # If still not found, try by type
                if not found_org:
                    if context_lower in ["familia", "familiar", "family"]:
                        # Look for family type organization
                        family_orgs = [org for org in user_organizations if org.type == "family"]
                        if family_orgs:
                            found_org = family_orgs[0]  # Take first family org
                
                if found_org:
                    target_organization_id = found_org.id
                    organization_name = found_org.name
                else:
                    # Organization not found - ask user to choose
                    if user_organizations:
                        available_contexts = []
                        for org in user_organizations:
                            org_type = org.type if hasattr(org, 'type') else "organization"
                            available_contexts.append({
                                "id": str(org.id),
                                "name": org.name,
                                "type": org_type
                            })
                        
                        # Store pending transaction for organization selection
                        from app.services.conversation_state import conversation_state
                        conversation_state.set_pending_transaction(user_id, {
                            "transaction_data": {
                                "amount": amount,
                                "description": description,
                                "type": "expense"
                            },
                            "available_contexts": available_contexts
                        })
                        
                        # Build organization options
                        org_options = []
                        for i, org in enumerate(available_contexts, 1):
                            emoji = "👨‍👩‍👧‍👦" if org["type"] == "family" else "🏢"
                            org_options.append(f"{i}. {emoji} {org['name']}")
                        
                        org_list = "\n".join(org_options)
                        personal_option = f"{len(available_contexts) + 1}. 👤 Personal"
                        
                        return f"🤔 No encontré la organización '{organization_context}'\n\n🏷️ **¿Dónde registrar el gasto?**\n\n{org_list}\n{personal_option}\n\n📝 Responde con el número:"
        
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


@tool("add_income")
def add_income_tool(amount: float, description: str, organization_context: str = None) -> str:
    """Add a financial income to the system. 
    Handles organization selection intelligently and creates the income transaction.
    Use this when user wants to record income like 'ingreso 60000' or 'salario 150000 personal'."""
    
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
            context_lower = organization_context.lower().strip()
            
            # Handle explicit "personal" keywords
            if context_lower in ["personal", "mío", "mio", "propio"]:
                target_organization_id = None
                organization_name = "Personal"
            else:
                # Search user's organizations by name or type
                found_org = None
                
                # First, try exact name match (case insensitive)
                for org in user_organizations:
                    if org.name.lower() == context_lower:
                        found_org = org
                        break
                
                # If not found, try partial name match
                if not found_org:
                    for org in user_organizations:
                        if context_lower in org.name.lower() or org.name.lower() in context_lower:
                            found_org = org
                            break
                
                # If still not found, try by type
                if not found_org:
                    if context_lower in ["familia", "familiar", "family"]:
                        # Look for family type organization
                        family_orgs = [org for org in user_organizations if org.type == "family"]
                        if family_orgs:
                            found_org = family_orgs[0]  # Take first family org
                
                if found_org:
                    target_organization_id = found_org.id
                    organization_name = found_org.name
                else:
                    # Organization not found - ask user to choose
                    if user_organizations:
                        available_contexts = []
                        for org in user_organizations:
                            org_type = org.type if hasattr(org, 'type') else "organization"
                            available_contexts.append({
                                "id": str(org.id),
                                "name": org.name,
                                "type": org_type
                            })
                        
                        # Store pending transaction for organization selection
                        from app.services.conversation_state import conversation_state
                        conversation_state.set_pending_transaction(user_id, {
                            "transaction_data": {
                                "amount": amount,
                                "description": description,
                                "type": "income"
                            },
                            "available_contexts": available_contexts
                        })
                        
                        # Build organization options
                        org_options = []
                        for i, org in enumerate(available_contexts, 1):
                            emoji = "👨‍👩‍👧‍👦" if org["type"] == "family" else "🏢"
                            org_options.append(f"{i}. {emoji} {org['name']}")
                        
                        org_list = "\n".join(org_options)
                        personal_option = f"{len(available_contexts) + 1}. 👤 Personal"
                        
                        return f"🤔 No encontré la organización '{organization_context}'\n\n🏷️ **¿Dónde registrar el ingreso?**\n\n{org_list}\n{personal_option}\n\n📝 Responde con el número:"
        else:
            # No organization context provided - need to ask user
            if user_organizations:
                available_contexts = []
                for org in user_organizations:
                    org_type = org.type if hasattr(org, 'type') else "organization"
                    available_contexts.append({
                        "id": str(org.id),
                        "name": org.name,
                        "type": org_type
                    })
                
                # Store pending transaction for organization selection
                from app.services.conversation_state import conversation_state
                conversation_state.set_pending_transaction(user_id, {
                    "transaction_data": {
                        "amount": amount,
                        "description": description,
                        "type": "income"
                    },
                    "available_contexts": available_contexts
                })
                
                # Ask user for organization selection
                org_options = []
                for i, org in enumerate(available_contexts, 1):
                    emoji = "👨‍👩‍👧‍👦" if org["type"] == "family" else "🏢"
                    org_options.append(f"{i}. {emoji} {org['name']}")
                
                org_list = "\n".join(org_options)
                personal_option = f"{len(available_contexts) + 1}. 👤 Personal"
                
                return f"🏷️ **¿Dónde registrar el ingreso?**\n\n{org_list}\n{personal_option}\n\n📝 Responde con el número:"
        
        # Simple income categorization
        def categorize_income(description: str) -> str:
            description_lower = description.lower()
            if any(word in description_lower for word in ["salario", "sueldo", "trabajo"]):
                return "Salario"
            elif any(word in description_lower for word in ["freelance", "proyecto", "consultoría"]):
                return "Freelance"
            elif any(word in description_lower for word in ["dividendos", "intereses", "inversión"]):
                return "Inversiones"
            elif any(word in description_lower for word in ["ventas", "venta", "vendí"]):
                return "Ventas"
            elif any(word in description_lower for word in ["regalo", "regalos"]):
                return "Regalos"
            else:
                return "Otros Ingresos"
        
        # Create the transaction
        transaction_data = TransactionCreate(
            user_id=UUID(user_id) if isinstance(user_id, str) else user_id,
            organization_id=target_organization_id,
            amount=Decimal(str(amount)),
            type=TransactionType.income,
            category=categorize_income(description),
            description=description
        )
        
        transaction = TransactionService.create_transaction(db, transaction_data)
        
        currency = "₡" if user and user.currency == "CRC" else "$"
        return f"✅ **Ingreso registrado**\n\n💰 {currency}{amount:,.0f} en {description}\n🏷️ Organización: {organization_name}\n📅 {transaction.date.strftime('%d/%m/%Y')}"
        
    except Exception as e:
        return f"❌ Error al registrar ingreso: {str(e)}"


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
        
        # Check if user has organizations and no organization specified
        if not organization:
            from app.services.organization_service import OrganizationService
            user_organizations = OrganizationService.get_user_organizations(db, user_id)
            
            if user_organizations:
                # Ask user which type of report they want
                org_options = []
                org_options.append("1. 👤 Personal")
                
                family_orgs = [org for org in user_organizations if org.type == "family"]
                if family_orgs:
                    org_options.append("2. 👨‍👩‍👧‍👦 Familia")
                
                # Add specific organizations
                for i, org in enumerate(user_organizations, 3):
                    emoji = "👨‍👩‍👧‍👦" if org.type == "family" else "🏢"
                    org_options.append(f"{i}. {emoji} {org.name}")
                
                org_list = "\n".join(org_options)
                return f"📊 **¿Qué tipo de resumen quieres?**\n\n{org_list}\n\n📝 Responde con el número o tipo:"
        
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
def manage_organizations_tool(action: str, organization_name: Optional[str] = None) -> str:
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
                org_type = org.type if hasattr(org, 'type') else "organization"
                if hasattr(org_type, 'value'):
                    org_type = org_type.value
                emoji = "👨‍👩‍👧‍👦" if org_type == "family" else "🏢"
                role_emoji = "👑" if str(org.owner_id) == str(user_id) else "👤"
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