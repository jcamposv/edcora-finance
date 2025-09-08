from crewai import Agent, Task, Crew
import re
from typing import Dict, Any, Optional, Tuple
from app.core.llm_config import get_openai_config

class CurrencyAgent:
    """Intelligent agent to detect currency from phone number context and message text."""
    
    def __init__(self):
        try:
            # Setup OpenAI environment
            self.has_openai = get_openai_config()
            
            if self.has_openai:
                self.agent = Agent(
                    role="Currency Detection Expert",
                    goal="Intelligently detect the correct currency based on phone number country context and message content",
                    backstory="""You are an expert in international currencies and regional financial conventions. 
                    You understand that people often omit currency symbols when writing amounts, especially when using 
                    their local currency. You can infer currency from:
                    1. Phone number country codes (+506 = Costa Rica, +52 = Mexico, etc.)
                    2. Explicit currency mentions (colones, dollars, pesos, etc.)
                    3. Currency symbols (₡, $, €, etc.)
                    4. Regional context and common usage patterns
                    
                    You're especially familiar with Latin American currencies and their common usage patterns.""",
                    verbose=True,
                    allow_delegation=False
                )
            else:
                self.agent = None
        except Exception as e:
            print(f"Warning: Failed to initialize CurrencyAgent: {e}")
            self.has_openai = False
            self.agent = None
    
    def detect_currency(self, message: str, phone_number: str) -> Dict[str, Any]:
        """
        Detect currency from message content and phone number context.
        Returns dict with currency_code, currency_symbol, confidence_level.
        """
        
        if not self.has_openai or not self.agent:
            return self._fallback_currency_detection(message, phone_number)
        
        try:
            # Extract country code from phone number
            country_context = self._get_country_context(phone_number)
            
            task = Task(
                description=f"""
                Analyze this financial message and phone number to detect the intended currency:
                
                Message: "{message}"
                Phone number: "{phone_number}"
                Likely country context: {country_context}
                
                Consider:
                1. Explicit currency mentions (colones, dollars, pesos, euros, etc.)
                2. Currency symbols (₡, $, €, £, etc.)
                3. Phone number country code context
                4. Regional conventions (e.g., Costa Ricans often say just "5000" meaning colones)
                5. Common patterns in Latin America
                
                Determine the most likely currency and provide:
                - Currency code (ISO 4217: USD, CRC, MXN, EUR, etc.)
                - Currency symbol (₡, $, €, etc.)
                - Confidence level (high/medium/low)
                - Brief reasoning
                
                Return ONLY in this exact format:
                Currency: [ISO_CODE]
                Symbol: [SYMBOL]
                Confidence: [high/medium/low]
                Reasoning: [brief_explanation]
                """,
                agent=self.agent,
                expected_output="Currency detection with code, symbol, confidence level and reasoning"
            )
            
            crew = Crew(
                agents=[self.agent],
                tasks=[task],
                verbose=False
            )
            
            result = crew.kickoff()
            return self._parse_agent_result(str(result), message, phone_number)
            
        except Exception as e:
            print(f"CurrencyAgent failed: {e}")
            return self._fallback_currency_detection(message, phone_number)
    
    def _parse_agent_result(self, result: str, message: str, phone_number: str) -> Dict[str, Any]:
        """Parse the AI agent result."""
        try:
            lines = result.strip().split('\n')
            currency_code = "USD"  # default
            currency_symbol = "$"  # default
            confidence = "medium"
            reasoning = "AI detection"
            
            for line in lines:
                if line.startswith("Currency:"):
                    currency_code = line.split(":", 1)[1].strip()
                elif line.startswith("Symbol:"):
                    currency_symbol = line.split(":", 1)[1].strip()
                elif line.startswith("Confidence:"):
                    confidence = line.split(":", 1)[1].strip().lower()
                elif line.startswith("Reasoning:"):
                    reasoning = line.split(":", 1)[1].strip()
            
            return {
                "currency_code": currency_code,
                "currency_symbol": currency_symbol,
                "confidence": confidence,
                "reasoning": reasoning,
                "success": True
            }
            
        except Exception:
            return self._fallback_currency_detection(message, phone_number)
    
    def _fallback_currency_detection(self, message: str, phone_number: str) -> Dict[str, Any]:
        """Fallback currency detection using simple rules."""
        message_lower = message.lower()
        
        # Explicit mentions
        if "colones" in message_lower or "₡" in message:
            return {
                "currency_code": "CRC",
                "currency_symbol": "₡",
                "confidence": "high",
                "reasoning": "Explicit colones mention",
                "success": True
            }
        elif ("dolares" in message_lower or "dólares" in message_lower or 
              ("$" in message and "pesos" not in message_lower)):
            return {
                "currency_code": "USD",
                "currency_symbol": "$",
                "confidence": "high",
                "reasoning": "Explicit dollars mention",
                "success": True
            }
        elif "pesos" in message_lower:
            # Default to Mexican pesos, could be improved with country context
            return {
                "currency_code": "MXN",
                "currency_symbol": "$",
                "confidence": "medium",
                "reasoning": "Pesos mention",
                "success": True
            }
        elif "euros" in message_lower or "€" in message:
            return {
                "currency_code": "EUR",
                "currency_symbol": "€",
                "confidence": "high",
                "reasoning": "Explicit euros mention",
                "success": True
            }
        
        # Country-based inference for numbers without currency
        country_info = self._get_country_currency_from_phone(phone_number)
        if country_info:
            return {
                "currency_code": country_info[0],
                "currency_symbol": country_info[1],
                "confidence": "medium",
                "reasoning": f"Inferred from phone country code",
                "success": True
            }
        
        # Ultimate fallback
        return {
            "currency_code": "USD",
            "currency_symbol": "$",
            "confidence": "low",
            "reasoning": "Default fallback",
            "success": True
        }
    
    def _get_country_context(self, phone_number: str) -> str:
        """Get human-readable country context from phone number."""
        clean_phone = phone_number.replace("+", "").replace(" ", "").replace("-", "")
        
        # Common country codes
        if clean_phone.startswith("506"):
            return "Costa Rica (colones - CRC)"
        elif clean_phone.startswith("52"):
            return "Mexico (pesos - MXN)"
        elif clean_phone.startswith("57"):
            return "Colombia (pesos - COP)"
        elif clean_phone.startswith("51"):
            return "Peru (soles - PEN)"
        elif clean_phone.startswith("34"):
            return "Spain (euros - EUR)"
        elif clean_phone.startswith("1"):
            return "USA/Canada (dollars - USD)"
        elif clean_phone.startswith("507"):
            return "Panama (balboas/dollars - PAB/USD)"
        elif clean_phone.startswith("504"):
            return "Honduras (lempiras - HNL)"
        elif clean_phone.startswith("503"):
            return "El Salvador (dollars - USD)"
        elif clean_phone.startswith("502"):
            return "Guatemala (quetzales - GTQ)"
        else:
            return "Unknown country"
    
    def _get_country_currency_from_phone(self, phone_number: str) -> Optional[Tuple[str, str]]:
        """Get (currency_code, symbol) from phone number."""
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