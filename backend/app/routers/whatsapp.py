from fastapi import APIRouter, Depends, HTTPException, Form, Request
from sqlalchemy.orm import Session
from typing import Optional

from app.core.database import get_db
from app.core.schemas import WhatsAppMessage, OTPRequest, OTPVerify
from app.services.user_service import UserService
from app.services.transaction_service import TransactionService
from app.services.whatsapp_service import WhatsAppService
from app.services.otp_service import OTPService
from app.agents.parser_agent import ParserAgent
from app.agents.categorizer_agent import CategorizerAgent
from app.agents.report_agent import ReportAgent
from app.models.transaction import TransactionType
from app.core.schemas import TransactionCreate

router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])

# Initialize services
whatsapp_service = WhatsAppService()
otp_service = OTPService()
parser_agent = ParserAgent()
categorizer_agent = CategorizerAgent()
report_agent = ReportAgent()

@router.post("/webhook")
async def whatsapp_webhook(
    request: Request,
    From: str = Form(...),
    Body: str = Form(...),
    db: Session = Depends(get_db)
):
    """
    Twilio WhatsApp webhook endpoint.
    Processes incoming WhatsApp messages and creates transactions.
    """
    
    try:
        # Clean phone number (remove whatsapp: prefix)
        phone_number = From.replace("whatsapp:", "")
        message_body = Body.strip()
        
        # Find or create user automatically
        user = UserService.get_user_by_phone(db, phone_number)
        if not user:
            # Detect default currency for user based on phone number
            from app.agents.currency_agent import CurrencyAgent
            currency_agent = CurrencyAgent()
            currency_info = currency_agent.detect_currency("registro", phone_number)
            default_currency = currency_info.get("currency_code", "USD")
            
            # Auto-register new user with detected currency
            from app.core.schemas import UserCreate
            new_user_data = UserCreate(
                phone_number=phone_number,
                name="Usuario WhatsApp",  # Default name, user can change later
                currency=default_currency,
                plan_type="free"
            )
            user = UserService.create_user(db, new_user_data)
            
            # Welcome message for new users
            whatsapp_service.send_message(
                From, 
                f"¡Bienvenido a Edcora Finanzas! 🎉\n\nTu cuenta ha sido creada automáticamente. \n\n📝 **Para registrar:**\n• Gasté ₡5000 en almuerzo\n• ₡10000 gasolina\n• Ingreso ₡50000 salario\n\n📊 **Para reportes:**\n• Resumen de gastos\n• Cuánto he gastado hoy\n• Balance del mes\n\n¡Comencemos! 💰"
            )
            return {"status": "user_created"}
        
        # Check if user can add more transactions
        if not UserService.can_add_transaction(db, str(user.id)):
            whatsapp_service.send_upgrade_prompt(From)
            return {"status": "limit_reached"}
        
        # Check if this is a report request first
        if report_agent.is_report_request(message_body):
            try:
                # Get user's currency symbol
                currency_symbol = "₡"  # Default
                if hasattr(user, 'currency'):
                    currency_map = {
                        "CRC": "₡", "USD": "$", "MXN": "$", "EUR": "€", 
                        "COP": "$", "PEN": "S/", "GTQ": "Q"
                    }
                    currency_symbol = currency_map.get(user.currency, "$")
                
                # Generate report
                report_result = report_agent.generate_report(
                    message_body, str(user.id), db, currency_symbol
                )
                
                if report_result["success"]:
                    whatsapp_service.send_message(From, report_result["report"])
                    return {"status": "report_sent", "report": report_result["report"]}
                else:
                    whatsapp_service.send_message(
                        From, 
                        "No pude generar el reporte solicitado. Intenta con: 'resumen de gastos' o 'cuánto he gastado este mes'"
                    )
                    return {"status": "report_error"}
                    
            except Exception as e:
                print(f"Error generating report: {e}")
                whatsapp_service.send_message(
                    From,
                    "Ocurrió un error generando tu reporte. Por favor intenta nuevamente."
                )
                return {"status": "report_error"}
        
        # If not a report request, parse as transaction
        parsed_data = parser_agent.parse_message(message_body, phone_number)
        
        if not parsed_data["success"] or not parsed_data["amount"]:
            whatsapp_service.send_message(
                From,
                "No pude entender el monto en tu mensaje. Por favor, intenta con este formato:\n\n'Gasté ₡5000 en almuerzo' o '₡10000 gasolina'"
            )
            return {"status": "parse_error"}
        
        # Categorize the transaction using CategorizerAgent
        transaction_type = parsed_data["type"]
        category = categorizer_agent.categorize_transaction(
            parsed_data["description"], 
            transaction_type
        )
        
        # Create transaction
        transaction_data = TransactionCreate(
            user_id=user.id,
            amount=parsed_data["amount"],
            type=TransactionType.income if transaction_type == "income" else TransactionType.expense,
            category=category,
            description=parsed_data["description"]
        )
        
        transaction = TransactionService.create_transaction(db, transaction_data)
        
        # Send confirmation with detected currency
        currency_symbol = parsed_data.get("currency_symbol", "₡")
        whatsapp_service.send_transaction_confirmation(
            From,
            float(parsed_data["amount"]),
            transaction_type,
            category,
            currency_symbol
        )
        
        return {"status": "success", "transaction_id": str(transaction.id)}
        
    except Exception as e:
        print(f"Error processing WhatsApp message: {e}")
        whatsapp_service.send_message(
            From,
            "Ocurrió un error procesando tu mensaje. Por favor, intenta nuevamente."
        )
        return {"status": "error", "message": str(e)}

@router.post("/send-otp")
def send_otp(otp_request: OTPRequest):
    """Send OTP code to phone number for verification."""
    try:
        otp_code = otp_service.generate_otp(otp_request.phone_number)
        
        success = whatsapp_service.send_otp(otp_request.phone_number, otp_code)
        
        if success:
            return {"status": "sent", "message": "OTP enviado exitosamente"}
        else:
            raise HTTPException(status_code=500, detail="Error enviando OTP")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@router.post("/verify-otp")
def verify_otp(otp_verify: OTPVerify):
    """Verify OTP code."""
    try:
        is_valid = otp_service.verify_otp(otp_verify.phone_number, otp_verify.code)
        
        if is_valid:
            return {"status": "verified", "message": "OTP verificado exitosamente"}
        else:
            raise HTTPException(status_code=400, detail="OTP inválido o expirado")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@router.post("/test-message")
def test_message(phone_number: str, message: str):
    """Test endpoint to send WhatsApp messages (for development)."""
    try:
        success = whatsapp_service.send_message(phone_number, message)
        
        if success:
            return {"status": "sent", "message": "Mensaje enviado exitosamente"}
        else:
            raise HTTPException(status_code=500, detail="Error enviando mensaje")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")