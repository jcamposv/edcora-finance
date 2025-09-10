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
from app.agents.organization_agent import OrganizationAgent
from app.agents.context_agent import ContextAgent
from app.agents.help_agent import HelpAgent
from app.agents.master_router_agent import MasterRouterAgent
from app.services.conversation_state import conversation_state
from app.models.transaction import TransactionType
from app.core.schemas import TransactionCreate

router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])

# Initialize services
whatsapp_service = WhatsAppService()
otp_service = OTPService()
parser_agent = ParserAgent()
categorizer_agent = CategorizerAgent()
report_agent = ReportAgent()
organization_agent = OrganizationAgent()
context_agent = ContextAgent()
help_agent = HelpAgent()
master_router = MasterRouterAgent()

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
            
            # Enhanced welcome message for new users
            welcome_message = f"""🎉 **¡Bienvenido a Edcora Finanzas!**

🔐 **Tu Privacidad es Nuestra Prioridad:**
• Tus datos financieros están encriptados y seguros
• Solo TÚ tienes acceso a tu información personal
• Nunca compartimos datos con terceros
• Puedes eliminar tu cuenta en cualquier momento

💰 **Tu Moneda:** {default_currency}
🆓 **Plan:** Gratuito (transacciones ilimitadas)

📱 **¿Qué puedes hacer?**

💳 **Registrar gastos/ingresos:**
• "Gasté ₡5000 en almuerzo"
• "Ingreso ₡50000 salario"
• "Pagué $25 Netflix"

👨‍👩‍👧‍👦 **Organizaciones (familia/empresa):**
• "Crear familia Mi Hogar"
• "Crear empresa Gymgo"
• "Invitar +50612345678"

📊 **Reportes inteligentes:**
• "Resumen de gastos"
• "Cuánto gasté esta semana"
• "Balance familiar"

❓ **Ayuda:**
• Escribe "ayuda" o "¿cómo funciona?"

🛡️ **Tus Derechos:**
• Acceso a todos tus datos
• Rectificación de información
• Eliminación de cuenta
• Portabilidad de datos

🔐 **Privacidad Garantizada:**
• Escribe 'privacidad' para info completa
• Escribe 'derechos' para tus derechos
• Escribe 'eliminar cuenta' si quieres irte

¡Comienza registrando tu primer gasto! 🚀

💡 **Tip:** Escribe 'ayuda' en cualquier momento"""
            
            whatsapp_service.send_message(From, welcome_message)
            return {"status": "user_created"}
        
        # Check if user can add more transactions
        if not UserService.can_add_transaction(db, str(user.id)):
            whatsapp_service.send_upgrade_prompt(From)
            return {"status": "limit_reached"}
        
        # First, check if user is responding to a context question
        pending_transaction = conversation_state.get_pending_transaction(str(user.id))
        if pending_transaction:
            return handle_context_response(From, message_body, user, pending_transaction, db)
        
        # Use Master Router for intelligent processing
        try:
            print(f"🤖 Processing with MasterRouter: '{message_body}'")
            result = master_router.route_and_process(message_body, str(user.id), db)
            print(f"🤖 MasterRouter result: {result}")
            
            if result.get("success", False):
                # Send main message
                whatsapp_service.send_message(From, result["message"])
                
                # Send additional messages if they exist (for long responses)
                additional_messages = result.get("additional_messages", [])
                for additional_msg in additional_messages:
                    whatsapp_service.send_message(From, additional_msg)
                
                return {"status": "master_router_success", "action": result.get("action", "unknown"), "messages_sent": 1 + len(additional_messages)}
            else:
                # If master router couldn't handle it, send the error message
                whatsapp_service.send_message(From, result.get("message", "No pude procesar tu mensaje."))
                return {"status": "master_router_handled", "action": result.get("action", "unknown")}
                
        except Exception as e:
            print(f"❌ CRITICAL Error in master router: {e}")
            print(f"❌ Error type: {type(e).__name__}")
            import traceback
            print(f"❌ Traceback: {traceback.format_exc()}")
            
            # Instead of falling back to transaction parsing, try direct report detection
            message_lower = message_body.lower()
            
            # Check if it's clearly a report request
            if any(word in message_lower for word in ["resumen", "reporte", "balance", "cuánto", "cuanto", "mis gastos", "total gastos", "gastos del", "como voy", "cómo voy"]):
                print("🔄 Detected report request in fallback, routing to ReportAgent")
                try:
                    from app.agents.report_agent import ReportAgent
                    from app.services.user_service import UserService
                    
                    report_agent = ReportAgent()
                    user_obj = UserService.get_user(db, str(user.id))
                    currency_symbol = "₡" if user_obj and user_obj.currency == "CRC" else "$"
                    
                    result = report_agent.generate_report(message_body, str(user.id), db, currency_symbol)
                    
                    if result.get("success", False):
                        whatsapp_service.send_message(From, result.get("report", "Reporte generado"))
                        return {"status": "fallback_report_success"}
                    else:
                        whatsapp_service.send_message(From, "No pude generar el reporte en este momento.")
                        return {"status": "fallback_report_failed"}
                        
                except Exception as report_error:
                    print(f"❌ Error in fallback report: {report_error}")
            
            # If not a report, then fallback to transaction parsing
            return handle_new_transaction(From, message_body, user, phone_number, db)
        
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


def handle_new_transaction(from_number: str, message_body: str, user, phone_number: str, db: Session):
    """Handle new transaction with intelligent context detection."""
    
    # Check if user has permission to create transactions (organization role check)  
    if not TransactionService.can_user_create_transaction(db, str(user.id)):
        whatsapp_service.send_message(
            from_number,
            "❌ No tienes permisos para registrar transacciones.\n\nSi perteneces a una organización, solo los miembros y administradores pueden agregar gastos. Los observadores solo pueden ver reportes."
        )
        return {"status": "permission_denied"}
    
    # Parse the transaction
    parsed_data = parser_agent.parse_message(message_body, phone_number)
    
    if not parsed_data["success"] or not parsed_data["amount"]:
        whatsapp_service.send_message(
            from_number,
            "No pude entender el monto en tu mensaje. Por favor, intenta con este formato:\n\n'Gasté ₡5000 en almuerzo' o '₡10000 gasolina'"
        )
        return {"status": "parse_error"}
    
    # Get user's available contexts (personal + organizations)
    user_contexts = context_agent.get_user_contexts(db, str(user.id))
    
    # Analyze if context clarification is needed
    context_analysis = context_agent.analyze_transaction_context(
        parsed_data["description"],
        float(parsed_data["amount"]),
        user_contexts
    )
    
    # If context is clear or only one context available, create transaction directly
    if not context_analysis["needs_clarification"]:
        return create_transaction_with_context(
            from_number, parsed_data, user, context_analysis.get("suggested_context", "personal"), db
        )
    
    # Context unclear - ask user to choose
    currency_symbol = parsed_data.get("currency_symbol", "₡")
    question = context_agent.generate_context_question(
        parsed_data["description"],
        float(parsed_data["amount"]),
        currency_symbol,
        user_contexts
    )
    
    # Store pending transaction state
    conversation_state.set_pending_transaction(
        str(user.id),
        parsed_data,
        user_contexts
    )
    
    # Send question to user
    whatsapp_service.send_message(from_number, question)
    
    return {"status": "context_question_sent", "question": question}


def handle_context_response(from_number: str, message_body: str, user, pending_transaction: dict, db: Session):
    """Handle user's response to context selection question."""
    
    try:
        # Parse user's context choice
        selected_context = context_agent.parse_context_response(
            message_body, 
            pending_transaction["available_contexts"]
        )
        
        if not selected_context:
            # User's response unclear, ask again
            whatsapp_service.send_message(
                from_number,
                "No entendí tu respuesta. ¿Podrías decirme si es 'personal', 'familia' o 'trabajo'? 😊"
            )
            return {"status": "context_unclear"}
        
        # Clear pending state
        conversation_state.clear_pending_transaction(str(user.id))
        
        # Create transaction with selected context
        return create_transaction_with_context(
            from_number,
            pending_transaction["transaction_data"], 
            user,
            selected_context,
            db
        )
        
    except Exception as e:
        print(f"Error handling context response: {e}")
        conversation_state.clear_pending_transaction(str(user.id))
        
        whatsapp_service.send_message(
            from_number,
            "Ocurrió un error. Por favor envía tu gasto nuevamente."
        )
        return {"status": "context_error"}


def create_transaction_with_context(from_number: str, parsed_data: dict, user, selected_context, db: Session):
    """Create transaction with the specified context."""
    
    try:
        # Categorize the transaction
        transaction_type = parsed_data["type"]
        category = categorizer_agent.categorize_transaction(
            parsed_data["description"], 
            transaction_type
        )
        
        # Determine organization_id based on context
        organization_id = None
        if isinstance(selected_context, dict) and selected_context.get("type") in ["family", "team", "department", "company"]:
            organization_id = selected_context.get("id")
        
        # Create transaction data
        transaction_data = TransactionCreate(
            user_id=user.id,
            amount=parsed_data["amount"],
            type=TransactionType.income if transaction_type == "income" else TransactionType.expense,
            category=category,
            description=parsed_data["description"],
            organization_id=organization_id
        )
        
        transaction = TransactionService.create_transaction(db, transaction_data)
        
        # Send context-aware confirmation
        currency_symbol = parsed_data.get("currency_symbol", "₡")
        context_name = "personal"
        if isinstance(selected_context, dict):
            context_name = selected_context.get("name", "personal")
        
        confirmation_message = f"✅ Registrado {transaction_type} de {currency_symbol}{float(parsed_data['amount']):,.0f} en {category}"
        
        if context_name != "personal":
            confirmation_message += f" (contexto: {context_name})"
        
        confirmation_message += " 💰"
        
        whatsapp_service.send_message(from_number, confirmation_message)
        
        return {"status": "success", "transaction_id": str(transaction.id), "context": context_name}
        
    except Exception as e:
        print(f"Error creating transaction with context: {e}")
        whatsapp_service.send_message(
            from_number,
            "Ocurrió un error creando la transacción. Por favor intenta nuevamente."
        )
        return {"status": "creation_error"}