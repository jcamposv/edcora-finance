from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from app.core.llm_config import get_openai_config
from crewai import Agent, Task, Crew
import json

class MasterRouterAgent:
    """
    Master intelligent router that understands ALL user intents and routes to specialized agents.
    This agent has complete knowledge of the system and makes smart routing decisions.
    """
    
    def __init__(self):
        try:
            self.has_openai = get_openai_config()
            
            if self.has_openai:
                self.agent = Agent(
                    role="Master Financial Assistant Router",
                    goal="Understand ANY user message perfectly and route it to the correct specialized agent or handle it directly with full system knowledge.",
                    backstory="""Eres un clasificador de intenciones que sigue reglas exactas.
                    
                    REGLA PRINCIPAL:
                    - "presupuesto" en el mensaje = manage_budgets (SIEMPRE)
                    - "familia/empresa/equipo" en el mensaje = create_organization
                    - Solo "crear" = unknown
                    
                    Respondes SOLO JSON, sin explicaciones adicionales.""",
                    verbose=True,
                    allow_delegation=False
                )
            else:
                self.agent = None
                
        except Exception as e:
            print(f"Warning: Failed to initialize MasterRouterAgent: {e}")
            self.has_openai = False
            self.agent = None
        
        # Load system context
        self.system_context = self._load_system_context()
    
    def _load_system_context(self) -> str:
        """Load complete system guide."""
        try:
            import os
            context_path = os.path.join(os.path.dirname(__file__), "../context/system_guide.md")
            with open(context_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            print(f"Warning: Could not load system context: {e}")
            return ""
    
    def route_and_process(self, message: str, user_id: str, db: Session) -> Dict[str, Any]:
        """
        Master method that analyzes ANY message and processes it intelligently.
        This replaces the fragmented routing in the WhatsApp router.
        """
        
        if self.has_openai and self.agent:
            return self._ai_route_and_process(message, user_id, db)
        else:
            return self._fallback_route_and_process(message, user_id, db)
    
    def _ai_route_and_process(self, message: str, user_id: str, db: Session) -> Dict[str, Any]:
        """Use AI to understand intent and process accordingly."""
        try:
            # Get user context
            from app.services.user_service import UserService
            from app.services.organization_service import OrganizationService
            
            user = UserService.get_user(db, user_id)
            user_organizations = OrganizationService.get_user_organizations(db, user_id) if user else []
            pending_invitations = OrganizationService.get_pending_invitations_for_phone(db, user.phone_number) if user else []
            
            user_context = f"""
            USUARIO ACTUAL:
            - Teléfono: {user.phone_number if user else 'N/A'}
            - Moneda: {user.currency if user else 'CRC'}
            - Organizaciones: {len(user_organizations)} ({[f"{org.name} ({org.type.value})" for org in user_organizations]})
            - Invitaciones pendientes: {len(pending_invitations)}
            """
            
            task = Task(
                description=f"""
                USUARIO: {user_context}
                MENSAJE: "{message}"
                
                REGLAS CRÍTICAS (SEGUIR EXACTAMENTE):
                
                1. Si el mensaje contiene "presupuesto" o "budget" → SIEMPRE "manage_budgets"
                2. Si el mensaje contiene "familia" o "empresa" o "equipo" → "create_organization"  
                3. Si el mensaje es solo "crear" → "unknown" (para que pregunte qué crear)
                4. Si contiene "acepto" → "accept_invitation"
                5. Si contiene "gasté" o números con ₡ → "create_transaction"
                6. Si contiene "resumen" o "reporte" → "generate_report"
                
                EJEMPLOS EXACTOS:
                - "crear presupuesto" → manage_budgets
                - "crear presupuesto 10000" → manage_budgets  
                - "presupuesto comida" → manage_budgets
                - "crear familia" → create_organization
                - "crear empresa" → create_organization
                - "crear" → unknown
                - "acepto" → accept_invitation
                
                TIPOS DE ACCIÓN VÁLIDOS:
                - accept_invitation
                - create_organization  
                - invite_member
                - list_members
                - leave_organization
                - create_transaction
                - generate_report
                - manage_transactions
                - manage_budgets
                - privacy_request
                - help_request
                - unknown
                
                RESPONDE SOLO JSON SIN TEXTO ADICIONAL:
                {{
                    "action_type": "una_de_las_acciones_válidas",
                    "confidence": "alta",
                    "parameters": {{
                        "amount": extraer_número_o_null,
                        "budget_category": extraer_categoría_o_null,
                        "organization_name": extraer_nombre_org_o_null
                    }}
                }}
                """,
                agent=self.agent,
                expected_output="JSON con análisis completo de la intención"
            )
            
            crew = Crew(agents=[self.agent], tasks=[task])
            result = str(crew.kickoff()).strip()
            
            print(f"🤖 AI Raw Response: {result}")
            
            # Parse AI response
            try:
                # Try to extract JSON from response if it has extra text
                import re
                json_match = re.search(r'\{.*\}', result, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                    analysis = json.loads(json_str)
                else:
                    analysis = json.loads(result)
                
                print(f"🧠 AI Parsed Analysis: {analysis}")
                return self._execute_analyzed_action(analysis, message, user_id, db)
            except json.JSONDecodeError as e:
                print(f"❌ Failed to parse AI response: {result}")
                print(f"❌ JSON Error: {e}")
                return self._fallback_route_and_process(message, user_id, db)
                
        except Exception as e:
            print(f"Error in AI routing: {e}")
            return self._fallback_route_and_process(message, user_id, db)
    
    def _execute_analyzed_action(self, analysis: Dict, original_message: str, user_id: str, db: Session) -> Dict[str, Any]:
        """Execute the action based on AI analysis."""
        action_type = analysis.get("action_type", "unknown")
        parameters = analysis.get("parameters", {})
        reasoning = analysis.get("reasoning", "")
        
        print(f"🧠 AI Analysis: {action_type} - {reasoning}")
        
        # Special debug for report requests
        if "resumen" in original_message.lower() or "reporte" in original_message.lower() or "balance" in original_message.lower():
            print(f"🔍 REPORT DEBUG: Message '{original_message}' detected as '{action_type}'")
        
        if action_type == "accept_invitation":
            return self._handle_accept_invitation(user_id, db)
        
        elif action_type == "create_transaction":
            return self._handle_smart_transaction(parameters, user_id, db)
        
        elif action_type == "create_organization":
            return self._handle_organization_action("create", parameters, user_id, db, original_message)
        
        elif action_type == "invite_member":
            return self._handle_organization_action("invite", parameters, user_id, db, original_message)
        
        elif action_type == "list_members":
            return self._handle_organization_action("list", parameters, user_id, db, original_message)
        
        elif action_type == "leave_organization":
            return self._handle_organization_action("leave", parameters, user_id, db, original_message)
        
        elif action_type == "generate_report":
            return self._handle_report_request(original_message, user_id, db)
        
        elif action_type == "manage_transactions":
            return self._handle_transaction_management(original_message, user_id, db)
        
        elif action_type == "manage_budgets":
            return self._handle_budget_management(parameters, original_message, user_id, db)
        
        elif action_type == "privacy_request":
            return self._handle_privacy_request(original_message, user_id, db)
        
        elif action_type == "help_request":
            return self._handle_help_request(original_message, user_id, db)
        
        elif action_type == "unknown":
            # Handle ambiguous commands with disambiguation agent
            return self._handle_ambiguous_command(original_message, user_id, db)
        
        else:
            # Handle ambiguous commands with disambiguation agent
            return self._handle_ambiguous_command(original_message, user_id, db)
    
    def _handle_accept_invitation(self, user_id: str, db: Session) -> Dict[str, Any]:
        """Handle invitation acceptance."""
        from app.agents.organization_agent import OrganizationAgent
        org_agent = OrganizationAgent()
        return org_agent._handle_accept_invitation_natural(user_id, db)
    
    def _handle_smart_transaction(self, parameters: Dict, user_id: str, db: Session) -> Dict[str, Any]:
        """Handle transaction creation with smart context detection."""
        amount = parameters.get("amount")
        description = parameters.get("description", "")
        org_context = parameters.get("organization_context")
        transaction_type = parameters.get("transaction_type", "expense")
        
        if not amount:
            return {
                "success": False,
                "message": "No pude identificar el monto. Intenta: 'gasté ₡5000 en almuerzo'",
                "action": "parse_error"
            }
        
        # Get user and organizations for context
        from app.services.user_service import UserService
        from app.services.organization_service import OrganizationService
        
        user = UserService.get_user(db, user_id)
        user_organizations = OrganizationService.get_user_organizations(db, user_id) if user else []
        
        # If specific organization context mentioned, try to find it
        target_organization_id = None
        if org_context:
            for org in user_organizations:
                if org_context.lower() in org.name.lower():
                    target_organization_id = str(org.id)
                    break
        
        # Create transaction
        from app.core.schemas import TransactionCreate
        from app.services.transaction_service import TransactionService
        from app.models.transaction import TransactionType
        
        # Auto-categorize if no description
        if not description:
            description = org_context if org_context else "Gasto general"
        
        transaction_data = TransactionCreate(
            user_id=user_id,
            organization_id=target_organization_id,
            amount=float(amount),
            type=TransactionType.expense if transaction_type == "expense" else TransactionType.income,
            category="Empresa" if org_context else "General",
            description=description
        )
        
        transaction = TransactionService.create_transaction(db, transaction_data)
        
        # Format response
        currency_symbol = "₡" if user and user.currency == "CRC" else "$"
        org_text = f" en {org_context}" if org_context else ""
        
        return {
            "success": True,
            "message": f"✅ Registrado {transaction_type} de {currency_symbol}{amount:,.0f}{org_text} en {transaction.category}",
            "action": "transaction_created",
            "transaction_id": str(transaction.id)
        }
    
    def _handle_organization_action(self, action: str, parameters: Dict, user_id: str, db: Session, original_message: str = "") -> Dict[str, Any]:
        """Handle organization actions directly."""
        from app.agents.organization_agent import OrganizationAgent
        org_agent = OrganizationAgent()
        
        if action == "create":
            organization_name = parameters.get("organization_name")
            if organization_name:
                return org_agent._handle_create_organization_natural(organization_name, user_id, db)
            else:
                return org_agent._ask_for_organization_name()
        
        elif action == "invite":
            phone_number = parameters.get("phone_number")
            person_to_invite = parameters.get("person_to_invite", "")
            
            # If AI didn't detect phone, try manual extraction
            if not phone_number and original_message:
                # Get original message to try pattern matching
                import re
                original_msg = original_message
                phone_patterns = [
                    r"(\+506\s?\d{4}\s?\d{4})",  # +506 1234 5678
                    r"(\+506\d{8})",            # +50612345678
                    r"(506\s?\d{4}\s?\d{4})",   # 506 1234 5678
                    r"(506\d{8})",              # 50612345678
                    r"(\d{4}[-\s]?\d{4})",      # 1234-5678 or 1234 5678
                    r"(\+\d{1,3}\d{8,})"       # Generic international
                ]
                
                for pattern in phone_patterns:
                    match = re.search(pattern, original_msg)
                    if match:
                        number = match.group(1)
                        # Normalize the number
                        if not number.startswith('+'):
                            if number.startswith('506'):
                                phone_number = '+' + number
                            else:
                                # Assume Costa Rica if no country code
                                phone_number = '+506' + number.replace('-', '').replace(' ', '')
                        else:
                            phone_number = number.replace(' ', '').replace('-', '')
                        break
            
            if phone_number:
                print(f"📞 Phone detected: {phone_number}")
                return org_agent._handle_invite_member_natural(phone_number, user_id, db)
            else:
                print(f"👤 No phone, asking for phone with context: {person_to_invite}")
                return org_agent._ask_for_phone_number_with_context(person_to_invite)
        
        elif action == "list":
            return org_agent._handle_list_members_natural(user_id, db)
        
        elif action == "leave":
            return org_agent._handle_leave_organization_natural(user_id, db)
        
        else:
            return {
                "success": False,
                "message": f"Acción de organización '{action}' no reconocida",
                "action": f"organization_{action}"
            }
    
    def _handle_report_request(self, message: str, user_id: str, db: Session) -> Dict[str, Any]:
        """Route to report agent."""
        print(f"📊 Handling report request: {message}")
        from app.agents.report_agent import ReportAgent
        report_agent = ReportAgent()
        
        # Get user currency
        from app.services.user_service import UserService
        user = UserService.get_user(db, user_id)
        currency_symbol = "₡" if user and user.currency == "CRC" else "$"
        
        print(f"💰 User currency: {user.currency if user else 'None'}, symbol: {currency_symbol}")
        
        result = report_agent.generate_report(message, user_id, db, currency_symbol)
        print(f"📈 Report result: {result.get('success', False)}")
        
        return result
    
    def _handle_transaction_management(self, message: str, user_id: str, db: Session) -> Dict[str, Any]:
        """Route to transaction manager agent."""
        print(f"🔧 Handling transaction management: {message}")
        from app.agents.transaction_manager_agent import TransactionManagerAgent
        
        transaction_manager = TransactionManagerAgent()
        result = transaction_manager.handle_transaction_management(message, user_id, db)
        print(f"🔧 Transaction management result: {result.get('success', False)}")
        
        return result
    
    def _handle_budget_management(self, parameters: Dict, message: str, user_id: str, db: Session) -> Dict[str, Any]:
        """Handle budget creation and management."""
        print(f"💰 Handling budget management: {message}")
        
        budget_name = parameters.get("budget_name")
        budget_amount = parameters.get("budget_amount") or parameters.get("amount")
        budget_category = parameters.get("budget_category", "General")
        budget_period = parameters.get("budget_period", "monthly")
        alert_percentage = parameters.get("alert_percentage", 80.0)
        
        # If no amount detected, prompt user
        if not budget_amount:
            # Try to extract category from the message for better prompting
            if budget_category == "General":
                # Try to extract category from message
                message_lower = message.lower()
                if "comida" in message_lower or "comidas" in message_lower:
                    budget_category = "Comida"
                elif "gasolina" in message_lower:
                    budget_category = "Gasolina"
                elif "entretenimiento" in message_lower:
                    budget_category = "Entretenimiento"
                else:
                    # Try to extract after "presupuesto"
                    words = message.split()
                    for i, word in enumerate(words):
                        if "presupuesto" in word.lower() and i + 1 < len(words):
                            next_word = words[i + 1]
                            if next_word.lower() not in ["para", "de", "mensual", "semanal", "anual"]:
                                budget_category = next_word.title()
                                break
            
            return {
                "success": False,
                "message": f"💰 ¿Cuál es el límite de tu presupuesto para {budget_category}?\n\nEjemplo: 'Presupuesto de ₡100000 para {budget_category.lower()}'",
                "action": "budget_amount_needed",
                "suggested_category": budget_category
            }
        
        try:
            from app.services.budget_service import BudgetService
            from app.services.user_service import UserService
            from app.core.schemas import BudgetCreate
            from app.models.budget import BudgetPeriod, BudgetStatus
            from datetime import datetime, timedelta
            import calendar
            
            user = UserService.get_user(db, user_id)
            
            # Ensure we have a valid category
            if not budget_category or budget_category == "General":
                budget_category = "General"
            
            # Calculate period dates
            start_date = datetime.now()
            if budget_period == "weekly":
                end_date = start_date + timedelta(days=7)
                period_enum = BudgetPeriod.weekly
            elif budget_period == "yearly":
                end_date = start_date.replace(year=start_date.year + 1)
                period_enum = BudgetPeriod.yearly
            else:  # monthly (default)
                # Get last day of current month
                last_day = calendar.monthrange(start_date.year, start_date.month)[1]
                end_date = start_date.replace(day=last_day)
                period_enum = BudgetPeriod.monthly
            
            # Auto-generate name if not provided
            if not budget_name:
                period_text = {"weekly": "Semanal", "monthly": "Mensual", "yearly": "Anual"}[budget_period]
                budget_name = f"Presupuesto {period_text} - {budget_category}"
            
            budget_data = BudgetCreate(
                user_id=user_id,
                organization_id=None,  # Personal budget for now
                name=budget_name,
                category=str(budget_category),  # Ensure it's a string
                amount=float(budget_amount),
                period=period_enum,
                start_date=start_date,
                end_date=end_date,
                status=BudgetStatus.active,
                alert_percentage=float(alert_percentage),
                auto_renew=False
            )
            
            budget_service = BudgetService(db)
            budget = budget_service.create_budget(budget_data)
            
            # Format response
            currency_symbol = "₡" if user and user.currency == "CRC" else "$"
            period_text = {"weekly": "semanal", "monthly": "mensual", "yearly": "anual"}[budget_period]
            
            return {
                "success": True,
                "message": f"✅ Presupuesto creado: '{budget_name}' - {currency_symbol}{budget_amount:,.0f} {period_text}\n📊 Categoría: {budget_category}\n🚨 Alerta al {alert_percentage}%",
                "action": "budget_created",
                "budget_id": str(budget.id)
            }
            
        except Exception as e:
            print(f"Error creating budget: {e}")
            return {
                "success": False,
                "message": f"Error al crear el presupuesto: {str(e)}",
                "action": "budget_error"
            }
    
    def _handle_privacy_request(self, message: str, user_id: str, db: Session) -> Dict[str, Any]:
        """Route to privacy agent."""
        from app.agents.privacy_agent import PrivacyAgent
        privacy_agent = PrivacyAgent()
        return privacy_agent.handle_privacy_inquiry(message, user_id, db)
    
    def _handle_help_request(self, message: str, user_id: str, db: Session) -> Dict[str, Any]:
        """Route to help agent."""
        from app.agents.help_agent import HelpAgent
        help_agent = HelpAgent()
        return help_agent.answer_question(message, user_id, db)
    
    def _fallback_route_and_process(self, message: str, user_id: str, db: Session) -> Dict[str, Any]:
        """Smart fallback routing using intent classifier when AI is not available."""
        from app.core.intent_classifier import IntentClassifier
        
        classifier = IntentClassifier()
        intent_match = classifier.classify_intent(message)
        
        if not intent_match:
            return {
                "success": False,
                "message": "No entendí tu mensaje. Escribe 'ayuda' para ver los comandos disponibles.",
                "action": "unknown"
            }
        
        print(f"🎯 Intent classified: {intent_match.action_type} (confidence: {intent_match.confidence:.2f}, priority: {intent_match.priority})")
        print(f"📋 Parameters: {intent_match.parameters}")
        
        # Route to appropriate handler based on classified intent
        return self._execute_classified_action(intent_match, message, user_id, db)
    
    def _execute_classified_action(self, intent_match, original_message: str, user_id: str, db: Session) -> Dict[str, Any]:
        """Execute action based on classified intent"""
        action_type = intent_match.action_type
        parameters = intent_match.parameters
        
        if action_type == "accept_invitation":
            return self._handle_accept_invitation(user_id, db)
        
        elif action_type == "create_transaction":
            return self._handle_smart_transaction(parameters, user_id, db)
        
        elif action_type == "create_organization":
            return self._handle_organization_action("create", parameters, user_id, db, original_message)
        
        elif action_type == "invite_member":
            return self._handle_organization_action("invite", parameters, user_id, db, original_message)
        
        elif action_type == "list_members":
            return self._handle_organization_action("list", parameters, user_id, db, original_message)
        
        elif action_type == "leave_organization":
            return self._handle_organization_action("leave", parameters, user_id, db, original_message)
        
        elif action_type == "generate_report":
            return self._handle_report_request(original_message, user_id, db)
        
        elif action_type == "manage_transactions":
            return self._handle_transaction_management(original_message, user_id, db)
        
        elif action_type == "manage_budgets":
            return self._handle_budget_management(parameters, original_message, user_id, db)
        
        elif action_type == "privacy_request":
            return self._handle_privacy_request(original_message, user_id, db)
        
        elif action_type == "help_request":
            return self._handle_help_request(original_message, user_id, db)
        
        else:
            return self._handle_ambiguous_command(original_message, user_id, db)
    
    def _handle_ambiguous_command(self, message: str, user_id: str, db: Session) -> Dict[str, Any]:
        """Handle ambiguous or unknown commands using disambiguation agent"""
        from app.agents.disambiguation_agent import DisambiguationAgent
        
        disambiguation_agent = DisambiguationAgent()
        
        # Check for ambiguous "crear" commands
        if "crear" in message.lower():
            return disambiguation_agent.handle_ambiguous_create(message, user_id, db)
        
        # Handle other unknown commands
        return disambiguation_agent._handle_unknown_command(message)