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
                    role="Expense Parser",
                    goal="Extract financial information from WhatsApp messages",
                    backstory="You are an expert at parsing Spanish text messages to extract financial transaction information. You understand multiple currencies and common expense descriptions across Latin America.",
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
            Parse this WhatsApp message to extract financial transaction information:
            "{message}"
            
            Extract:
            1. Amount (numeric value, handle symbols like ₡, colones, etc.)
            2. Transaction type (income or expense - default to expense if unclear)
            3. Description (clean description of the transaction)
            
            Return the information in this exact format:
            Amount: [numeric_value]
            Type: [income|expense]
            Description: [clean_description]
            """,
            agent=self.agent,
            expected_output="Structured transaction information with amount, type, and description"
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
            lines = result.strip().split('\n')
            amount = None
            transaction_type = "expense"  # default
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
                "success": amount is not None
            }
        except Exception:
            return self._regex_fallback_parse(original_message)
    
    def _regex_fallback_parse(self, message: str) -> Dict[str, Any]:
        """Fallback regex parsing when CrewAI fails."""
        # Extract amount using regex
        amount_patterns = [
            r'₡\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',  # ₡1,000 or ₡1,000.50
            r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*(?:colones?|₡)',  # 1000 colones
            r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',  # Just numbers
        ]
        
        amount = None
        for pattern in amount_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                amount_str = match.group(1)
                amount = self._extract_amount(amount_str)
                break
        
        # Determine transaction type
        transaction_type = "expense"  # default
        income_keywords = ["ingreso", "ganancia", "salario", "pago", "cobré", "recibí"]
        if any(keyword in message.lower() for keyword in income_keywords):
            transaction_type = "income"
        
        return {
            "amount": amount,
            "type": transaction_type,
            "description": message.strip(),
            "success": amount is not None
        }
    
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