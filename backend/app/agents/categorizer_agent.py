from crewai import Agent, Task, Crew
from typing import Dict, Any
from app.core.llm_config import get_openai_config
from app.tools.categorizer_tools import (
    categorize_transaction_tool,
    validate_category_tool
)

class CategorizerAgent:
    def __init__(self):
        try:
            # Setup OpenAI environment
            self.has_openai = get_openai_config()
            
            # Initialize tools for transaction categorization
            self.tools = [
                categorize_transaction_tool,
                validate_category_tool
            ]
            
            if self.has_openai:
                self.agent = Agent(
                    role="Experto Categorizador Financiero Costarricense con Herramientas",
                    goal="Categorizar transacciones usando herramientas especializadas de análisis",
                    backstory="""Eres un experto en categorización financiera con acceso a herramientas avanzadas.

HERRAMIENTAS DISPONIBLES:
• categorize_transaction: Categoriza transacciones basado en descripción y tipo
• validate_category: Valida la categorización para consistencia

PROCESO DE TRABAJO:
1. SIEMPRE usa "categorize_transaction" para analizar la descripción
2. SIEMPRE usa "validate_category" para verificar la categorización

CATEGORÍAS COSTARRICENSES:
GASTOS: Alimentación, Gasolina, Transporte, Entretenimiento, Salud, Educación, Servicios, Ropa, Hogar, General
INGRESOS: Salario, Freelance, Inversiones, Ventas, Regalos, Otros Ingresos

CONTEXTO CULTURAL:
• "gasolina" = Gasolina (NO Transporte)
• "uber/taxi" = Transporte
• "soda/pulpería" = Alimentación
• "ICE/Kolbi" = Servicios

NUNCA inventes categorías. SIEMPRE usa las herramientas.""",
                    verbose=True,
                    allow_delegation=False,
                    tools=self.tools
                )
            else:
                self.agent = None
        except Exception as e:
            print(f"Warning: Failed to initialize CategorizerAgent: {e}")
            self.has_openai = False
            self.agent = None
        
        # Predefined categories (enhanced for Costa Rica)
        self.expense_categories = {
            "Alimentación": ["comida", "restaurant", "supermercado", "almuerzo", "desayuno", "cena", "groceries", "food", "soda", "pulpería", "walmart", "automercado", "mas x menos"],
            "Gasolina": ["gasolina", "combustible", "diesel", "gas", "estación"],
            "Transporte": ["uber", "taxi", "bus", "transporte", "parking", "parqueo", "peaje", "viaje"],
            "Entretenimiento": ["cine", "bar", "fiesta", "diversión", "entretenimiento", "netflix", "spotify", "amazon prime", "disney"],
            "Salud": ["doctor", "medicina", "farmacia", "hospital", "salud", "médico", "ccss", "consulta", "laboratorio"],
            "Educación": ["libros", "curso", "universidad", "educación", "estudio", "escuela", "colegio"],
            "Servicios": ["electricidad", "agua", "internet", "teléfono", "cable", "streaming", "ice", "kolbi", "cnfl", "aya", "recibo", "luz"],
            "Ropa": ["ropa", "zapatos", "vestido", "camisa", "pantalón", "tienda"],
            "Hogar": ["casa", "hogar", "muebles", "decoración", "limpieza", "ferretería", "epa"],
            "General": []  # fallback category
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
        
        if not self.has_openai or not self.agent:
            return self._keyword_fallback_categorize(description, transaction_type)
        
        try:
            task = Task(
                description=f"""
                Categoriza esta transacción usando las herramientas disponibles.
                
                DESCRIPCIÓN: "{description}"
                TIPO: {transaction_type}
                
                PROCESO OBLIGATORIO:
                1. USA "categorize_transaction" para categorizar: descripción="{description}", tipo="{transaction_type}"
                2. USA "validate_category" para verificar la categorización
                
                IMPORTANTE:
                • SIEMPRE usa ambas herramientas en orden
                • NO inventes categorías, usa solo las válidas
                • Considera contexto costarricense (gasolina ≠ transporte)
                • Devuelve solo el nombre exacto de la categoría
                """,
                agent=self.agent,
                expected_output="Categorización usando herramientas especializadas"
            )
            
            crew = Crew(
                agents=[self.agent],
                tasks=[task],
                verbose=False
            )
            
            result = crew.kickoff()
            category = str(result).strip()
            
            # Validate the category exists in our predefined lists
            if transaction_type == "expense":
                if category in self.expense_categories:
                    return category
            else:  # income
                if category in self.income_categories:
                    return category
            
            # If result is invalid, fallback to keyword matching
            print(f"Invalid category from agent: {category}, falling back to keywords")
            return self._keyword_fallback_categorize(description, transaction_type)
            
        except Exception as e:
            print(f"CrewAI categorization failed: {e}")
            return self._keyword_fallback_categorize(description, transaction_type)
    
    def _keyword_fallback_categorize(self, description: str, transaction_type: str) -> str:
        """Fallback categorization using keyword matching."""
        description_lower = description.lower()
        
        if transaction_type == "expense":
            categories = self.expense_categories
            default = "General"
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