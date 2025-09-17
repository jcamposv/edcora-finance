from crewai import Agent, Task, Crew
from typing import Dict, Any
from app.core.llm_config import get_openai_config

class CategorizerAgent:
    def __init__(self):
        try:
            # Setup OpenAI environment
            self.has_openai = get_openai_config()
            
            self.agent = Agent(
                role="Experto Categorizador Financiero Costarricense",
                goal="Categorizar transacciones financieras con precisión perfecta entendiendo el contexto cultural y económico de Costa Rica",
                backstory="""Eres un experto en categorización financiera especializado en Costa Rica y Latinoamérica.

ENTIENDES PERFECTAMENTE:
• Contexto costarricense: "gasolina" = Transporte, "soda" = Alimentación, "pulpería" = Alimentación
• Marcas locales: Walmart, AutoMercado, Kolbi, ICE, AyA, CNFL
• Servicios típicos: recibo de luz, agua, cable, internet
• Transporte: Uber, taxi, gasolina, parqueo
• Entretenimiento: cine, bar, streaming (Netflix, Spotify)

CATEGORÍAS PRECISAS:
GASTOS: Alimentación, Transporte, Entretenimiento, Salud, Educación, Servicios, Ropa, Hogar, Gasolina, General
INGRESOS: Salario, Freelance, Inversiones, Otros Ingresos

EJEMPLOS REALES:
- "gasolina" → Gasolina
- "almuerzo" → Alimentación  
- "supermercado" → Alimentación
- "uber" → Transporte
- "netflix" → Entretenimiento
- "recibo luz" → Servicios
- "doctor" → Salud

Siempre devuelves UNA sola categoría exacta.""",
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
        
        task = Task(
            description=f"""
            Categoriza esta transacción de {transaction_type} basada en su descripción:
            DESCRIPCIÓN: "{description}"
            
            CATEGORÍAS DISPONIBLES:
            
            Para GASTOS (expense):
            • Alimentación: comida, restaurantes, supermercado, almuerzo, soda, pulpería
            • Gasolina: gasolina, combustible, diesel, estación de servicio
            • Transporte: Uber, taxi, bus, parqueo, peaje (NO gasolina)
            • Entretenimiento: cine, bar, Netflix, Spotify, diversión
            • Salud: doctor, medicina, farmacia, hospital, CCSS
            • Educación: libros, cursos, universidad, escuela
            • Servicios: electricidad, agua, internet, teléfono, ICE, Kolbi, CNFL, AyA
            • Ropa: ropa, zapatos, vestidos, tienda de ropa
            • Hogar: casa, muebles, decoración, ferretería, EPA
            • General: cualquier otro gasto
            
            Para INGRESOS (income):
            • Salario: salario, sueldo, pago regular
            • Freelance: freelance, proyectos, consultoría
            • Inversiones: dividendos, intereses, inversiones
            • Otros Ingresos: cualquier otro ingreso
            
            EJEMPLOS ESPECÍFICOS:
            - "gasolina" → Gasolina
            - "uber" → Transporte  
            - "almuerzo" → Alimentación
            - "netflix" → Entretenimiento
            - "recibo luz" → Servicios
            - "doctor" → Salud
            
            RESPONDE SOLO con el nombre exacto de la categoría en español.
            """,
            agent=self.agent,
            expected_output="Nombre exacto de la categoría en español"
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