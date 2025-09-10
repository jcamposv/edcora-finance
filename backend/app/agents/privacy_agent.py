from typing import Dict, Any
from sqlalchemy.orm import Session
from app.core.llm_config import get_openai_config
from crewai import Agent, Task, Crew
import json

class PrivacyAgent:
    """
    Specialized agent for handling privacy, data protection, and user rights inquiries.
    Provides transparent information about data handling and user rights.
    """
    
    def __init__(self):
        try:
            self.has_openai = get_openai_config()
            
            if self.has_openai:
                self.agent = Agent(
                    role="Privacy and Data Protection Specialist",
                    goal="Provide clear, transparent information about data privacy, security, and user rights in Spanish. Help users understand their data protection rights and how Edcora handles their information.",
                    backstory="""Eres un especialista en protección de datos y privacidad que trabaja para Edcora Finanzas.
                    
                    CONOCES PERFECTAMENTE:
                    
                    DATOS QUE MANEJAMOS:
                    - Transacciones financieras (montos, categorías, descripciones)
                    - Organizaciones (familias, empresas) y sus miembros
                    - Números de teléfono para WhatsApp
                    - Preferencias de moneda y configuración
                    
                    DATOS QUE NO MANEJAMOS:
                    - Información bancaria (cuentas, tarjetas)
                    - Contraseñas o credenciales bancarias
                    - Documentos de identidad
                    - Información no relacionada con finanzas
                    
                    SEGURIDAD IMPLEMENTADA:
                    - Encriptación de datos en tránsito y reposo
                    - Acceso restringido solo al usuario propietario
                    - Servidores seguros con certificaciones
                    - Auditorías regulares de seguridad
                    
                    DERECHOS DEL USUARIO (GDPR/CCPA):
                    - Acceso: Ver todos sus datos
                    - Rectificación: Corregir información incorrecta
                    - Supresión: Eliminar cuenta y datos
                    - Portabilidad: Exportar datos en formato legible
                    - Oposición: Rechazar procesamiento
                    - Limitación: Restringir ciertos usos
                    
                    USO DE DATOS:
                    - Solo para proporcionar el servicio financiero
                    - Generar reportes personalizados
                    - Facilitar colaboración en organizaciones
                    - Mejorar la experiencia del usuario
                    
                    NO COMPARTIMOS DATOS CON:
                    - Terceros comerciales
                    - Empresas de marketing
                    - Otros usuarios sin permiso
                    - Gobiernos (excepto orden judicial)
                    
                    Respondes de forma clara, honesta y transparente. Siempre proteges los derechos del usuario.""",
                    verbose=True,
                    allow_delegation=False
                )
            else:
                self.agent = None
                
        except Exception as e:
            print(f"Warning: Failed to initialize PrivacyAgent: {e}")
            self.has_openai = False
            self.agent = None
            
        # Privacy-related keywords
        self.privacy_keywords = [
            "privacidad", "privacy", "datos", "data", "seguridad", "security",
            "derechos", "rights", "gdpr", "ccpa", "protección", "protection",
            "eliminar cuenta", "delete account", "borrar datos", "delete data",
            "exportar", "export", "descargar", "download", "acceso", "access",
            "rectificar", "correct", "cambiar", "change", "portabilidad", "portability",
            "quién ve", "who sees", "compartir", "share", "terceros", "third party",
            "encriptación", "encryption", "seguro", "secure", "confidencial", "confidential"
        ]
    
    def is_privacy_request(self, message: str) -> bool:
        """Detect if a message is about privacy or data protection."""
        message_lower = message.lower()
        return any(keyword in message_lower for keyword in self.privacy_keywords)
    
    def handle_privacy_inquiry(self, message: str, user_id: str, db: Session) -> Dict[str, Any]:
        """Handle privacy and data protection inquiries."""
        
        if self.has_openai and self.agent:
            return self._ai_handle_privacy_inquiry(message, user_id, db)
        else:
            return self._fallback_privacy_response(message)
    
    def _ai_handle_privacy_inquiry(self, message: str, user_id: str, db: Session) -> Dict[str, Any]:
        """Use AI to provide detailed privacy information."""
        try:
            # Get user context for personalized response
            from app.services.user_service import UserService
            from app.services.organization_service import OrganizationService
            
            user = UserService.get_user(db, user_id)
            user_organizations = OrganizationService.get_user_organizations(db, user_id) if user else []
            
            user_context = f"""
            CONTEXTO DEL USUARIO:
            - Registrado: {'Sí' if user else 'No'}
            - Organizaciones: {len(user_organizations)} organizaciones
            - Moneda: {user.currency if user else 'N/A'}
            """
            
            task = Task(
                description=f"""
                El usuario pregunta sobre privacidad y protección de datos:
                
                PREGUNTA: "{message}"
                
                {user_context}
                
                Proporciona una respuesta clara y transparente sobre:
                
                SI PREGUNTA SOBRE DATOS:
                - Qué datos guardamos exactamente
                - Cómo los protegemos
                - Quién tiene acceso
                - Por qué los necesitamos
                
                SI PREGUNTA SOBRE DERECHOS:
                - Derechos específicos (GDPR/CCPA)
                - Cómo ejercer cada derecho
                - Timeframes y procesos
                - Contacto para solicitudes
                
                SI PREGUNTA SOBRE SEGURIDAD:
                - Medidas técnicas implementadas
                - Encriptación y protocolos
                - Auditorías y certificaciones
                - Prevención de accesos no autorizados
                
                SI PREGUNTA SOBRE COMPARTIR:
                - Con quién NO compartimos
                - Casos excepcionales (legales)
                - Control del usuario sobre compartir
                - Transparencia en organizaciones
                
                SI QUIERE ELIMINAR CUENTA:
                - Proceso paso a paso
                - Qué datos se eliminan
                - Qué datos se conservan (legales)
                - Timeframe de eliminación
                
                IMPORTANTE:
                - Sé específico y técnico pero comprensible
                - Da ejemplos concretos
                - Incluye acciones que puede tomar
                - Sé 100% honesto y transparente
                
                Responde en español de forma clara y profesional.
                """,
                agent=self.agent,
                expected_output="Respuesta detallada sobre privacidad y protección de datos"
            )
            
            crew = Crew(agents=[self.agent], tasks=[task])
            result = crew.kickoff()
            
            return {
                "success": True,
                "message": str(result).strip(),
                "type": "privacy_response"
            }
            
        except Exception as e:
            print(f"Error in privacy AI response: {e}")
            return self._fallback_privacy_response(message)
    
    def _fallback_privacy_response(self, message: str) -> Dict[str, Any]:
        """Fallback privacy responses when AI is not available."""
        message_lower = message.lower()
        
        # Data protection inquiry
        if any(word in message_lower for word in ["datos", "data", "información", "information"]):
            return {
                "success": True,
                "message": """🔐 **Tus Datos en Edcora Finanzas**

📊 **Datos que guardamos:**
• Transacciones (monto, descripción, fecha)
• Organizaciones y miembros
• Número de teléfono (WhatsApp)
• Preferencias de moneda

❌ **Datos que NO guardamos:**
• Información bancaria
• Contraseñas bancarias
• Documentos de identidad
• Datos personales irrelevantes

🛡️ **Cómo los protegemos:**
• Encriptación de extremo a extremo
• Servidores seguros certificados
• Acceso restringido solo a ti
• Auditorías regulares de seguridad

❓ Para más detalles, escribe 'seguridad' o 'derechos'""",
                "type": "privacy_response"
            }
        
        # User rights inquiry
        elif any(word in message_lower for word in ["derechos", "rights", "gdpr", "ccpa"]):
            return {
                "success": True,
                "message": """🛡️ **Tus Derechos de Protección de Datos**

✅ **Derecho de Acceso:**
• Ver todos tus datos guardados
• Exportar tu información completa
• Comando: 'exportar mis datos'

✏️ **Derecho de Rectificación:**
• Corregir información incorrecta
• Actualizar datos obsoletos
• Proceso automático al editar

🗑️ **Derecho al Olvido:**
• Eliminar tu cuenta completamente
• Borrar todos tus datos
• Comando: 'eliminar mi cuenta'

📤 **Derecho de Portabilidad:**
• Llevarte tus datos a otro servicio
• Formato legible (JSON/CSV)
• Descarga instantánea

⚖️ **Derechos adicionales:** Oposición, Limitación, No discriminación

📧 Para ejercer derechos: privacidad@edcora.com""",
                "type": "privacy_response"
            }
        
        # Security inquiry
        elif any(word in message_lower for word in ["seguridad", "security", "protección", "protection"]):
            return {
                "success": True,
                "message": """🔒 **Seguridad en Edcora Finanzas**

🛡️ **Protección Técnica:**
• Encriptación AES-256 en reposo
• TLS 1.3 en tránsito
• Autenticación multifactor disponible
• Firewalls y detección de intrusiones

🏢 **Infraestructura Segura:**
• Servidores certificados SOC 2
• Backups encriptados diarios
• Monitoreo 24/7 de seguridad
• Actualizaciones de seguridad automáticas

👥 **Control de Acceso:**
• Solo TÚ accedes a tus datos
• Logs de acceso auditables
• Sesiones con timeout automático
• Revocación inmediata de permisos

🔍 **Auditorías:**
• Revisiones de seguridad trimestrales
• Pruebas de penetración anuales
• Certificaciones de cumplimiento
• Transparencia en reportes de seguridad""",
                "type": "privacy_response"
            }
        
        # Account deletion inquiry
        elif any(word in message_lower for word in ["eliminar", "delete", "borrar", "cerrar cuenta"]):
            return {
                "success": True,
                "message": """🗑️ **Eliminar tu Cuenta de Edcora**

⚠️ **¿Estás seguro?** Esta acción es irreversible.

📝 **Proceso de Eliminación:**
1. Escribe: 'confirmar eliminar cuenta'
2. Te enviaremos código de verificación
3. Confirma con el código recibido
4. Eliminación inmediata de datos

🗂️ **Qué se elimina:**
• Todas tus transacciones
• Organizaciones donde eres propietario
• Preferencias y configuraciones
• Historial de reportes

⚖️ **Qué se conserva (legal):**
• Logs de auditoría (90 días)
• Datos requeridos por ley fiscal
• Solo metadatos sin información personal

⏱️ **Tiempo:** Eliminación completa en 24-48 horas

🔄 **Alternativa:** Puedes pausar tu cuenta temporalmente""",
                "type": "privacy_response"
            }
        
        # Data sharing inquiry
        elif any(word in message_lower for word in ["compartir", "share", "terceros", "third party"]):
            return {
                "success": True,
                "message": """🚫 **Política de No Compartir Datos**

❌ **NUNCA compartimos con:**
• Empresas de marketing
• Redes sociales
• Brokers de datos
• Servicios de publicidad
• Otros usuarios sin tu permiso

✅ **Solo compartimos cuando:**
• TÚ das permiso explícito
• Es necesario para el servicio
• Orden judicial válida
• Emergencia de seguridad

👥 **En Organizaciones:**
• Miembros ven transacciones compartidas
• TÚ controlas qué se comparte
• Puedes salirte en cualquier momento
• Datos personales siguen privados

🔒 **Control Total:**
• Configuras nivel de privacidad
• Apruebas cada compartir
• Revocas permisos cuando quieras
• Transparencia completa en logs

📧 **Reportar uso indebido:** privacidad@edcora.com""",
                "type": "privacy_response"
            }
        
        # General privacy help
        else:
            return {
                "success": True,
                "message": """🔐 **Centro de Privacidad de Edcora**

🎯 **Temas Disponibles:**

📊 **'datos'** - Qué información guardamos
🛡️ **'derechos'** - Tus derechos de protección
🔒 **'seguridad'** - Cómo protegemos tu información
🚫 **'compartir'** - Política de no compartir
🗑️ **'eliminar cuenta'** - Proceso de eliminación
📤 **'exportar'** - Descargar tus datos

💡 **Ejemplos de preguntas:**
• "¿Qué datos guardáis de mí?"
• "¿Cómo puedo eliminar mi cuenta?"
• "¿Compartís mis datos con terceros?"
• "¿Cómo exporto mi información?"

📧 **Contacto directo:** privacidad@edcora.com
⚖️ **Cumplimos:** GDPR, CCPA, LOPD

¡Tu privacidad es nuestra máxima prioridad! 🛡️""",
                "type": "privacy_response"
            }
    
    def get_privacy_summary(self) -> str:
        """Get a quick privacy summary for new users."""
        return """🔐 **Resumen de Privacidad:**

✅ Tus datos están encriptados y seguros
✅ Solo TÚ tienes acceso a tu información
✅ NUNCA compartimos con terceros sin permiso
✅ Puedes eliminar tu cuenta cuando quieras
✅ Tienes control total sobre tus datos

🛡️ Para más info: escribe 'privacidad'"""