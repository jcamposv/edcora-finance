from crewai import Agent, Task, Crew
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from app.core.llm_config import get_openai_config
from app.services.transaction_service import TransactionService
from app.services.organization_service import OrganizationService
from app.models.transaction import TransactionType
import calendar

class ReportAgent:
    """Intelligent agent to generate financial reports and summaries from natural language requests."""
    
    def __init__(self):
        try:
            # Setup OpenAI environment
            self.has_openai = get_openai_config()
            
            if self.has_openai:
                self.agent = Agent(
                    role="Analista Financiero Experto Costarricense",
                    goal="Generar reportes financieros claros, útiles y motivadores que ayuden a los usuarios a entender y mejorar sus finanzas personales",
                    backstory="""Eres un consultor financiero experto especializado en Costa Rica que crea reportes personalizados y motivadores.

ENTIENDES PERFECTAMENTE:
• Contexto cultural: colones, salarios típicos, gastos comunes costarricenses
• Períodos naturales: "esta semana", "este mes", "últimos días", "desde que empecé"
• Categorías locales: gasolina, soda, supermercado, servicios (ICE, AyA, CNFL)
• Organizaciones: gastos familiares vs personales vs empresariales

GENERAS REPORTES QUE INCLUYEN:
• Resumen claro del período solicitado
• Gastos por categoría con íconos
• Comparaciones inteligentes (vs mes anterior, promedio)
• Insights específicos y consejos útiles
• Alertas sobre patrones inusuales
• Motivación positiva para mejorar finanzas

FORMATO PERFECTO PARA WHATSAPP:
• Usas emojis para mayor claridad
• Mensajes estructurados pero concisos
• Colones (₡) como moneda principal
• Lenguaje amigable y motivador
• Datos específicos y accionables

EJEMPLOS DE INSIGHTS:
"💡 Tu mayor gasto fue gasolina (₡45,000). ¡Podrías ahorrar combinando viajes!"
"🎉 ¡Gastaste 20% menos que el mes pasado en entretenimiento!"
"⚠️ Este mes gastaste mucho en servicios. Revisa si hay pagos duplicados."

Siempre motivas al usuario a mejorar sus finanzas.""",
                    verbose=True,
                    allow_delegation=False
                )
            else:
                self.agent = None
        except Exception as e:
            print(f"Warning: Failed to initialize ReportAgent: {e}")
            self.has_openai = False
            self.agent = None
    
    def is_report_request(self, message: str) -> bool:
        """Detect if a message is requesting a report or summary."""
        report_keywords = [
            "resumen", "resume", "reporte", "gastos", "total", "cuanto", "cuánto",
            "balance", "estado", "informe", "hasta hoy", "esta semana", "este mes",
            "mes pasado", "semana pasada", "últimos", "ultimos", "balance del mes",
            "mis gastos", "mis ingresos", "total gastos", "total ingresos",
            "¿cuanto", "¿cuánto", "cómo voy", "como voy",
            # Family keywords
            "gastos familia", "gastos familiares", "balance familia", "balance familiar",
            "reporte familia", "reporte familiar", "resumen familia", "resumen familiar",
            "familia gastos", "familiar gastos"
        ]
        
        message_lower = message.lower()
        return any(keyword in message_lower for keyword in report_keywords)
    
    def generate_report(self, message: str, user_id: str, db: Session, currency_symbol: str = "₡") -> Dict[str, Any]:
        """Generate a financial report based on the user's natural language request."""
        
        # Get transaction data
        transactions_data = self._get_transactions_data(user_id, db, message)
        
        if not self.has_openai or not self.agent:
            return self._generate_simple_report(transactions_data, currency_symbol, message)
        
        try:
            task = Task(
                description=f"""
                Generate a financial report based on this user request: "{message}"
                
                Transaction Data:
                {self._format_transactions_for_ai(transactions_data, currency_symbol)}
                
                Create a comprehensive but concise report that includes:
                1. Direct response to the user's specific question
                2. Total expenses and income for the requested period
                3. Top spending categories if applicable
                4. Brief insights or observations
                5. Friendly recommendations if relevant
                
                Keep the response conversational and suitable for WhatsApp (under 500 characters if possible).
                Use the currency symbol: {currency_symbol}
                Respond in Spanish.
                
                Format the response to be clear and easy to read in a messaging app.
                """,
                agent=self.agent,
                expected_output="A friendly, informative financial report in Spanish suitable for WhatsApp"
            )
            
            crew = Crew(
                agents=[self.agent],
                tasks=[task],
                memory=True,  # 🧠 Enable memory for report context
                verbose=False
            )
            
            result = crew.kickoff()
            
            return {
                "success": True,
                "report": str(result).strip(),
                "data": transactions_data
            }
            
        except Exception as e:
            print(f"ReportAgent failed: {e}")
            return self._generate_simple_report(transactions_data, currency_symbol, message)
    
    def _is_family_report_request(self, message: str) -> bool:
        """Detect if user is requesting a family report."""
        family_keywords = [
            "familia", "familiar", "family"
        ]
        message_lower = message.lower()
        return any(keyword in message_lower for keyword in family_keywords)
    
    def _get_transactions_data(self, user_id: str, db: Session, message: str) -> Dict[str, Any]:
        """Extract transaction data based on the time period mentioned in the message."""
        
        # Determine time period from message
        period = self._extract_time_period(message)
        start_date, end_date = self._get_date_range(period)
        
        # Check if this is a family report request
        is_family_report = self._is_family_report_request(message)
        
        # Debug: Print date range
        print(f"DEBUG: Searching transactions for user {user_id}")
        print(f"DEBUG: Date range: {start_date} to {end_date}")
        print(f"DEBUG: Period: {period}")
        print(f"DEBUG: Family report: {is_family_report}")
        
        # Get transactions (individual or family)
        if is_family_report:
            transactions = self._get_family_transactions(db, user_id, start_date, end_date)
        else:
            transactions = TransactionService.get_transactions_by_date_range(
                db, user_id, start_date, end_date
            )
        
        # Debug: Print results
        print(f"DEBUG: Found {len(transactions)} transactions")
        for t in transactions[:3]:  # Show first 3
            print(f"DEBUG: Transaction date: {t.date}, amount: {t.amount}")
        
        # Calculate totals
        total_expenses = sum(float(t.amount) for t in transactions if t.type == TransactionType.expense)
        total_income = sum(float(t.amount) for t in transactions if t.type == TransactionType.income)
        
        # Group by category
        category_totals = {}
        for transaction in transactions:
            if transaction.type == TransactionType.expense:
                category = transaction.category or "Sin categoría"
                category_totals[category] = category_totals.get(category, 0) + float(transaction.amount)
        
        # Sort categories by amount
        top_categories = sorted(category_totals.items(), key=lambda x: x[1], reverse=True)[:5]
        
        return {
            "period": period,
            "start_date": start_date,
            "end_date": end_date,
            "is_family_report": is_family_report,
            "total_transactions": len(transactions),
            "total_expenses": total_expenses,
            "total_income": total_income,
            "net_balance": total_income - total_expenses,
            "top_categories": top_categories,
            "transaction_count_by_type": {
                "expenses": len([t for t in transactions if t.type == TransactionType.expense]),
                "income": len([t for t in transactions if t.type == TransactionType.income])
            }
        }
    
    def _extract_time_period(self, message: str) -> str:
        """Extract time period from natural language message."""
        message_lower = message.lower()
        
        if any(word in message_lower for word in ["hoy", "today", "hasta hoy"]):
            return "today"
        elif any(word in message_lower for word in ["esta semana", "semana actual"]):
            return "this_week"
        elif any(word in message_lower for word in ["semana pasada", "última semana", "ultima semana"]):
            return "last_week"
        elif any(word in message_lower for word in ["este mes", "mes actual"]):
            return "this_month"
        elif any(word in message_lower for word in ["mes pasado", "último mes", "ultimo mes"]):
            return "last_month"
        elif any(word in message_lower for word in ["últimos 7", "ultimos 7", "última semana"]):
            return "last_7_days"
        elif any(word in message_lower for word in ["últimos 30", "ultimos 30"]):
            return "last_30_days"
        else:
            return "this_month"  # Default
    
    def _get_date_range(self, period: str) -> tuple:
        """Get start and end dates for the specified period."""
        now = datetime.now()
        today = now.date()
        
        # Debug: Print current date info
        print(f"DEBUG: Current datetime: {now}")
        print(f"DEBUG: Current date: {today}")
        print(f"DEBUG: Current year: {today.year}, month: {today.month}")
        
        if period == "today":
            return today, today
        elif period == "this_week":
            days_since_monday = today.weekday()
            monday = today - timedelta(days=days_since_monday)
            return monday, today
        elif period == "last_week":
            days_since_monday = today.weekday()
            last_monday = today - timedelta(days=days_since_monday + 7)
            last_sunday = last_monday + timedelta(days=6)
            return last_monday, last_sunday
        elif period == "this_month":
            first_day = today.replace(day=1)
            return first_day, today
        elif period == "last_month":
            first_current = today.replace(day=1)
            last_month_end = first_current - timedelta(days=1)
            last_month_start = last_month_end.replace(day=1)
            return last_month_start, last_month_end
        elif period == "last_7_days":
            seven_days_ago = today - timedelta(days=7)
            return seven_days_ago, today
        elif period == "last_30_days":
            thirty_days_ago = today - timedelta(days=30)
            return thirty_days_ago, today
        else:
            # Default to this month
            first_day = today.replace(day=1)
            return first_day, today
    
    def _format_transactions_for_ai(self, data: Dict[str, Any], currency_symbol: str) -> str:
        """Format transaction data for AI consumption."""
        period_names = {
            "today": "hoy",
            "this_week": "esta semana",
            "last_week": "la semana pasada",
            "this_month": "este mes",
            "last_month": "el mes pasado",
            "last_7_days": "los últimos 7 días",
            "last_30_days": "los últimos 30 días"
        }
        
        period_text = period_names.get(data["period"], data["period"])
        
        report = f"""
        Período: {period_text}
        Total de transacciones: {data["total_transactions"]}
        Gastos totales: {currency_symbol}{data["total_expenses"]:,.0f}
        Ingresos totales: {currency_symbol}{data["total_income"]:,.0f}
        Balance neto: {currency_symbol}{data["net_balance"]:,.0f}
        
        Principales categorías de gastos:
        """
        
        for i, (category, amount) in enumerate(data["top_categories"][:3], 1):
            report += f"\n{i}. {category}: {currency_symbol}{amount:,.0f}"
        
        return report
    
    def _generate_simple_report(self, data: Dict[str, Any], currency_symbol: str, original_message: str) -> Dict[str, Any]:
        """Generate a simple report without AI when OpenAI is not available."""
        
        period_names = {
            "today": "hoy",
            "this_week": "esta semana", 
            "last_week": "la semana pasada",
            "this_month": "este mes",
            "last_month": "el mes pasado",
            "last_7_days": "los últimos 7 días",
            "last_30_days": "los últimos 30 días"
        }
        
        period_text = period_names.get(data["period"], data["period"])
        
        # Add family indicator if it's a family report
        report_type = "📊 **Resumen Familiar de" if data.get("is_family_report", False) else "📊 **Resumen de"
        report = f"{report_type} {period_text}**\n\n"
        report += f"💸 Gastos: {currency_symbol}{data['total_expenses']:,.0f}\n"
        report += f"💰 Ingresos: {currency_symbol}{data['total_income']:,.0f}\n"
        report += f"📈 Balance: {currency_symbol}{data['net_balance']:,.0f}\n"
        
        if data["top_categories"]:
            report += f"\n🏆 **Top categorías:**\n"
            for category, amount in data["top_categories"][:3]:
                report += f"• {category}: {currency_symbol}{amount:,.0f}\n"
        
        if data["total_transactions"] == 0:
            report = f"No tienes transacciones registradas para {period_text} 📝"
        
        return {
            "success": True,
            "report": report.strip(),
            "data": data
        }
    
    def _get_family_transactions(self, db: Session, user_id: str, start_date, end_date) -> List:
        """Get transactions for all organization members the user belongs to."""
        from datetime import datetime, time
        
        # Get user's organizations
        user_organizations = OrganizationService.get_user_organizations(db, user_id)
        
        if not user_organizations:
            # No organizations, return individual transactions
            return TransactionService.get_transactions_by_date_range(
                db, user_id, start_date, end_date
            )
        
        all_transactions = []
        
        for organization in user_organizations:
            # Get all organization members
            organization_members = OrganizationService.get_organization_members(db, str(organization.id))
            
            for member in organization_members:
                # Get transactions for each member
                member_transactions = TransactionService.get_transactions_by_date_range(
                    db, str(member.user_id), start_date, end_date
                )
                all_transactions.extend(member_transactions)
        
        # Remove duplicates and sort by date
        unique_transactions = list(set(all_transactions))
        unique_transactions.sort(key=lambda x: x.date, reverse=True)
        
        return unique_transactions