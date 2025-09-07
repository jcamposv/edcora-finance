from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from app.models.user import User
from app.models.transaction import Transaction, TransactionType
from app.models.report import Report
from app.core.schemas import ReportCreate
from app.services.transaction_service import TransactionService
from app.services.whatsapp_service import WhatsAppService
from app.agents.advisor_agent import AdvisorAgent
from datetime import datetime, date, timedelta
from typing import List, Dict, Any
import calendar

class ReportService:
    def __init__(self):
        self.whatsapp_service = WhatsAppService()
        self.advisor_agent = AdvisorAgent()
    
    @staticmethod
    def create_report(db: Session, report: ReportCreate) -> Report:
        """Create a new report record."""
        db_report = Report(**report.dict())
        db.add(db_report)
        db.commit()
        db.refresh(db_report)
        return db_report
    
    @staticmethod
    def get_user_reports(db: Session, user_id: str, period: str = None) -> List[Report]:
        """Get user reports, optionally filtered by period."""
        query = db.query(Report).filter(Report.user_id == user_id)
        
        if period:
            query = query.filter(Report.period == period)
        
        return query.order_by(Report.created_at.desc()).all()
    
    def generate_weekly_report(self, db: Session, user_id: str) -> Dict[str, Any]:
        """Generate weekly financial report for a user."""
        # Get date range for current week (Monday to Sunday)
        today = date.today()
        days_since_monday = today.weekday()
        start_date = today - timedelta(days=days_since_monday)
        end_date = start_date + timedelta(days=6)
        
        return self._generate_period_report(db, user_id, start_date, end_date, "semanal")
    
    def generate_monthly_report(self, db: Session, user_id: str, year: int = None, month: int = None) -> Dict[str, Any]:
        """Generate monthly financial report for a user."""
        if year is None:
            year = datetime.now().year
        if month is None:
            month = datetime.now().month
        
        # Get first and last day of the month
        start_date = date(year, month, 1)
        _, last_day = calendar.monthrange(year, month)
        end_date = date(year, month, last_day)
        
        return self._generate_period_report(db, user_id, start_date, end_date, "mensual")
    
    def generate_yearly_report(self, db: Session, user_id: str, year: int = None) -> Dict[str, Any]:
        """Generate yearly financial report for a user."""
        if year is None:
            year = datetime.now().year
        
        start_date = date(year, 1, 1)
        end_date = date(year, 12, 31)
        
        return self._generate_period_report(db, user_id, start_date, end_date, "anual")
    
    def _generate_period_report(self, db: Session, user_id: str, start_date: date, end_date: date, period: str) -> Dict[str, Any]:
        """Generate report for a specific period."""
        
        # Get transactions for the period
        transactions = TransactionService.get_user_transactions(
            db, user_id, 
            start_date=start_date, 
            end_date=end_date,
            limit=1000  # Get all transactions for the period
        )
        
        # Calculate totals
        total_income = sum(t.amount for t in transactions if t.type == TransactionType.income)
        total_expenses = sum(t.amount for t in transactions if t.type == TransactionType.expense)
        balance = total_income - total_expenses
        
        # Get expenses by category
        expenses_by_category = TransactionService.get_expenses_by_category(
            db, user_id, start_date, end_date
        )
        
        # Generate financial advice using AdvisorAgent
        financial_data = {
            "period": period,
            "total_income": float(total_income),
            "total_expenses": float(total_expenses),
            "balance": float(balance),
            "expenses_by_category": expenses_by_category
        }
        
        advice = self.advisor_agent.generate_advice(financial_data)
        
        # Prepare summary
        summary = {
            "period": period,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "total_income": float(total_income),
            "total_expenses": float(total_expenses),
            "balance": float(balance),
            "transaction_count": len(transactions),
            "expenses_by_category": expenses_by_category,
            "top_expense_category": self._get_top_category(expenses_by_category),
            "advice": advice
        }
        
        return summary
    
    def _get_top_category(self, expenses_by_category: List[Dict]) -> str:
        """Get the category with highest expenses."""
        if not expenses_by_category:
            return "N/A"
        
        top_category = max(expenses_by_category, key=lambda x: x['amount'])
        return top_category['category']
    
    def save_and_send_report(self, db: Session, user_id: str, report_data: Dict[str, Any]) -> bool:
        """Save report to database and send via WhatsApp."""
        
        # Get user info
        from app.services.user_service import UserService
        user = UserService.get_user(db, user_id)
        if not user:
            return False
        
        # Only send automatic reports to premium users
        if user.plan_type != "premium" and report_data["period"] in ["semanal", "mensual"]:
            return False
        
        # Save report to database
        report_create = ReportCreate(
            user_id=user_id,
            period=report_data["period"],
            start_date=date.fromisoformat(report_data["start_date"]),
            end_date=date.fromisoformat(report_data["end_date"]),
            summary=report_data
        )
        
        try:
            report = self.create_report(db, report_create)
            
            # Send report via WhatsApp
            whatsapp_data = {
                "period": report_data["period"],
                "income": report_data["total_income"],
                "expenses": report_data["total_expenses"],
                "balance": report_data["balance"],
                "advice": report_data["advice"]
            }
            
            success = self.whatsapp_service.send_report(user.phone_number, whatsapp_data)
            
            return success
            
        except Exception as e:
            print(f"Error saving/sending report: {e}")
            return False
    
    def send_weekly_reports(self, db: Session) -> int:
        """Send weekly reports to all premium users."""
        
        # Get all premium users
        premium_users = db.query(User).filter(User.plan_type == "premium").all()
        
        sent_count = 0
        for user in premium_users:
            try:
                # Generate weekly report
                report_data = self.generate_weekly_report(db, str(user.id))
                
                # Send report
                if self.save_and_send_report(db, str(user.id), report_data):
                    sent_count += 1
                    print(f"Weekly report sent to user {user.id}")
                
            except Exception as e:
                print(f"Error sending weekly report to user {user.id}: {e}")
        
        return sent_count
    
    def send_monthly_reports(self, db: Session) -> int:
        """Send monthly reports to all premium users."""
        
        # Get all premium users
        premium_users = db.query(User).filter(User.plan_type == "premium").all()
        
        sent_count = 0
        for user in premium_users:
            try:
                # Generate monthly report for previous month
                today = date.today()
                if today.month == 1:
                    year, month = today.year - 1, 12
                else:
                    year, month = today.year, today.month - 1
                
                report_data = self.generate_monthly_report(db, str(user.id), year, month)
                
                # Send report
                if self.save_and_send_report(db, str(user.id), report_data):
                    sent_count += 1
                    print(f"Monthly report sent to user {user.id}")
                
            except Exception as e:
                print(f"Error sending monthly report to user {user.id}: {e}")
        
        return sent_count