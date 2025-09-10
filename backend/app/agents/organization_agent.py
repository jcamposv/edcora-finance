from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from app.services.organization_service import OrganizationService
from app.services.user_service import UserService
from app.models.organization import OrganizationType, OrganizationRole
from app.core.llm_config import get_openai_config
from crewai import Agent, Task, Crew
import re
import json

class OrganizationAgent:
    """Intelligent agent to handle organization-related conversations in natural language."""
    
    def __init__(self):
        try:
            # Setup OpenAI environment
            self.has_openai = get_openai_config()
            
            if self.has_openai:
                self.agent = Agent(
                    role="Organization Financial Assistant",
                    goal="Help users manage organization finances through natural conversation in Spanish. Understand organization requests, invitations, and management in a human-like way.",
                    backstory="""Eres un asistente financiero organizacional que habla español de forma natural y amigable. 
                    Entiendes cuando las personas quieren:
                    - Crear una organización para compartir gastos (familia, equipo, empresa)
                    - Invitar miembros a organizaciones
                    - Ver quién está en sus organizaciones
                    - Salirse de organizaciones
                    - Manejar permisos de organizaciones
                    
                    Respondes de forma conversacional, como si fueras un amigo que ayuda con las finanzas organizacionales.
                    Siempre eres positivo, claro y das ejemplos prácticos.""",
                    verbose=True,
                    allow_delegation=False
                )
            else:
                self.agent = None
                
        except Exception as e:
            print(f"Warning: Failed to initialize OrganizationAgent: {e}")
            self.has_openai = False
            self.agent = None
            
        # Fallback keywords for regex detection
        self.organization_keywords = [
            "familia", "family", "familiares", "compartir gastos", "crear familia", "nueva familia",
            "empresa", "company", "negocio", "corporación", "crear empresa", "nueva empresa",
            "equipo", "team", "grupo", "departamento", "crear equipo", "nuevo equipo",
            "organizacion", "organización", "crear organizacion", "nueva organizacion",
            "invitar", "invite", "agregar", "roommate", "compañero", "esposa", "esposo",
            "hermana", "hermano", "colega", "empleado", "socio", "mi esposa", "mi hermano",
            "miembros", "members", "quienes", "quien esta", "mostrar miembros",
            "salir", "leave", "abandonar", "irse", "irme", "dejar",
            "en que", "que familia", "cual", "a que", "pertenezco", "estoy en",
            "aceptar", "acepto", "unirme", "quiero unirme"
        ]
        
        # Load system context
        self.system_context = self._load_system_context()
    
    def _load_system_context(self) -> str:
        """Load system guide for enhanced AI context."""
        try:
            import os
            context_path = os.path.join(os.path.dirname(__file__), "../context/system_guide.md")
            with open(context_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            print(f"Warning: Could not load system context: {e}")
            return ""
    
    def is_organization_command(self, message: str) -> bool:
        """Detect if a message is organization-related using AI or fallback keywords."""
        if self.has_openai and self.agent:
            return self._ai_detect_organization_intent(message)
        else:
            # Fallback: keyword detection
            message_lower = message.lower()
            return any(keyword in message_lower for keyword in self.organization_keywords)
    
    def _ai_detect_organization_intent(self, message: str) -> bool:
        """Use AI to detect if message is about organization management."""
        try:
            task = Task(
                description=f"""
                Usa esta guía del sistema para determinar si el mensaje es sobre organizaciones:
                
                {self.system_context[:1000]}  # Primeros 1000 chars para no sobrecargar
                
                Analiza este mensaje: "{message}"
                
                El mensaje ES sobre organizaciones si menciona:
                - Crear organizaciones: "crear familia", "nueva empresa", "hacer equipo"
                - Invitar personas: "invitar a mi esposa", "agregar colega", "invita a mi hermano"
                - Gestión de miembros: "miembros", "quién está", "mostrar miembros"
                - Aceptar invitaciones: "acepto", "quiero unirme"
                - Salir de organizaciones: "salir familia", "abandonar empresa"
                
                IMPORTANTE: "crear familia" = SÍ es comando de organización
                IMPORTANTE: "invitar a mi esposa" = SÍ es comando de organización
                
                Responde solo con "true" o "false".
                """,
                agent=self.agent,
                expected_output="true o false"
            )
            
            crew = Crew(agents=[self.agent], tasks=[task])
            result = crew.kickoff()
            
            return str(result).strip().lower() == "true"
            
        except Exception as e:
            print(f"Error in AI organization intent detection: {e}")
            # Fallback to keyword detection
            message_lower = message.lower()
            return any(keyword in message_lower for keyword in self.organization_keywords)
    
    def process_organization_command(self, message: str, user_id: str, db: Session) -> Dict[str, Any]:
        """Process organization-related conversations using AI for natural language understanding."""
        
        if self.has_openai and self.agent:
            return self._ai_process_organization_conversation(message, user_id, db)
        else:
            # Fallback to command-based system
            return self._fallback_process_organization_command(message, user_id, db)
    
    def _ai_process_organization_conversation(self, message: str, user_id: str, db: Session) -> Dict[str, Any]:
        """Process organization conversation using AI to understand intent."""
        try:
            # Get current user context
            user = UserService.get_user(db, user_id)
            user_organizations = OrganizationService.get_user_organizations(db, user_id)
            pending_invitations = OrganizationService.get_pending_invitations_for_phone(db, user.phone_number) if user else []
            
            # Context for the AI
            context = f"""
            Usuario actual:
            - Teléfono: {user.phone_number if user else 'No disponible'}
            - Organizaciones actuales: {len(user_organizations)} organizaciones
            - Invitaciones pendientes: {len(pending_invitations)}
            """
            
            task = Task(
                description=f"""
                CONTEXTO DEL SISTEMA:
                {self.system_context[:2000]}
                
                CONTEXTO DEL USUARIO:
                {context}
                
                MENSAJE DEL USUARIO: "{message}"
                
                Analiza el mensaje y determina la acción exacta que el usuario quiere realizar:
                
                ACCIONES POSIBLES:
                1. create_organization - Crear organización
                   Ejemplos: "crear familia", "nueva empresa Gymgo", "hacer equipo", "crear organizacion", "nueva familia Mi Casa"
                   
                2. invite_member - Invitar persona
                   CON NÚMERO: "invitar +50612345678", "agregar +506... admin"
                   SIN NÚMERO: "invitar a mi esposa", "agregar mi hermano", "invita mi colega"
                   
                3. list_members - Ver miembros
                   Ejemplos: "miembros", "quién está", "mostrar miembros"
                   
                4. accept_invitation - Aceptar invitación
                   Ejemplos: "acepto", "sí quiero unirme", "está bien"
                   
                5. leave_organization - Salir de organización
                   Ejemplos: "salir familia", "abandonar empresa", "me quiero salir"
                
                EXTRAER INFORMACIÓN:
                - Para create_organization: nombre de la organización
                - Para invite_member: número de teléfono (si existe) y persona a invitar
                
                DETECCIÓN INTELIGENTE DE NÚMEROS:
                - "+50686956438" → teléfono completo detectado
                - "506 8695 6438" → teléfono sin + detectado
                - "8695-6438" → teléfono local detectado
                - "invita a +50686956438" → acción COMPLETA, NO preguntar más
                - "invitar mi esposa" → sin número, SÍ preguntar teléfono
                
                EJEMPLOS CRÍTICOS:
                - "Invita a +50686956438" → phone_number: "+50686956438", person_to_invite: null
                - "agregar +506..." → phone_number: detectar número completo
                - "invitar mi esposa" → phone_number: null, person_to_invite: "mi esposa"
                
                Responde en JSON:
                {{
                    "action": "acción_detectada",
                    "organization_name": "nombre_si_aplica_o_null",
                    "phone_number": "número_si_existe_o_null",
                    "person_to_invite": "descripción_persona_si_aplica",
                    "confidence": "alta/media/baja"
                }}
                """,
                agent=self.agent,
                expected_output="JSON con la acción detectada y datos extraídos"
            )
            
            crew = Crew(agents=[self.agent], tasks=[task])
            result = str(crew.kickoff()).strip()
            
            # Parse AI response
            try:
                intent = json.loads(result)
            except:
                # If JSON parsing fails, try to extract key information
                intent = self._parse_ai_response_fallback(result, message)
            
            # Execute the detected action
            return self._execute_organization_action(intent, message, user_id, db)
            
        except Exception as e:
            print(f"Error in AI organization conversation processing: {e}")
            return self._fallback_process_organization_command(message, user_id, db)
    
    def _parse_ai_response_fallback(self, response: str, original_message: str) -> dict:
        """Parse AI response when JSON parsing fails."""
        response_lower = response.lower()
        
        if "create_organization" in response_lower or any(phrase in original_message.lower() for phrase in ["crear familia", "nueva familia", "crear empresa", "nueva empresa", "crear organizacion", "nueva organizacion", "hacer familia", "hacer empresa"]):
            organization_name = self._extract_organization_name_fallback(original_message)
            return {"action": "create_organization", "organization_name": organization_name, "confidence": "media"}
        elif "invite_member" in response_lower:
            phone = self._extract_phone_fallback(original_message)
            return {"action": "invite_member", "phone_number": phone, "confidence": "media"}
        elif "list_members" in response_lower:
            return {"action": "list_members", "confidence": "alta"}
        elif "accept_invitation" in response_lower:
            return {"action": "accept_invitation", "confidence": "alta"}
        elif "leave_organization" in response_lower:
            return {"action": "leave_organization", "confidence": "alta"}
        else:
            return {"action": "help", "confidence": "baja"}
    
    def _extract_organization_name_fallback(self, message: str) -> Optional[str]:
        """Extract organization name from message using simple patterns."""
        patterns = [
            r"(?:crear|nueva?)\s+familia\s+(.+)",
            r"(?:crear|nueva?)\s+empresa\s+(.+)",
            r"(?:crear|nuevo)\s+equipo\s+(.+)",
            r"(?:crear|nuevo)\s+grupo\s+(.+)",
            r"(?:crear|nueva?)\s+organizaci[oó]n\s+(.+)",
            r"familia\s+(.+?)(?:\s|$)",
            r"empresa\s+(.+?)(?:\s|$)",
            r"equipo\s+(.+?)(?:\s|$)",
            r"grupo\s+(.+?)(?:\s|$)",
            r"organizaci[oó]n\s+(.+?)(?:\s|$)",
            r"casa\s+(.+?)(?:\s|$)"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, message.lower())
            if match:
                name = match.group(1).strip()
                # Don't return empty names or very short names
                if name and len(name) > 1:
                    return name
        
        return None
    
    def _extract_phone_fallback(self, message: str) -> Optional[str]:
        """Extract phone number from message using AI or regex fallback."""
        if self.has_openai and self.agent:
            return self._ai_extract_phone_number(message)
        else:
            # Enhanced regex patterns for Costa Rican numbers
            phone_patterns = [
                r"(\+506\s?\d{4}\s?\d{4})",  # +506 1234 5678
                r"(\+506\d{8})",            # +50612345678
                r"(506\s?\d{4}\s?\d{4})",   # 506 1234 5678
                r"(506\d{8})",              # 50612345678
                r"(\d{4}[-\s]?\d{4})",      # 1234-5678 or 1234 5678
                r"(\+\d{1,3}\d{8,})"       # Generic international
            ]
            
            for pattern in phone_patterns:
                match = re.search(pattern, message)
                if match:
                    number = match.group(1)
                    # Normalize the number
                    if not number.startswith('+'):
                        if number.startswith('506'):
                            number = '+' + number
                        else:
                            # Assume Costa Rica if no country code
                            number = '+506' + number.replace('-', '').replace(' ', '')
                    return number.replace(' ', '').replace('-', '')
            
            return None
    
    def _ai_extract_phone_number(self, message: str) -> Optional[str]:
        """Use AI to extract phone number from message."""
        try:
            task = Task(
                description=f"""
                Extrae el número de teléfono del siguiente mensaje:
                
                MENSAJE: "{message}"
                
                FORMATOS POSIBLES:
                - +50612345678
                - +506 1234 5678
                - 506 1234 5678
                - 50612345678
                - 1234-5678 (asumir +506)
                - 12345678 (asumir +506)
                
                IMPORTANTE:
                - Si encuentras un número, devuélvelo en formato +50612345678
                - Si NO hay número, devuelve "null"
                - No incluyas texto adicional
                
                Ejemplos:
                - "Invita a +50686956438" → "+50686956438"
                - "agregar mi hermana" → "null"
                - "506 8695 6438" → "+50686956438"
                """,
                agent=self.agent,
                expected_output="Número de teléfono en formato +50612345678 o 'null'"
            )
            
            crew = Crew(agents=[self.agent], tasks=[task])
            result = str(crew.kickoff()).strip()
            
            if result.lower() == 'null' or not result:
                return None
            
            # Clean and validate the result
            cleaned = result.replace('"', '').replace("'", '').strip()
            if cleaned.startswith('+') and len(cleaned) >= 10:
                return cleaned
            
            return None
            
        except Exception as e:
            print(f"Error in AI phone extraction: {e}")
            return None
    
    def _execute_organization_action(self, intent: dict, message: str, user_id: str, db: Session) -> Dict[str, Any]:
        """Execute the organization action based on AI-detected intent."""
        action = intent.get("action", "help")
        
        if action == "create_organization":
            organization_name = intent.get("organization_name") or self._extract_organization_name_fallback(message)
            if organization_name:
                return self._handle_create_organization_natural(organization_name, user_id, db)
            else:
                return self._ask_for_organization_name()
                
        elif action == "invite_member":
            phone = intent.get("phone_number") or self._extract_phone_fallback(message)
            person_to_invite = intent.get("person_to_invite", "")
            
            if phone:
                # Phone number provided - proceed with invitation
                return self._handle_invite_member_natural(phone, user_id, db)
            elif person_to_invite:
                # Person described but no phone - ask for phone with context
                return self._ask_for_phone_number_with_context(person_to_invite)
            else:
                # Generic invitation request - ask for details
                return self._ask_for_phone_number()
                
        elif action == "list_members":
            return self._handle_list_members_natural(user_id, db)
            
        elif action == "accept_invitation":
            return self._handle_accept_invitation_natural(user_id, db)
            
        elif action == "leave_organization":
            return self._handle_leave_organization_natural(user_id, db)
            
        else:
            return self._handle_organization_help_natural()
    
    def _handle_create_organization_natural(self, organization_name: str, user_id: str, db: Session) -> Dict[str, Any]:
        """Handle organization creation with natural conversation."""
        user = UserService.get_user(db, user_id)
        if not user:
            return {
                "success": False,
                "message": "¡Ups! Parece que hubo un problema. ¿Podrías intentar de nuevo?"
            }
        
        # Detect organization type from name
        org_type = OrganizationType.family  # default
        if any(word in organization_name.lower() for word in ["empresa", "company", "corp", "inc"]):
            org_type = OrganizationType.company
        elif any(word in organization_name.lower() for word in ["equipo", "team"]):
            org_type = OrganizationType.team
        elif any(word in organization_name.lower() for word in ["departamento", "department"]):
            org_type = OrganizationType.department
        
        try:
            organization = OrganizationService.create_organization(
                db=db,
                name=organization_name,
                created_by=user_id,
                organization_type=org_type,
                currency=user.currency
            )
            
            org_type_names = {
                OrganizationType.family: "familia",
                OrganizationType.company: "empresa",
                OrganizationType.team: "equipo",
                OrganizationType.department: "departamento"
            }
            
            return {
                "success": True,
                "message": f"🎉 ¡Perfecto! He creado la {org_type_names[org_type]} '{organization_name}' para ti.\n\n👑 Eres el propietario, así que puedes invitar a quien quieras.\n💰 Vamos a usar {user.currency} como moneda.\n\n¿Quieres invitar a alguien ahora? Solo dime algo como 'invita a mi compañero al +506...' o 'agrega a mi colega +506...'"
            }
            
        except Exception as e:
            print(f"Error creating organization: {e}")
            return {
                "success": False,
                "message": f"¡Ay! Algo salió mal creando la organización. ¿Podrías intentar de nuevo? 😅"
            }
    
    def _handle_invite_member_natural(self, phone: str, user_id: str, db: Session) -> Dict[str, Any]:
        """Handle member invitation with natural conversation."""
        user_organizations = OrganizationService.get_user_organizations(db, user_id)
        admin_organizations = []
        
        for organization in user_organizations:
            role = OrganizationService.get_member_role(db, str(organization.id), user_id)
            if role in [OrganizationRole.owner, OrganizationRole.admin]:
                admin_organizations.append(organization)
        
        if not admin_organizations:
            return {
                "success": False,
                "message": "¡Hmm! Para invitar a alguien necesitas ser propietario o administrador de una organización. 🤔\n\n¿Quieres crear una organización nueva? Solo dime algo como 'quiero crear un grupo para los gastos de la casa' o 'hagamos una empresa'"
            }
        
        organization = admin_organizations[0]
        
        try:
            invitation = OrganizationService.invite_member(
                db=db,
                organization_id=str(organization.id),
                invited_phone=phone,
                invited_by=user_id,
                role=OrganizationRole.member,
                message=f"¡Te invitamos a unirte a '{organization.name}' en Edcora Finanzas!"
            )
            
            # Send WhatsApp invitation message to the invited person
            print(f"📧 Preparing to send invitation to {phone}")
            from app.services.whatsapp_service import WhatsAppService
            whatsapp_service = WhatsAppService()
            
            # Get inviter info for personal message
            from app.services.user_service import UserService
            inviter = UserService.get_user(db, user_id)
            inviter_name = inviter.name if inviter else "Alguien"
            
            print(f"👤 Inviter: {inviter_name}")
            print(f"🏢 Organization: {organization.name}")
            
            # Create concise invitation message
            invitation_message = f"""🎉 **Invitación a Edcora Finanzas**

¡Hola! {inviter_name} te invitó a '{organization.name}' para llevar control de gastos juntos.

✅ **Para aceptar:** Responde 'acepto'
❌ **Para rechazar:** Ignora este mensaje

🔐 **Tu privacidad está protegida:**
• Solo compartes gastos con miembros de esta organización
• Puedes salirte cuando quieras

¿Aceptas la invitación? 😊"""
            
            print(f"📝 Invitation message prepared, length: {len(invitation_message)}")
            print(f"📞 Attempting to send to: {phone}")
            
            # Send the invitation message
            invitation_sent = whatsapp_service.send_message(phone, invitation_message)
            
            print(f"📤 Invitation sent result: {invitation_sent}")
            
            if invitation_sent:
                return {
                    "success": True,
                    "message": f"🎉 ¡Listo! Le envié una invitación por WhatsApp a {phone} para unirse a '{organization.name}'.\n\nLa persona recibirá un mensaje explicando cómo aceptar la invitación.\n\n¿Hay alguien más que quieras invitar?"
                }
            else:
                # Invitation created in DB but WhatsApp failed
                return {
                    "success": True,
                    "message": f"✅ Invitación creada para {phone} en '{organization.name}'.\n\n⚠️ No pude enviar el mensaje de WhatsApp automáticamente. La persona puede escribir 'acepto' cuando se comunique contigo.\n\n¿Hay alguien más que quieras invitar?"
                }
            
        except ValueError as e:
            if "already invited" in str(e).lower():
                return {
                    "success": False,
                    "message": f"¡Ah! Ya invitaste a {phone} antes. Tal vez todavía no han aceptado la invitación. 🤷‍♀️"
                }
            else:
                return {
                    "success": False,
                    "message": f"¡Ups! {str(e)} 😅"
                }
    
    def _handle_list_members_natural(self, user_id: str, db: Session) -> Dict[str, Any]:
        """Handle listing members with natural conversation."""
        user_organizations = OrganizationService.get_user_organizations(db, user_id)
        
        if not user_organizations:
            return {
                "success": True,
                "message": "Aún no tienes ninguna organización creada. 🏠\n\n¿Te gustaría crear una? Solo dime algo como 'quiero hacer un grupo para los gastos' o 'crear empresa Gymgo'."
            }
        
        if len(user_organizations) == 1:
            organization = user_organizations[0]
            members = OrganizationService.get_organization_members(db, str(organization.id))
            
            org_type_emojis = {
                OrganizationType.family: "👨‍👩‍👧‍👦",
                OrganizationType.company: "🏢",
                OrganizationType.team: "👥",
                OrganizationType.department: "🏢"
            }
            
            emoji = org_type_emojis.get(organization.type, "📋")
            response = f"{emoji} Tu organización '{organization.name}' tiene {len(members)} miembro(s):\n\n"
            
            for member in members:
                user_info = UserService.get_user(db, str(member.user_id))
                role_emojis = {
                    OrganizationRole.owner: "👑",
                    OrganizationRole.admin: "⚡",
                    OrganizationRole.manager: "📊",
                    OrganizationRole.member: "👤", 
                    OrganizationRole.viewer: "👁️"
                }
                emoji = role_emojis.get(member.role, "👤")
                name = member.nickname or (user_info.name if user_info else "Miembro")
                
                if str(member.user_id) == user_id:
                    response += f"  {emoji} {name} (¡Eres tú!)\n"
                else:
                    response += f"  {emoji} {name}\n"
            
            response += f"\n💰 Moneda: {organization.currency}"
            
        else:
            response = f"📋 Tienes {len(user_organizations)} organizaciones:\n\n"
            
            for organization in user_organizations:
                members = OrganizationService.get_organization_members(db, str(organization.id))
                org_type_names = {
                    OrganizationType.family: "Familia",
                    OrganizationType.company: "Empresa",
                    OrganizationType.team: "Equipo",
                    OrganizationType.department: "Departamento"
                }
                org_type = org_type_names.get(organization.type, "Organización")
                response += f"**{org_type}: {organization.name}** - {len(members)} miembro(s)\n"
                
                for member in members:
                    user_info = UserService.get_user(db, str(member.user_id))
                    role_emojis = {
                        OrganizationRole.owner: "👑",
                        OrganizationRole.admin: "⚡",
                        OrganizationRole.manager: "📊",
                        OrganizationRole.member: "👤",
                        OrganizationRole.viewer: "👁️"
                    }
                    emoji = role_emojis.get(member.role, "👤")
                    name = member.nickname or (user_info.name if user_info else "Miembro")
                    response += f"  {emoji} {name}\n"
                
                response += "\n"
        
        return {
            "success": True,
            "message": response.strip()
        }
    
    def _handle_accept_invitation_natural(self, user_id: str, db: Session) -> Dict[str, Any]:
        """Handle accepting invitation with natural conversation."""
        user = UserService.get_user(db, user_id)
        if not user:
            return {
                "success": False,
                "message": "¡Ups! Hubo un problema. ¿Podrías intentar de nuevo?"
            }
        
        invitations = OrganizationService.get_pending_invitations_for_phone(db, user.phone_number)
        
        if not invitations:
            return {
                "success": True,
                "message": "No veo ninguna invitación pendiente para ti. 🤔\n\n¿Quizás ya aceptaste todas? O si quieres, puedes crear tu propia organización diciéndome algo como 'quiero crear un grupo organizacional'."
            }
        
        invitation = invitations[0]
        
        try:
            member = OrganizationService.accept_invitation(db, str(invitation.id), user_id)
            organization = OrganizationService.get_organization_by_id(db, str(invitation.organization_id))
            
            role_names = {
                OrganizationRole.owner: "propietario",
                OrganizationRole.admin: "administrador",
                OrganizationRole.manager: "gerente",
                OrganizationRole.member: "miembro",
                OrganizationRole.viewer: "observador"
            }
            
            return {
                "success": True,
                "message": f"🎉 ¡Bienvenido a '{organization.name}'!\n\nYa eres {role_names[member.role]} oficial del grupo. Ahora cuando registres gastos como 'gasté ₡5000 en almuerzo', los otros miembros también lo verán en sus reportes organizacionales.\n\n¡Perfecto para llevar las cuentas en orden! 📊"
            }
            
        except ValueError as e:
            return {
                "success": False,
                "message": f"¡Ay! Algo salió mal: {str(e)} 😅"
            }
    
    def _handle_leave_organization_natural(self, user_id: str, db: Session) -> Dict[str, Any]:
        """Handle leaving organization with natural conversation."""
        user_organizations = OrganizationService.get_user_organizations(db, user_id)
        
        if not user_organizations:
            return {
                "success": True,
                "message": "No estás en ninguna organización en este momento. 🤷‍♀️"
            }
        
        organization = user_organizations[0]
        
        try:
            OrganizationService.remove_member(
                db=db,
                organization_id=str(organization.id),
                user_id=user_id,
                removed_by=user_id
            )
            
            return {
                "success": True,
                "message": f"✅ Te saliste de '{organization.name}'.\n\nTus gastos personales siguen siendo solo tuyos. Si cambias de opinión, alguien te puede volver a invitar. 😊"
            }
            
        except ValueError as e:
            return {
                "success": False,
                "message": f"Hubo un problema: {str(e)} 😅"
            }
    
    def _ask_for_organization_name(self) -> Dict[str, Any]:
        """Ask user to provide organization name."""
        return {
            "success": False,
            "message": "¡Me gusta la idea! 😊 ¿Cómo quieres llamar a tu organización?\n\nPuedes decir algo como:\n• 'Familia García'\n• 'Empresa Gymgo'\n• 'Casa de roommates'\n• 'Mi hogar'"
        }
    
    def _ask_for_phone_number(self) -> Dict[str, Any]:
        """Ask user to provide phone number."""
        return {
            "success": False,
            "message": "¡Perfecto! ¿A quién quieres invitar? 📱\n\nNecesito el número de teléfono. Dime algo como:\n• 'Invita a +50612345678'\n• 'Agrega a mi compañero al +50612345678'"
        }
    
    def _ask_for_phone_number_with_context(self, person_description: str) -> Dict[str, Any]:
        """Ask user to provide phone number with context of who they want to invite."""
        if person_description:
            return {
                "success": False,
                "message": f"¡Perfecto! Quieres invitar a {person_description}. 😊\n\n¿Cuál es su número de teléfono?\n\nEjemplo: +50612345678"
            }
        else:
            return self._ask_for_phone_number()
    
    def _handle_organization_help_natural(self) -> Dict[str, Any]:
        """Provide natural help about organization features."""
        help_message = """📋 ¡Te ayudo con las organizaciones!

🌟 **¿Qué puedes hacer?**

🏠 **Crear una organización:** 
Dime 'quiero crear un grupo familiar', 'crear empresa Gymgo' o 'hagamos un equipo'

👥 **Invitar gente:** 
'Invita a mi hermana al +506...' o 'agrega a mi colega +506...'

👀 **Ver quién está:** 
'¿Quiénes están en mi organización?' o 'muéstrame los miembros'

✅ **Aceptar invitaciones:** 
Si te invitaron, solo di 'acepto' o 'sí quiero unirme'

🚪 **Salirte:** 
'Me quiero salir de la organización' o 'ya no quiero estar'

💡 **¡Tip!** Una vez en una organización, todos tus gastos los verán los demás miembros en reportes compartidos. ¡Perfecto para llevar cuentas claras!"""

        return {
            "success": True,
            "message": help_message
        }
    
    def _fallback_process_organization_command(self, message: str, user_id: str, db: Session) -> Dict[str, Any]:
        """Fallback to simple command processing when AI is not available."""
        message_lower = message.lower().strip()
        
        # Simple pattern matching for basic commands
        if "crear" in message_lower and ("familia" in message_lower or "empresa" in message_lower or "organizacion" in message_lower):
            return self._handle_create_organization_simple(message, user_id, db)
        elif "miembros" in message_lower or "quienes" in message_lower:
            return self._handle_list_members_natural(user_id, db)
        elif "acepto" in message_lower or "aceptar" in message_lower:
            return self._handle_accept_invitation_natural(user_id, db)
        else:
            return self._handle_organization_help_natural()
    
    def _handle_create_organization_simple(self, message: str, user_id: str, db: Session) -> Dict[str, Any]:
        """Simple organization creation without AI."""
        # Extract name using regex
        patterns = [
            r"crear\s+familia\s+(.+)",
            r"crear\s+empresa\s+(.+)",
            r"crear\s+organizaci[oó]n\s+(.+)",
            r"nueva\s+familia\s+(.+)",
            r"nueva\s+empresa\s+(.+)",
            r"nueva\s+organizaci[oó]n\s+(.+)"
        ]
        
        organization_name = None
        org_type = OrganizationType.family
        
        for pattern in patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                organization_name = match.group(1).strip()
                if "empresa" in pattern:
                    org_type = OrganizationType.company
                break
        
        if not organization_name:
            return self._ask_for_organization_name()
        
        return self._handle_create_organization_natural(organization_name, user_id, db)