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
        message = f"Tu código de verificación para Control Finanzas es: {otp_code}\n\nEste código expira en 5 minutos."
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