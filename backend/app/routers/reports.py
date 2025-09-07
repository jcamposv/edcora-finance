from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.core.database import get_db
from app.core.schemas import Report
from app.services.report_service import ReportService
from app.services.user_service import UserService

router = APIRouter(prefix="/reports", tags=["reports"])

report_service = ReportService()

@router.get("/user/{user_id}", response_model=List[Report])
def get_user_reports(
    user_id: str,
    period: Optional[str] = Query(None, description="Filter by period: weekly, monthly, yearly"),
    db: Session = Depends(get_db)
):
    """Get all reports for a user, optionally filtered by period."""
    
    # Check if user exists
    user = UserService.get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    reports = ReportService.get_user_reports(db, user_id, period)
    return reports

@router.post("/generate/weekly/{user_id}")
def generate_weekly_report(user_id: str, db: Session = Depends(get_db)):
    """Generate and return weekly report for a user."""
    
    # Check if user exists
    user = UserService.get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    try:
        report_data = report_service.generate_weekly_report(db, user_id)
        return {
            "status": "success",
            "report": report_data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating report: {str(e)}")

@router.post("/generate/monthly/{user_id}")
def generate_monthly_report(
    user_id: str,
    year: Optional[int] = Query(None, description="Year for the report"),
    month: Optional[int] = Query(None, description="Month for the report (1-12)"),
    db: Session = Depends(get_db)
):
    """Generate and return monthly report for a user."""
    
    # Check if user exists
    user = UserService.get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    try:
        report_data = report_service.generate_monthly_report(db, user_id, year, month)
        return {
            "status": "success",
            "report": report_data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating report: {str(e)}")

@router.post("/generate/yearly/{user_id}")
def generate_yearly_report(
    user_id: str,
    year: Optional[int] = Query(None, description="Year for the report"),
    db: Session = Depends(get_db)
):
    """Generate and return yearly report for a user."""
    
    # Check if user exists
    user = UserService.get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    try:
        report_data = report_service.generate_yearly_report(db, user_id, year)
        return {
            "status": "success",
            "report": report_data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating report: {str(e)}")

@router.post("/send/weekly/{user_id}")
def send_weekly_report(user_id: str, db: Session = Depends(get_db)):
    """Generate and send weekly report via WhatsApp."""
    
    # Check if user exists
    user = UserService.get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    try:
        # Generate report
        report_data = report_service.generate_weekly_report(db, user_id)
        
        # Save and send report
        success = report_service.save_and_send_report(db, user_id, report_data)
        
        if success:
            return {"status": "success", "message": "Weekly report sent successfully"}
        else:
            raise HTTPException(status_code=500, detail="Error sending report")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@router.post("/send/monthly/{user_id}")
def send_monthly_report(
    user_id: str,
    year: Optional[int] = Query(None, description="Year for the report"),
    month: Optional[int] = Query(None, description="Month for the report (1-12)"),
    db: Session = Depends(get_db)
):
    """Generate and send monthly report via WhatsApp."""
    
    # Check if user exists
    user = UserService.get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    try:
        # Generate report
        report_data = report_service.generate_monthly_report(db, user_id, year, month)
        
        # Save and send report
        success = report_service.save_and_send_report(db, user_id, report_data)
        
        if success:
            return {"status": "success", "message": "Monthly report sent successfully"}
        else:
            raise HTTPException(status_code=500, detail="Error sending report")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")