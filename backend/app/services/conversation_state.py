from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import json

class ConversationState:
    """
    Manages conversation state for multi-step interactions like context selection.
    Simple in-memory implementation for MVP, can be moved to Redis later.
    """
    
    def __init__(self):
        # In-memory storage: {user_id: {state_data}}
        self._states = {}
        # Auto-cleanup after 10 minutes
        self._expiry_minutes = 10
    
    def set_pending_transaction(self, user_id: str, transaction_data: Dict[str, Any], available_contexts: list) -> None:
        """
        Store a pending transaction waiting for context selection.
        
        Args:
            user_id: User ID
            transaction_data: Parsed transaction data (amount, description, etc.)
            available_contexts: List of available contexts for the user
        """
        
        self._states[user_id] = {
            "type": "pending_transaction_context",
            "transaction_data": transaction_data,
            "available_contexts": available_contexts,
            "created_at": datetime.now(),
            "expires_at": datetime.now() + timedelta(minutes=self._expiry_minutes)
        }
    
    def get_pending_transaction(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get pending transaction for user if it exists and hasn't expired.
        
        Returns:
            Dict with transaction data and contexts, or None if no pending transaction
        """
        
        if user_id not in self._states:
            return None
        
        state = self._states[user_id]
        
        # Check if expired
        if datetime.now() > state["expires_at"]:
            del self._states[user_id]
            return None
        
        if state["type"] == "pending_transaction_context":
            return {
                "transaction_data": state["transaction_data"],
                "available_contexts": state["available_contexts"]
            }
        
        return None
    
    def clear_pending_transaction(self, user_id: str) -> None:
        """Clear pending transaction for user."""
        if user_id in self._states:
            del self._states[user_id]
    
    def has_pending_transaction(self, user_id: str) -> bool:
        """Check if user has a pending transaction waiting for context."""
        return self.get_pending_transaction(user_id) is not None
    
    def cleanup_expired(self) -> None:
        """Remove expired states."""
        now = datetime.now()
        expired_users = [
            user_id for user_id, state in self._states.items()
            if now > state["expires_at"]
        ]
        
        for user_id in expired_users:
            del self._states[user_id]
    
    def get_state_info(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get state info for debugging."""
        if user_id in self._states:
            state = self._states[user_id].copy()
            # Convert datetime to string for JSON serialization
            state["created_at"] = state["created_at"].isoformat()
            state["expires_at"] = state["expires_at"].isoformat()
            return state
        return None


# Global instance
conversation_state = ConversationState()