"""
CrewAI Tools for Message Parsing
Tools that can be used by ParserAgent for extracting financial information from messages
"""

from crewai.tools import tool
from typing import Dict, Any, Optional
from decimal import Decimal
import re
import json


@tool("parse_message")
def parse_message_tool(message: str, phone_number: str = None) -> str:
    """Parse WhatsApp messages to extract financial transaction information.
    Extracts amount, type, description, organization context, and category from natural language."""
    
    try:
        # Try intelligent parsing first
        result = _intelligent_parse(message)
        if result["success"]:
            return f"Análisis exitoso: Monto={result['amount']}, Tipo={result['type']}, Descripción='{result['description']}', Organización={result['organization_context']}, Categoría={result['category']}"
        
        # Fallback to regex parsing
        result = _regex_parse(message)
        return f"Análisis fallback: Monto={result['amount']}, Tipo={result['type']}, Descripción='{result['description']}', Organización={result['organization_context']}, Categoría={result['category']}"
        
    except Exception as e:
        return f"Error parseando mensaje: {str(e)}"


@tool("validate_parsing")
def validate_parsing_tool(parsed_data: str, original_message: str) -> str:
    """Validate parsed transaction data for consistency and completeness.
    Ensures all required fields are present and data makes sense."""
    
    try:
        validation_errors = []
        warnings = []
        
        # Extract data from parsed result string
        amount_match = re.search(r'Monto=([\d.]+|None)', parsed_data)
        type_match = re.search(r"Tipo=(\w+)", parsed_data)
        description_match = re.search(r"Descripción='([^']*)'", parsed_data)
        org_match = re.search(r"Organización=(\w+|None)", parsed_data)
        
        amount = float(amount_match.group(1)) if amount_match and amount_match.group(1) != "None" else None
        transaction_type = type_match.group(1) if type_match else None
        description = description_match.group(1) if description_match else None
        organization = org_match.group(1) if org_match and org_match.group(1) != "None" else None
        
        # Check required fields
        if not amount:
            validation_errors.append("Monto faltante o cero")
        
        if not description:
            validation_errors.append("Descripción faltante")
        
        # Validate amount
        if amount and amount < 0:
            validation_errors.append("El monto no puede ser negativo")
        
        if amount and amount > 10000000:  # 10 million threshold
            warnings.append("El monto parece inusualmente grande")
        
        # Validate type
        if transaction_type not in ["income", "expense"]:
            validation_errors.append(f"Tipo de transacción inválido: {transaction_type}")
        
        # Validate organization context
        valid_contexts = ["personal", "familia", "empresa", "hogar", None]
        if organization not in valid_contexts:
            warnings.append(f"Contexto organizacional inusual: {organization}")
        
        # Calculate confidence
        confidence = _calculate_confidence(amount, description, original_message)
        
        if len(validation_errors) == 0:
            return f"Validación exitosa: Sin errores, {len(warnings)} advertencias, Confianza={confidence}"
        else:
            return f"Validación fallida: {len(validation_errors)} errores, {len(warnings)} advertencias"
        
    except Exception as e:
        return f"Error validando parsing: {str(e)}"


def _intelligent_parse(message: str) -> Dict[str, Any]:
    """Intelligent parsing using pattern recognition"""
    message_lower = message.lower().strip()
    
    # Extract amount
    amount = _extract_amount(message)
    
    # Extract transaction type
    transaction_type = _extract_type(message_lower)
    
    # Extract organization context
    organization_context = _extract_organization_context(message_lower)
    
    # Extract description
    description = _extract_description(message, amount)
    
    # Extract category
    category = _extract_category(description)
    
    return {
        "success": amount is not None,
        "amount": float(amount) if amount else None,
        "type": transaction_type,
        "description": description,
        "organization_context": organization_context,
        "category": category
    }


def _extract_amount(message: str) -> Optional[Decimal]:
    """Extract amount from message"""
    # Enhanced amount patterns
    amount_patterns = [
        r'₡\s*(\d{1,3}(?:,?\d{3})*(?:\.\d{2})?)',  # ₡1,000 or ₡1,000.50
        r'\$\s*(\d{1,3}(?:,?\d{3})*(?:\.\d{2})?)',  # $1,000 or $1,000.50
        r'(\d{1,3}(?:,?\d{3})*(?:\.\d{2})?)\s*(?:colones?|₡)',  # 1000 colones
        r'(\d{1,3}(?:,?\d{3})*(?:\.\d{2})?)\s*(?:dollars?|dólares?|\$)',  # 1000 dollars
        r'(\d{4,})',  # Just numbers with 4+ digits (likely amounts)
        r'(\d{1,3}(?:,\d{3})+)',  # Numbers with comma separators like 1,000
        r'(\d+(?:\.\d+)?)',  # Any number as last resort
    ]
    
    for pattern in amount_patterns:
        matches = re.findall(pattern, message, re.IGNORECASE)
        if matches:
            try:
                amounts = []
                for match in matches:
                    amount_str = match.replace(',', '')
                    parsed_amount = Decimal(amount_str)
                    if parsed_amount > 0:
                        amounts.append(parsed_amount)
                
                if amounts:
                    return max(amounts)  # Return largest amount found
            except:
                continue
    
    return None


def _extract_type(message_lower: str) -> str:
    """Extract transaction type from message"""
    income_keywords = ["ingreso", "ganancia", "salario", "pago", "cobré", "recibí", "recibo", "gané"]
    expense_keywords = ["gasto", "gasté", "pagué", "compré", "pago", "compra", "costo", "costó"]
    
    if any(keyword in message_lower for keyword in income_keywords):
        return "income"
    elif any(keyword in message_lower for keyword in expense_keywords):
        return "expense"
    
    return "expense"  # Default


def _extract_organization_context(message_lower: str) -> Optional[str]:
    """Extract organization context from message - ONLY if explicitly mentioned"""
    
    # Check for explicit mentions
    if any(word in message_lower for word in ["personal", "mío", "mio", "propio"]):
        return "personal"
    elif any(word in message_lower for word in ["familia", "familiar", "family"]):
        return "familia"
    elif any(word in message_lower for word in ["empresa", "trabajo", "work", "oficina"]):
        return "empresa"
    elif any(word in message_lower for word in ["casa", "hogar", "home"]):
        return "hogar"
    
    return None  # CRITICAL: Return None if no explicit context


def _extract_description(message: str, amount: Optional[Decimal]) -> str:
    """Extract clean description from message"""
    clean_message = message
    
    # Remove action words
    action_patterns = [
        r"gasté\s+", r"gaste\s+", r"pagué\s+", r"pague\s+", 
        r"compré\s+", r"compre\s+", r"gasto\s+", r"agregar\s+gasto\s+",
        r"pago\s+", r"compra\s+", r"costo\s+", r"costó\s+", r"invertí\s+", r"invirtí\s+"
    ]
    
    for pattern in action_patterns:
        clean_message = re.sub(pattern, "", clean_message, count=1, flags=re.IGNORECASE)
    
    # Remove amount and currency patterns
    clean_message = re.sub(r'₡\s*\d+(?:[,\d]*)?(?:\.\d+)?', '', clean_message)
    clean_message = re.sub(r'\$\s*\d+(?:[,\d]*)?(?:\.\d+)?', '', clean_message)
    clean_message = re.sub(r'\d+(?:[,\d]*)?(?:\.\d+)?\s*(?:colones?|dollars?|dólares?)', '', clean_message, flags=re.IGNORECASE)
    clean_message = re.sub(r'\b\d{4,}\b', '', clean_message)  # Remove large numbers
    
    # Remove organization context words to get clean description
    org_words = ["personal", "familia", "familiar", "empresa", "trabajo", "casa", "hogar"]
    for word in org_words:
        clean_message = re.sub(r'\b' + word + r'\b', '', clean_message, flags=re.IGNORECASE)
    
    # Clean up spaces and prepositions
    clean_message = re.sub(r'\s+', ' ', clean_message)
    clean_message = re.sub(r'^\s*(en|de|para|del|de\s+la)\s+', '', clean_message, flags=re.IGNORECASE)
    
    description = clean_message.strip()
    
    # If description is too short or empty, use a default
    if len(description) < 2:
        description = "Gasto general"
    
    return description


def _extract_category(description: str) -> str:
    """Extract category based on description"""
    description_lower = description.lower()
    
    # Category mapping
    if any(word in description_lower for word in ["gasolina", "combustible", "gas"]):
        return "Gasolina"
    elif any(word in description_lower for word in ["comida", "almuerzo", "cena", "desayuno", "restaurant", "soda"]):
        return "Comida"
    elif any(word in description_lower for word in ["supermercado", "super", "compras"]):
        return "Supermercado"
    elif any(word in description_lower for word in ["transporte", "taxi", "uber", "bus"]):
        return "Transporte"
    elif any(word in description_lower for word in ["entretenimiento", "cine", "diversión"]):
        return "Entretenimiento"
    elif any(word in description_lower for word in ["salud", "medicina", "doctor", "médico"]):
        return "Salud"
    elif any(word in description_lower for word in ["casa", "hogar", "renta", "alquiler"]):
        return "Hogar"
    elif any(word in description_lower for word in ["internet", "teléfono", "luz", "agua"]):
        return "Servicios"
    else:
        return "General"


def _regex_parse(message: str) -> Dict[str, Any]:
    """Fallback regex parsing"""
    amount = _extract_amount(message)
    transaction_type = _extract_type(message.lower())
    description = _extract_description(message, amount)
    category = _extract_category(description)
    
    return {
        "success": amount is not None,
        "amount": float(amount) if amount else None,
        "type": transaction_type,
        "description": description,
        "organization_context": None,  # Regex can't reliably detect context
        "category": category
    }


def _calculate_confidence(amount: Optional[float], description: str, original_message: str) -> str:
    """Calculate confidence level of parsing"""
    score = 0
    
    # Amount detection confidence
    if amount:
        score += 30
    
    # Description quality
    if description and len(description) > 5:
        score += 20
    
    # Message completeness
    if len(original_message) > 10:
        score += 15
    
    # Category accuracy (not General)
    if description and "general" not in description.lower():
        score += 15
    
    # Organization context detection
    org_keywords = ["personal", "familia", "empresa"]
    if any(word in original_message.lower() for word in org_keywords):
        score += 20
    
    if score >= 80:
        return "high"
    elif score >= 60:
        return "medium"
    else:
        return "low"


# Export tools for easy access
ParseMessageTool = parse_message_tool
ValidateParsingTool = validate_parsing_tool