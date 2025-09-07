from crewai import Agent, Task, Crew
from typing import Dict, Any, List
from decimal import Decimal
from app.core.llm_config import get_advisor_config

class AdvisorAgent:
    def __init__(self):
        try:
            # Setup OpenAI environment
            self.has_openai = get_advisor_config()
            
            self.agent = Agent(
                role="Financial Advisor",
                goal="Provide personalized financial advice based on spending patterns and financial data",
                backstory="You are a financial advisor specialized in personal finance management for Costa Rican users. You provide practical, actionable advice in Spanish.",
                verbose=True,
                allow_delegation=False
            )
        except Exception as e:
            print(f"Warning: Failed to initialize AdvisorAgent: {e}")
            # Initialize without OpenAI as fallback
            self.has_openai = False
            self.agent = Agent(
                role="Financial Advisor",
                goal="Provide personalized financial advice based on spending patterns and financial data",
                backstory="You are a financial advisor specialized in personal finance management for Costa Rican users. You provide practical, actionable advice in Spanish.",
                verbose=True,
                allow_delegation=False
            )
    
    def generate_advice(self, financial_data: Dict[str, Any]) -> str:
        """
        Generate financial advice based on user's financial data.
        
        Args:
            financial_data: Dict containing:
                - total_income: Total income for the period
                - total_expenses: Total expenses for the period
                - balance: Current balance
                - expenses_by_category: List of expenses by category
                - period: Period type (weekly, monthly, yearly)
        """
        
        task = Task(
            description=f"""
            Generate personalized financial advice in Spanish based on this financial data:
            
            Período: {financial_data.get('period', 'mensual')}
            Ingresos totales: ₡{financial_data.get('total_income', 0):,.2f}
            Gastos totales: ₡{financial_data.get('total_expenses', 0):,.2f}
            Balance: ₡{financial_data.get('balance', 0):,.2f}
            
            Gastos por categoría:
            {self._format_expenses_by_category(financial_data.get('expenses_by_category', []))}
            
            Provide advice that includes:
            1. Overall financial health assessment
            2. Spending pattern analysis
            3. One specific, actionable recommendation
            4. Encouragement or warning as appropriate
            
            Keep the advice concise (max 3 sentences) and practical for Costa Rican context.
            Use positive, encouraging tone while being realistic.
            """,
            agent=self.agent,
            expected_output="Concise financial advice in Spanish (max 3 sentences)"
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
                advice = str(result).strip()
                
                # Ensure advice is not too long
                sentences = advice.split('.')
                if len(sentences) > 3:
                    advice = '. '.join(sentences[:3]) + '.'
                
                return advice
            else:
                # Use rule-based fallback if no OpenAI configured
                return self._generate_fallback_advice(financial_data)
            
        except Exception as e:
            print(f"CrewAI advice generation failed: {e}")
            # Fallback to rule-based advice if CrewAI fails
            return self._generate_fallback_advice(financial_data)
    
    def _format_expenses_by_category(self, expenses_by_category: List[Dict]) -> str:
        """Format expenses by category for the prompt."""
        if not expenses_by_category:
            return "No hay gastos registrados"
        
        formatted = []
        for expense in expenses_by_category:
            category = expense.get('category', 'Sin categoría')
            amount = expense.get('amount', 0)
            formatted.append(f"- {category}: ₡{amount:,.2f}")
        
        return '\n'.join(formatted)
    
    def _generate_fallback_advice(self, financial_data: Dict[str, Any]) -> str:
        """Generate rule-based advice as fallback."""
        balance = financial_data.get('balance', 0)
        total_income = financial_data.get('total_income', 0)
        total_expenses = financial_data.get('total_expenses', 0)
        
        if balance > 0:
            if total_income > 0 and (total_expenses / total_income) < 0.7:
                return "¡Excelente! Tienes un balance positivo y tus gastos están bajo control. Considera ahorrar o invertir el excedente para el futuro."
            else:
                return "Tienes un balance positivo, lo cual es bueno. Trata de mantener tus gastos controlados para seguir ahorrando."
        elif balance == 0:
            return "Estás gastando exactamente lo que ganas. Considera reducir algunos gastos para crear un fondo de emergencia."
        else:
            return "⚠️ Estás gastando más de lo que ganas. Es importante revisar tus gastos y encontrar áreas donde puedas reducir."
    
    def generate_category_insight(self, category: str, amount: float, percentage: float) -> str:
        """Generate specific insight for a spending category."""
        
        insights = {
            "Alimentación": f"Gastas ₡{amount:,.0f} ({percentage:.1f}%) en alimentación. Si es más del 30% de tus ingresos, considera cocinar más en casa.",
            "Transporte": f"Tus gastos de transporte son ₡{amount:,.0f} ({percentage:.1f}%). Considera opciones más económicas si superan el 15% de tus ingresos.",
            "Entretenimiento": f"Inviertes ₡{amount:,.0f} ({percentage:.1f}%) en entretenimiento. Está bien disfrutar, pero no debería superar el 10% de tus ingresos.",
            "Servicios": f"Los servicios básicos te cuestan ₡{amount:,.0f} ({percentage:.1f}%). Revisa si puedes optimizar algunos planes.",
            "Otros": f"Tienes gastos varios por ₡{amount:,.0f} ({percentage:.1f}%). Trata de categorizar mejor para un mejor control."
        }
        
        return insights.get(category, f"Gastas ₡{amount:,.0f} ({percentage:.1f}%) en {category}.")