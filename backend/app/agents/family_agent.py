from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from app.services.family_service import FamilyService
from app.services.user_service import UserService
from app.models.family import FamilyRole
from app.core.llm_config import get_openai_config
from crewai import Agent, Task, Crew
import re
import json

class FamilyAgent:
    """Intelligent agent to handle family-related conversations in natural language."""
    
    def __init__(self):
        try:
            # Setup OpenAI environment
            self.has_openai = get_openai_config()
            
            if self.has_openai:
                self.agent = Agent(
                    role="Family Financial Assistant",
                    goal="Help users manage family finances through natural conversation in Spanish. Understand family requests, invitations, and management in a human-like way.",
                    backstory="""Eres un asistente financiero familiar que habla español de forma natural y amigable. 
                    Entiendes cuando las personas quieren:
                    - Crear una familia para compartir gastos
                    - Invitar familiares o roommates
                    - Ver quién está en su familia
                    - Salirse de una familia
                    - Manejar permisos familiares
                    
                    Respondes de forma conversacional, como si fueras un amigo que ayuda con las finanzas familiares.
                    Siempre eres positivo, claro y das ejemplos prácticos.""",
                    verbose=True,
                    allow_delegation=False
                )
            else:
                self.agent = None
                
        except Exception as e:
            print(f"Warning: Failed to initialize FamilyAgent: {e}")
            self.has_openai = False
            self.agent = None
            
        # Fallback keywords for regex detection
        self.family_keywords = [
            "familia", "family", "familiares", "compartir gastos",
            "invitar", "invite", "agregar", "roommate", "compañero",
            "miembros", "members", "quienes", "quien esta",
            "salir", "leave", "abandonar", "irse", "irme"
        ]
    
    def is_family_command(self, message: str) -> bool:
        """Detect if a message is family-related using AI or fallback keywords."""
        if self.has_openai and self.agent:
            return self._ai_detect_family_intent(message)
        else:
            # Fallback: keyword detection
            message_lower = message.lower()
            return any(keyword in message_lower for keyword in self.family_keywords)
    
    def _ai_detect_family_intent(self, message: str) -> bool:
        """Use AI to detect if message is about family finances."""
        try:
            task = Task(
                description=f"""
                Analiza este mensaje para determinar si está relacionado con manejo de familias financieras:
                "{message}"
                
                Considera que es sobre familias si habla de:
                - Crear grupos familiares para gastos
                - Invitar familiares, roommates o amigos a compartir gastos
                - Ver miembros de familia
                - Salirse de grupos familiares
                - Manejar permisos familiares
                
                Responde solo con "true" o "false".
                """,
                agent=self.agent,
                expected_output="true o false"
            )
            
            crew = Crew(agents=[self.agent], tasks=[task])
            result = crew.kickoff()
            
            return str(result).strip().lower() == "true"
            
        except Exception as e:
            print(f"Error in AI family intent detection: {e}")
            # Fallback to keyword detection
            message_lower = message.lower()
            return any(keyword in message_lower for keyword in self.family_keywords)
    
    def process_family_command(self, message: str, user_id: str, db: Session) -> Dict[str, Any]:
        """Process family-related conversations using AI for natural language understanding."""
        
        if self.has_openai and self.agent:
            return self._ai_process_family_conversation(message, user_id, db)
        else:
            # Fallback to old command-based system
            return self._fallback_process_family_command(message, user_id, db)
    
    def _ai_process_family_conversation(self, message: str, user_id: str, db: Session) -> Dict[str, Any]:
        """Process family conversation using AI to understand intent."""
        try:
            # Get current user context
            user = UserService.get_user(db, user_id)
            user_families = FamilyService.get_user_families(db, user_id)
            pending_invitations = FamilyService.get_pending_invitations_for_phone(db, user.phone_number) if user else []
            
            # Context for the AI
            context = f"""
            Usuario actual:
            - Teléfono: {user.phone_number if user else 'No disponible'}
            - Familias actuales: {len(user_families)} familias
            - Invitaciones pendientes: {len(pending_invitations)}
            """
            
            task = Task(
                description=f"""
                Analiza esta conversación sobre familias financieras y determina la intención del usuario:
                
                Mensaje: "{message}"
                
                {context}
                
                Determina cuál de estas acciones quiere realizar:
                1. create_family - Crear una nueva familia (nombres como "familia García", "mi casa", "roommates", etc.)
                2. invite_member - Invitar a alguien (menciona números de teléfono o "invitar a mi hermana")
                3. list_members - Ver quién está en la familia ("quiénes están", "miembros", "quién más")
                4. accept_invitation - Aceptar una invitación ("acepto", "sí quiero unirme", "está bien")
                5. leave_family - Salirse de una familia ("me quiero salir", "ya no quiero estar")
                6. help - Necesita ayuda o no está clara la intención
                
                Para create_family, extrae también el nombre de la familia del mensaje.
                Para invite_member, extrae el número de teléfono si lo menciona.
                
                Responde en formato JSON:
                {{
                    "action": "acción_detectada",
                    "family_name": "nombre_extraído_si_aplica",
                    "phone_number": "número_extraído_si_aplica",
                    "confidence": "alta/media/baja"
                }}
                """,
                agent=self.agent,
                expected_output="JSON con la acción detectada"
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
            return self._execute_family_action(intent, message, user_id, db)
            
        except Exception as e:
            print(f"Error in AI family conversation processing: {e}")
            return self._fallback_process_family_command(message, user_id, db)
    
    def _parse_ai_response_fallback(self, response: str, original_message: str) -> dict:
        """Parse AI response when JSON parsing fails."""
        response_lower = response.lower()
        
        if "create_family" in response_lower:
            # Try to extract family name from original message
            family_name = self._extract_family_name_fallback(original_message)
            return {"action": "create_family", "family_name": family_name, "confidence": "media"}
        elif "invite_member" in response_lower:
            phone = self._extract_phone_fallback(original_message)
            return {"action": "invite_member", "phone_number": phone, "confidence": "media"}
        elif "list_members" in response_lower:
            return {"action": "list_members", "confidence": "alta"}
        elif "accept_invitation" in response_lower:
            return {"action": "accept_invitation", "confidence": "alta"}
        elif "leave_family" in response_lower:
            return {"action": "leave_family", "confidence": "alta"}
        else:
            return {"action": "help", "confidence": "baja"}
    
    def _extract_family_name_fallback(self, message: str) -> Optional[str]:
        """Extract family name from message using simple patterns."""
        patterns = [
            r"familia\s+(.+?)(?:\s|$)",
            r"grupo\s+(.+?)(?:\s|$)",
            r"casa\s+(.+?)(?:\s|$)",
            r"llamar(?:la|lo)?\s+(.+?)(?:\s|$)"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, message.lower())
            if match:
                return match.group(1).strip()
        
        return None
    
    def _extract_phone_fallback(self, message: str) -> Optional[str]:
        """Extract phone number from message."""
        phone_pattern = r"(\+\d{1,3}\d{8,})"
        match = re.search(phone_pattern, message)
        return match.group(1) if match else None
    
    def _execute_family_action(self, intent: dict, message: str, user_id: str, db: Session) -> Dict[str, Any]:
        """Execute the family action based on AI-detected intent."""
        action = intent.get("action", "help")
        
        if action == "create_family":
            family_name = intent.get("family_name") or self._extract_family_name_fallback(message)
            if family_name:
                return self._handle_create_family_natural(family_name, user_id, db)
            else:
                return self._ask_for_family_name()
                
        elif action == "invite_member":
            phone = intent.get("phone_number") or self._extract_phone_fallback(message)
            if phone:
                return self._handle_invite_member_natural(phone, user_id, db)
            else:
                return self._ask_for_phone_number()
                
        elif action == "list_members":
            return self._handle_list_members_natural(user_id, db)
            
        elif action == "accept_invitation":
            return self._handle_accept_invitation_natural(user_id, db)
            
        elif action == "leave_family":
            return self._handle_leave_family_natural(user_id, db)
            
        else:
            return self._handle_family_help_natural()
    
    def _fallback_process_family_command(self, message: str, user_id: str, db: Session) -> Dict[str, Any]:
        """Fallback to command-based processing when AI is not available."""
        message_lower = message.lower().strip()
        
        try:
            # Create family commands
            if self._is_create_family_command(message_lower):
                return self._handle_create_family(message, user_id, db)
            
            # Invite commands
            elif self._is_invite_command(message_lower):
                return self._handle_invite_member(message, user_id, db)
            
            # List members command
            elif self._is_list_members_command(message_lower):
                return self._handle_list_members(user_id, db)
            
            # List families command
            elif self._is_list_families_command(message_lower):
                return self._handle_list_families(user_id, db)
            
            # Accept invitation command
            elif self._is_accept_invitation_command(message_lower):
                return self._handle_accept_invitation(user_id, db)
            
            # Leave family command
            elif self._is_leave_family_command(message_lower):
                return self._handle_leave_family(message, user_id, db)
            
            # Help command
            else:
                return self._handle_family_help()
                
        except Exception as e:
            return {
                "success": False,
                "message": f"Error procesando comando familiar: {str(e)}"
            }
    
    def _is_create_family_command(self, message: str) -> bool:
        patterns = [
            r"crear familia",
            r"nueva familia", 
            r"family create",
            r"crear.*familia.*(.+)"
        ]
        return any(re.search(pattern, message) for pattern in patterns)
    
    def _is_invite_command(self, message: str) -> bool:
        patterns = [
            r"invitar.*(\+\d+)",
            r"invite.*(\+\d+)",
            r"agregar.*(\+\d+)"
        ]
        return any(re.search(pattern, message) for pattern in patterns)
    
    def _is_list_members_command(self, message: str) -> bool:
        return any(phrase in message for phrase in [
            "miembros", "members", "familia miembros", "ver miembros"
        ])
    
    def _is_list_families_command(self, message: str) -> bool:
        return any(phrase in message for phrase in [
            "mis familias", "my families", "familias", "ver familias"
        ])
    
    def _is_accept_invitation_command(self, message: str) -> bool:
        return any(phrase in message for phrase in [
            "aceptar invitacion", "accept invitation", "unirse", "join"
        ])
    
    def _is_leave_family_command(self, message: str) -> bool:
        return any(phrase in message for phrase in [
            "salir familia", "leave family", "abandonar familia"
        ])
    
    def _handle_create_family(self, message: str, user_id: str, db: Session) -> Dict[str, Any]:
        """Handle family creation command."""
        # Extract family name from message
        patterns = [
            r"crear familia[:\s]+(.+)",
            r"nueva familia[:\s]+(.+)",
            r"family create[:\s]+(.+)"
        ]
        
        family_name = None
        for pattern in patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                family_name = match.group(1).strip()
                break
        
        if not family_name:
            return {
                "success": False,
                "message": "Por favor especifica el nombre de la familia.\n\nEjemplo:\n• Crear familia: Los García\n• Nueva familia: Mi Hogar"
            }
        
        # Get user's currency
        user = UserService.get_user(db, user_id)
        if not user:
            return {
                "success": False,
                "message": "Error: Usuario no encontrado."
            }
        
        # Create family
        family = FamilyService.create_family(
            db=db,
            name=family_name,
            created_by=user_id,
            currency=user.currency
        )
        
        return {
            "success": True,
            "message": f"✅ ¡Familia '{family_name}' creada exitosamente!\n\n👑 Eres el administrador\n💰 Moneda: {user.currency}\n\n📨 Para invitar miembros:\n• Invitar +50612345678\n• Invitar +50612345678 admin"
        }
    
    def _handle_invite_member(self, message: str, user_id: str, db: Session) -> Dict[str, Any]:
        """Handle member invitation command."""
        # Extract phone number and optional role
        patterns = [
            r"invitar[:\s]+(\+\d+)(?:\s+(admin|member|viewer))?",
            r"invite[:\s]+(\+\d+)(?:\s+(admin|member|viewer))?",
            r"agregar[:\s]+(\+\d+)(?:\s+(admin|member|viewer))?"
        ]
        
        phone_match = None
        role_str = "member"
        
        for pattern in patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                phone_match = match.group(1)
                if match.group(2):
                    role_str = match.group(2).lower()
                break
        
        if not phone_match:
            return {
                "success": False,
                "message": "Por favor especifica un número de teléfono válido.\n\nEjemplo:\n• Invitar +50612345678\n• Invitar +50612345678 admin\n• Invitar +50612345678 viewer"
            }
        
        # Get user's families where they are admin
        user_families = FamilyService.get_user_families(db, user_id)
        admin_families = []
        
        for family in user_families:
            role = FamilyService.get_member_role(db, str(family.id), user_id)
            if role == FamilyRole.admin:
                admin_families.append(family)
        
        if not admin_families:
            return {
                "success": False,
                "message": "❌ No tienes permisos de administrador en ninguna familia.\n\nPara crear una familia:\n• Crear familia: Mi Hogar"
            }
        
        # If multiple families, use the first one (could be improved)
        family = admin_families[0]
        
        # Convert role string to enum
        role_map = {
            "admin": FamilyRole.admin,
            "member": FamilyRole.member,
            "viewer": FamilyRole.viewer
        }
        role = role_map.get(role_str, FamilyRole.member)
        
        # Create invitation
        try:
            invitation = FamilyService.invite_member(
                db=db,
                family_id=str(family.id),
                invited_phone=phone_match,
                invited_by=user_id,
                role=role,
                message=f"¡Te invitamos a unirte a la familia '{family.name}' en Edcora Finanzas!"
            )
            
            role_names = {
                FamilyRole.admin: "Administrador",
                FamilyRole.member: "Miembro",
                FamilyRole.viewer: "Observador"
            }
            
            return {
                "success": True,
                "message": f"✅ ¡Invitación enviada!\n\n👨‍👩‍👧‍👦 Familia: {family.name}\n📱 Número: {phone_match}\n👤 Rol: {role_names[role]}\n⏰ Expira en 7 días\n\nLa persona debe escribir 'aceptar invitacion' para unirse."
            }
            
        except ValueError as e:
            return {
                "success": False,
                "message": f"❌ {str(e)}"
            }
    
    def _handle_list_members(self, user_id: str, db: Session) -> Dict[str, Any]:
        """Handle list family members command."""
        user_families = FamilyService.get_user_families(db, user_id)
        
        if not user_families:
            return {
                "success": True,
                "message": "❌ No perteneces a ninguna familia.\n\nPara crear una:\n• Crear familia: Mi Hogar"
            }
        
        response = "👨‍👩‍👧‍👦 **Tus Familias:**\n\n"
        
        for family in user_families:
            members = FamilyService.get_family_members(db, str(family.id))
            response += f"**{family.name}** ({family.currency})\n"
            
            for member in members:
                user_info = UserService.get_user(db, str(member.user_id))
                role_icons = {
                    FamilyRole.admin: "👑",
                    FamilyRole.member: "👤",
                    FamilyRole.viewer: "👁️"
                }
                icon = role_icons.get(member.role, "👤")
                name = member.nickname or (user_info.name if user_info else "Usuario")
                response += f"  {icon} {name}\n"
            
            response += "\n"
        
        return {
            "success": True,
            "message": response.strip()
        }
    
    def _handle_list_families(self, user_id: str, db: Session) -> Dict[str, Any]:
        """Handle list user's families command."""
        return self._handle_list_members(user_id, db)
    
    def _handle_accept_invitation(self, user_id: str, db: Session) -> Dict[str, Any]:
        """Handle accept invitation command."""
        user = UserService.get_user(db, user_id)
        if not user:
            return {
                "success": False,
                "message": "Error: Usuario no encontrado."
            }
        
        # Get pending invitations for this phone
        invitations = FamilyService.get_pending_invitations_for_phone(db, user.phone_number)
        
        if not invitations:
            return {
                "success": True,
                "message": "📭 No tienes invitaciones pendientes.\n\nPara crear tu propia familia:\n• Crear familia: Mi Hogar"
            }
        
        # Accept the first pending invitation
        invitation = invitations[0]
        
        try:
            member = FamilyService.accept_invitation(db, str(invitation.id), user_id)
            family = FamilyService.get_family_by_id(db, str(invitation.family_id))
            
            role_names = {
                FamilyRole.admin: "Administrador",
                FamilyRole.member: "Miembro", 
                FamilyRole.viewer: "Observador"
            }
            
            return {
                "success": True,
                "message": f"🎉 ¡Te has unido exitosamente!\n\n👨‍👩‍👧‍👦 Familia: {family.name}\n👤 Tu rol: {role_names[member.role]}\n💰 Moneda: {family.currency}\n\nYa puedes registrar gastos familiares. Los otros miembros verán tus transacciones en los reportes familiares."
            }
            
        except ValueError as e:
            return {
                "success": False,
                "message": f"❌ {str(e)}"
            }
    
    def _handle_leave_family(self, message: str, user_id: str, db: Session) -> Dict[str, Any]:
        """Handle leave family command."""
        user_families = FamilyService.get_user_families(db, user_id)
        
        if not user_families:
            return {
                "success": True,
                "message": "❌ No perteneces a ninguna familia."
            }
        
        # For simplicity, leave the first family (could be improved to specify which one)
        family = user_families[0]
        
        try:
            FamilyService.remove_member(
                db=db,
                family_id=str(family.id),
                user_id=user_id,
                removed_by=user_id
            )
            
            return {
                "success": True,
                "message": f"✅ Has salido de la familia '{family.name}'.\n\nTus transacciones personales seguirán siendo privadas."
            }
            
        except ValueError as e:
            return {
                "success": False,
                "message": f"❌ {str(e)}"
            }
    
    # Natural language handlers - more conversational responses
    def _handle_create_family_natural(self, family_name: str, user_id: str, db: Session) -> Dict[str, Any]:
        """Handle family creation with natural conversation."""
        user = UserService.get_user(db, user_id)
        if not user:
            return {
                "success": False,
                "message": "¡Ups! Parece que hubo un problema. ¿Podrías intentar de nuevo?"
            }
        
        try:
            family = FamilyService.create_family(
                db=db,
                name=family_name,
                created_by=user_id,
                currency=user.currency
            )
            
            return {
                "success": True,
                "message": f"🎉 ¡Perfecto! He creado la familia '{family_name}' para ti.\n\n👑 Eres el administrador, así que puedes invitar a quien quieras.\n💰 Vamos a usar {user.currency} como moneda.\n\n¿Quieres invitar a alguien ahora? Solo dime algo como 'invita a mi hermana al +506...' o 'agrega a mi roommate +506...'"
            }
            
        except Exception as e:
            return {
                "success": False,
                "message": f"¡Ay! Algo salió mal creando la familia. ¿Podrías intentar de nuevo? 😅"
            }
    
    def _handle_invite_member_natural(self, phone: str, user_id: str, db: Session) -> Dict[str, Any]:
        """Handle member invitation with natural conversation."""
        user_families = FamilyService.get_user_families(db, user_id)
        admin_families = []
        
        for family in user_families:
            role = FamilyService.get_member_role(db, str(family.id), user_id)
            if role == FamilyRole.admin:
                admin_families.append(family)
        
        if not admin_families:
            return {
                "success": False,
                "message": "¡Hmm! Para invitar a alguien necesitas ser administrador de una familia. 🤔\n\n¿Quieres crear una familia nueva? Solo dime algo como 'quiero crear un grupo para los gastos de la casa' o 'hagamos una familia de roommates'."
            }
        
        family = admin_families[0]
        
        try:
            invitation = FamilyService.invite_member(
                db=db,
                family_id=str(family.id),
                invited_phone=phone,
                invited_by=user_id,
                role=FamilyRole.member,
                message=f"¡Te invitamos a unirte a la familia '{family.name}' en Edcora Finanzas!"
            )
            
            return {
                "success": True,
                "message": f"🎉 ¡Listo! Le envié una invitación a {phone} para unirse a '{family.name}'.\n\nLa persona solo necesita escribir algo como 'acepto' o 'sí quiero unirme' para formar parte del grupo.\n\n¿Hay alguien más que quieras invitar?"
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
        user_families = FamilyService.get_user_families(db, user_id)
        
        if not user_families:
            return {
                "success": True,
                "message": "Aún no tienes ninguna familia creada. 🏠\n\n¿Te gustaría crear una? Solo dime algo como 'quiero hacer un grupo para los gastos' o 'crear familia de roommates'."
            }
        
        if len(user_families) == 1:
            family = user_families[0]
            members = FamilyService.get_family_members(db, str(family.id))
            
            response = f"👨‍👩‍👧‍👦 Tu familia '{family.name}' tiene {len(members)} miembro(s):\n\n"
            
            for member in members:
                user_info = UserService.get_user(db, str(member.user_id))
                role_emojis = {
                    FamilyRole.admin: "👑",
                    FamilyRole.member: "👤", 
                    FamilyRole.viewer: "👁️"
                }
                emoji = role_emojis.get(member.role, "👤")
                name = member.nickname or (user_info.name if user_info else "Miembro")
                
                if str(member.user_id) == user_id:
                    response += f"  {emoji} {name} (¡Eres tú!)\n"
                else:
                    response += f"  {emoji} {name}\n"
            
            response += f"\n💰 Moneda: {family.currency}"
            
        else:
            response = f"👨‍👩‍👧‍👦 Tienes {len(user_families)} familias:\n\n"
            
            for family in user_families:
                members = FamilyService.get_family_members(db, str(family.id))
                response += f"**{family.name}** - {len(members)} miembro(s)\n"
                
                for member in members:
                    user_info = UserService.get_user(db, str(member.user_id))
                    role_emojis = {
                        FamilyRole.admin: "👑",
                        FamilyRole.member: "👤",
                        FamilyRole.viewer: "👁️"
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
        
        invitations = FamilyService.get_pending_invitations_for_phone(db, user.phone_number)
        
        if not invitations:
            return {
                "success": True,
                "message": "No veo ninguna invitación pendiente para ti. 🤔\n\n¿Quizás ya aceptaste todas? O si quieres, puedes crear tu propia familia diciéndome algo como 'quiero crear un grupo familiar'."
            }
        
        invitation = invitations[0]
        
        try:
            member = FamilyService.accept_invitation(db, str(invitation.id), user_id)
            family = FamilyService.get_family_by_id(db, str(invitation.family_id))
            
            role_names = {
                FamilyRole.admin: "administrador",
                FamilyRole.member: "miembro",
                FamilyRole.viewer: "observador"
            }
            
            return {
                "success": True,
                "message": f"🎉 ¡Bienvenido a la familia '{family.name}'!\n\nYa eres {role_names[member.role]} oficial del grupo. Ahora cuando registres gastos como 'gasté ₡5000 en almuerzo', los otros miembros también lo verán en sus reportes familiares.\n\n¡Perfecto para llevar las cuentas en orden! 📊"
            }
            
        except ValueError as e:
            return {
                "success": False,
                "message": f"¡Ay! Algo salió mal: {str(e)} 😅"
            }
    
    def _handle_leave_family_natural(self, user_id: str, db: Session) -> Dict[str, Any]:
        """Handle leaving family with natural conversation."""
        user_families = FamilyService.get_user_families(db, user_id)
        
        if not user_families:
            return {
                "success": True,
                "message": "No estás en ninguna familia en este momento. 🤷‍♀️"
            }
        
        family = user_families[0]
        
        try:
            FamilyService.remove_member(
                db=db,
                family_id=str(family.id),
                user_id=user_id,
                removed_by=user_id
            )
            
            return {
                "success": True,
                "message": f"✅ Te saliste de la familia '{family.name}'.\n\nTus gastos personales siguen siendo solo tuyos. Si cambias de opinión, alguien te puede volver a invitar. 😊"
            }
            
        except ValueError as e:
            return {
                "success": False,
                "message": f"Hubo un problema: {str(e)} 😅"
            }
    
    def _ask_for_family_name(self) -> Dict[str, Any]:
        """Ask user to provide family name."""
        return {
            "success": False,
            "message": "¡Me gusta la idea! 😊 ¿Cómo quieres llamar a tu familia?\n\nPuedes decir algo como:\n• 'Familia García'\n• 'Casa de roommates'\n• 'Gastos de pareja'\n• 'Mi hogar'"
        }
    
    def _ask_for_phone_number(self) -> Dict[str, Any]:
        """Ask user to provide phone number."""
        return {
            "success": False,
            "message": "¡Perfecto! ¿A quién quieres invitar? 📱\n\nNecesito el número de teléfono. Dime algo como:\n• 'Invita a +50612345678'\n• 'Agrega a mi hermana al +50612345678'"
        }
    
    def _handle_family_help_natural(self) -> Dict[str, Any]:
        """Provide natural help about family features."""
        help_message = """👨‍👩‍👧‍👦 ¡Te ayudo con las familias!

🌟 **¿Qué puedes hacer?**

🏠 **Crear una familia:** 
Dime 'quiero crear un grupo familiar' o 'hagamos una familia de roommates'

👥 **Invitar gente:** 
'Invita a mi hermana al +506...' o 'agrega a mi roommate +506...'

👀 **Ver quién está:** 
'¿Quiénes están en mi familia?' o 'muéstrame los miembros'

✅ **Aceptar invitaciones:** 
Si te invitaron, solo di 'acepto' o 'sí quiero unirme'

🚪 **Salirte:** 
'Me quiero salir de la familia' o 'ya no quiero estar'

💡 **¡Tip!** Una vez en familia, todos tus gastos los verán los demás miembros en reportes compartidos. ¡Perfecto para llevar cuentas claras!"""

        return {
            "success": True,
            "message": help_message
        }

    def _handle_family_help(self) -> Dict[str, Any]:
        """Provide family commands help."""
        help_message = """👨‍👩‍👧‍👦 **Comandos Familiares:**

🆕 **Crear Familia:**
• Crear familia: Los García
• Nueva familia: Mi Hogar

📨 **Invitar Miembros:**
• Invitar +50612345678
• Invitar +50612345678 admin
• Invitar +50612345678 viewer

👥 **Ver Información:**
• Miembros
• Mis familias

🤝 **Unirse:**
• Aceptar invitacion

🚪 **Salir:**
• Salir familia

**Roles:**
👑 Admin - Puede invitar/remover
👤 Member - Puede agregar gastos
👁️ Viewer - Solo puede ver reportes"""

        return {
            "success": True,
            "message": help_message
        }