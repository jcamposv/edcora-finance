from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from app.services.family_service import FamilyService
from app.services.user_service import UserService
from app.models.family import FamilyRole
import re

class FamilyAgent:
    """Agent to handle family-related WhatsApp commands."""
    
    def __init__(self):
        self.family_keywords = [
            "crear familia", "nueva familia", "family", "familia",
            "invitar", "invite", "unirse", "join",
            "familia miembros", "members", "miembros",
            "salir familia", "leave family", "abandonar familia"
        ]
    
    def is_family_command(self, message: str) -> bool:
        """Detect if a message is a family-related command."""
        message_lower = message.lower()
        return any(keyword in message_lower for keyword in self.family_keywords)
    
    def process_family_command(self, message: str, user_id: str, db: Session) -> Dict[str, Any]:
        """Process family-related commands from WhatsApp."""
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