"""
Simplified Master Router using CrewAI Tools Architecture
Replaces complex manual routing with tool-based financial agent
"""

from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from app.agents.financial_agent import FinancialAgent
from app.services.conversation_state import conversation_state


class MasterRouterAgent:
    """
    Simplified master router using FinancialAgent with CrewAI Tools
    This eliminates the complex manual routing that was causing bugs
    """
    
    def __init__(self):
        pass  # No complex initialization needed
    
    def route_and_process(self, message: str, user_id: str, db: Session) -> Dict[str, Any]:
        """
        Main routing method using tools-based FinancialAgent
        """
        print(f"🤖 Processing with ToolsBased FinancialAgent: '{message}'")
        
        try:
            # Check for pending transaction selection first
            pending_transaction = conversation_state.get_pending_transaction(user_id)
            if pending_transaction:
                print(f"💾 FOUND PENDING TRANSACTION - handling organization selection")
                return self._handle_pending_organization_selection(message, user_id, db, pending_transaction)
            
            # Use FinancialAgent with tools for all other cases
            financial_agent = FinancialAgent(db=db, user_id=user_id)
            result = financial_agent.process_message(message)
            
            print(f"🤖 FinancialAgent result: {result.get('success')}")
            return result
            
        except Exception as e:
            print(f"Error in MasterRouterAgent: {e}")
            return {
                "success": False,
                "message": "🤔 Ocurrió un error procesando tu mensaje. Intenta de nuevo.",
                "action": "error"
            }
    
    def _handle_pending_organization_selection(self, message: str, user_id: str, db: Session, pending_transaction: Dict) -> Dict[str, Any]:
        """Handle organization selection for pending transactions"""
        
        transaction_data = pending_transaction["transaction_data"]
        available_contexts = pending_transaction["available_contexts"]
        
        print(f"🔍 HANDLING ORG SELECTION: message='{message}', contexts={len(available_contexts)}")
        
        # Simple organization selection logic
        message_lower = message.lower().strip()
        
        # Handle "personal" variations
        if message_lower in ["personal", "mío", "mio", "propio", "yo"]:
            org_selection = {
                "organization_id": None,
                "organization_name": "Personal"
            }
        # Handle numeric selection
        elif message_lower.isdigit():
            selection_num = int(message_lower)
            if 1 <= selection_num <= len(available_contexts):
                org = available_contexts[selection_num - 1]
                org_selection = {
                    "organization_id": org["id"],
                    "organization_name": org["name"]
                }
            elif selection_num == len(available_contexts) + 1:
                # Personal option (last number)
                org_selection = {
                    "organization_id": None,
                    "organization_name": "Personal"
                }
            else:
                org_selection = None
        # Handle organization name matches
        else:
            org_selection = None
            for org in available_contexts:
                if org["name"].lower() in message_lower or message_lower in org["name"].lower():
                    org_selection = {
                        "organization_id": org["id"],
                        "organization_name": org["name"]
                    }
                    break
        
        if org_selection:
            # Clear pending transaction
            conversation_state.clear_pending_transaction(user_id)
            
            # Update transaction data with organization
            transaction_data.update(org_selection)
            
            # Create the expense using AddExpenseTool
            from app.tools.financial_tools import AddExpenseTool
            
            add_expense_tool = AddExpenseTool(db=db, user_id=user_id)
            
            # Create transaction directly since we have all data
            try:
                from app.services.transaction_service import TransactionService
                from app.services.user_service import UserService
                from app.core.schemas import TransactionCreate
                from app.models.transaction import TransactionType
                from uuid import UUID
                from decimal import Decimal
                
                user = UserService.get_user(db, user_id)
                
                # Convert organization_id to UUID if needed
                org_uuid = None
                if transaction_data.get("organization_id"):
                    org_uuid = UUID(transaction_data["organization_id"]) if isinstance(transaction_data["organization_id"], str) else transaction_data["organization_id"]
                
                transaction_create = TransactionCreate(
                    user_id=UUID(user_id) if isinstance(user_id, str) else user_id,
                    organization_id=org_uuid,
                    amount=Decimal(str(transaction_data["amount"])),
                    type=TransactionType.expense,
                    category=add_expense_tool._categorize_expense(transaction_data["description"]),
                    description=transaction_data["description"]
                )
                
                transaction = TransactionService.create_transaction(db, transaction_create)
                
                currency = "₡" if user and user.currency == "CRC" else "$"
                org_name = transaction_data.get("organization_name", "Personal")
                
                return {
                    "success": True,
                    "message": f"✅ **Gasto registrado**\n\n💸 {currency}{transaction_data['amount']:,.0f} en {transaction_data['description']}\n🏷️ Organización: {org_name}\n📅 {transaction.date.strftime('%d/%m/%Y')}",
                    "action": "expense_created"
                }
                
            except Exception as e:
                print(f"Error creating transaction: {e}")
                return {
                    "success": False,
                    "message": f"❌ Error al crear la transacción: {str(e)}",
                    "action": "creation_error"
                }
        else:
            # Invalid selection, ask again
            org_options = []
            for i, org in enumerate(available_contexts, 1):
                emoji = "👨‍👩‍👧‍👦" if org["type"] == "family" else "🏢"
                org_options.append(f"{i}. {emoji} {org['name']}")
            
            org_list = "\n".join(org_options)
            personal_option = f"{len(available_contexts) + 1}. 👤 Personal"
            
            return {
                "success": False,
                "message": f"🤔 No entendí tu selección\n\n🏷️ **¿Dónde registrar el gasto?**\n\n{org_list}\n{personal_option}\n\n📝 Responde con el número:",
                "action": "expense_need_organization"
            }