from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import sessionmaker
from app.core.database import engine
from app.services.report_service import ReportService
from app.services.otp_service import OTPService
import atexit

class SchedulerService:
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.report_service = ReportService()
        self.otp_service = OTPService()
        
        # Create database session
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        self.db_session = SessionLocal
        
        self._setup_jobs()
    
    def _setup_jobs(self):
        """Setup all scheduled jobs."""
        
        # Weekly reports - every Sunday at 8:00 PM
        self.scheduler.add_job(
            func=self._send_weekly_reports,
            trigger=CronTrigger(day_of_week=6, hour=20, minute=0),  # Sunday = 6
            id='weekly_reports',
            name='Send Weekly Reports',
            replace_existing=True
        )
        
        # Monthly reports - first day of month at 9:00 AM
        self.scheduler.add_job(
            func=self._send_monthly_reports,
            trigger=CronTrigger(day=1, hour=9, minute=0),
            id='monthly_reports',
            name='Send Monthly Reports',
            replace_existing=True
        )
        
        # Cleanup expired OTPs - every hour
        self.scheduler.add_job(
            func=self._cleanup_expired_otps,
            trigger=CronTrigger(minute=0),  # Every hour at minute 0
            id='cleanup_otps',
            name='Cleanup Expired OTPs',
            replace_existing=True
        )
        
        # Test job - every minute (remove in production)
        # self.scheduler.add_job(
        #     func=self._test_job,
        #     trigger=CronTrigger(minute='*'),
        #     id='test_job',
        #     name='Test Job',
        #     replace_existing=True
        # )
    
    def _send_weekly_reports(self):
        """Job function to send weekly reports."""
        print("Starting weekly reports job...")
        db = self.db_session()
        try:
            sent_count = self.report_service.send_weekly_reports(db)
            print(f"Weekly reports job completed. Sent {sent_count} reports.")
        except Exception as e:
            print(f"Error in weekly reports job: {e}")
        finally:
            db.close()
    
    def _send_monthly_reports(self):
        """Job function to send monthly reports."""
        print("Starting monthly reports job...")
        db = self.db_session()
        try:
            sent_count = self.report_service.send_monthly_reports(db)
            print(f"Monthly reports job completed. Sent {sent_count} reports.")
        except Exception as e:
            print(f"Error in monthly reports job: {e}")
        finally:
            db.close()
    
    def _cleanup_expired_otps(self):
        """Job function to cleanup expired OTPs."""
        try:
            self.otp_service.cleanup_expired_otps()
            print("OTP cleanup completed.")
        except Exception as e:
            print(f"Error in OTP cleanup job: {e}")
    
    def _test_job(self):
        """Test job function (remove in production)."""
        print("Test job executed successfully!")
    
    def start(self):
        """Start the scheduler."""
        print("Starting scheduler...")
        self.scheduler.start()
        
        # Print scheduled jobs
        print("Scheduled jobs:")
        for job in self.scheduler.get_jobs():
            print(f"  - {job.name} ({job.id}): next run at {job.next_run_time}")
        
        # Shutdown scheduler when the application exits
        atexit.register(lambda: self.scheduler.shutdown())
    
    def stop(self):
        """Stop the scheduler."""
        print("Stopping scheduler...")
        self.scheduler.shutdown()
    
    def get_jobs(self):
        """Get list of scheduled jobs."""
        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append({
                'id': job.id,
                'name': job.name,
                'next_run_time': job.next_run_time.isoformat() if job.next_run_time else None,
                'trigger': str(job.trigger)
            })
        return jobs
    
    def pause_job(self, job_id: str):
        """Pause a specific job."""
        try:
            self.scheduler.pause_job(job_id)
            return True
        except Exception as e:
            print(f"Error pausing job {job_id}: {e}")
            return False
    
    def resume_job(self, job_id: str):
        """Resume a specific job."""
        try:
            self.scheduler.resume_job(job_id)
            return True
        except Exception as e:
            print(f"Error resuming job {job_id}: {e}")
            return False