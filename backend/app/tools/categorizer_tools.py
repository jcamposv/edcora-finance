"""
CrewAI Tools for Transaction Categorization
Tools that can be used by CategorizerAgent for intelligent expense and income categorization
"""

from crewai.tools import tool
from typing import Dict, Any, List


@tool("categorize_transaction")
def categorize_transaction_tool(description: str, transaction_type: str, amount: float = 0) -> str:
    """Categorize financial transactions into appropriate categories based on description.
    Understands Costa Rican context and common spending patterns."""
    
    try:
        description_lower = description.lower().strip()
        
        if transaction_type.lower() == "expense":
            category = _categorize_expense(description_lower, amount)
        else:
            category = _categorize_income(description_lower, amount)
        
        return f"Categoría asignada: {category}"
        
    except Exception as e:
        return f"Error categorizando transacción: {str(e)}"


@tool("validate_category")
def validate_category_tool(category: str, transaction_type: str, description: str) -> str:
    """Validate that a category assignment is appropriate for the transaction type and description.
    Ensures categorization consistency and accuracy."""
    
    try:
        # Valid categories by type
        valid_expense_categories = [
            "Alimentación", "Gasolina", "Transporte", "Entretenimiento", 
            "Salud", "Educación", "Servicios", "Ropa", "Hogar", "General"
        ]
        
        valid_income_categories = [
            "Salario", "Freelance", "Inversiones", "Ventas", "Regalos", "Otros Ingresos"
        ]
        
        errors = []
        warnings = []
        suggestions = []
        
        # Check if category exists for transaction type
        if transaction_type.lower() == "expense":
            if category not in valid_expense_categories:
                errors.append(f"Categoría de gasto inválida: {category}")
                suggestions.append("Usar: " + ", ".join(valid_expense_categories))
        elif transaction_type.lower() == "income":
            if category not in valid_income_categories:
                errors.append(f"Categoría de ingreso inválida: {category}")
                suggestions.append("Usar: " + ", ".join(valid_income_categories))
        else:
            errors.append(f"Tipo de transacción inválido: {transaction_type}")
        
        # Contextual validation
        description_lower = description.lower()
        
        # Check for common misclassifications
        if category == "Transporte" and "gasolina" in description_lower:
            warnings.append("Gasolina debería categorizarse como 'Gasolina', no 'Transporte'")
            suggestions.append("Considerar cambiar a categoría 'Gasolina'")
        
        if category == "General" and len(description) > 5:
            warnings.append("Descripciones detalladas deberían tener categorías más específicas que 'General'")
        
        # Calculate confidence
        confidence = _calculate_confidence(category, transaction_type, description_lower)
        
        if len(errors) == 0:
            return f"Validación exitosa: Categoría válida, {len(warnings)} advertencias, Confianza={confidence}"
        else:
            return f"Validación fallida: {len(errors)} errores, {len(warnings)} advertencias"
        
    except Exception as e:
        return f"Error validando categoría: {str(e)}"


def _categorize_expense(description_lower: str, amount: float) -> str:
    """Categorize expense transactions"""
    
    # Enhanced category mapping for Costa Rica
    expense_patterns = {
        "Gasolina": [
            "gasolina", "combustible", "diesel", "gas", "estación", "petroleo", "bomba"
        ],
        "Alimentación": [
            "comida", "restaurant", "supermercado", "almuerzo", "desayuno", "cena", 
            "groceries", "food", "soda", "pulpería", "walmart", "automercado", 
            "mas x menos", "hipermas", "pali", "fresh market", "little caesars",
            "mcdonald", "burger king", "pizza", "restaurante", "buffet", "cafetería"
        ],
        "Transporte": [
            "uber", "taxi", "bus", "transporte", "parking", "parqueo", "peaje", 
            "viaje", "pasaje", "moto", "bicicleta", "tren", "autobus"
        ],
        "Entretenimiento": [
            "cine", "bar", "fiesta", "diversión", "entretenimiento", "netflix", 
            "spotify", "amazon prime", "disney", "hbo", "youtube", "gaming",
            "juegos", "concierto", "teatro", "club", "discoteca", "streaming",
            "cerveza", "licor", "vino", "trago", "alcohol", "bebidas"
        ],
        "Salud": [
            "doctor", "medicina", "farmacia", "hospital", "salud", "médico", 
            "ccss", "consulta", "laboratorio", "dentista", "optometría",
            "fisioterapia", "psicólogo", "vitaminas", "pastillas"
        ],
        "Educación": [
            "libros", "curso", "universidad", "educación", "estudio", "escuela", 
            "colegio", "matrícula", "mensualidad", "material", "útiles"
        ],
        "Servicios": [
            "electricidad", "agua", "internet", "teléfono", "cable", "streaming", 
            "ice", "kolbi", "cnfl", "aya", "recibo", "luz", "televisión",
            "telefonía", "móvil", "celular", "plan", "datos"
        ],
        "Ropa": [
            "ropa", "zapatos", "vestido", "camisa", "pantalón", "tienda", 
            "mall", "boutique", "fashion", "jean", "blusa", "falda"
        ],
        "Hogar": [
            "casa", "hogar", "muebles", "decoración", "limpieza", "ferretería", 
            "epa", "construplaza", "depot", "jardín", "cocina", "baño",
            "electrodomésticos", "reparación", "mantenimiento"
        ]
    }
    
    # Special amount-based categorization
    if amount > 50000:  # Large amounts might be specific categories
        if any(word in description_lower for word in ["casa", "hogar", "alquiler", "renta"]):
            return "Hogar"
        elif any(word in description_lower for word in ["carro", "auto", "vehiculo"]):
            return "Transporte"
    
    # Check patterns
    for category, keywords in expense_patterns.items():
        if any(keyword in description_lower for keyword in keywords):
            return category
    
    # Special cases
    if any(word in description_lower for word in ["pago", "cuota", "mensualidad"]):
        return "Servicios"
    
    return "General"


def _categorize_income(description_lower: str, amount: float) -> str:
    """Categorize income transactions"""
    
    income_patterns = {
        "Salario": [
            "salario", "sueldo", "pago", "trabajo", "nomina", "planilla",
            "quincenal", "mensual", "empleador", "empresa"
        ],
        "Freelance": [
            "freelance", "proyecto", "consultoría", "independiente", 
            "contrato", "servicio", "cliente", "honorarios"
        ],
        "Inversiones": [
            "dividendos", "intereses", "inversión", "acciones", "fondos",
            "banco", "ahorro", "rendimiento", "bono"
        ],
        "Ventas": [
            "venta", "vendí", "ebay", "mercadolibre", "facebook", "marketplace"
        ],
        "Regalos": [
            "regalo", "bono", "premio", "aguinaldo", "extra"
        ]
    }
    
    # Check patterns
    for category, keywords in income_patterns.items():
        if any(keyword in description_lower for keyword in keywords):
            return category
    
    return "Otros Ingresos"


def _calculate_confidence(category: str, transaction_type: str, description_lower: str) -> str:
    """Calculate confidence in categorization"""
    
    # High confidence keywords by category
    high_confidence_keywords = {
        "Gasolina": ["gasolina", "combustible"],
        "Alimentación": ["almuerzo", "desayuno", "cena", "supermercado"],
        "Transporte": ["uber", "taxi", "bus"],
        "Salud": ["doctor", "farmacia", "medicina"],
        "Servicios": ["luz", "agua", "internet", "teléfono"],
        "Salario": ["salario", "sueldo", "planilla"]
    }
    
    # Check for high confidence keywords
    keywords = high_confidence_keywords.get(category, [])
    if any(keyword in description_lower for keyword in keywords):
        return "high"
    
    # Medium confidence for non-General categories
    if category not in ["General", "Otros Ingresos"]:
        return "medium"
    
    return "low"


# Export tools for easy access
CategorizeTransactionTool = categorize_transaction_tool
ValidateCategoryTool = validate_category_tool