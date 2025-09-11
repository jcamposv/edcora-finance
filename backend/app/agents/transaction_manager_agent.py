from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from app.core.llm_config import get_openai_config
from crewai import Agent, Task, Crew
from app.services.transaction_service import TransactionService
from app.services.user_service import UserService
from app.models.transaction import TransactionType
import json

class TransactionManagerAgent:
    """Agent for managing transactions: delete, edit, and list recent transactions."""
    
    def __init__(self):
        try:
            self.has_openai = get_openai_config()
            
            if self.has_openai:
                self.agent = Agent(
                    role="Transaction Manager Assistant",
                    goal="Help users delete, edit, and manage their transactions through natural conversation in Spanish.",
                    backstory="""Eres un asistente especializado en gestión de transacciones financieras.
                    
                    FUNCIONES QUE MANEJAS:
                    
                    ELIMINAR TRANSACCIONES:
                    - "eliminar el último gasto", "borrar gasto de almuerzo", "quitar el gasto de ₡5000"
                    - Muestras las transacciones recientes para que el usuario elija
                    - Confirmas antes de eliminar
                    
                    EDITAR TRANSACCIONES:
                    - "cambiar el gasto de almuerzo a ₡6000", "editar último gasto"
                    - Permites cambiar monto, descripción o categoría
                    - Confirmas los cambios
                    
                    VER TRANSACCIONES RECIENTES:
                    - "mis últimos gastos", "transacciones recientes", "últimos movimientos"
                    - Muestras lista numerada con ID, fecha, monto y descripción
                    
                    IMPORTANTE:
                    - Solo el propietario de la transacción puede editarla/eliminarla
                    - Siempre confirmas antes de hacer cambios permanentes
                    - Muestras información clara y organizada
                    - Respondes en español de forma amigable
                    """,
                    verbose=True,
                    allow_delegation=False
                )
            else:
                self.agent = None
                
        except Exception as e:
            print(f"Warning: Failed to initialize TransactionManagerAgent: {e}")
            self.has_openai = False
            self.agent = None
    
    def is_transaction_management_request(self, message: str) -> bool:
        """Detect if message is about managing transactions."""
        keywords = [
            "eliminar", "borrar", "quitar", "delete", "remove",
            "editar", "cambiar", "modificar", "edit", "change", "update",
            "últimos gastos", "transacciones recientes", "últimos movimientos",
            "mis gastos recientes", "ver gastos", "listar gastos"
        ]
        
        message_lower = message.lower()
        return any(keyword in message_lower for keyword in keywords)
    
    def handle_transaction_management(self, message: str, user_id: str, db: Session) -> Dict[str, Any]:
        """Handle transaction management requests."""
        
        if self.has_openai and self.agent:
            return self._ai_handle_transaction_management(message, user_id, db)
        else:
            return self._fallback_handle_transaction_management(message, user_id, db)
    
    def _ai_handle_transaction_management(self, message: str, user_id: str, db: Session) -> Dict[str, Any]:
        """Use AI to understand and process transaction management requests."""
        try:
            # Get recent transactions
            recent_transactions = TransactionService.get_user_transactions(
                db, user_id, skip=0, limit=10
            )
            
            # Format transactions for AI
            transactions_info = self._format_transactions_for_ai(recent_transactions)
            
            task = Task(
                description=f"""
                El usuario quiere gestionar sus transacciones: "{message}"
                
                TRANSACCIONES RECIENTES:
                {transactions_info}
                
                USUARIO ID: {user_id}
                
                ANALIZA QUE QUIERE HACER:
                
                1. MOSTRAR TRANSACCIONES RECIENTES:
                   - "mis últimos gastos", "ver transacciones", "transacciones recientes"
                   - Acción: "list_recent"
                
                2. ELIMINAR TRANSACCIÓN:
                   - "eliminar último gasto", "borrar gasto de almuerzo", "quitar el de ₡5000"
                   - Acción: "delete" + transaction_id si es específico
                   - Si no es específico, mostrar lista para elegir
                
                3. EDITAR TRANSACCIÓN:
                   - "cambiar último gasto a ₡6000", "editar gasto de almuerzo"
                   - Acción: "edit" + transaction_id + nuevos datos
                   - Si no es específico, mostrar lista para elegir
                
                RESPONDE EN JSON:
                {{
                    "action": "list_recent|delete|edit",
                    "transaction_id": "id_si_específico_o_null",
                    "new_amount": "nuevo_monto_si_aplica",
                    "new_description": "nueva_descripción_si_aplica",
                    "confidence": "alta|media|baja"
                }}
                """,
                agent=self.agent,
                expected_output="JSON con la acción a realizar"
            )
            
            crew = Crew(agents=[self.agent], tasks=[task])
            result = str(crew.kickoff()).strip()
            
            # Parse AI response
            try:
                # Extract JSON from response
                import re
                json_match = re.search(r'\{.*\}', result, re.DOTALL)
                if json_match:
                    analysis = json.loads(json_match.group(0))
                else:
                    analysis = json.loads(result)
            except:
                analysis = {"action": "list_recent", "confidence": "baja"}
            
            return self._execute_transaction_action(analysis, message, user_id, db, recent_transactions)
            
        except Exception as e:
            print(f"Error in AI transaction management: {e}")
            return self._fallback_handle_transaction_management(message, user_id, db)
    
    def _execute_transaction_action(self, analysis: Dict, original_message: str, user_id: str, 
                                   db: Session, transactions: List) -> Dict[str, Any]:
        """Execute the transaction management action."""
        action = analysis.get("action", "list_recent")
        
        # Check if user is referring to a number in the list (e.g., "gasto 2", "eliminar 3")
        transaction_index = self._extract_transaction_number(original_message)
        print(f"🔍 Extracted transaction index: {transaction_index} from message: '{original_message}'")
        
        if transaction_index is not None and 1 <= transaction_index <= len(transactions):
            selected_transaction = transactions[transaction_index - 1]  # Convert to 0-based index
            transaction_id = str(selected_transaction.id)
            print(f"🎯 Selected transaction: {transaction_id} (index {transaction_index}, amount: ₡{selected_transaction.amount})")
            
            if action == "delete" or any(word in original_message.lower() for word in ["eliminar", "borrar"]):
                return self._delete_specific_transaction(transaction_id, user_id, db)
            elif action == "edit" or any(word in original_message.lower() for word in ["editar", "cambiar"]):
                new_amount = analysis.get("new_amount")
                new_description = analysis.get("new_description")
                return self._edit_specific_transaction(transaction_id, user_id, db, new_amount, new_description)
        
        if action == "list_recent":
            return self._show_recent_transactions(transactions, user_id)
            
        elif action == "delete":
            transaction_id = analysis.get("transaction_id")
            if transaction_id:
                return self._delete_specific_transaction(transaction_id, user_id, db)
            else:
                return self._show_transactions_for_deletion(transactions)
                
        elif action == "edit":
            transaction_id = analysis.get("transaction_id")
            new_amount = analysis.get("new_amount")
            new_description = analysis.get("new_description")
            
            if transaction_id:
                return self._edit_specific_transaction(
                    transaction_id, user_id, db, new_amount, new_description
                )
            else:
                return self._show_transactions_for_editing(transactions)
        
        else:
            return self._show_recent_transactions(transactions, user_id)
    
    def _extract_transaction_number(self, message: str) -> Optional[int]:
        """Extract transaction number from message like 'eliminar gasto 2' or 'cambiar 3'."""
        import re
        
        # Patterns to match numbers referring to transactions
        patterns = [
            r"(?:gasto|transacción|transaccion)\s+(\d+)",  # "gasto 2", "transacción 3"
            r"(?:eliminar|borrar|editar|cambiar)\s+(?:gasto\s+)?(\d+)",  # "eliminar 2", "eliminar gasto 2"
            r"(?:el\s+)?(\d+)(?:\s*$)",  # Just a number at the end
            r"\b(\d+)\b"  # Any single digit in the message
        ]
        
        for pattern in patterns:
            match = re.search(pattern, message.lower())
            if match:
                try:
                    return int(match.group(1))
                except (ValueError, IndexError):
                    continue
        
        return None
    
    def _format_transactions_for_ai(self, transactions: List) -> str:
        """Format transactions for AI processing."""
        if not transactions:
            return "No hay transacciones recientes"
        
        formatted = []
        for i, t in enumerate(transactions[:5], 1):
            type_symbol = "💸" if t.type == TransactionType.expense else "💰"
            formatted.append(f"{i}. ID:{str(t.id)[:8]} | {t.date} | {type_symbol} ₡{t.amount:,.0f} | {t.description}")
        
        return "\n".join(formatted)
    
    def _show_recent_transactions(self, transactions: List, user_id: str) -> Dict[str, Any]:
        """Show recent transactions to user."""
        if not transactions:
            return {
                "success": True,
                "message": "📊 No tienes transacciones registradas aún.\n\n💡 Registra tu primer gasto con: 'Gasté ₡5000 en almuerzo'"
            }
        
        message = "📊 **Tus Últimas Transacciones:**\n\n"
        
        for i, t in enumerate(transactions[:10], 1):
            type_symbol = "💸" if t.type == TransactionType.expense else "💰"
            date_str = t.date.strftime("%d/%m")
            message += f"{i}. {date_str} | {type_symbol} ₡{t.amount:,.0f} | {t.description}\n"
        
        message += "\n💡 **Para gestionar:**\n"
        message += "• 'Eliminar gasto 3' (número de la lista)\n"
        message += "• 'Cambiar gasto 2 a ₡8000'\n"
        message += "• 'Borrar último gasto'"
        
        return {
            "success": True,
            "message": message
        }
    
    def _show_transactions_for_deletion(self, transactions: List) -> Dict[str, Any]:
        """Show transactions with deletion options."""
        if not transactions:
            return {
                "success": True,
                "message": "📊 No tienes transacciones para eliminar."
            }
        
        message = "🗑️ **¿Cuál gasto quieres eliminar?**\n\n"
        
        for i, t in enumerate(transactions[:5], 1):
            type_symbol = "💸" if t.type == TransactionType.expense else "💰"
            date_str = t.date.strftime("%d/%m")
            message += f"{i}. {date_str} | {type_symbol} ₡{t.amount:,.0f} | {t.description}\n"
        
        message += "\n💡 Responde con el número (ej: '3') o 'cancelar'"
        
        return {
            "success": True,
            "message": message,
            "awaiting_selection": True,
            "action_type": "delete",
            "transactions": [str(t.id) for t in transactions[:5]]
        }
    
    def _show_transactions_for_editing(self, transactions: List) -> Dict[str, Any]:
        """Show transactions with editing options."""
        if not transactions:
            return {
                "success": True,
                "message": "📊 No tienes transacciones para editar."
            }
        
        message = "✏️ **¿Cuál gasto quieres editar?**\n\n"
        
        for i, t in enumerate(transactions[:5], 1):
            type_symbol = "💸" if t.type == TransactionType.expense else "💰"
            date_str = t.date.strftime("%d/%m")
            message += f"{i}. {date_str} | {type_symbol} ₡{t.amount:,.0f} | {t.description}\n"
        
        message += "\n💡 Responde con el número (ej: '2') o 'cancelar'"
        
        return {
            "success": True,
            "message": message,
            "awaiting_selection": True,
            "action_type": "edit",
            "transactions": [str(t.id) for t in transactions[:5]]
        }
    
    def _delete_specific_transaction(self, transaction_id: str, user_id: str, db: Session) -> Dict[str, Any]:
        """Delete a specific transaction."""
        try:
            print(f"🗑️ Attempting to delete transaction: {transaction_id} for user: {user_id}")
            
            # Verify ownership
            transaction = TransactionService.get_transaction(db, transaction_id)
            print(f"🔍 Found transaction: {transaction is not None}")
            
            if not transaction:
                print(f"❌ Transaction not found: {transaction_id}")
                return {
                    "success": False,
                    "message": "❌ No se encontró esa transacción."
                }
                
            if str(transaction.user_id) != user_id:
                print(f"❌ User {user_id} doesn't own transaction owned by {transaction.user_id}")
                return {
                    "success": False,
                    "message": "❌ No tienes permisos para eliminar esa transacción."
                }
            
            # Delete transaction
            success = TransactionService.delete_transaction(db, transaction_id)
            
            if success:
                type_text = "gasto" if transaction.type == TransactionType.expense else "ingreso"
                return {
                    "success": True,
                    "message": f"✅ {type_text.capitalize()} eliminado: ₡{transaction.amount:,.0f} - {transaction.description}"
                }
            else:
                return {
                    "success": False,
                    "message": "❌ No se pudo eliminar la transacción. Intenta de nuevo."
                }
                
        except Exception as e:
            print(f"Error deleting transaction: {e}")
            return {
                "success": False,
                "message": "❌ Error eliminando la transacción."
            }
    
    def _edit_specific_transaction(self, transaction_id: str, user_id: str, db: Session, 
                                 new_amount: Optional[str], new_description: Optional[str]) -> Dict[str, Any]:
        """Edit a specific transaction."""
        try:
            # Verify ownership
            transaction = TransactionService.get_transaction(db, transaction_id)
            if not transaction or str(transaction.user_id) != user_id:
                return {
                    "success": False,
                    "message": "❌ No tienes permisos para editar esa transacción."
                }
            
            # Prepare updates
            from app.core.schemas import TransactionUpdate
            updates = {}
            
            if new_amount:
                try:
                    # Extract numeric value
                    import re
                    amount_match = re.search(r'(\d+(?:\.\d+)?)', new_amount.replace(',', ''))
                    if amount_match:
                        updates['amount'] = float(amount_match.group(1))
                except:
                    pass
            
            if new_description:
                updates['description'] = new_description
            
            if not updates:
                return {
                    "success": False,
                    "message": "❌ No hay cambios válidos para realizar."
                }
            
            # Update transaction
            transaction_update = TransactionUpdate(**updates)
            updated_transaction = TransactionService.update_transaction(db, transaction_id, transaction_update)
            
            if updated_transaction:
                type_text = "gasto" if updated_transaction.type == TransactionType.expense else "ingreso"
                return {
                    "success": True,
                    "message": f"✅ {type_text.capitalize()} actualizado: ₡{updated_transaction.amount:,.0f} - {updated_transaction.description}"
                }
            else:
                return {
                    "success": False,
                    "message": "❌ No se pudo actualizar la transacción."
                }
                
        except Exception as e:
            print(f"Error updating transaction: {e}")
            return {
                "success": False,
                "message": "❌ Error actualizando la transacción."
            }
    
    def _fallback_handle_transaction_management(self, message: str, user_id: str, db: Session) -> Dict[str, Any]:
        """Fallback when AI is not available."""
        message_lower = message.lower()
        
        # Get recent transactions for any operation
        recent_transactions = TransactionService.get_user_transactions(
            db, user_id, skip=0, limit=10
        )
        
        if "eliminar" in message_lower or "borrar" in message_lower:
            return self._show_transactions_for_deletion(recent_transactions)
        elif "editar" in message_lower or "cambiar" in message_lower:
            return self._show_transactions_for_editing(recent_transactions)
        else:
            return self._show_recent_transactions(recent_transactions, user_id)