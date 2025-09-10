from typing import Dict, Any
from sqlalchemy.orm import Session
from app.core.llm_config import get_openai_config
from crewai import Agent, Task, Crew
import json

class HelpAgent:
    """Intelligent help agent that answers user questions about system functionality."""
    
    def __init__(self):
        try:
            # Setup OpenAI environment
            self.has_openai = get_openai_config()
            
            if self.has_openai:
                self.agent = Agent(
                    role="Sistema de Ayuda Inteligente",
                    goal="Ayudar a usuarios a entender cómo usar el sistema de finanzas, respondiendo preguntas sobre comandos, funcionalidades y casos de uso específicos.",
                    backstory="""Eres un asistente experto en el sistema de finanzas Edcora. 
                    Conoces todas las funcionalidades:
                    
                    ORGANIZACIONES:
                    - Crear: 'crear familia Mi Hogar', 'crear empresa Gymgo', 'crear equipo Ventas'
                    - Invitar: 'invitar +50612345678', 'invitar +50612345678 admin'
                    - Ver miembros: 'miembros', 'quiénes están', 'mostrar miembros'
                    - Aceptar invitación: 'acepto', 'sí quiero unirme'
                    - Salirse: 'salir de la familia', 'abandonar empresa'
                    
                    ROLES DISPONIBLES:
                    - owner: Propietario (máximo control)
                    - admin: Administrador (puede invitar/remover)
                    - manager: Gerente (puede ver reportes detallados)
                    - member: Miembro (puede agregar gastos)
                    - viewer: Observador (solo ve reportes)
                    
                    TRANSACCIONES:
                    - Gastos: 'gasté ₡5000 en almuerzo', '₡10000 gasolina'
                    - Ingresos: 'ingreso ₡50000 salario', 'recibí ₡5000'
                    - Con contexto: El sistema pregunta a qué organización va si tienes varias
                    
                    REPORTES:
                    - 'resumen de gastos', 'cuánto he gastado hoy'
                    - 'balance del mes', 'gastos de esta semana'
                    - 'reporte familiar', 'gastos de empresa'
                    
                    Respondes en español de forma clara y práctica, con ejemplos específicos.""",
                    verbose=True,
                    allow_delegation=False
                )
            else:
                self.agent = None
                
        except Exception as e:
            print(f"Warning: Failed to initialize HelpAgent: {e}")
            self.has_openai = False
            self.agent = None
            
        # Help keywords for detection
        self.help_keywords = [
            "cómo", "como", "how", "ayuda", "help", "qué puedo", "que puedo",
            "comandos", "commands", "funciones", "features", "manual", "instrucciones",
            "no sé", "no se", "don't know", "confused", "perdido", "lost",
            "tutorial", "guía", "guide", "explicar", "explain"
        ]
    
    def is_help_request(self, message: str) -> bool:
        """Detect if a message is asking for help."""
        message_lower = message.lower()
        
        # Direct help requests
        if any(keyword in message_lower for keyword in self.help_keywords):
            return True
            
        # Question patterns
        question_patterns = [
            "¿cómo", "¿como", "¿qué", "¿que", "¿dónde", "¿donde",
            "¿cuándo", "¿cuando", "¿por qué", "¿porque"
        ]
        
        if any(pattern in message_lower for pattern in question_patterns):
            return True
            
        return False
    
    def answer_question(self, question: str, user_id: str, db: Session) -> Dict[str, Any]:
        """Answer user's question about system functionality."""
        
        if self.has_openai and self.agent:
            return self._ai_answer_question(question, user_id, db)
        else:
            return self._fallback_help_response(question)
    
    def _ai_answer_question(self, question: str, user_id: str, db: Session) -> Dict[str, Any]:
        """Use AI to provide contextual help based on user's question."""
        try:
            # Get user context to provide personalized help
            from app.services.user_service import UserService
            from app.services.organization_service import OrganizationService
            
            user = UserService.get_user(db, user_id)
            user_organizations = OrganizationService.get_user_organizations(db, user_id) if user else []
            
            user_context = f"""
            Usuario actual:
            - Moneda: {user.currency if user else 'USD'}
            - Organizaciones: {len(user_organizations)} organizaciones
            - Tipos de organizaciones: {[org.type.value for org in user_organizations] if user_organizations else 'ninguna'}
            """
            
            task = Task(
                description=f"""
                El usuario pregunta: "{question}"
                
                Contexto del usuario:
                {user_context}
                
                Proporciona una respuesta clara y práctica sobre cómo usar el sistema de finanzas Edcora.
                
                IMPORTANTE: Incluye ejemplos específicos usando la moneda del usuario y su contexto.
                
                Si la pregunta es sobre:
                
                ORGANIZACIONES:
                - Crear: Explica cómo crear familias, empresas, equipos con ejemplos
                - Invitar: Explica roles (admin, member, viewer) y cómo invitar con ejemplos de números
                - Salirse: Explica cómo abandonar organizaciones
                - Ver miembros: Explica comandos para ver quién está
                
                TRANSACCIONES:
                - Gastos: Muestra formatos como 'gasté ₡5000 en almuerzo'
                - Ingresos: Muestra formatos como 'ingreso ₡50000 salario'
                - Contexto: Explica cómo el sistema pregunta a qué organización va el gasto
                
                REPORTES:
                - Explica comandos como 'resumen de gastos', 'balance del mes'
                - Diferencia entre reportes personales y organizacionales
                
                ROLES:
                - Explica diferencias entre owner, admin, manager, member, viewer
                
                Responde de forma conversacional en español, con ejemplos prácticos y pasos específicos.
                Máximo 500 caracteres para WhatsApp.
                """,
                agent=self.agent,
                expected_output="Respuesta clara y práctica con ejemplos específicos en español"
            )
            
            crew = Crew(
                agents=[self.agent],
                tasks=[task],
                verbose=False
            )
            
            result = crew.kickoff()
            
            return {
                "success": True,
                "message": str(result).strip(),
                "type": "help_response"
            }
            
        except Exception as e:
            print(f"HelpAgent AI failed: {e}")
            return self._fallback_help_response(question)
    
    def _fallback_help_response(self, question: str) -> Dict[str, Any]:
        """Fallback help responses when AI is not available."""
        question_lower = question.lower()
        
        # Organization-related help
        if any(word in question_lower for word in ["crear", "create", "nueva", "nuevo"]):
            if any(word in question_lower for word in ["empresa", "company"]):
                return {
                    "success": True,
                    "message": "🏢 **Crear Empresa:**\n\n• Crear empresa: Gymgo\n• Nueva empresa: Mi Startup\n\n¡Serás el propietario! 👑",
                    "type": "help_response"
                }
            elif any(word in question_lower for word in ["familia", "family"]):
                return {
                    "success": True,
                    "message": "👨‍👩‍👧‍👦 **Crear Familia:**\n\n• Crear familia: Los García\n• Nueva familia: Mi Hogar\n\n¡Serás el propietario! 👑",
                    "type": "help_response"
                }
            else:
                return {
                    "success": True,
                    "message": "🆕 **Crear Organizaciones:**\n\n• Crear familia: Mi Hogar\n• Crear empresa: Gymgo\n• Crear equipo: Ventas\n\n¡Automático serás el propietario! 👑",
                    "type": "help_response"
                }
        
        # Invitation-related help
        elif any(word in question_lower for word in ["invitar", "invite", "agregar", "colega", "rol", "role"]):
            return {
                "success": True,
                "message": "👥 **Invitar Miembros:**\n\n• Invitar +50612345678\n• Invitar +50612345678 admin\n• Invitar +50612345678 viewer\n\n**Roles:** admin, member, viewer\n\nSolo propietarios/admins pueden invitar.",
                "type": "help_response"
            }
        
        # Leaving organization help
        elif any(word in question_lower for word in ["salir", "leave", "abandonar", "irse"]):
            return {
                "success": True,
                "message": "🚪 **Salir de Organización:**\n\n• 'Me quiero salir de la familia'\n• 'Abandonar empresa'\n• 'Ya no quiero estar'\n\nTus gastos personales seguirán siendo privados.",
                "type": "help_response"
            }
        
        # Transaction help
        elif any(word in question_lower for word in ["gasto", "expense", "ingreso", "income", "transacción"]):
            return {
                "success": True,
                "message": "💰 **Registrar Transacciones:**\n\n**Gastos:**\n• Gasté ₡5000 en almuerzo\n• ₡10000 gasolina\n\n**Ingresos:**\n• Ingreso ₡50000 salario\n• Recibí ₡5000\n\nSi tienes varias organizaciones, el sistema preguntará a cuál va.",
                "type": "help_response"
            }
        
        # Reports help
        elif any(word in question_lower for word in ["resumen", "reporte", "balance", "cuánto", "cuanto"]):
            return {
                "success": True,
                "message": "📊 **Reportes:**\n\n**Personales:**\n• Resumen de gastos\n• Cuánto he gastado hoy\n• Balance del mes\n\n**Organizacionales:**\n• Reporte familiar\n• Gastos de empresa\n• Resumen familiar",
                "type": "help_response"
            }
        
        # Members help
        elif any(word in question_lower for word in ["miembros", "members", "quién", "quien"]):
            return {
                "success": True,
                "message": "👥 **Ver Miembros:**\n\n• Miembros\n• ¿Quiénes están?\n• Mostrar miembros\n• Ver familia\n\n**Roles:**\n👑 Owner - Control total\n⚡ Admin - Puede invitar\n👤 Member - Agregar gastos\n👁️ Viewer - Solo ver reportes",
                "type": "help_response"
            }
        
        # Accept invitation help
        elif any(word in question_lower for word in ["aceptar", "accept", "invitación", "invitation"]):
            return {
                "success": True,
                "message": "✅ **Aceptar Invitaciones:**\n\n• Acepto\n• Sí quiero unirme\n• Aceptar invitación\n\nUna vez aceptada, tus gastos aparecerán en los reportes organizacionales.",
                "type": "help_response"
            }
        
        # General help
        else:
            return {
                "success": True,
                "message": self._get_general_help(),
                "type": "help_response"
            }
    
    def _get_general_help(self) -> str:
        """Provide general system help."""
        return """🤖 **Edcora Finanzas - Ayuda**

🏢 **Organizaciones:**
• Crear familia: Mi Hogar
• Crear empresa: Gymgo
• Invitar +50612345678 admin

💰 **Transacciones:**
• Gasté ₡5000 en almuerzo
• Ingreso ₡50000 salario

📊 **Reportes:**
• Resumen de gastos
• Balance del mes
• Reporte familiar

👥 **Miembros:**
• Miembros (ver quién está)
• Acepto (aceptar invitación)
• Salir familia (abandonar)

❓ Pregúntame sobre cualquier función específica!"""

    def get_contextual_help(self, user_id: str, db: Session) -> Dict[str, Any]:
        """Provide contextual help based on user's current state."""
        try:
            from app.services.user_service import UserService
            from app.services.organization_service import OrganizationService
            
            user = UserService.get_user(db, user_id)
            if not user:
                return {
                    "success": True,
                    "message": "¡Hola! Soy tu asistente de Edcora Finanzas. ¿En qué te puedo ayudar? 😊",
                    "type": "contextual_help"
                }
            
            user_organizations = OrganizationService.get_user_organizations(db, user_id)
            pending_invitations = OrganizationService.get_pending_invitations_for_phone(db, user.phone_number)
            
            if pending_invitations:
                return {
                    "success": True,
                    "message": f"👋 ¡Tienes {len(pending_invitations)} invitación(es) pendiente(s)!\n\nEscribe 'acepto' para unirte o pregúntame '¿cómo acepto invitaciones?' para más ayuda.",
                    "type": "contextual_help"
                }
            elif not user_organizations:
                return {
                    "success": True,
                    "message": "👋 ¡Hola! Aún no tienes organizaciones.\n\n¿Quieres crear una? Pregúntame:\n• '¿Cómo creo una familia?'\n• '¿Cómo creo una empresa?'\n\nO simplemente di 'crear familia Mi Hogar' 😊",
                    "type": "contextual_help"
                }
            else:
                org_types = [org.type.value for org in user_organizations]
                return {
                    "success": True,
                    "message": f"👋 ¡Hola! Tienes {len(user_organizations)} organización(es): {', '.join(set(org_types))}.\n\n¿Necesitas ayuda con:\n• Agregar gastos\n• Invitar miembros\n• Ver reportes\n\n¡Pregúntame lo que necesites! 😊",
                    "type": "contextual_help"
                }
                
        except Exception as e:
            print(f"Error getting contextual help: {e}")
            return {
                "success": True,
                "message": "¡Hola! Soy tu asistente de Edcora Finanzas. ¿En qué te puedo ayudar? 😊",
                "type": "contextual_help"
            }