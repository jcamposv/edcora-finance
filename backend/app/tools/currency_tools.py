"""
CrewAI Tools for Currency Detection
Tools that can be used by CurrencyAgent for intelligent currency detection
"""

from crewai.tools import tool
from typing import Dict, Any, Optional, Tuple
import re


@tool("detect_currency")
def detect_currency_tool(message: str, phone_number: str) -> str:
    """Detect the intended currency from a financial message and phone number context.
    Analyzes explicit currency mentions, symbols, and country-based inference."""
    
    try:
        # First check for explicit currency mentions
        explicit_result = _detect_explicit_currency(message)
        if explicit_result["confidence"] == "high":
            return f"Moneda detectada: {explicit_result['currency_code']} ({explicit_result['currency_symbol']}) - {explicit_result['reasoning']}"
        
        # If no explicit mention, use country context
        country_result = _detect_from_country_context(phone_number)
        if country_result:
            country_name = _get_country_name(phone_number)
            return f"Moneda detectada: {country_result[0]} ({country_result[1]}) - Inferido del país {country_name}"
        
        # Ultimate fallback
        return "Moneda detectada: USD ($) - Fallback por defecto"
        
    except Exception as e:
        return f"Error en detección de moneda: {str(e)}"


@tool("validate_currency")
def validate_currency_tool(currency_code: str, currency_symbol: str) -> str:
    """Validate that currency code and symbol are consistent and supported.
    Ensures currency data integrity."""
    
    try:
        # Known valid currency combinations
        valid_currencies = {
            "CRC": "₡",     # Costa Rican Colón
            "USD": "$",     # US Dollar
            "MXN": "$",     # Mexican Peso
            "COP": "$",     # Colombian Peso
            "PEN": "S/",    # Peruvian Sol
            "EUR": "€",     # Euro
            "HNL": "L",     # Honduran Lempira
            "GTQ": "Q",     # Guatemalan Quetzal
            "PAB": "B/.",   # Panamanian Balboa
        }
        
        # Check if currency code is supported
        if currency_code not in valid_currencies:
            return f"Moneda no válida: {currency_code}. Usar USD ($) como alternativa."
        
        # Check if symbol matches code
        expected_symbol = valid_currencies[currency_code]
        if currency_symbol != expected_symbol:
            return f"Símbolo incorrecto: {currency_symbol} no coincide con {currency_code}. Debería ser {expected_symbol}"
        
        currency_name = _get_currency_name(currency_code)
        return f"Moneda válida: {currency_code} ({currency_symbol}) - {currency_name}"
        
    except Exception as e:
        return f"Error validando moneda: {str(e)}"


def _detect_explicit_currency(message: str) -> Dict[str, Any]:
    """Detect explicitly mentioned currencies"""
    message_lower = message.lower()
    
    # High confidence explicit mentions
    if "colones" in message_lower or "₡" in message:
        return {
            "currency_code": "CRC",
            "currency_symbol": "₡",
            "confidence": "high",
            "reasoning": "Mención explícita de colones o símbolo ₡"
        }
    elif ("dolares" in message_lower or "dólares" in message_lower or 
          ("$" in message and "pesos" not in message_lower)):
        return {
            "currency_code": "USD",
            "currency_symbol": "$",
            "confidence": "high",
            "reasoning": "Mención explícita de dólares o símbolo $"
        }
    elif "pesos" in message_lower:
        return {
            "currency_code": "MXN",
            "currency_symbol": "$",
            "confidence": "high",
            "reasoning": "Mención explícita de pesos"
        }
    elif "euros" in message_lower or "€" in message:
        return {
            "currency_code": "EUR",
            "currency_symbol": "€",
            "confidence": "high",
            "reasoning": "Mención explícita de euros o símbolo €"
        }
    elif "soles" in message_lower:
        return {
            "currency_code": "PEN",
            "currency_symbol": "S/",
            "confidence": "high",
            "reasoning": "Mención explícita de soles"
        }
    elif "quetzales" in message_lower:
        return {
            "currency_code": "GTQ",
            "currency_symbol": "Q",
            "confidence": "high",
            "reasoning": "Mención explícita de quetzales"
        }
    
    return {
        "currency_code": "USD",
        "currency_symbol": "$",
        "confidence": "low",
        "reasoning": "No se encontró moneda explícita"
    }


def _detect_from_country_context(phone_number: str) -> Optional[Tuple[str, str]]:
    """Get (currency_code, symbol) from phone number country code"""
    clean_phone = phone_number.replace("+", "").replace(" ", "").replace("-", "")
    
    phone_to_currency = {
        "506": ("CRC", "₡"),    # Costa Rica
        "52": ("MXN", "$"),     # Mexico  
        "57": ("COP", "$"),     # Colombia
        "51": ("PEN", "S/"),    # Peru
        "34": ("EUR", "€"),     # Spain
        "1": ("USD", "$"),      # USA/Canada
        "507": ("USD", "$"),    # Panama
        "504": ("HNL", "L"),    # Honduras
        "503": ("USD", "$"),    # El Salvador
        "502": ("GTQ", "Q"),    # Guatemala
    }
    
    for prefix, currency_info in phone_to_currency.items():
        if clean_phone.startswith(prefix):
            return currency_info
    
    return None


def _get_country_name(phone_number: str) -> str:
    """Get country name from phone number"""
    clean_phone = phone_number.replace("+", "").replace(" ", "").replace("-", "")
    
    phone_to_country = {
        "506": "Costa Rica",
        "52": "México",
        "57": "Colombia", 
        "51": "Perú",
        "34": "España",
        "1": "Estados Unidos/Canadá",
        "507": "Panamá",
        "504": "Honduras",
        "503": "El Salvador",
        "502": "Guatemala"
    }
    
    for prefix, country in phone_to_country.items():
        if clean_phone.startswith(prefix):
            return country
    
    return "País desconocido"


def _get_currency_name(currency_code: str) -> str:
    """Get full currency name"""
    currency_names = {
        "CRC": "Colón Costarricense",
        "USD": "Dólar Estadounidense",
        "MXN": "Peso Mexicano",
        "COP": "Peso Colombiano", 
        "PEN": "Sol Peruano",
        "EUR": "Euro",
        "HNL": "Lempira Hondureño",
        "GTQ": "Quetzal Guatemalteco",
        "PAB": "Balboa Panameño"
    }
    
    return currency_names.get(currency_code, currency_code)


# Export tools for easy access
DetectCurrencyTool = detect_currency_tool
ValidateCurrencyTool = validate_currency_tool