from crewai import Agent, Task, Crew
import re
from decimal import Decimal
from typing import Optional, Dict, Any
from app.core.llm_config import get_openai_config
from app.agents.currency_agent import CurrencyAgent
from app.tools.parser_tools import (
    parse_message_tool,
    validate_parsing_tool
)

class ParserAgent:
    def __init__(self):
        try:
            # Setup OpenAI environment
            self.has_openai = get_openai_config()
            
            # Initialize tools for message parsing
            self.tools = [
                parse_message_tool,
                validate_parsing_tool
            ]
            
            if self.has_openai:
                self.agent = Agent(
                    role="Experto Analizador de Mensajes Financieros con Herramientas",
                    goal="Extraer información financiera usando herramientas especializadas de análisis",
                    backstory="""Eres un experto en procesamiento de lenguaje natural con acceso a herramientas avanzadas.

HERRAMIENTAS DISPONIBLES:
• parse_message: Analiza mensajes para extraer información financiera
• validate_parsing: Valida la información extraída para consistencia

PROCESO DE TRABAJO:
1. SIEMPRE usa "parse_message" para analizar el mensaje financiero
2. SIEMPRE usa "validate_parsing" para verificar la calidad de los datos extraídos
3. Contexto organizacional SOLO si se menciona explícitamente

EJEMPLOS CRÍTICOS:
- "Gasto familia gasolina 40000" → organization_context: "familia" (explícito)
- "Compré almuerzo 5000" → organization_context: null (NO mencionado)
- "Gasto personal 2000" → organization_context: "personal" (explícito)

NUNCA inventes contextos organizacionales. SIEMPRE usa las herramientas.""",
                    verbose=True,
                    allow_delegation=False,
                    tools=self.tools
                )
            else:
                self.agent = None
                
            # Initialize currency detection agent
            self.currency_agent = CurrencyAgent()
            
        except Exception as e:
            print(f"Warning: Failed to initialize ParserAgent: {e}")
            self.has_openai = False
            self.agent = None
            self.currency_agent = None
    
    def parse_message(self, message: str, phone_number: str = None) -> Dict[str, Any]:
        """
        Parse a WhatsApp message to extract transaction information.
        Returns dict with amount, description, transaction type, and currency info.
        """
        
        if not self.has_openai or not self.agent:
            return self._regex_fallback_parse(message)
        
        try:
            task = Task(
                description=f"""
                Analiza este mensaje financiero usando las herramientas disponibles.
                
                MENSAJE: "{message}"
                TELÉFONO: "{phone_number or 'No disponible'}"
                
                PROCESO OBLIGATORIO:
                1. USA "parse_message" para extraer información del mensaje: "{message}"
                2. USA "validate_parsing" para verificar la calidad de los datos extraídos
                
                IMPORTANTE:
                • SIEMPRE usa ambas herramientas en orden
                • NO inventes contextos organizacionales
                • Organization_context SOLO si se menciona explícitamente
                • Devuelve el resultado final de las herramientas
                
                EJEMPLOS CRÍTICOS:
                - "Gasto familia gasolina 40000" → organization_context: "familia" (explícito)
                - "Compré almuerzo 5000" → organization_context: null (NO mencionado)
                - "Gasto personal 2000" → organization_context: "personal" (explícito)
                """,
                agent=self.agent,
                expected_output="Información financiera extraída usando herramientas especializadas"
            )
            
            crew = Crew(
                agents=[self.agent],
                tasks=[task],
                verbose=False
            )
            
            result = crew.kickoff()
            parsed_data = self._parse_crew_result(str(result), message)
            
            # Detect currency using the intelligent agent
            if parsed_data["success"] and phone_number and self.currency_agent:
                currency_info = self.currency_agent.detect_currency(message, phone_number)
                parsed_data.update({
                    "currency_code": currency_info.get("currency_code", "USD"),
                    "currency_symbol": currency_info.get("currency_symbol", "$"),
                    "currency_confidence": currency_info.get("confidence", "medium")
                })
            
            return parsed_data
            
        except Exception as e:
            print(f"CrewAI parsing failed: {e}")
            # Fallback to regex parsing if CrewAI fails
            parsed_data = self._regex_fallback_parse(message)
            
            # Still try currency detection on fallback
            if parsed_data["success"] and phone_number and self.currency_agent:
                try:
                    currency_info = self.currency_agent.detect_currency(message, phone_number)
                    parsed_data.update({
                        "currency_code": currency_info.get("currency_code", "USD"),
                        "currency_symbol": currency_info.get("currency_symbol", "$"),
                        "currency_confidence": currency_info.get("confidence", "medium")
                    })
                except Exception:
                    pass  # Continue without currency detection
            
            return parsed_data
    
    def _parse_crew_result(self, result: str, original_message: str) -> Dict[str, Any]:
        """Parse the CrewAI result to extract structured information."""
        try:
            # Try to parse as JSON first (new format)
            import json
            import re
            
            # Extract JSON from the result
            json_match = re.search(r'\{.*\}', result, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                parsed_json = json.loads(json_str)
                
                # Extract and validate data
                amount = parsed_json.get("amount")
                if isinstance(amount, str):
                    amount = self._extract_amount(amount)
                elif isinstance(amount, (int, float)):
                    amount = Decimal(str(amount))
                
                transaction_type = parsed_json.get("type", "expense").lower()
                if transaction_type not in ["income", "expense"]:
                    transaction_type = "expense"
                
                description = parsed_json.get("description", original_message)
                organization_context = parsed_json.get("organization_context")
                category = parsed_json.get("category", "General")
                
                print(f"🧠 AI PARSED: amount={amount}, description='{description}', org_context='{organization_context}', category='{category}'")
                
                return {
                    "amount": amount,
                    "type": transaction_type,
                    "description": description,
                    "organization_context": organization_context,
                    "category": category,
                    "success": amount is not None
                }
            
            # Fallback to old format parsing
            lines = result.strip().split('\n')
            amount = None
            transaction_type = "expense"
            description = original_message
            
            for line in lines:
                if line.startswith("Amount:"):
                    amount_str = line.split(":", 1)[1].strip()
                    amount = self._extract_amount(amount_str)
                elif line.startswith("Type:"):
                    type_str = line.split(":", 1)[1].strip().lower()
                    if type_str in ["income", "ingreso"]:
                        transaction_type = "income"
                elif line.startswith("Description:"):
                    description = line.split(":", 1)[1].strip()
            
            return {
                "amount": amount,
                "type": transaction_type,
                "description": description,
                "organization_context": None,
                "category": "General",
                "success": amount is not None
            }
            
        except Exception as e:
            print(f"Error parsing CrewAI result: {e}")
            return self._regex_fallback_parse(original_message)
    
    def _regex_fallback_parse(self, message: str) -> Dict[str, Any]:
        """Fallback regex parsing when CrewAI fails."""
        # Extract amount using regex - enhanced patterns
        amount_patterns = [
            r'₡\s*(\d{1,3}(?:,?\d{3})*(?:\.\d{2})?)',  # ₡1,000 or ₡1,000.50
            r'\$\s*(\d{1,3}(?:,?\d{3})*(?:\.\d{2})?)',  # $1,000 or $1,000.50
            r'(\d{1,3}(?:,?\d{3})*(?:\.\d{2})?)\s*(?:colones?|₡)',  # 1000 colones
            r'(\d{1,3}(?:,?\d{3})*(?:\.\d{2})?)\s*(?:dollars?|dólares?|\$)',  # 1000 dollars
            r'(\d{4,})',  # Just numbers with 4+ digits (likely amounts)
            r'(\d{1,3}(?:,\d{3})+)',  # Numbers with comma separators like 1,000
            r'(\d+(?:\.\d+)?)',  # Any number as last resort
        ]
        
        amount = None
        for pattern in amount_patterns:
            matches = re.findall(pattern, message, re.IGNORECASE)
            if matches:
                try:
                    # Take the largest number found (most likely to be the amount)
                    amounts = []
                    for match in matches:
                        amount_str = match.replace(',', '')
                        parsed_amount = self._extract_amount(amount_str)
                        if parsed_amount and parsed_amount > 0:
                            amounts.append(parsed_amount)
                    
                    if amounts:
                        amount = max(amounts)
                        break
                except:
                    continue
        
        # Determine transaction type
        transaction_type = "expense"  # default
        income_keywords = ["ingreso", "ganancia", "salario", "pago", "cobré", "recibí", "recibo", "gané"]
        expense_keywords = ["gasto", "gasté", "pagué", "compré", "pago", "compra", "costo", "costó"]
        
        message_lower = message.lower()
        if any(keyword in message_lower for keyword in income_keywords):
            transaction_type = "income"
        elif any(keyword in message_lower for keyword in expense_keywords):
            transaction_type = "expense"
        
        # Extract description by removing amounts and action words
        description = self._extract_clean_description(message)
        
        return {
            "amount": amount,
            "type": transaction_type,
            "description": description,
            "organization_context": None,  # Regex can't detect context
            "category": "General",  # Default category for regex
            "success": amount is not None
        }
    
    def _extract_clean_description(self, message: str) -> str:
        """Extract a clean description from the message"""
        import re
        
        # Remove action words
        clean_message = message
        action_patterns = [
            r"gasté\s+", r"gaste\s+", r"pagué\s+", r"pague\s+", 
            r"compré\s+", r"compre\s+", r"gasto\s+", r"agregar\s+gasto\s+",
            r"pago\s+", r"compra\s+", r"costo\s+", r"costó\s+", r"invertí\s+", r"invirtí\s+"
        ]
        
        for pattern in action_patterns:
            clean_message = re.sub(pattern, "", clean_message, count=1, flags=re.IGNORECASE)
        
        # Remove amount patterns and currency symbols
        clean_message = re.sub(r'₡\s*\d+(?:[,\d]*)?(?:\.\d+)?', '', clean_message)
        clean_message = re.sub(r'\$\s*\d+(?:[,\d]*)?(?:\.\d+)?', '', clean_message)
        clean_message = re.sub(r'\d+(?:[,\d]*)?(?:\.\d+)?\s*(?:colones?|dollars?|dólares?)', '', clean_message, flags=re.IGNORECASE)
        clean_message = re.sub(r'\b\d{4,}\b', '', clean_message)  # Remove large numbers
        
        # Remove standalone currency symbols
        clean_message = re.sub(r'\s*[₡\$]\s*', ' ', clean_message)
        
        # Clean up extra spaces and prepositions
        clean_message = re.sub(r'\s+', ' ', clean_message)
        clean_message = re.sub(r'^\s*(en|de|para|del|de\s+la)\s+', '', clean_message, flags=re.IGNORECASE)
        
        description = clean_message.strip()
        
        # If description is too short or empty, use a default
        if len(description) < 2:
            description = "Gasto general"
        
        return description
    
    def _extract_amount(self, amount_str: str) -> Optional[Decimal]:
        """Extract decimal amount from string."""
        try:
            # Remove currency symbols and spaces
            cleaned = re.sub(r'[₡\s]', '', amount_str)
            # Remove commas used as thousand separators
            cleaned = cleaned.replace(',', '')
            return Decimal(cleaned)
        except (ValueError, TypeError):
            return None