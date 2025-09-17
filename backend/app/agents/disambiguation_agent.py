from typing import Dict, Any, List
from sqlalchemy.orm import Session

class DisambiguationAgent:
    """Agent that handles ambiguous commands and asks for clarification"""
    
    def handle_ambiguous_create(self, message: str, user_id: str, db: Session) -> Dict[str, Any]:
        """Handle ambiguous 'crear' commands"""
        message_lower = message.lower().strip()
        
        # Check what they want to create
        if "crear" in message_lower:
            # Extract what comes after "crear"
            words = message.split()
            crear_index = -1
            for i, word in enumerate(words):
                if "crear" in word.lower():
                    crear_index = i
                    break
            
            if crear_index >= 0 and crear_index + 1 < len(words):
                next_word = words[crear_index + 1].lower()
                
                # Handle specific cases
                if "presupuesto" in next_word:
                    return self._handle_budget_creation_start(message, user_id, db)
                elif next_word in ["familia", "empresa", "equipo", "organizacion", "organización"]:
                    return self._handle_organization_creation_start(message, user_id, db)
            
            # Generic "crear" - ask what they want to create
            return {
                "success": False,
                "message": "🤔 ¿Qué quieres crear?\n\n📊 **Presupuesto** - 'crear presupuesto'\n👥 **Familia/Organización** - 'crear familia'\n🏢 **Empresa** - 'crear empresa'\n\n¿Cuál prefieres?",
                "action": "clarification_needed",
                "context": "create_what"
            }
        
        return self._handle_unknown_command(message)
    
    def _handle_budget_creation_start(self, message: str, user_id: str, db: Session) -> Dict[str, Any]:
        """Start budget creation flow with missing parameters"""
        # Extract any amount from message
        import re
        amount_match = re.search(r"(\d+(?:\.\d+)?)", message)
        amount = float(amount_match.group(1)) if amount_match else None
        
        # Extract category hints
        message_lower = message.lower()
        category_hints = []
        
        category_map = {
            "comida": "Comida",
            "comidas": "Comida", 
            "alimentacion": "Alimentación",
            "gasolina": "Gasolina",
            "combustible": "Gasolina",
            "entretenimiento": "Entretenimiento",
            "diversión": "Entretenimiento",
            "casa": "Casa",
            "hogar": "Casa",
            "salud": "Salud",
            "medicinas": "Salud",
            "trabajo": "Trabajo",
            "oficina": "Trabajo",
            "educacion": "Educación",
            "educación": "Educación",
            "ropa": "Ropa",
            "vestimenta": "Ropa"
        }
        
        detected_category = None
        for keyword, category in category_map.items():
            if keyword in message_lower:
                detected_category = category
                break
        
        # Build response based on what we have
        if amount and detected_category:
            # We have both, try to create budget
            return self._create_budget_with_params(amount, detected_category, user_id, db)
        elif amount:
            # We have amount, ask for category
            return {
                "success": False,
                "message": f"💰 Perfecto, presupuesto de ₡{amount:,.0f}\n\n📊 ¿Para qué categoría?\n\n• Comida\n• Gasolina\n• Entretenimiento\n• Casa\n• Salud\n• Otro (especifica)",
                "action": "budget_category_needed",
                "context": {
                    "amount": amount,
                    "step": "category"
                }
            }
        elif detected_category:
            # We have category, ask for amount
            return {
                "success": False,
                "message": f"📊 Presupuesto para {detected_category}\n\n💰 ¿Cuál es el límite?\n\nEjemplo: '₡100000' o '100000'",
                "action": "budget_amount_needed",
                "context": {
                    "category": detected_category,
                    "step": "amount"
                }
            }
        else:
            # Ask for both
            return {
                "success": False,
                "message": "💰 **Crear Presupuesto**\n\n¿Para qué categoría y cuánto?\n\n📝 Ejemplos:\n• 'Presupuesto de ₡100000 para comida'\n• 'Límite de ₡50000 en gasolina'\n• '₡200000 para entretenimiento'\n\n¿Cuál prefieres?",
                "action": "budget_full_info_needed",
                "context": {
                    "step": "both"
                }
            }
    
    def _create_budget_with_params(self, amount: float, category: str, user_id: str, db: Session) -> Dict[str, Any]:
        """Create budget with provided parameters"""
        try:
            from app.services.budget_service import BudgetService
            from app.services.user_service import UserService
            from app.core.schemas import BudgetCreate
            from app.models.budget import BudgetPeriod, BudgetStatus
            from datetime import datetime
            import calendar
            
            user = UserService.get_user(db, user_id)
            
            # Calculate period dates (default monthly)
            start_date = datetime.now()
            last_day = calendar.monthrange(start_date.year, start_date.month)[1]
            end_date = start_date.replace(day=last_day)
            
            # Create budget name
            budget_name = f"Presupuesto Mensual - {category}"
            
            budget_data = BudgetCreate(
                user_id=user_id,
                organization_id=None,
                name=budget_name,
                category=category,
                amount=float(amount),
                period=BudgetPeriod.monthly,
                start_date=start_date,
                end_date=end_date,
                status=BudgetStatus.active,
                alert_percentage=80.0,
                auto_renew=False
            )
            
            budget_service = BudgetService(db)
            budget = budget_service.create_budget(budget_data)
            
            currency_symbol = "₡" if user and user.currency == "CRC" else "$"
            
            return {
                "success": True,
                "message": f"✅ **Presupuesto Creado**\n\n📊 **{budget_name}**\n💰 Límite: {currency_symbol}{amount:,.0f}\n📅 Período: Este mes\n🚨 Alerta: 80% del límite\n\n¡Listo para controlar tus gastos en {category}!",
                "action": "budget_created",
                "budget_id": str(budget.id)
            }
            
        except Exception as e:
            print(f"Error creating budget: {e}")
            return {
                "success": False,
                "message": f"❌ Error al crear presupuesto: {str(e)}\n\n🔄 Intenta de nuevo con: 'Presupuesto de ₡{amount:,.0f} para {category}'",
                "action": "budget_error"
            }
    
    def _handle_organization_creation_start(self, message: str, user_id: str, db: Session) -> Dict[str, Any]:
        """Handle organization creation"""
        from app.agents.organization_agent import OrganizationAgent
        org_agent = OrganizationAgent()
        return org_agent.process_organization_command(message, user_id, db)
    
    def _handle_unknown_command(self, message: str) -> Dict[str, Any]:
        """Handle completely unknown commands"""
        return {
            "success": False,
            "message": "🤔 No entendí tu mensaje.\n\n💡 **¿Qué quieres hacer?**\n\n📊 **Presupuestos**: 'crear presupuesto'\n👥 **Organizaciones**: 'crear familia'\n💰 **Gastos**: 'gasté ₡5000'\n📈 **Reportes**: 'resumen'\n❓ **Ayuda**: 'ayuda'\n\n¿Cuál prefieres?",
            "action": "unknown_command",
            "suggestions": [
                "crear presupuesto",
                "crear familia", 
                "gasté ₡5000",
                "resumen",
                "ayuda"
            ]
        }
    
    def handle_budget_followup(self, message: str, context: Dict[str, Any], user_id: str, db: Session) -> Dict[str, Any]:
        """Handle follow-up messages for budget creation"""
        step = context.get("step")
        
        if step == "category":
            # User provided category, we have amount from context
            amount = context.get("amount")
            category = self._extract_category_from_message(message)
            
            if category:
                return self._create_budget_with_params(amount, category, user_id, db)
            else:
                return {
                    "success": False,
                    "message": "🤔 No entendí la categoría.\n\n📊 **Categorías disponibles:**\n• Comida\n• Gasolina\n• Entretenimiento\n• Casa\n• Salud\n• Ropa\n• Trabajo\n\n¿Cuál eliges?",
                    "action": "budget_category_needed",
                    "context": context
                }
        
        elif step == "amount":
            # User provided amount, we have category from context
            category = context.get("category")
            amount = self._extract_amount_from_message(message)
            
            if amount:
                return self._create_budget_with_params(amount, category, user_id, db)
            else:
                return {
                    "success": False,
                    "message": f"💰 ¿Cuál es el límite para {category}?\n\n💡 Ejemplos válidos:\n• '₡100000'\n• '100000'\n• 'cien mil colones'",
                    "action": "budget_amount_needed",
                    "context": context
                }
        
        elif step == "both":
            # Try to extract both from the message
            amount = self._extract_amount_from_message(message)
            category = self._extract_category_from_message(message)
            
            if amount and category:
                return self._create_budget_with_params(amount, category, user_id, db)
            elif amount:
                return {
                    "success": False,
                    "message": f"💰 Perfecto, ₡{amount:,.0f}\n\n📊 ¿Para qué categoría?",
                    "action": "budget_category_needed",
                    "context": {
                        "amount": amount,
                        "step": "category"
                    }
                }
            elif category:
                return {
                    "success": False,
                    "message": f"📊 Perfecto, para {category}\n\n💰 ¿Cuál es el límite?",
                    "action": "budget_amount_needed", 
                    "context": {
                        "category": category,
                        "step": "amount"
                    }
                }
            else:
                return {
                    "success": False,
                    "message": "🤔 Necesito el monto y la categoría.\n\n📝 Ejemplo: 'Presupuesto de ₡100000 para comida'",
                    "action": "budget_full_info_needed",
                    "context": context
                }
        
        return self._handle_unknown_command(message)
    
    def _extract_category_from_message(self, message: str) -> str:
        """Extract category from user message"""
        message_lower = message.lower().strip()
        
        category_map = {
            "comida": "Comida",
            "comidas": "Comida",
            "alimentacion": "Alimentación", 
            "alimentación": "Alimentación",
            "gasolina": "Gasolina",
            "combustible": "Gasolina",
            "entretenimiento": "Entretenimiento",
            "diversion": "Entretenimiento",
            "diversión": "Entretenimiento",
            "casa": "Casa",
            "hogar": "Casa",
            "vivienda": "Casa",
            "salud": "Salud",
            "medicina": "Salud",
            "medicinas": "Salud",
            "trabajo": "Trabajo",
            "oficina": "Trabajo",
            "educacion": "Educación",
            "educación": "Educación",
            "ropa": "Ropa",
            "vestimenta": "Ropa",
            "transporte": "Transporte",
            "otro": "Otro",
            "otros": "Otro",
            "general": "General"
        }
        
        # Direct match
        for keyword, category in category_map.items():
            if keyword == message_lower or keyword in message_lower:
                return category
        
        # If user just typed the category name directly
        if message_lower.title() in category_map.values():
            return message_lower.title()
        
        return None
    
    def _extract_amount_from_message(self, message: str) -> float:
        """Extract amount from user message"""
        import re
        
        # Remove currency symbols
        clean_message = message.replace('₡', '').replace('$', '').replace(',', '')
        
        # Try to find numbers
        patterns = [
            r"(\d+(?:\.\d+)?)",
            r"(\d+(?:,\d+)*)"
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, clean_message)
            if matches:
                try:
                    amount = float(matches[0].replace(',', ''))
                    if amount > 0:
                        return amount
                except:
                    continue
        
        return None