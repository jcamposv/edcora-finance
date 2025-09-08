from typing import Optional, Dict, Tuple

class CountryService:
    """Service to detect country and currency from phone numbers."""
    
    # Phone country codes to currency mapping
    COUNTRY_CURRENCIES = {
        # Central America
        "506": ("Costa Rica", "CRC", "₡"),      # Costa Rica
        "507": ("Panama", "PAB", "$"),          # Panama  
        "504": ("Honduras", "HNL", "L"),        # Honduras
        "503": ("El Salvador", "USD", "$"),     # El Salvador
        "502": ("Guatemala", "GTQ", "Q"),       # Guatemala
        "505": ("Nicaragua", "NIO", "C$"),      # Nicaragua
        "501": ("Belize", "BZD", "BZ$"),       # Belize
        
        # Mexico & North America
        "52": ("Mexico", "MXN", "$"),
        "1": ("USA/Canada", "USD", "$"),
        
        # South America
        "57": ("Colombia", "COP", "$"),
        "51": ("Peru", "PEN", "S/"),
        "593": ("Ecuador", "USD", "$"),
        "58": ("Venezuela", "VES", "Bs"),
        "56": ("Chile", "CLP", "$"),
        "54": ("Argentina", "ARS", "$"),
        "55": ("Brazil", "BRL", "R$"),
        "598": ("Uruguay", "UYU", "$"),
        "595": ("Paraguay", "PYG", "₲"),
        "591": ("Bolivia", "BOB", "Bs"),
        
        # Europe
        "34": ("Spain", "EUR", "€"),
        "33": ("France", "EUR", "€"),
        "49": ("Germany", "EUR", "€"),
        "39": ("Italy", "EUR", "€"),
        "44": ("UK", "GBP", "£"),
    }
    
    @staticmethod
    def detect_country_from_phone(phone_number: str) -> Optional[Tuple[str, str, str]]:
        """
        Detect country, currency code, and symbol from phone number.
        Returns (country_name, currency_code, currency_symbol) or None
        """
        # Clean phone number - remove + and spaces
        clean_phone = phone_number.replace("+", "").replace(" ", "").replace("-", "")
        
        # Try different prefix lengths (1-4 digits)
        for prefix_len in [4, 3, 2, 1]:
            if len(clean_phone) >= prefix_len:
                prefix = clean_phone[:prefix_len]
                if prefix in CountryService.COUNTRY_CURRENCIES:
                    return CountryService.COUNTRY_CURRENCIES[prefix]
        
        return None
    
    @staticmethod
    def get_default_currency_for_amount(amount_text: str, country_info: Optional[Tuple[str, str, str]] = None) -> Tuple[str, str]:
        """
        Determine currency code and symbol from amount text and country info.
        Returns (currency_code, currency_symbol)
        """
        amount_lower = amount_text.lower()
        
        # Explicit currency mentions
        if "colones" in amount_lower or "₡" in amount_text:
            return ("CRC", "₡")
        elif "dolares" in amount_lower or "dólares" in amount_lower or "$" in amount_text:
            return ("USD", "$")
        elif "euros" in amount_lower or "€" in amount_text:
            return ("EUR", "€")
        elif "pesos" in amount_lower:
            if country_info and country_info[0] in ["Mexico", "Colombia", "Chile", "Argentina"]:
                return (country_info[1], country_info[2])
            return ("MXN", "$")  # Default to Mexican peso
        
        # If no explicit currency, use country default
        if country_info:
            return (country_info[1], country_info[2])
        
        # Ultimate fallback
        return ("USD", "$")
    
    @staticmethod
    def needs_country_confirmation(phone_number: str) -> bool:
        """Check if we need to ask user for country confirmation."""
        country_info = CountryService.detect_country_from_phone(phone_number)
        return country_info is None