"""
CrewAI Tools for Financial Advisory
Tools that can be used by AdvisorAgent and other financial analysis agents
"""

from crewai.tools import tool
from typing import Dict, Any, List
from decimal import Decimal


@tool("analyze_spending_patterns")
def analyze_spending_patterns_tool(expenses_by_category: str, total_income: float, period: str = "monthly") -> str:
    """Analyze user's spending patterns by category and identify potential savings opportunities.
    Returns insights about spending distribution and recommendations."""
    
    if not expenses_by_category:
        return "No hay gastos para analizar en este período."
    
    try:
        # Parse expenses by category (expecting format like "Comida: 50000, Gasolina: 40000")
        expenses = []
        if expenses_by_category:
            for item in expenses_by_category.split(","):
                if ":" in item:
                    category, amount_str = item.split(":", 1)
                    try:
                        amount = float(amount_str.strip())
                        expenses.append((category.strip(), amount))
                    except ValueError:
                        continue
        
        if not expenses:
            return "No se pudieron procesar los gastos por categoría."
        
        total_expenses = sum(amount for _, amount in expenses)
        
        # Sort by amount (highest first)
        sorted_expenses = sorted(expenses, key=lambda x: x[1], reverse=True)
        
        analysis = f"📊 **Análisis de Patrones de Gasto ({period}):**\n\n"
        
        # Overall spending rate
        if total_income > 0:
            spending_rate = (total_expenses / total_income) * 100
            analysis += f"💰 Tasa de gasto: {spending_rate:.1f}% de ingresos\n"
            
            if spending_rate > 90:
                analysis += "🚨 **ALERTA:** Estás gastando más del 90% de tus ingresos\n"
            elif spending_rate > 70:
                analysis += "⚠️ **CUIDADO:** Alto nivel de gasto (>70%)\n" 
            else:
                analysis += "✅ **BIEN:** Nivel de gasto controlado\n"
        
        analysis += f"\n**Top 3 Categorías de Gasto:**\n"
        
        # Top 3 categories
        for i, (category, amount) in enumerate(sorted_expenses[:3], 1):
            percentage = (amount / total_expenses * 100) if total_expenses > 0 else 0
            analysis += f"{i}. {category}: ₡{amount:,.0f} ({percentage:.1f}%)\n"
        
        # Recommendations based on top category
        if sorted_expenses:
            top_category, top_amount = sorted_expenses[0]
            top_percentage = (top_amount / total_expenses * 100) if total_expenses > 0 else 0
            
            analysis += f"\n💡 **Recomendaciones:**\n"
            
            if top_percentage > 40:
                analysis += f"• Tu gasto en {top_category} representa {top_percentage:.1f}% del total\n"
                analysis += f"• Considera optimizar esta categoría para ahorrar más\n"
            
            # Category-specific advice
            category_lower = top_category.lower()
            if "comida" in category_lower or "restaurant" in category_lower:
                analysis += "• Cocinar en casa puede reducir gastos significativamente\n"
                analysis += "• Planifica menús semanales y compra ingredientes\n"
            elif "gasolina" in category_lower or "transporte" in category_lower:
                analysis += "• Considera combinar viajes o usar transporte público\n"
                analysis += "• Evalúa trabajar desde casa algunos días\n"
            elif "entretenimiento" in category_lower:
                analysis += "• Busca actividades gratuitas: parques, museos públicos\n"
                analysis += "• Establece un presupuesto mensual fijo para entretenimiento\n"
            elif "supermercado" in category_lower or "compras" in category_lower:
                analysis += "• Haz listas de compras y evita compras impulsivas\n"
                analysis += "• Compara precios y aprovecha ofertas\n"
        
        return analysis
        
    except Exception as e:
        return f"Error analizando patrones de gasto: {str(e)}"


@tool("calculate_savings_goal")
def calculate_savings_goal_tool(current_income: float, current_expenses: float, target_savings_rate: float = 20.0) -> str:
    """Calculate realistic savings goals based on income and expenses.
    Provides specific targets and actionable steps to achieve savings goals."""
    
    try:
        current_savings = current_income - current_expenses
        current_savings_rate = (current_savings / current_income * 100) if current_income > 0 else 0
        
        target_savings_amount = current_income * (target_savings_rate / 100)
        required_expense_reduction = current_expenses - (current_income - target_savings_amount)
        
        analysis = f"🎯 **Meta de Ahorro ({target_savings_rate}%):**\n\n"
        
        analysis += f"💰 Ingresos actuales: ₡{current_income:,.0f}\n"
        analysis += f"💸 Gastos actuales: ₡{current_expenses:,.0f}\n"
        analysis += f"💵 Ahorro actual: ₡{current_savings:,.0f} ({current_savings_rate:.1f}%)\n\n"
        
        analysis += f"🎯 **Meta de ahorro:** ₡{target_savings_amount:,.0f}/mes\n"
        
        if current_savings_rate >= target_savings_rate:
            analysis += f"🎉 **¡FELICIDADES!** Ya estás ahorrando más del {target_savings_rate}%\n"
            analysis += f"💡 Considera aumentar tu meta o invertir tus ahorros\n"
        else:
            analysis += f"📉 **Necesitas reducir gastos:** ₡{required_expense_reduction:,.0f}/mes\n\n"
            
            # Provide actionable steps
            analysis += f"📋 **Plan de Acción:**\n"
            
            # Calculate weekly and daily targets
            weekly_reduction = required_expense_reduction / 4.33  # average weeks per month
            daily_reduction = required_expense_reduction / 30
            
            analysis += f"• Reduce gastos ₡{weekly_reduction:,.0f} por semana\n"
            analysis += f"• O ₡{daily_reduction:,.0f} por día\n\n"
            
            # Percentage reduction needed
            reduction_percentage = (required_expense_reduction / current_expenses * 100) if current_expenses > 0 else 0
            analysis += f"• Esto representa reducir {reduction_percentage:.1f}% de tus gastos actuales\n\n"
            
            # Suggestions by reduction level
            if reduction_percentage < 10:
                analysis += f"💡 **Fácil:** Elimina pequeños gastos innecesarios\n"
            elif reduction_percentage < 20:
                analysis += f"⚡ **Moderado:** Revisa suscripciones y gastos recurrentes\n"  
            else:
                analysis += f"🔥 **Desafiante:** Requiere cambios significativos en estilo de vida\n"
        
        return analysis
        
    except Exception as e:
        return f"Error calculando meta de ahorro: {str(e)}"


@tool("budget_recommendation")
def budget_recommendation_tool(monthly_income: float, family_size: int = 1, location: str = "Costa Rica") -> str:
    """Recommend budget allocation percentages for different expense categories
    based on income level and family size. Uses best practices for Costa Rican context."""
    
    try:
        # Adjust percentages based on income level (Costa Rican context)
        if monthly_income < 500000:  # Lower income
            housing_pct = 35
            food_pct = 25
            transport_pct = 15
            savings_pct = 10
            utilities_pct = 8
            other_pct = 7
        elif monthly_income < 1000000:  # Middle income  
            housing_pct = 30
            food_pct = 20
            transport_pct = 15
            savings_pct = 15
            utilities_pct = 8
            other_pct = 12
        else:  # Higher income
            housing_pct = 25
            food_pct = 15
            transport_pct = 12
            savings_pct = 20
            utilities_pct = 6
            other_pct = 22
        
        # Adjust for family size
        if family_size > 1:
            food_pct += (family_size - 1) * 3
            utilities_pct += (family_size - 1) * 2
            housing_pct += (family_size - 1) * 2
            savings_pct = max(5, savings_pct - (family_size - 1) * 3)
            other_pct = max(5, other_pct - (family_size - 1) * 4)
        
        recommendations = f"💰 **Recomendaciones de Presupuesto**\n"
        recommendations += f"👥 Familia de {family_size} personas\n"
        recommendations += f"💵 Ingresos: ₡{monthly_income:,.0f}/mes\n\n"
        
        categories = [
            ("🏠 Vivienda (alquiler/hipoteca)", housing_pct, monthly_income * housing_pct / 100),
            ("🍽️ Comida y alimentación", food_pct, monthly_income * food_pct / 100), 
            ("🚗 Transporte", transport_pct, monthly_income * transport_pct / 100),
            ("💡 Servicios públicos", utilities_pct, monthly_income * utilities_pct / 100),
            ("💰 Ahorro e inversión", savings_pct, monthly_income * savings_pct / 100),
            ("🎯 Otros gastos", other_pct, monthly_income * other_pct / 100)
        ]
        
        for category, percentage, amount in categories:
            recommendations += f"{category}: {percentage}% (₡{amount:,.0f})\n"
        
        recommendations += f"\n📋 **Consejos Específicos:**\n"
        recommendations += f"• Prioriza el ahorro del {savings_pct}% antes de otros gastos\n"
        recommendations += f"• Mantén gastos de vivienda bajo {housing_pct}% de ingresos\n"
        
        if family_size > 2:
            recommendations += f"• Con familia grande, planifica comidas en casa\n"
            recommendations += f"• Considera seguros de salud familiares\n"
        
        recommendations += f"• Revisa y ajusta cada 3 meses según necesidades\n"
        
        return recommendations
        
    except Exception as e:
        return f"Error generando recomendaciones de presupuesto: {str(e)}"


# Export tools for easy access
AnalyzeSpendingPatternsTool = analyze_spending_patterns_tool
CalculateSavingsGoalTool = calculate_savings_goal_tool
BudgetRecommendationTool = budget_recommendation_tool