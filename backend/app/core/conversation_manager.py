from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.core.llm_config import get_openai_config
from crewai import Agent, Task, Crew
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
        
        # Initialize OpenAI agent for intelligent parsing
        try:
            self.has_openai = get_openai_config()
            if self.has_openai:
                self.intelligent_agent = Agent(
                    role="Asistente Financiero Inteligente",
                    goal="Entender completamente mensajes en español sobre finanzas y extraer información precisa sobre gastos, ingresos y contexto organizacional.",
                    backstory="""Eres un experto en procesamiento de lenguaje natural en español, especializado en transacciones financieras.
                    
                    Entiendes patrones como:
                    - "Gasto familia gasolina 40000" = gasto de 40000 en gasolina para la familia
                    - "Compré almuerzo 5000" = gasto de 5000 en almuerzo (personal)
                    - "Pago empresa 25000" = gasto de 25000 para la empresa
                    
                    Siempre respondes en JSON con la información extraída.""",
                    verbose=True,
                    allow_delegation=False
                )
            else:
                self.intelligent_agent = None
        except Exception as e:
            print(f"Warning: Could not initialize intelligent agent: {e}")
            self.has_openai = False
            self.intelligent_agent = None
    
    def process_message(self, message: str, user_id: str, db: Session) -> Dict[str, Any]:
        """Process message with conversation context"""
        
        # Get or create session
        context = self._get_or_create_context(user_id)
        context.message_count += 1
        context.last_message_time = datetime.now()
        
        # Clean up old sessions
        self._cleanup_old_sessions()
        
        # Determine if this is a new intent or continuation
        message_intent = self._analyze_message_intent(message, context, db)
        
        # Route based on intent and context
        if context.current_flow == "none":
            return self._handle_new_conversation(message_intent, message, user_id, db, context)
        else:
            return self._handle_ongoing_conversation(message_intent, message, user_id, db, context)
    
    def _analyze_message_intent(self, message: str, context: ConversationContext, db: Session = None) -> Dict[str, Any]:
        """Analyze message intent with AI or fallback to regex"""
        
        # Get user organizations for context if we have db session
        user_organizations = []
        if db:
            try:
                from app.services.organization_service import OrganizationService
                user_organizations = OrganizationService.get_user_organizations(db, context.user_id)
            except:
                user_organizations = []
        
        if self.has_openai and self.intelligent_agent:
            return self._ai_analyze_intent(message, context, user_organizations)
        else:
            return self._regex_analyze_intent(message, context)
    
    def _ai_analyze_intent(self, message: str, context: ConversationContext, user_organizations: List = None) -> Dict[str, Any]:
        """Use AI to analyze message intent and extract data intelligently"""
        
        org_context = ""
        if user_organizations:
            org_names = [org.name for org in user_organizations]
            org_context = f"El usuario pertenece a estas organizaciones: {', '.join(org_names)}"
        
        task = Task(
            description=f"""
            Analiza este mensaje en español y extrae la información:
            MENSAJE: "{message}"
            CONTEXTO: {org_context}
            
            Determina:
            1. TIPO DE ACCIÓN (debe ser UNO de estos):
               - add_expense: cualquier gasto, compra, pago (ej: "gasto", "gasté", "compré", "pago")
               - create_budget: crear presupuesto
               - create_organization: crear familia/empresa/equipo
               - view_report: ver resumen/reporte/balance
               - list_organizations: listar organizaciones (ej: "en qué familias estoy", "mis organizaciones", "cuáles familias", "donde estoy")
               - accept_invitation: acepta invitación
               - help: pide ayuda
               - unknown: no está claro
            
            2. DATOS EXTRAÍDOS:
               - amount: número del monto (solo el número, sin símbolos)
               - description: descripción del gasto (sin el monto)
               - organization_context: nombre de organización mencionada o null
               - category: categoría inferida (Gasolina, Comida, etc.)
            
            EJEMPLOS:
            - "Gasto familia gasolina 40000" → add_expense, amount: 40000, description: "gasolina", organization_context: "familia"
            - "Compré almuerzo 5000" → add_expense, amount: 5000, description: "almuerzo", organization_context: null
            - "Gasto 40000" → add_expense, amount: 40000, description: null, organization_context: null
            - "Crear presupuesto comida" → create_budget, category: "Comida"
            - "En qué familias estoy" → list_organizations
            - "Cuáles organizaciones tengo" → list_organizations
            - "Mis familias" → list_organizations
            
            RESPONDE SOLO JSON:
            {{
                "type": "tipo_de_accion",
                "confidence": 0.9,
                "is_new_flow": true,
                "extracted_data": {{
                    "amount": numero_o_null,
                    "description": "texto_o_null",
                    "organization_context": "nombre_org_o_null",
                    "category": "categoria_o_null"
                }}
            }}
            """,
            agent=self.intelligent_agent,
            expected_output="JSON con análisis completo del mensaje"
        )
        
        try:
            crew = Crew(agents=[self.intelligent_agent], tasks=[task])
            result = str(crew.kickoff()).strip()
            
            # Parse AI response
            import re
            json_match = re.search(r'\{.*\}', result, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                intent = json.loads(json_str)
                
                # Ensure required fields exist
                if "type" not in intent:
                    intent["type"] = "unknown"
                if "confidence" not in intent:
                    intent["confidence"] = 0.5
                if "is_new_flow" not in intent:
                    intent["is_new_flow"] = True
                if "extracted_data" not in intent:
                    intent["extracted_data"] = {}
                
                return intent
            else:
                print(f"❌ AI response not JSON: {result}")
                return self._regex_analyze_intent(message, context)
                
        except Exception as e:
            print(f"❌ AI intent analysis failed: {e}")
            return self._regex_analyze_intent(message, context)
    
    def _regex_analyze_intent(self, message: str, context: ConversationContext) -> Dict[str, Any]:
        """Fallback regex analysis when AI is not available"""
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
            "create_organization": [
                "crear familia", "crear empresa", "crear equipo", "nueva familia", 
                "nueva empresa", "nuevo equipo", "agregar familia", "agregar empresa",
                "crear organizacion", "crear organización"
            ],
            "add_expense": [
                "gasté", "gaste", "pagué", "pague", "compré", "compre",
                "gasto de", "agregar gasto", "anotar gasto", "gasto", 
                "pago", "compra", "costo", "costó", "invertí", "invirtí"
            ],
            "view_report": [
                "resumen", "reporte", "balance", "cuánto", "total",
                "mis gastos", "gastos del mes"
            ],
            "list_organizations": [
                "qué familias", "que familias", "cuáles familias", "cuales familias",
                "mis organizaciones", "mis familias", "donde estoy", "dónde estoy",
                "en qué", "en que", "organizaciones tengo", "familias tengo"
            ],
            "help": [
                "ayuda", "help", "qué puedo hacer", "comandos", "no entiendo"
            ],
            "accept_invitation": [
                "acepto", "aceptar", "quiero unirme", "sí quiero"
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
        elif intent["type"] == "create_organization":
            intent["extracted_data"] = self._extract_organization_data(message)
        
        # Check if this could be a continuation of current flow
        if context.current_flow != "none" and intent["confidence"] < 0.8:
            intent["is_new_flow"] = False
            intent["type"] = "continuation"
        
        return intent
    
    def _handle_new_conversation(self, intent: Dict, message: str, user_id: str, db: Session, context: ConversationContext) -> Dict[str, Any]:
        """Handle start of new conversation flow"""
        
        if intent["type"] == "create_budget":
            return self._start_budget_creation(intent, message, user_id, db, context)
        
        elif intent["type"] == "create_organization":
            return self._handle_organization_creation(intent, message, user_id, db, context)
        
        elif intent["type"] == "add_expense":
            return self._start_expense_addition(intent, message, user_id, db, context)
        
        elif intent["type"] == "view_report":
            return self._generate_report(message, user_id, db)
        
        elif intent["type"] == "list_organizations":
            return self._list_user_organizations(user_id, db)
        
        elif intent["type"] == "accept_invitation":
            return self._handle_accept_invitation(user_id, db)
        
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
        """Start expense addition flow with organization context"""
        data = intent["extracted_data"]
        
        # Get user organizations
        from app.services.organization_service import OrganizationService
        user_organizations = OrganizationService.get_user_organizations(db, user_id)
        
        # Check what we have
        has_amount = data.get("amount") is not None
        has_description = data.get("description") is not None
        organization_context = data.get("organization_context")
        
        # Determine target organization
        target_organization = None
        if organization_context and user_organizations:
            # Try to match mentioned organization
            for org in user_organizations:
                if organization_context.lower() in org.name.lower():
                    target_organization = org
                    break
        
        # Check if we need to ask for organization
        needs_org_clarification = False
        if len(user_organizations) > 1:  # User has multiple organizations
            if not target_organization:  # No organization matched or mentioned
                needs_org_clarification = True
        
        # If we have everything and organization is clear, create the expense
        if has_amount and has_description and not needs_org_clarification:
            # Add organization info to data
            if target_organization:
                data["organization_id"] = str(target_organization.id)
                data["organization_name"] = target_organization.name
            return self._create_expense_directly(data, user_id, db, context)
        
        # Start guided flow
        context.current_flow = "adding_expense"
        context.flow_data = data
        context.flow_data["user_organizations"] = [{"id": str(org.id), "name": org.name, "type": org.type.value} for org in user_organizations]
        
        # If we need organization clarification first
        if needs_org_clarification and has_amount and has_description:
            return self._ask_for_organization(data, user_organizations)
        
        # If missing amount
        if not has_amount:
            return {
                "success": False,
                "message": "💸 ¡Entendido! Quieres anotar un gasto\n\n💰 ¿Cuánto gastaste?\n📝 Ejemplos: ₡5000, 5000, cinco mil\n\n💡 O puedes decir: 'Gasté ₡5000 en almuerzo'",
                "action": "expense_need_amount"
            }
        
        # If missing description
        if not has_description:
            return {
                "success": False,
                "message": f"💸 Perfecto! Gasto de ₡{data['amount']:,.0f}\n\n📝 ¿En qué lo gastaste?\n\nEjemplos:\n• Almuerzo\n• Gasolina\n• Supermercado\n\nDescribe el gasto:",
                "action": "expense_need_description"
            }
        
        # Should not reach here, but just in case
        return {
            "success": False,
            "message": "💸 ¡Entendido! Quieres anotar un gasto\n\n💰 ¿Cuánto gastaste?\n📝 Ejemplos: ₡5000, 5000, cinco mil",
            "action": "expense_need_amount"
        }
    
    def _ask_for_organization(self, data: Dict, user_organizations: List) -> Dict[str, Any]:
        """Ask user to choose organization for the expense"""
        
        amount_text = f"₡{data['amount']:,.0f}" if data.get('amount') else "tu gasto"
        description_text = f" en {data['description']}" if data.get('description') else ""
        
        org_options = []
        for i, org in enumerate(user_organizations, 1):
            emoji = "👨‍👩‍👧‍👦" if org.type.value == "family" else "🏢"
            org_options.append(f"{i}. {emoji} {org.name}")
        
        org_list = "\n".join(org_options)
        personal_option = f"{len(user_organizations) + 1}. 👤 Personal"
        
        message = f"""💸 **Gasto de {amount_text}{description_text}**

🏷️ **¿Dónde quieres registrarlo?**

{org_list}
{personal_option}

📝 Responde con el número o nombre:
• "1" o "{user_organizations[0].name}"
• "Personal"
"""
        
        return {
            "success": False,
            "message": message,
            "action": "expense_need_organization"
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
        user_organizations = data.get("user_organizations", [])
        
        # Handle organization selection if needed
        if data.get("amount") and data.get("description") and not data.get("organization_id"):
            if len(user_organizations) > 1:  # User has multiple organizations
                org_selection = self._parse_organization_selection(message, user_organizations)
                if org_selection:
                    data["organization_id"] = org_selection.get("organization_id")
                    data["organization_name"] = org_selection.get("organization_name")
                    return self._create_expense_directly(data, user_id, db, context)
                else:
                    # Invalid selection, ask again
                    org_options = []
                    for i, org in enumerate(user_organizations, 1):
                        emoji = "👨‍👩‍👧‍👦" if org["type"] == "family" else "🏢"
                        org_options.append(f"{i}. {emoji} {org['name']}")
                    
                    org_list = "\n".join(org_options)
                    personal_option = f"{len(user_organizations) + 1}. 👤 Personal"
                    
                    return {
                        "success": False,
                        "message": f"🤔 No entendí tu selección\n\n🏷️ **¿Dónde registrar el gasto?**\n\n{org_list}\n{personal_option}\n\n📝 Responde con el número:",
                        "action": "expense_need_organization"
                    }
        
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
        
        # Check if we need organization selection
        if data.get("amount") and data.get("description"):
            if len(user_organizations) > 1 and not data.get("organization_id"):
                return self._ask_for_organization(data, [{"id": org["id"], "name": org["name"], "type": type("", (), {"value": org["type"]})() } for org in user_organizations])
            else:
                return self._create_expense_directly(data, user_id, db, context)
        
        # Still missing something
        return {
            "success": False,
            "message": "🤔 Necesito más información para anotar tu gasto",
            "action": "expense_incomplete"
        }
    
    def _parse_organization_selection(self, message: str, user_organizations: List) -> Optional[Dict]:
        """Parse user's organization selection response"""
        message_lower = message.lower().strip()
        
        # Try numeric selection first
        try:
            selection_num = int(message_lower)
            if 1 <= selection_num <= len(user_organizations):
                org = user_organizations[selection_num - 1]
                return {
                    "organization_id": org["id"],
                    "organization_name": org["name"]
                }
            elif selection_num == len(user_organizations) + 1:
                # Personal selection
                return {
                    "organization_id": None,
                    "organization_name": "Personal"
                }
        except ValueError:
            pass
        
        # Try name matching
        if "personal" in message_lower:
            return {
                "organization_id": None,
                "organization_name": "Personal"
            }
        
        for org in user_organizations:
            if org["name"].lower() in message_lower:
                return {
                    "organization_id": org["id"],
                    "organization_name": org["name"]
                }
        
        return None
    
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
            
            # Get organization ID if specified
            organization_id = data.get('organization_id')
            organization_name = data.get('organization_name', 'Personal')
            
            transaction_data = TransactionCreate(
                user_id=user_id,
                organization_id=organization_id,
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
            
            # Create context-aware confirmation message
            context_text = ""
            if organization_name and organization_name != "Personal":
                context_text = f" ({organization_name})"
            
            return {
                "success": True,
                "message": f"✅ **Gasto anotado{context_text}**\n\n💸 {currency}{data['amount']:,.0f} en {data['description']}\n📊 Categoría: {category}\n\n💡 Puedes ver tu resumen con: 'resumen'",
                "action": "expense_created"
            }
            
        except Exception as e:
            context.current_flow = "none"
            context.flow_data = {}
            currency = "₡"  # Default fallback
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
    
    def _extract_organization_data(self, message: str) -> Dict[str, Any]:
        """Extract organization data from message"""
        data = {}
        
        # Extract organization name (after action words)
        import re
        
        # Remove action patterns
        clean_message = message
        action_patterns = [
            r"crear\s+(familia|empresa|equipo|organizacion|organización)\s*",
            r"nueva?\s+(familia|empresa|equipo|organizacion|organización)\s*", 
            r"agregar\s+(familia|empresa|equipo|organizacion|organización)\s*"
        ]
        
        for pattern in action_patterns:
            match = re.search(pattern, clean_message, re.IGNORECASE)
            if match:
                # Get organization type
                org_type = match.group(1).lower()
                data["organization_type"] = org_type
                
                # Remove the matched pattern to get the name
                clean_message = re.sub(pattern, "", clean_message, flags=re.IGNORECASE)
                break
        
        # Extract name (remaining text)
        org_name = clean_message.strip()
        if len(org_name) > 0:
            data["organization_name"] = org_name
        
        return data
    
    def _extract_amount(self, message: str) -> Optional[float]:
        """Extract amount from message"""
        import re
        
        # Find numbers with various patterns
        patterns = [
            r"₡\s*(\d{1,3}(?:,?\d{3})*(?:\.\d{2})?)",  # ₡1000 or ₡1,000.50
            r"\$\s*(\d{1,3}(?:,?\d{3})*(?:\.\d{2})?)",  # $1000 or $1,000.50
            r"(\d{1,3}(?:,?\d{3})*(?:\.\d{2})?)\s*(?:colones?|₡)",  # 1000 colones
            r"(\d{1,3}(?:,?\d{3})*(?:\.\d{2})?)\s*(?:dollars?|dólares?|\$)",  # 1000 dollars
            r"(\d{4,})",  # Just numbers with 4+ digits (likely amounts)
            r"(\d{1,3}(?:,\d{3})+)",  # Numbers with comma separators
            r"(\d+(?:\.\d+)?)"  # Any number as last resort
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, message)
            if matches:
                try:
                    # Take the largest number found (most likely to be the amount)
                    amounts = []
                    for match in matches:
                        clean_amount = match.replace(',', '')
                        amount = float(clean_amount)
                        if amount > 0:
                            amounts.append(amount)
                    
                    if amounts:
                        # Return the largest amount found
                        return max(amounts)
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
        import re
        
        # Remove action words more carefully
        clean_message = message
        action_patterns = [
            r"gasté\s+", r"gaste\s+", r"pagué\s+", r"pague\s+", 
            r"compré\s+", r"compre\s+", r"gasto\s+", r"agregar\s+gasto\s+",
            r"pago\s+", r"compra\s+", r"costo\s+", r"costó\s+", r"invertí\s+", r"invirtí\s+"
        ]
        
        for pattern in action_patterns:
            clean_message = re.sub(pattern, "", clean_message, count=1, flags=re.IGNORECASE)
        
        # For patterns like "Gasto familia gasolina 40000", extract the middle part
        # Split by spaces and remove numbers
        words = clean_message.split()
        description_words = []
        
        for word in words:
            # Skip if it's purely numeric (likely amount)
            if re.match(r'^\d+(\.\d+)?$', word):
                continue
            # Skip if it's currency-related
            if word.lower() in ['₡', '$', 'colones', 'colón', 'dollars', 'dólares']:
                continue
            # Skip if it's a pure number with currency symbol
            if re.match(r'^[₡\$]\d+', word):
                continue
                
            description_words.append(word)
        
        # Join the remaining words
        description = ' '.join(description_words).strip()
        
        # Remove prepositions that might remain at the start
        description = re.sub(r"^\s*(en|de|para|del|de\s+la|de\s+los|de\s+las)\s+", "", description, flags=re.IGNORECASE)
        
        # Clean up spaces and punctuation
        description = description.strip().strip(",").strip()
        
        # If description is reasonable length, return it
        if len(description) > 1 and len(description) < 100:
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
    
    def _handle_organization_creation(self, intent: Dict, message: str, user_id: str, db: Session, context: ConversationContext) -> Dict[str, Any]:
        """Handle organization creation"""
        from app.agents.organization_agent import OrganizationAgent
        
        org_agent = OrganizationAgent()
        return org_agent.process_organization_command(message, user_id, db)
    
    def _list_user_organizations(self, user_id: str, db: Session) -> Dict[str, Any]:
        """List user's organizations and memberships"""
        try:
            from app.services.organization_service import OrganizationService
            from app.services.user_service import UserService
            
            # Get user's organizations
            user_organizations = OrganizationService.get_user_organizations(db, user_id)
            user = UserService.get_user(db, user_id)
            
            if not user_organizations:
                return {
                    "success": True,
                    "message": "👤 **Solo tienes tu cuenta personal**\n\n💡 ¿Quieres crear una organización?\n• 'Crear familia Mi Hogar'\n• 'Crear empresa Mi Negocio'",
                    "action": "no_organizations"
                }
            
            # Build organization list
            org_list = ["🏷️ **Tus organizaciones:**\n"]
            
            for i, org in enumerate(user_organizations, 1):
                # Get emoji based on type
                if org.type.value == "family":
                    emoji = "👨‍👩‍👧‍👦"
                elif org.type.value == "company":
                    emoji = "🏢" 
                elif org.type.value == "team":
                    emoji = "👥"
                else:
                    emoji = "🏷️"
                
                # Get role
                membership = OrganizationService.get_user_membership(db, user_id, str(org.id))
                role_emoji = "👑" if membership.role.value == "owner" else "👤" if membership.role.value == "member" else "👀"
                
                org_list.append(f"{i}. {emoji} **{org.name}** {role_emoji}")
            
            org_list.append(f"\n👤 **Personal** (siempre disponible)")
            org_list.append(f"\n💡 **Tip:** Menciona el nombre para gastos específicos:\n• 'Gasto {user_organizations[0].name.lower()} gasolina 40000'")
            
            message = "\n".join(org_list)
            
            return {
                "success": True,
                "message": message,
                "action": "organizations_listed",
                "organization_count": len(user_organizations)
            }
            
        except Exception as e:
            print(f"Error listing organizations: {e}")
            return {
                "success": False,
                "message": "❌ No pude obtener tus organizaciones en este momento.",
                "action": "list_error"
            }
    
    def _handle_accept_invitation(self, user_id: str, db: Session) -> Dict[str, Any]:
        """Handle invitation acceptance"""
        from app.agents.organization_agent import OrganizationAgent
        
        org_agent = OrganizationAgent()
        return org_agent._handle_accept_invitation_natural(user_id, db)
    
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
• "Gasto familia gasolina 40000" - Con contexto

🏷️ **ORGANIZACIONES:**
• "En qué familias estoy" - Ver tus organizaciones
• "Mis organizaciones" - Lista completa
• "Crear familia Mi Hogar" - Nueva familia

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
            "message": f"🤔 No estoy seguro qué quieres hacer\n\n💡 **Puedes probar:**\n\n📊 'Crear presupuesto'\n💸 'Gasté ₡5000'\n🏷️ 'En qué familias estoy'\n📈 'Resumen'\n❓ 'Ayuda'\n\n¿Qué te gustaría hacer?",
            "action": "unclear_message",
            "suggestions": [
                "Crear presupuesto",
                "Gasté ₡5000",
                "En qué familias estoy",
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