from crewai import Agent, Task, Crew
import re
from decimal import Decimal
from typing import Optional, Dict, Any
from app.core.llm_config import get_openai_config
from app.agents.currency_agent import CurrencyAgent

class ParserAgent:
    def __init__(self):
        try:
            # Setup OpenAI environment
            self.has_openai = get_openai_config()
            
            if self.has_openai:
                self.agent = Agent(
                    role="Experto Analizador de Mensajes Financieros",
                    goal="Extraer información financiera completa y precisa de mensajes en español, manejando patrones naturales de conversación.",
                    backstory="""Eres un experto en procesamiento de lenguaje natural especializado en finanzas para usuarios latinos.

ENTIENDES PERFECTAMENTE:
• Patrones naturales: "Gasto familia gasolina 40000" = 40000 en gasolina para familia
• Múltiples formatos: "₡5000", "5000 colones", "5000", "$25 USD"  
• Contextos: familia, empresa, personal, trabajo
• Categorías automáticas: gasolina, comida, entretenimiento, etc.
• Tipos: gastos (default), ingresos, pagos, compras

EJEMPLOS REALES:
- "Gasto familia gasolina 40000" → amount: 40000, description: "gasolina", context: "familia"
- "Compré almuerzo 5000" → amount: 5000, description: "almuerzo", context: null
- "Pago empresa internet 25000" → amount: 25000, description: "internet", context: "empresa"
- "Ingreso salario 500000" → amount: 500000, type: "income", description: "salario"

Siempre respondes JSON preciso y estructurado.""",
                    verbose=True,
                    allow_delegation=False
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
        
        task = Task(
            description=f"""
            Analiza este mensaje de WhatsApp y extrae información financiera completa:
            MENSAJE: "{message}"
            
            EXTRAE:
            1. AMOUNT: Número exacto del monto (sin símbolos, solo número)
            2. TYPE: income o expense (default: expense)
            3. DESCRIPTION: Descripción limpia del gasto/ingreso
            4. ORGANIZATION_CONTEXT: Contexto mencionado (familia, empresa, trabajo, etc.) o null
            5. CATEGORY: Categoría inferida (Gasolina, Comida, Entretenimiento, etc.)
            
            EJEMPLOS DE ANÁLISIS:
            - "Gasto familia gasolina 40000" → amount: 40000, type: expense, description: "gasolina", organization_context: "familia", category: "Gasolina"
            - "Compré almuerzo 5000" → amount: 5000, type: expense, description: "almuerzo", organization_context: null, category: "Comida"
            - "Pago empresa 25000" → amount: 25000, type: expense, description: "pago empresa", organization_context: "empresa", category: "Empresa"
            - "Ingreso salario 500000" → amount: 500000, type: income, description: "salario", organization_context: null, category: "Salario"
            - "Gasto 40000" → amount: 40000, type: expense, description: "gasto general", organization_context: null, category: "General"
            
            RESPONDE EN FORMATO JSON:
            {{
                "amount": numero_exacto,
                "type": "expense_o_income", 
                "description": "descripcion_limpia",
                "organization_context": "contexto_o_null",
                "category": "categoria_inferida"
            }}
            """,
            agent=self.agent,
            expected_output="JSON estructurado con información financiera completa extraída"
        )
        
        crew = Crew(
            agents=[self.agent],
            tasks=[task],
            verbose=True
        )
        
        try:
            # Parse the message for amount and type
            if self.has_openai:
                result = crew.kickoff()
                parsed_data = self._parse_crew_result(str(result), message)
            else:
                # Use regex fallback if no OpenAI configured
                parsed_data = self._regex_fallback_parse(message)
            
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