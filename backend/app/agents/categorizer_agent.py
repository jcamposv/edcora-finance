from crewai import Agent, Task, Crew
from typing import Dict, Any
from app.core.llm_config import get_openai_config

class CategorizerAgent:
    def __init__(self):
        try:
            # Setup OpenAI environment
            self.has_openai = get_openai_config()
            
            self.agent = Agent(
                role="Expense Categorizer",
                goal="Categorize financial transactions into appropriate categories",
                backstory="You are an expert at categorizing expenses and income based on transaction descriptions. You understand Costa Rican context and common spending patterns.",
                verbose=True,
                allow_delegation=False
            )
        except Exception as e:
            print(f"Warning: Failed to initialize CategorizerAgent: {e}")
            # Initialize without OpenAI as fallback
            self.has_openai = False
            self.agent = Agent(
                role="Expense Categorizer",
                goal="Categorize financial transactions into appropriate categories",
                backstory="You are an expert at categorizing expenses and income based on transaction descriptions. You understand Costa Rican context and common spending patterns.",
                verbose=True,
                allow_delegation=False
            )
        
        # Predefined categories
        self.expense_categories = {
            "Alimentación": ["comida", "restaurant", "supermercado", "almuerzo", "desayuno", "cena", "groceries", "food"],
            "Transporte": ["uber", "taxi", "gasolina", "bus", "transporte", "combustible", "parking"],
            "Entretenimiento": ["cine", "bar", "fiesta", "diversión", "entretenimiento", "netflix", "spotify"],
            "Salud": ["doctor", "medicina", "farmacia", "hospital", "salud", "médico"],
            "Educación": ["libros", "curso", "universidad", "educación", "estudio"],
            "Servicios": ["electricidad", "agua", "internet", "teléfono", "cable", "streaming"],
            "Ropa": ["ropa", "zapatos", "vestido", "camisa", "pantalón"],
            "Hogar": ["casa", "hogar", "muebles", "decoración", "limpieza"],
            "Otros": []  # fallback category
        }
        
        self.income_categories = {
            "Salario": ["salario", "sueldo", "pago", "trabajo"],
            "Freelance": ["freelance", "proyecto", "consultoría"],
            "Inversiones": ["dividendos", "intereses", "inversión"],
            "Otros Ingresos": []  # fallback category
        }
    
    def categorize_transaction(self, description: str, transaction_type: str) -> str:
        """
        Categorize a transaction based on its description and type.
        """
        
        task = Task(
            description=f"""
            Categorize this {transaction_type} transaction based on its description:
            "{description}"
            
            For expenses, choose from these categories:
            - Alimentación (food, restaurants, groceries)
            - Transporte (transportation, fuel, parking)
            - Entretenimiento (entertainment, movies, streaming)
            - Salud (health, medicine, doctor visits)
            - Educación (education, books, courses)
            - Servicios (utilities, internet, phone)
            - Ropa (clothing, shoes)
            - Hogar (home, furniture, cleaning)
            - Otros (other expenses)
            
            For income, choose from these categories:
            - Salario (salary, regular pay)
            - Freelance (freelance work, projects)
            - Inversiones (investments, dividends)
            - Otros Ingresos (other income)
            
            Return only the category name in Spanish.
            """,
            agent=self.agent,
            expected_output="Single category name in Spanish"
        )
        
        crew = Crew(
            agents=[self.agent],
            tasks=[task],
            verbose=True
        )
        
        try:
            # Only use CrewAI if OpenAI is configured
            if self.has_openai:
                result = crew.kickoff()
                category = str(result).strip()
                
                # Validate the category exists
                if transaction_type == "expense":
                    if category in self.expense_categories:
                        return category
                else:  # income
                    if category in self.income_categories:
                        return category
                
                # If CrewAI result is invalid, fallback to keyword matching
                return self._keyword_fallback_categorize(description, transaction_type)
            else:
                # Use keyword fallback if no OpenAI configured
                return self._keyword_fallback_categorize(description, transaction_type)
            
        except Exception as e:
            print(f"CrewAI categorization failed: {e}")
            # Fallback to keyword matching if CrewAI fails
            return self._keyword_fallback_categorize(description, transaction_type)
    
    def _keyword_fallback_categorize(self, description: str, transaction_type: str) -> str:
        """Fallback categorization using keyword matching."""
        description_lower = description.lower()
        
        if transaction_type == "expense":
            categories = self.expense_categories
            default = "Otros"
        else:
            categories = self.income_categories
            default = "Otros Ingresos"
        
        # Check each category for keyword matches
        for category, keywords in categories.items():
            if category == default:  # Skip default category in keyword search
                continue
            
            for keyword in keywords:
                if keyword in description_lower:
                    return category
        
        # Return default category if no matches found
        return default