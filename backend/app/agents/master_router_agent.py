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
                    backstory="""Eres el cerebro central del sistema Edcora Finanzas. 
                    
                    CONOCES PERFECTAMENTE TODO EL SISTEMA:
                    
                    ORGANIZACIONES:
                    - Crear: "crear familia", "nueva empresa", "hacer equipo"
                    - Invitar: "invitar +506...", "agregar mi esposa", "invita a mi hermano"
                    - Gestionar: "miembros", "acepto", "salir familia"
                    
                    TRANSACCIONES:
                    - Gastos: "gasté ₡5000", "4000 en almuerzo", "pagué 50 dólares"
                    - Contexto: Si usuario tiene múltiples organizaciones, SIEMPRE preguntar dónde va
                    - Formatos flexibles: "gaste 4000 en Gymgo", "agregar 5000 a empresa"
                    
                    REPORTES:
                    - "resumen", "cuánto gasté", "balance", "reporte familiar"
                    
                    AYUDA:
                    - "cómo", "ayuda", "no entiendo", "comandos"
                    
                    INVITACIONES:
                    - "acepto", "sí quiero unirme" = ACEPTAR INVITACIÓN (NO es transacción)
                    
                    TU TRABAJO:
                    1. ENTENDER la intención real del usuario
                    2. DETECTAR el contexto correcto (personal/familia/empresa)
                    3. MANEJAR casos especiales como "acepto", "agregar a empresa"
                    4. SER INTELIGENTE con formatos flexibles
                    
                    NUNCA CONFUNDAS:
                    - "acepto" = aceptar invitación, NO transacción
                    - "agregar 4000 a Gymgo" = gasto en empresa Gymgo
                    - "gaste en Gymgo" = gasto en contexto de empresa Gymgo
                    
                    Siempre das respuestas claras, contextuales y precisas.""",
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
                CONTEXTO COMPLETO DEL SISTEMA:
                {self.system_context[:3000]}
                
                CONTEXTO DEL USUARIO:
                {user_context}
                
                MENSAJE DEL USUARIO: "{message}"
                
                ANALIZA EL MENSAJE Y DETERMINA:
                
                1. TIPO DE ACCIÓN:
                   - "accept_invitation": "acepto", "sí quiero unirme" (NO ES TRANSACCIÓN)
                   - "create_organization": "crear familia", "nueva empresa", "agregar familia", "agregar empresa"
                   - "invite_member": "invitar", "agregar persona" (con nombre de persona)
                   - "list_members": "miembros", "quién está"
                   - "leave_organization": "salir", "abandonar"
                   - "create_transaction": gastos/ingresos ("gasté", "ingreso", "4000 en")
                   - "generate_report": "resumen", "cuánto", "balance"
                   - "privacy_request": "privacidad", "datos", "derechos", "seguridad", "eliminar cuenta"
                   - "help_request": "cómo", "ayuda", "no entiendo"
                
                2. PARÁMETROS ESPECÍFICOS:
                   Para transacciones:
                   - amount: cantidad numérica
                   - description: descripción del gasto
                   - organization_context: a qué organización va (si se especifica)
                   - transaction_type: "expense" o "income"
                   
                   Para organizaciones:
                   - organization_name: nombre de la organización
                   - person_to_invite: persona a invitar
                   - phone_number: número si se proporciona
                
                3. CASOS ESPECIALES:
                   - "acepto" = DEFINITIVAMENTE accept_invitation
                   - "agregar 4000 a Gymgo" = transacción de 4000 en contexto Gymgo
                   - "gaste 4000 en Gymgo" = transacción de 4000 en contexto Gymgo
                   - "agregar familia Campos Carranza" = create_organization con nombre "Campos Carranza"
                   - "crear empresa MiEmpresa" = create_organization con nombre "MiEmpresa"
                   - "invitar a mi esposa" = invite_member con persona "mi esposa"
                
                RESPONDE EN JSON:
                {{
                    "action_type": "tipo_de_acción",
                    "confidence": "alta/media/baja",
                    "parameters": {{
                        "amount": number_o_null,
                        "description": "descripción_o_null",
                        "organization_context": "organización_específica_o_null",
                        "transaction_type": "expense/income/null",
                        "organization_name": "nombre_org_o_null",
                        "person_to_invite": "persona_o_null",
                        "phone_number": "número_o_null"
                    }},
                    "reasoning": "explicación_breve_de_la_decisión"
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
        
        if action_type == "accept_invitation":
            return self._handle_accept_invitation(user_id, db)
        
        elif action_type == "create_transaction":
            return self._handle_smart_transaction(parameters, user_id, db)
        
        elif action_type == "create_organization":
            return self._handle_organization_action("create", parameters, user_id, db)
        
        elif action_type == "invite_member":
            return self._handle_organization_action("invite", parameters, user_id, db)
        
        elif action_type == "list_members":
            return self._handle_organization_action("list", parameters, user_id, db)
        
        elif action_type == "leave_organization":
            return self._handle_organization_action("leave", parameters, user_id, db)
        
        elif action_type == "generate_report":
            return self._handle_report_request(original_message, user_id, db)
        
        elif action_type == "privacy_request":
            return self._handle_privacy_request(original_message, user_id, db)
        
        elif action_type == "help_request":
            return self._handle_help_request(original_message, user_id, db)
        
        else:
            return {
                "success": False,
                "message": f"No pude entender tu mensaje: '{original_message}'. ¿Podrías ser más específico?",
                "action": "unknown"
            }
    
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
    
    def _handle_organization_action(self, action: str, parameters: Dict, user_id: str, db: Session) -> Dict[str, Any]:
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
            
            if phone_number:
                return org_agent._handle_invite_member_natural(phone_number, user_id, db)
            else:
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
        from app.agents.report_agent import ReportAgent
        report_agent = ReportAgent()
        
        # Get user currency
        from app.services.user_service import UserService
        user = UserService.get_user(db, user_id)
        currency_symbol = "₡" if user and user.currency == "CRC" else "$"
        
        return report_agent.generate_report(message, user_id, db, currency_symbol)
    
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
        """Fallback routing when AI is not available."""
        message_lower = message.lower().strip()
        
        # Accept invitation
        if any(word in message_lower for word in ["acepto", "aceptar", "quiero unirme"]):
            return self._handle_accept_invitation(user_id, db)
        
        # Create organization - Let the org agent handle name extraction intelligently
        elif any(phrase in message_lower for phrase in ["crear familia", "crear empresa", "nueva familia", "nueva empresa", "agregar familia", "agregar empresa"]):
            # Pass the full message to let OrganizationAgent extract the name intelligently
            from app.agents.organization_agent import OrganizationAgent
            org_agent = OrganizationAgent()
            # Use the organization agent's own intelligence to parse the message
            return org_agent.process_organization_command(message, user_id, db)
        
        # Transaction patterns
        elif any(phrase in message_lower for phrase in ["gasté", "gaste", "pagué", "pague", "compré", "compre"]) or any(char.isdigit() for char in message):
            # Try to extract amount
            import re
            amount_match = re.search(r"(\d+(?:\.\d+)?)", message)
            if amount_match:
                amount = float(amount_match.group(1))
                return self._handle_smart_transaction({
                    "amount": amount,
                    "description": message,
                    "organization_context": None,
                    "transaction_type": "expense"
                }, user_id, db)
        
        # Privacy requests
        elif any(word in message_lower for word in ["privacidad", "datos", "derechos", "seguridad", "eliminar cuenta", "privacy", "rights"]):
            return self._handle_privacy_request(message, user_id, db)
        
        # Help requests
        elif any(word in message_lower for word in ["ayuda", "help", "cómo", "como", "comandos"]):
            return self._handle_help_request(message, user_id, db)
        
        # Default
        return {
            "success": False,
            "message": "No entendí tu mensaje. Escribe 'ayuda' para ver los comandos disponibles.",
            "action": "unknown"
        }