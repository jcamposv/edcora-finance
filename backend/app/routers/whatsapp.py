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
from app.models.transaction import TransactionType
from app.core.schemas import TransactionCreate

router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])

# Initialize services
whatsapp_service = WhatsAppService()
otp_service = OTPService()
parser_agent = ParserAgent()
categorizer_agent = CategorizerAgent()

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
        
        # Find or suggest user registration
        user = UserService.get_user_by_phone(db, phone_number)
        if not user:
            whatsapp_service.send_message(
                From, 
                "¡Hola! Para usar Control Finanzas, primero debes registrarte en nuestro sitio web. Visita nuestro dashboard y regístrate con este número de teléfono."
            )
            return {"status": "user_not_found"}
        
        # Check if user can add more transactions
        if not UserService.can_add_transaction(db, str(user.id)):
            whatsapp_service.send_upgrade_prompt(From)
            return {"status": "limit_reached"}
        
        # Parse the message using ParserAgent
        parsed_data = parser_agent.parse_message(message_body)
        
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
        
        # Send confirmation
        whatsapp_service.send_transaction_confirmation(
            From,
            float(parsed_data["amount"]),
            transaction_type,
            category,
            user.currency if user.currency != "CRC" else "₡"
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