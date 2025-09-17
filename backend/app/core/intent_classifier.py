from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import re

@dataclass
class IntentPattern:
    """Pattern for intent detection"""
    action_type: str
    keywords: List[str]
    priority: int  # Higher number = higher priority
    requires_amount: bool = False
    requires_phone: bool = False
    exclude_keywords: List[str] = None
    
    def __post_init__(self):
        if self.exclude_keywords is None:
            self.exclude_keywords = []

@dataclass
class IntentMatch:
    """Result of intent matching"""
    action_type: str
    confidence: float
    priority: int
    matched_keywords: List[str]
    parameters: Dict[str, Any]

class IntentClassifier:
    """Intelligent intent classification system for easy feature addition"""
    
    def __init__(self):
        self.patterns = self._initialize_patterns()
    
    def _initialize_patterns(self) -> List[IntentPattern]:
        """Initialize all intent patterns with priorities"""
        return [
            # BUDGET MANAGEMENT - High priority to prevent org conflicts
            IntentPattern(
                action_type="manage_budgets",
                keywords=["crear presupuesto", "presupuesto para", "presupuesto mensual", 
                         "presupuesto semanal", "presupuesto anual", "límite de gasto", 
                         "budget", "alertas de gasto", "presupuesto", "presupuestos"],
                priority=100,  # Very high priority
                requires_amount=False,  # Allow without amount for prompting
                exclude_keywords=["familia", "empresa", "equipo", "organización"]
            ),
            
            # ACCEPT INVITATION - Highest priority for exact matches
            IntentPattern(
                action_type="accept_invitation",
                keywords=["acepto", "aceptar", "quiero unirme", "sí quiero"],
                priority=200,  # Highest priority
            ),
            
            # ORGANIZATION MANAGEMENT
            IntentPattern(
                action_type="create_organization",
                keywords=["crear familia", "crear empresa", "nueva familia", 
                         "nueva empresa", "agregar familia", "agregar empresa", 
                         "crear organizacion", "crear equipo"],
                priority=80,
                exclude_keywords=["presupuesto", "budget", "límite"]
            ),
            
            IntentPattern(
                action_type="invite_member",
                keywords=["invitar", "invita", "agregar"],
                priority=90,
                requires_phone=True
            ),
            
            IntentPattern(
                action_type="list_members",
                keywords=["miembros", "quiénes están", "mostrar miembros", "ver miembros"],
                priority=70
            ),
            
            IntentPattern(
                action_type="leave_organization",
                keywords=["salir", "abandonar", "dejar familia", "dejar empresa"],
                priority=70
            ),
            
            # TRANSACTION MANAGEMENT
            IntentPattern(
                action_type="create_transaction",
                keywords=["gasté", "gaste", "pagué", "pague", "compré", "compre", 
                         "ingreso", "recibí", "gané"],
                priority=60,
                requires_amount=True
            ),
            
            IntentPattern(
                action_type="manage_transactions",
                keywords=["eliminar gasto", "borrar gasto", "editar gasto", 
                         "cambiar gasto", "últimos gastos", "transacciones recientes",
                         "eliminar último", "borrar último", "modificar gasto"],
                priority=85
            ),
            
            # REPORTS
            IntentPattern(
                action_type="generate_report",
                keywords=["resumen", "reporte", "balance", "cuánto", "cuanto", 
                         "mis gastos", "total gastos", "gastos del mes", 
                         "como voy", "cómo voy"],
                priority=75
            ),
            
            # HELP
            IntentPattern(
                action_type="help_request",
                keywords=["ayuda", "help", "cómo", "como", "comandos", 
                         "funciones", "qué puedo hacer", "no entiendo"],
                priority=50  # Lower priority to avoid conflicts
            ),
            
            # PRIVACY
            IntentPattern(
                action_type="privacy_request",
                keywords=["privacidad", "datos", "derechos", "seguridad", 
                         "eliminar cuenta", "privacy", "rights"],
                priority=60
            )
        ]
    
    def classify_intent(self, message: str) -> Optional[IntentMatch]:
        """Classify user intent with smart matching"""
        message_lower = message.lower().strip()
        
        matches = []
        
        for pattern in self.patterns:
            match = self._match_pattern(pattern, message_lower, message)
            if match:
                matches.append(match)
        
        if not matches:
            return None
        
        # Sort by priority (descending) then by confidence (descending)
        matches.sort(key=lambda x: (x.priority, x.confidence), reverse=True)
        
        # Return best match
        return matches[0]
    
    def _match_pattern(self, pattern: IntentPattern, message_lower: str, original_message: str) -> Optional[IntentMatch]:
        """Check if message matches a specific pattern"""
        
        # Check for exclude keywords first
        if any(exclude in message_lower for exclude in pattern.exclude_keywords):
            return None
        
        # Find matching keywords
        matched_keywords = []
        for keyword in pattern.keywords:
            if keyword in message_lower:
                matched_keywords.append(keyword)
        
        if not matched_keywords:
            return None
        
        # Check requirements
        parameters = {}
        
        # Extract amount if required
        if pattern.requires_amount:
            amount = self._extract_amount(original_message)
            if not amount:
                return None  # Required amount not found
            parameters["amount"] = amount
        
        # Extract phone if required
        if pattern.requires_phone:
            phone = self._extract_phone_number(original_message)
            if not phone:
                return None  # Required phone not found
            parameters["phone_number"] = phone
        
        # Extract additional parameters based on action type
        parameters.update(self._extract_action_specific_parameters(
            pattern.action_type, original_message, message_lower
        ))
        
        # Calculate confidence based on keyword matches and requirements
        confidence = self._calculate_confidence(
            matched_keywords, pattern.keywords, pattern, parameters
        )
        
        return IntentMatch(
            action_type=pattern.action_type,
            confidence=confidence,
            priority=pattern.priority,
            matched_keywords=matched_keywords,
            parameters=parameters
        )
    
    def _extract_amount(self, message: str) -> Optional[float]:
        """Extract monetary amount from message"""
        # Remove currency symbols for better matching
        clean_message = message.replace('₡', '').replace('$', '')
        
        patterns = [
            r"(\d{1,3}(?:[,\s]\d{3})*(?:[.,]\d{2})?)",  # 1,000.00 or 1 000,50
            r"(\d+(?:\.\d+)?)"  # Simple numbers
        ]
        
        amounts = []
        for pattern in patterns:
            matches = re.findall(pattern, clean_message)
            for match in matches:
                try:
                    # Clean and convert
                    clean_amount = match.replace(',', '').replace(' ', '')
                    amount = float(clean_amount)
                    if amount > 0:  # Valid amount
                        amounts.append(amount)
                except:
                    continue
        
        return max(amounts) if amounts else None
    
    def _extract_phone_number(self, message: str) -> Optional[str]:
        """Extract phone number from message"""
        phone_patterns = [
            r"(\+506\s?\d{4}\s?\d{4})",  # +506 1234 5678
            r"(\+506\d{8})",            # +50612345678
            r"(506\s?\d{4}\s?\d{4})",   # 506 1234 5678
            r"(506\d{8})",              # 50612345678
            r"(\d{4}[-\s]?\d{4})",      # 1234-5678 or 1234 5678
            r"(\+\d{1,3}\d{8,})"       # Generic international
        ]
        
        for pattern in phone_patterns:
            match = re.search(pattern, message)
            if match:
                number = match.group(1)
                # Normalize the number
                if not number.startswith('+'):
                    if number.startswith('506'):
                        return '+' + number.replace(' ', '').replace('-', '')
                    else:
                        # Assume Costa Rica if no country code
                        return '+506' + number.replace('-', '').replace(' ', '')
                else:
                    return number.replace(' ', '').replace('-', '')
        
        return None
    
    def _extract_action_specific_parameters(self, action_type: str, message: str, message_lower: str) -> Dict[str, Any]:
        """Extract parameters specific to each action type"""
        parameters = {}
        
        if action_type == "manage_budgets":
            # Extract budget-specific parameters
            parameters.update(self._extract_budget_parameters(message, message_lower))
        
        elif action_type == "create_transaction":
            # Extract transaction-specific parameters
            parameters.update(self._extract_transaction_parameters(message, message_lower))
        
        elif action_type == "create_organization":
            # Extract organization name
            org_name = self._extract_organization_name(message, message_lower)
            if org_name:
                parameters["organization_name"] = org_name
        
        elif action_type == "invite_member":
            # Extract person to invite (if no phone number)
            person = self._extract_person_to_invite(message, message_lower)
            if person:
                parameters["person_to_invite"] = person
        
        return parameters
    
    def _extract_budget_parameters(self, message: str, message_lower: str) -> Dict[str, Any]:
        """Extract budget-specific parameters"""
        parameters = {}
        
        # Extract category (after "para")
        if " para " in message_lower:
            parts = message_lower.split(" para ")
            if len(parts) > 1:
                parameters["budget_category"] = parts[1].strip().title()
        
        # Extract period
        period = "monthly"  # default
        if "semanal" in message_lower or "weekly" in message_lower:
            period = "weekly"
        elif "anual" in message_lower or "yearly" in message_lower:
            period = "yearly"
        parameters["budget_period"] = period
        
        # Extract alert percentage if mentioned
        alert_match = re.search(r"alert[a-z]*\s+al?\s+(\d+)%", message_lower)
        if alert_match:
            parameters["alert_percentage"] = float(alert_match.group(1))
        
        return parameters
    
    def _extract_transaction_parameters(self, message: str, message_lower: str) -> Dict[str, Any]:
        """Extract transaction-specific parameters"""
        parameters = {
            "description": message,
            "transaction_type": "expense"  # default
        }
        
        # Detect income vs expense
        income_keywords = ["ingreso", "recibí", "gané", "cobré", "entrada"]
        if any(keyword in message_lower for keyword in income_keywords):
            parameters["transaction_type"] = "income"
        
        # Extract organization context
        org_context = self._extract_organization_context(message, message_lower)
        if org_context:
            parameters["organization_context"] = org_context
        
        return parameters
    
    def _extract_organization_name(self, message: str, message_lower: str) -> Optional[str]:
        """Extract organization name from creation message"""
        # Remove action keywords to get the name
        clean_message = message
        remove_patterns = [
            r"crear\s+(familia|empresa|equipo|organizacion)\s*",
            r"nueva?\s+(familia|empresa|equipo|organizacion)\s*",
            r"agregar\s+(familia|empresa|equipo|organizacion)\s*"
        ]
        
        for pattern in remove_patterns:
            clean_message = re.sub(pattern, "", clean_message, flags=re.IGNORECASE)
        
        name = clean_message.strip()
        return name if len(name) > 0 else None
    
    def _extract_person_to_invite(self, message: str, message_lower: str) -> Optional[str]:
        """Extract person description when no phone number provided"""
        # Remove action keywords
        clean_message = message_lower
        remove_patterns = [
            r"invitar?\s+(a\s+)?",
            r"agregar\s+(a\s+)?",
            r"invita\s+(a\s+)?"
        ]
        
        for pattern in remove_patterns:
            clean_message = re.sub(pattern, "", clean_message)
        
        person = clean_message.strip()
        return person if len(person) > 2 else None
    
    def _extract_organization_context(self, message: str, message_lower: str) -> Optional[str]:
        """Extract organization context from transaction message"""
        # Look for patterns like "en [organization]" or "a [organization]"
        context_patterns = [
            r"en\s+([a-zA-Z]+)",
            r"a\s+([a-zA-Z]+)",
            r"para\s+([a-zA-Z]+)"
        ]
        
        for pattern in context_patterns:
            match = re.search(pattern, message_lower)
            if match:
                context = match.group(1)
                # Skip common words
                skip_words = ["el", "la", "los", "las", "un", "una", "casa", "trabajo"]
                if context not in skip_words:
                    return context.title()
        
        return None
    
    def _calculate_confidence(self, matched_keywords: List[str], all_keywords: List[str], 
                            pattern: IntentPattern, parameters: Dict[str, Any]) -> float:
        """Calculate confidence score for a match"""
        base_confidence = len(matched_keywords) / len(all_keywords)
        
        # Boost confidence if requirements are met
        if pattern.requires_amount and "amount" in parameters:
            base_confidence += 0.2
        
        if pattern.requires_phone and "phone_number" in parameters:
            base_confidence += 0.2
        
        # Boost for exact keyword matches
        for keyword in matched_keywords:
            if len(keyword) > 10:  # Longer, more specific keywords
                base_confidence += 0.1
        
        return min(1.0, base_confidence)
    
    def add_pattern(self, pattern: IntentPattern):
        """Add a new intent pattern (for easy feature addition)"""
        self.patterns.append(pattern)
        # Sort by priority to maintain order
        self.patterns.sort(key=lambda x: x.priority, reverse=True)
    
    def get_supported_actions(self) -> List[str]:
        """Get list of all supported action types"""
        return list(set(pattern.action_type for pattern in self.patterns))