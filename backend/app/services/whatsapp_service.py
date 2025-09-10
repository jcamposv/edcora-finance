from twilio.rest import Client
import os
from typing import Optional

class WhatsAppService:
    def __init__(self):
        self.account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        self.auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        self.whatsapp_number = os.getenv("TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886")
        
        if self.account_sid and self.auth_token:
            self.client = Client(self.account_sid, self.auth_token)
        else:
            self.client = None
    
    def send_message(self, to_number: str, message: str) -> bool:
        """Send a WhatsApp message to a phone number."""
        if not self.client:
            print("Twilio client not configured")
            return False
        
        try:
            # Ensure the number has whatsapp: prefix
            if not to_number.startswith("whatsapp:"):
                to_number = f"whatsapp:{to_number}"
            
            message = self.client.messages.create(
                body=message,
                from_=self.whatsapp_number,
                to=to_number
            )
            
            print(f"Message sent successfully: {message.sid}")
            return True
            
        except Exception as e:
            print(f"Error sending WhatsApp message: {e}")
            return False
    
    def send_otp(self, to_number: str, otp_code: str) -> bool:
        """Send OTP code via WhatsApp."""
        message = f"Tu código de verificación para Edcora Finanzas es: {otp_code}\n\nEste código expira en 5 minutos."
        return self.send_message(to_number, message)
    
    def send_transaction_confirmation(self, to_number: str, amount: float, transaction_type: str, category: str, currency: str = "₡") -> bool:
        """Send transaction confirmation message."""
        type_text = "ingreso" if transaction_type == "income" else "gasto"
        message = f"✅ Registrado {type_text} de {currency}{amount:,.0f} en {category}."
        return self.send_message(to_number, message)
    
    def send_report(self, to_number: str, report_data: dict) -> bool:
        """Send financial report via WhatsApp."""
        period = report_data.get('period', 'mensual')
        income = report_data.get('income', 0)
        expenses = report_data.get('expenses', 0)
        balance = report_data.get('balance', 0)
        advice = report_data.get('advice', '')
        
        message = f"""📊 *Reporte {period}*
        
💰 Ingresos: ₡{income:,.0f}
💸 Gastos: ₡{expenses:,.0f}
💵 Balance: ₡{balance:,.0f}

{advice}

¡Sigue así! 🚀"""
        
        return self.send_message(to_number, message)
    
    def send_upgrade_prompt(self, to_number: str) -> bool:
        """Send upgrade to premium prompt."""
        message = """⚠️ Has alcanzado el límite de 50 transacciones del plan gratuito.

🚀 *Actualiza a Premium por solo $5/mes:*
• Transacciones ilimitadas
• Reportes automáticos
• Análisis avanzados

Visita tu dashboard para actualizar."""
        
        return self.send_message(to_number, message)
    
    def send_family_invitation_notification(self, to_number: str, family_name: str, inviter_name: str = None) -> bool:
        """Send natural family invitation notification."""
        inviter_text = f" (invitado por {inviter_name})" if inviter_name else ""
        
        message = f"""🎉 ¡Te invitaron a una familia en Edcora Finanzas!

👨‍👩‍👧‍👦 Familia: {family_name}{inviter_text}

Con una familia puedes compartir gastos y ver reportes juntos. ¡Perfecto para roommates, parejas o familias!

¿Te unes? Solo responde algo como:
• "Acepto"
• "Sí quiero unirme"
• "¡Perfecto!"

O si prefieres no unirte, simplemente ignora este mensaje. 😊"""

        return self.send_message(to_number, message)
    
    def send_family_welcome_message(self, to_number: str, family_name: str, role: str) -> bool:
        """Send welcome message after joining family."""
        role_descriptions = {
            "admin": "administrador (puedes invitar y gestionar miembros)",
            "member": "miembro (puedes agregar gastos familiares)", 
            "viewer": "observador (puedes ver reportes pero no agregar gastos)"
        }
        
        role_desc = role_descriptions.get(role, "miembro")
        
        message = f"""🎉 ¡Bienvenido a la familia '{family_name}'!

👤 Tu rol: {role_desc}

✨ **¿Qué sigue?**
• Registra gastos normalmente: "gasté ₡5000 en almuerzo"
• Los otros miembros verán tus gastos en reportes familiares
• Pregúntame "¿quiénes están en mi familia?" para ver los miembros

¡Ya están listos para llevar cuentas en familia! 📊"""

        return self.send_message(to_number, message)
    
    def send_conversational_help(self, to_number: str) -> bool:
        """Send conversational help about what the bot can do."""
        message = """👋 ¡Hola! Soy tu asistente financiero. Te ayudo de forma súper natural.

💰 **Para gastos:**
• "Gasté 5000 colones en almuerzo"
• "Pagué ₡15000 de gasolina"
• "Recibí ₡50000 de salario"

👨‍👩‍👧‍👦 **Para familias:**
• "Quiero crear un grupo familiar"
• "Invita a mi roommate al +506..."
• "¿Quiénes están en mi familia?"
• "Acepto la invitación"

📊 **Para reportes:**
• "¿Cómo van mis gastos?"
• "Muéstrame mi balance"
• "Reporte del mes"

¡Háblame como le hablarías a un amigo! 😊"""

        return self.send_message(to_number, message)