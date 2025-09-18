"""
CrewAI Tools for Financial Reporting
Tools that can be used by ReportAgent for generating financial reports
"""

from crewai.tools import tool
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta


# Global variables to store context for tools
_current_db = None

def set_report_tool_context(db):
    """Set the database session for report tools to use"""
    global _current_db
    _current_db = db


@tool("get_transaction_data")
def get_transaction_data_tool(user_id: str, period: str, organization: str = None) -> str:
    """Retrieve transaction data for a user within a specific time period.
    Can filter by organization context (personal, family, etc.)."""
    
    try:
        from app.services.transaction_service import TransactionService
        from app.services.organization_service import OrganizationService
        from app.models.transaction import TransactionType
        
        db = _current_db
        if not db:
            return "Error: Database session not available"
        
        # Determine date range
        start_date, end_date = _get_date_range(period)
        
        # Get transactions based on organization filter
        if organization and organization.lower() in ["family", "familia", "familiar"]:
            # Get family transactions
            transactions = _get_family_transactions(db, user_id, start_date, end_date)
        else:
            # Get personal transactions
            transactions = TransactionService.get_transactions_by_date_range(
                db, user_id, start_date, end_date
            )
        
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
        
        # Format result as string for AI consumption
        result = {
            "period": period,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "total_transactions": len(transactions),
            "total_expenses": total_expenses,
            "total_income": total_income,
            "net_balance": total_income - total_expenses,
            "top_categories": top_categories,
            "transaction_count": {
                "expenses": len([t for t in transactions if t.type == TransactionType.expense]),
                "income": len([t for t in transactions if t.type == TransactionType.income])
            }
        }
        
        return f"Datos obtenidos: {len(transactions)} transacciones, Gastos: {total_expenses}, Ingresos: {total_income}, Balance: {total_income - total_expenses}, Categorías principales: {dict(top_categories[:3])}"
        
    except Exception as e:
        return f"Error retrieving transaction data: {str(e)}"


@tool("format_report")
def format_report_tool(transaction_data: str, currency_symbol: str = "₡", report_type: str = "standard") -> str:
    """Format raw transaction data into user-friendly financial reports.
    Supports different report types and currency formatting."""
    
    try:
        # Parse the transaction data string
        # Expected format: "Datos obtenidos: X transacciones, Gastos: Y, Ingresos: Z, Balance: W, Categorías principales: {...}"
        
        import re
        
        # Extract numbers from the data string
        transactions_match = re.search(r'(\d+)\s+transacciones', transaction_data)
        expenses_match = re.search(r'Gastos:\s*([\d.]+)', transaction_data)
        income_match = re.search(r'Ingresos:\s*([\d.]+)', transaction_data)
        balance_match = re.search(r'Balance:\s*([-\d.]+)', transaction_data)
        
        total_transactions = int(transactions_match.group(1)) if transactions_match else 0
        total_expenses = float(expenses_match.group(1)) if expenses_match else 0
        total_income = float(income_match.group(1)) if income_match else 0
        net_balance = float(balance_match.group(1)) if balance_match else 0
        
        # Extract categories if present
        categories_match = re.search(r"Categorías principales:\s*(\{[^}]+\})", transaction_data)
        top_categories = []
        if categories_match:
            try:
                import ast
                categories_dict = ast.literal_eval(categories_match.group(1))
                top_categories = list(categories_dict.items())
            except:
                pass
        
        # Determine period from context
        period = "período actual"
        if "hoy" in transaction_data.lower():
            period = "hoy"
        elif "semana" in transaction_data.lower():
            period = "esta semana"
        elif "mes" in transaction_data.lower():
            period = "este mes"
        
        # Period name translation
        period_names = {
            "today": "hoy",
            "this_week": "esta semana",
            "last_week": "la semana pasada",
            "this_month": "este mes",
            "last_month": "el mes pasado",
            "last_7_days": "los últimos 7 días",
            "last_30_days": "los últimos 30 días"
        }
        
        period_text = period_names.get(period, period)
        
        if report_type == "summary":
            # Quick summary format
            report = f"📊 **Resumen de {period_text}**\n\n"
            report += f"💸 Gastos: {currency_symbol}{total_expenses:,.0f}\n"
            report += f"💰 Ingresos: {currency_symbol}{total_income:,.0f}\n"
            report += f"📈 Balance: {currency_symbol}{net_balance:,.0f}\n"
            
            if total_transactions == 0:
                report = f"📝 No tienes transacciones registradas para {period_text}"
            
            return report
        
        elif report_type == "detailed":
            # Detailed format with categories
            report = f"📊 **Reporte Detallado - {period_text.title()}**\n\n"
            report += f"📈 **Resumen Financiero:**\n"
            report += f"• Total transacciones: {total_transactions}\n"
            report += f"• Gastos totales: {currency_symbol}{total_expenses:,.0f}\n"
            report += f"• Ingresos totales: {currency_symbol}{total_income:,.0f}\n"
            report += f"• Balance neto: {currency_symbol}{net_balance:,.0f}\n\n"
            
            if top_categories:
                report += f"🏆 **Top Categorías de Gastos:**\n"
                for i, (category, amount) in enumerate(top_categories[:5], 1):
                    percentage = (amount / total_expenses * 100) if total_expenses > 0 else 0
                    report += f"{i}. {category}: {currency_symbol}{amount:,.0f} ({percentage:.1f}%)\n"
            
            # Add insights
            if net_balance > 0:
                savings_rate = (net_balance / total_income * 100) if total_income > 0 else 0
                report += f"\n💡 **Insight:** Ahorraste {savings_rate:.1f}% de tus ingresos"
            else:
                report += f"\n⚠️ **Atención:** Gastaste más de lo que ingresaste"
                
            if total_transactions == 0:
                report = f"📝 No tienes transacciones registradas para {period_text}"
            
            return report
        
        else:
            # Standard format
            report = f"📊 **Resumen de {period_text}**\n\n"
            report += f"💸 Gastos: {currency_symbol}{total_expenses:,.0f}\n"
            report += f"💰 Ingresos: {currency_symbol}{total_income:,.0f}\n"
            report += f"📈 Balance: {currency_symbol}{net_balance:,.0f}\n"
            
            if top_categories:
                report += f"\n🏆 **Top categorías:**\n"
                for category, amount in top_categories[:3]:
                    report += f"• {category}: {currency_symbol}{amount:,.0f}\n"
            
            if total_transactions == 0:
                report = f"📝 No tienes transacciones registradas para {period_text}"
            
            return report
            
    except Exception as e:
        return f"Error formatting report: {str(e)}"


@tool("detect_report_type")
def detect_report_type_tool(message: str) -> str:
    """Analyze user message to determine what type of financial report they want.
    Detects period, organization filter, and report detail level."""
    
    try:
        message_lower = message.lower().strip()
        
        # Detect period
        period = "this_month"  # default
        if any(word in message_lower for word in ["hoy", "today"]):
            period = "today"
        elif any(word in message_lower for word in ["esta semana", "semana actual"]):
            period = "this_week"
        elif any(word in message_lower for word in ["semana pasada", "última semana"]):
            period = "last_week"
        elif any(word in message_lower for word in ["este mes", "mes actual"]):
            period = "this_month"
        elif any(word in message_lower for word in ["mes pasado", "último mes"]):
            period = "last_month"
        elif any(word in message_lower for word in ["últimos 7", "última semana"]):
            period = "last_7_days"
        elif any(word in message_lower for word in ["últimos 30"]):
            period = "last_30_days"
        
        # Detect organization filter
        organization = None
        if any(word in message_lower for word in ["personal", "mío", "mio"]):
            organization = "personal"
        elif any(word in message_lower for word in ["familia", "familiar", "family"]):
            organization = "family"
        elif any(word in message_lower for word in ["empresa", "trabajo", "work"]):
            organization = "empresa"
        
        # Detect report detail level
        report_type = "standard"
        if any(word in message_lower for word in ["detallado", "completo", "full"]):
            report_type = "detailed"
        elif any(word in message_lower for word in ["rápido", "resumen", "summary"]):
            report_type = "summary"
        
        result = {
            "period": period,
            "organization": organization,
            "report_type": report_type,
            "is_report_request": True
        }
        
        return f"Tipo detectado: período={period}, organización={organization or 'ninguna'}, tipo={report_type}"
        
    except Exception as e:
        return f"Error detecting report type: {str(e)}"


def _get_date_range(period: str) -> tuple:
    """Get start and end dates for the specified period"""
    now = datetime.now()
    today = now.date()
    
    if period == "today" or period == "hoy":
        return today, today
    elif period == "this_week" or period == "esta semana":
        days_since_monday = today.weekday()
        monday = today - timedelta(days=days_since_monday)
        return monday, today
    elif period == "last_week" or period == "semana pasada":
        days_since_monday = today.weekday()
        last_monday = today - timedelta(days=days_since_monday + 7)
        last_sunday = last_monday + timedelta(days=6)
        return last_monday, last_sunday
    elif period == "this_month" or period == "este mes":
        first_day = today.replace(day=1)
        return first_day, today
    elif period == "last_month" or period == "mes pasado":
        first_current = today.replace(day=1)
        last_month_end = first_current - timedelta(days=1)
        last_month_start = last_month_end.replace(day=1)
        return last_month_start, last_month_end
    elif period == "last_7_days" or period == "últimos 7 días":
        seven_days_ago = today - timedelta(days=7)
        return seven_days_ago, today
    elif period == "last_30_days" or period == "últimos 30 días":
        thirty_days_ago = today - timedelta(days=30)
        return thirty_days_ago, today
    else:
        # Default to this month
        first_day = today.replace(day=1)
        return first_day, today


def _get_family_transactions(db, user_id: str, start_date, end_date) -> List:
    """Get transactions for all organization members the user belongs to"""
    try:
        from app.services.organization_service import OrganizationService
        from app.services.transaction_service import TransactionService
        
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
        
    except Exception as e:
        print(f"Error getting family transactions: {e}")
        return []


# Export tools for easy access
GetTransactionDataTool = get_transaction_data_tool
FormatReportTool = format_report_tool
DetectReportTypeTool = detect_report_type_tool