from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
import json
import uuid

@dataclass
class ConversationContext:
    """Context for ongoing conversation"""
    user_id: str
    session_id: str
    current_flow: str  # "creating_budget", "adding_expense", "none"
    flow_data: Dict[str, Any]
    last_message_time: datetime
    message_count: int = 0

class ConversationManager:
    """Manages natural conversation flow and context"""
    
    def __init__(self):
        self.active_sessions: Dict[str, ConversationContext] = {}
        self.session_timeout = timedelta(minutes=10)  # 10 min timeout
    
    def process_message(self, message: str, user_id: str, db: Session) -> Dict[str, Any]:
        """Process message with conversation context"""
        
        # Get or create session
        context = self._get_or_create_context(user_id)
        context.message_count += 1
        context.last_message_time = datetime.now()
        
        # Clean up old sessions
        self._cleanup_old_sessions()
        
        # Determine if this is a new intent or continuation
        message_intent = self._analyze_message_intent(message, context)
        
        # Route based on intent and context
        if context.current_flow == "none":
            return self._handle_new_conversation(message_intent, message, user_id, db, context)
        else:
            return self._handle_ongoing_conversation(message_intent, message, user_id, db, context)
    
    def _analyze_message_intent(self, message: str, context: ConversationContext) -> Dict[str, Any]:
        """Analyze message intent with context awareness"""
        message_lower = message.lower().strip()
        
        intent = {
            "type": "unknown",
            "confidence": 0.0,
            "is_new_flow": True,
            "extracted_data": {}
        }
        
        # High-confidence patterns for NEW flows
        new_flow_patterns = {
            "create_budget": [
                "crear presupuesto", "nuevo presupuesto", "presupuesto para",
                "límite de", "budget", "presupuesto de"
            ],
            "add_expense": [
                "gasté", "gaste", "pagué", "pague", "compré", "compre",
                "gasto de", "agregar gasto", "anotar gasto"
            ],
            "view_report": [
                "resumen", "reporte", "balance", "cuánto", "total",
                "mis gastos", "gastos del mes"
            ],
            "help": [
                "ayuda", "help", "qué puedo hacer", "comandos", "no entiendo"
            ]
        }
        
        # Check for new flow intentions
        for flow_type, patterns in new_flow_patterns.items():
            for pattern in patterns:
                if pattern in message_lower:
                    intent["type"] = flow_type
                    intent["confidence"] = 0.9
                    intent["is_new_flow"] = True
                    break
            if intent["confidence"] > 0:
                break
        
        # Extract data based on type
        if intent["type"] == "create_budget":
            intent["extracted_data"] = self._extract_budget_data(message)
        elif intent["type"] == "add_expense":
            intent["extracted_data"] = self._extract_expense_data(message)
        
        # Check if this could be a continuation of current flow
        if context.current_flow != "none" and intent["confidence"] < 0.8:
            intent["is_new_flow"] = False
            intent["type"] = "continuation"
        
        return intent
    
    def _handle_new_conversation(self, intent: Dict, message: str, user_id: str, db: Session, context: ConversationContext) -> Dict[str, Any]:
        """Handle start of new conversation flow"""
        
        if intent["type"] == "create_budget":
            return self._start_budget_creation(intent, message, user_id, db, context)
        
        elif intent["type"] == "add_expense":
            return self._start_expense_addition(intent, message, user_id, db, context)
        
        elif intent["type"] == "view_report":
            return self._generate_report(message, user_id, db)
        
        elif intent["type"] == "help":
            return self._show_help()
        
        else:
            return self._handle_unclear_message(message, context)
    
    def _start_budget_creation(self, intent: Dict, message: str, user_id: str, db: Session, context: ConversationContext) -> Dict[str, Any]:
        """Start budget creation flow"""
        data = intent["extracted_data"]
        
        # Check what we have
        has_amount = data.get("amount") is not None
        has_category = data.get("category") is not None
        
        if has_amount and has_category:
            # We have everything, create the budget
            return self._create_budget_directly(data, user_id, db, context)
        
        # Start guided flow
        context.current_flow = "creating_budget"
        context.flow_data = data
        
        if has_amount:
            return {
                "success": False,
                "message": f"💰 Perfecto! Presupuesto de ₡{data['amount']:,.0f}\n\n🏷️ ¿Para qué lo vas a usar?\n\n📝 Ejemplos:\n• Comida\n• Gasolina\n• Entretenimiento\n• Casa\n\nEscribe la categoría:",
                "action": "budget_need_category"
            }
        
        elif has_category:
            return {
                "success": False,
                "message": f"🏷️ Perfecto! Presupuesto para {data['category']}\n\n💰 ¿Cuánto quieres gastar máximo?\n\n📝 Ejemplos:\n• ₡100000\n• 100000\n• Cien mil\n\nEscribe el monto:",
                "action": "budget_need_amount"
            }
        
        else:
            return {
                "success": False,
                "message": "💰 ¡Perfecto! Vamos a crear tu presupuesto\n\n🏷️ ¿Para qué categoría?\n📝 Ejemplos: Comida, Gasolina, Entretenimiento\n\n💡 O puedes decir: 'Presupuesto de ₡100000 para comida'",
                "action": "budget_need_both"
            }
    
    def _start_expense_addition(self, intent: Dict, message: str, user_id: str, db: Session, context: ConversationContext) -> Dict[str, Any]:
        """Start expense addition flow"""
        data = intent["extracted_data"]
        
        # Check what we have
        has_amount = data.get("amount") is not None
        has_description = data.get("description") is not None
        
        if has_amount and has_description:
            # We have everything, create the expense
            return self._create_expense_directly(data, user_id, db, context)
        
        # Start guided flow
        context.current_flow = "adding_expense"
        context.flow_data = data
        
        if has_amount:
            return {
                "success": False,
                "message": f"💸 Perfecto! Gasto de ₡{data['amount']:,.0f}\n\n📝 ¿En qué lo gastaste?\n\nEjemplos:\n• Almuerzo\n• Gasolina\n• Supermercado\n\nDescribe el gasto:",
                "action": "expense_need_description"
            }
        
        else:
            return {
                "success": False,
                "message": "💸 ¡Entendido! Quieres anotar un gasto\n\n💰 ¿Cuánto gastaste?\n📝 Ejemplos: ₡5000, 5000, cinco mil\n\n💡 O puedes decir: 'Gasté ₡5000 en almuerzo'",
                "action": "expense_need_amount"
            }
    
    def _handle_ongoing_conversation(self, intent: Dict, message: str, user_id: str, db: Session, context: ConversationContext) -> Dict[str, Any]:
        """Handle continuation of ongoing conversation"""
        
        # Check if user wants to start something new
        if intent["is_new_flow"] and intent["confidence"] > 0.8:
            # Reset context and start new flow
            context.current_flow = "none"
            context.flow_data = {}
            return self._handle_new_conversation(intent, message, user_id, db, context)
        
        # Continue current flow
        if context.current_flow == "creating_budget":
            return self._continue_budget_creation(message, user_id, db, context)
        
        elif context.current_flow == "adding_expense":
            return self._continue_expense_addition(message, user_id, db, context)
        
        else:
            # Unknown flow, reset
            context.current_flow = "none"
            context.flow_data = {}
            return self._handle_unclear_message(message, context)
    
    def _continue_budget_creation(self, message: str, user_id: str, db: Session, context: ConversationContext) -> Dict[str, Any]:
        """Continue budget creation with user input"""
        data = context.flow_data
        
        # Extract missing information
        if not data.get("amount"):
            amount = self._extract_amount(message)
            if amount:
                data["amount"] = amount
            else:
                return {
                    "success": False,
                    "message": "🤔 No entendí el monto\n\n💰 ¿Cuánto quieres gastar máximo?\n📝 Ejemplos: ₡100000, 100000, cien mil",
                    "action": "budget_need_amount"
                }
        
        if not data.get("category"):
            category = self._extract_category(message)
            if category:
                data["category"] = category
            else:
                return {
                    "success": False,
                    "message": "🤔 No entendí la categoría\n\n🏷️ ¿Para qué vas a usar este presupuesto?\n📝 Ejemplos: Comida, Gasolina, Entretenimiento",
                    "action": "budget_need_category"
                }
        
        # If we have everything, create budget
        if data.get("amount") and data.get("category"):
            return self._create_budget_directly(data, user_id, db, context)
        
        # Still missing something
        return {
            "success": False,
            "message": "🤔 Necesito más información para crear tu presupuesto",
            "action": "budget_incomplete"
        }
    
    def _continue_expense_addition(self, message: str, user_id: str, db: Session, context: ConversationContext) -> Dict[str, Any]:
        """Continue expense addition with user input"""
        data = context.flow_data
        
        # Extract missing information
        if not data.get("amount"):
            amount = self._extract_amount(message)
            if amount:
                data["amount"] = amount
            else:
                return {
                    "success": False,
                    "message": "🤔 No entendí el monto\n\n💰 ¿Cuánto gastaste?\n📝 Ejemplos: ₡5000, 5000, cinco mil",
                    "action": "expense_need_amount"
                }
        
        if not data.get("description"):
            # Use the whole message as description if it's reasonable
            if len(message.strip()) > 2 and len(message.strip()) < 100:
                data["description"] = message.strip()
            else:
                return {
                    "success": False,
                    "message": "🤔 No entendí en qué gastaste\n\n📝 ¿En qué lo gastaste?\nEjemplos: Almuerzo, Gasolina, Supermercado",
                    "action": "expense_need_description"
                }
        
        # If we have everything, create expense
        if data.get("amount") and data.get("description"):
            return self._create_expense_directly(data, user_id, db, context)
        
        # Still missing something
        return {
            "success": False,
            "message": "🤔 Necesito más información para anotar tu gasto",
            "action": "expense_incomplete"
        }
    
    def _create_budget_directly(self, data: Dict, user_id: str, db: Session, context: ConversationContext) -> Dict[str, Any]:
        """Create budget with all required data"""
        try:
            from app.services.budget_service import BudgetService
            from app.services.user_service import UserService
            from app.core.schemas import BudgetCreate
            from app.models.budget import BudgetPeriod, BudgetStatus
            from datetime import datetime
            import calendar
            
            user = UserService.get_user(db, user_id)
            
            # Calculate period dates (monthly)
            start_date = datetime.now()
            last_day = calendar.monthrange(start_date.year, start_date.month)[1]
            end_date = start_date.replace(day=last_day)
            
            budget_data = BudgetCreate(
                user_id=user_id,
                organization_id=None,
                name=f"Presupuesto de {data['category']}",
                category=str(data['category']),
                amount=float(data['amount']),
                period=BudgetPeriod.monthly,
                start_date=start_date,
                end_date=end_date,
                status=BudgetStatus.active,
                alert_percentage=80.0,
                auto_renew=False
            )
            
            budget_service = BudgetService(db)
            budget = budget_service.create_budget(budget_data)
            
            # Reset conversation context
            context.current_flow = "none"
            context.flow_data = {}
            
            currency = "₡" if user and user.currency == "CRC" else "$"
            
            return {
                "success": True,
                "message": f"✅ **Presupuesto creado exitosamente**\n\n🏷️ **{data['category']}**\n💰 Límite: {currency}{data['amount']:,.0f} este mes\n🚨 Te avisaré cuando gastes el 80%\n\n💡 Ahora puedes agregar gastos con:\n'Gasté ₡5000 en almuerzo'",
                "action": "budget_created"
            }
            
        except Exception as e:
            context.current_flow = "none"
            context.flow_data = {}
            return {
                "success": False,
                "message": f"❌ Ups! Hubo un error creando tu presupuesto.\n\n🔄 Intenta de nuevo: 'Presupuesto de {currency}{data['amount']:,.0f} para {data['category']}'",
                "action": "budget_error"
            }
    
    def _create_expense_directly(self, data: Dict, user_id: str, db: Session, context: ConversationContext) -> Dict[str, Any]:
        """Create expense with all required data"""
        try:
            from app.services.transaction_service import TransactionService
            from app.services.user_service import UserService
            from app.core.schemas import TransactionCreate
            from app.models.transaction import TransactionType
            
            user = UserService.get_user(db, user_id)
            
            # Determine category from description
            category = self._smart_categorize(data['description'])
            
            transaction_data = TransactionCreate(
                user_id=user_id,
                organization_id=None,
                amount=float(data['amount']),
                type=TransactionType.expense,
                category=category,
                description=data['description']
            )
            
            transaction = TransactionService.create_transaction(db, transaction_data)
            
            # Check budget alerts
            self._check_budget_alerts(user_id, float(data['amount']), category, db)
            
            # Reset conversation context
            context.current_flow = "none"
            context.flow_data = {}
            
            currency = "₡" if user and user.currency == "CRC" else "$"
            
            return {
                "success": True,
                "message": f"✅ **Gasto anotado**\n\n💸 {currency}{data['amount']:,.0f} en {data['description']}\n📊 Categoría: {category}\n\n💡 Puedes ver tu resumen con: 'resumen'",
                "action": "expense_created"
            }
            
        except Exception as e:
            context.current_flow = "none"
            context.flow_data = {}
            return {
                "success": False,
                "message": f"❌ Ups! No pude anotar tu gasto.\n\n🔄 Intenta: 'Gasté {currency}{data['amount']:,.0f} en {data['description']}'",
                "action": "expense_error"
            }
    
    def _extract_budget_data(self, message: str) -> Dict[str, Any]:
        """Extract budget data from message"""
        data = {}
        
        # Extract amount
        amount = self._extract_amount(message)
        if amount:
            data["amount"] = amount
        
        # Extract category
        category = self._extract_category(message)
        if category:
            data["category"] = category
        
        return data
    
    def _extract_expense_data(self, message: str) -> Dict[str, Any]:
        """Extract expense data from message"""
        data = {}
        
        # Extract amount
        amount = self._extract_amount(message)
        if amount:
            data["amount"] = amount
        
        # Extract description (everything after amount/action words)
        description = self._extract_description(message)
        if description:
            data["description"] = description
        
        return data
    
    def _extract_amount(self, message: str) -> Optional[float]:
        """Extract amount from message"""
        import re
        
        # Remove currency symbols
        clean_message = message.replace('₡', '').replace('$', '').replace(',', '')
        
        # Find numbers
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
    
    def _extract_category(self, message: str) -> Optional[str]:
        """Extract category from message"""
        message_lower = message.lower()
        
        category_map = {
            "comida": "Comida", "comidas": "Comida", "almuerzo": "Comida", "cena": "Comida",
            "gasolina": "Gasolina", "combustible": "Gasolina", "diesel": "Gasolina",
            "entretenimiento": "Entretenimiento", "diversión": "Entretenimiento", "cine": "Entretenimiento",
            "casa": "Casa", "hogar": "Casa", "vivienda": "Casa",
            "salud": "Salud", "medicina": "Salud", "doctor": "Salud",
            "trabajo": "Trabajo", "oficina": "Trabajo",
            "transporte": "Transporte", "uber": "Transporte", "taxi": "Transporte",
            "ropa": "Ropa", "vestimenta": "Ropa"
        }
        
        for keyword, category in category_map.items():
            if keyword in message_lower:
                return category
        
        # Check if "para" is used
        if " para " in message_lower:
            parts = message_lower.split(" para ")
            if len(parts) > 1:
                category_text = parts[1].strip().title()
                return category_text
        
        return None
    
    def _extract_description(self, message: str) -> Optional[str]:
        """Extract description from expense message"""
        message_lower = message.lower()
        
        # Remove action words
        clean_message = message
        action_words = ["gasté", "gaste", "pagué", "pague", "compré", "compre", "gasto", "agregar gasto"]
        
        for word in action_words:
            clean_message = clean_message.replace(word, "", 1)
        
        # Remove amount patterns
        import re
        clean_message = re.sub(r"₡?\s*\d+(?:[,\s]\d+)*(?:\.\d+)?", "", clean_message)
        
        # Clean up
        description = clean_message.strip()
        if len(description) > 2:
            return description
        
        return None
    
    def _smart_categorize(self, description: str) -> str:
        """Smart categorization of expenses"""
        description_lower = description.lower()
        
        category_keywords = {
            "Comida": ["almuerzo", "cena", "desayuno", "comida", "restaurante", "café", "pizza"],
            "Gasolina": ["gasolina", "combustible", "diesel", "gas"],
            "Transporte": ["uber", "taxi", "bus", "transporte", "viaje"],
            "Entretenimiento": ["cine", "película", "juego", "diversión", "entretenimiento"],
            "Casa": ["casa", "hogar", "supermercado", "mercado", "tienda"],
            "Salud": ["medicina", "doctor", "farmacia", "salud", "hospital"],
            "Trabajo": ["oficina", "trabajo", "materiales"],
            "Ropa": ["ropa", "zapatos", "vestido", "camisa"]
        }
        
        for category, keywords in category_keywords.items():
            for keyword in keywords:
                if keyword in description_lower:
                    return category
        
        return "General"
    
    def _check_budget_alerts(self, user_id: str, amount: float, category: str, db: Session):
        """Check if this expense triggers budget alerts"""
        try:
            from app.services.budget_service import BudgetService
            from decimal import Decimal
            
            budget_service = BudgetService(db)
            budget_service.check_budget_alerts(user_id, Decimal(str(amount)), category)
        except Exception as e:
            print(f"Error checking budget alerts: {e}")
    
    def _generate_report(self, message: str, user_id: str, db: Session) -> Dict[str, Any]:
        """Generate expense report"""
        from app.agents.report_agent import ReportAgent
        from app.services.user_service import UserService
        
        report_agent = ReportAgent()
        user = UserService.get_user(db, user_id)
        currency_symbol = "₡" if user and user.currency == "CRC" else "$"
        
        return report_agent.generate_report(message, user_id, db, currency_symbol)
    
    def _show_help(self) -> Dict[str, Any]:
        """Show helpful commands"""
        return {
            "success": True,
            "message": """💡 **¿Qué puedes hacer?**

📊 **PRESUPUESTOS:**
• "Crear presupuesto" - Te guío paso a paso
• "Presupuesto de ₡100000 para comida" - Directo

💸 **GASTOS:**
• "Gasté ₡5000" - Te pregunto en qué
• "Gasté ₡5000 en almuerzo" - Directo

📈 **REPORTES:**
• "Resumen" - Ver tus gastos
• "Balance" - ¿Cómo vas?

❓ **AYUDA:**
• "Ayuda" - Ver comandos
• Solo escríbeme en lenguaje natural 😊""",
            "action": "help_shown"
        }
    
    def _handle_unclear_message(self, message: str, context: ConversationContext) -> Dict[str, Any]:
        """Handle unclear messages with helpful suggestions"""
        return {
            "success": False,
            "message": f"🤔 No estoy seguro qué quieres hacer\n\n💡 **Puedes probar:**\n\n📊 'Crear presupuesto'\n💸 'Gasté ₡5000'\n📈 'Resumen'\n❓ 'Ayuda'\n\n¿Qué te gustaría hacer?",
            "action": "unclear_message",
            "suggestions": [
                "Crear presupuesto",
                "Gasté ₡5000",
                "Resumen",
                "Ayuda"
            ]
        }
    
    def _get_or_create_context(self, user_id: str) -> ConversationContext:
        """Get or create conversation context for user"""
        
        # Clean up expired sessions first
        self._cleanup_old_sessions()
        
        if user_id not in self.active_sessions:
            self.active_sessions[user_id] = ConversationContext(
                user_id=user_id,
                session_id=str(uuid.uuid4()),
                current_flow="none",
                flow_data={},
                last_message_time=datetime.now()
            )
        
        return self.active_sessions[user_id]
    
    def _cleanup_old_sessions(self):
        """Remove expired conversation sessions"""
        now = datetime.now()
        expired_users = []
        
        for user_id, context in self.active_sessions.items():
            if now - context.last_message_time > self.session_timeout:
                expired_users.append(user_id)
        
        for user_id in expired_users:
            del self.active_sessions[user_id]