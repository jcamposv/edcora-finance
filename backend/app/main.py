from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.routers import users, transactions, whatsapp, stripe, reports
from app.core.database import engine, Base
from app.services.scheduler import SchedulerService

# Global scheduler instance
scheduler_service = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle application startup and shutdown events."""
    global scheduler_service
    
    # Startup
    print("Starting up the application...")
    
    # Create database tables
    Base.metadata.create_all(bind=engine)
    print("Database tables created/verified")
    
    # Start scheduler
    scheduler_service = SchedulerService()
    scheduler_service.start()
    print("Scheduler started")
    
    yield
    
    # Shutdown
    print("Shutting down the application...")
    if scheduler_service:
        scheduler_service.stop()
    print("Scheduler stopped")

# Create FastAPI app with lifespan events
app = FastAPI(
    title="Control Finanzas API",
    description="MVP de control de finanzas personales vía WhatsApp",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],  # Add your frontend URLs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(users.router)
app.include_router(transactions.router)
app.include_router(whatsapp.router)
app.include_router(stripe.router)
app.include_router(reports.router)

@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Control Finanzas API - MVP", "version": "1.0.0"}

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "Control Finanzas API"}

@app.get("/scheduler/status")
async def scheduler_status():
    """Get scheduler status and jobs."""
    global scheduler_service
    
    if not scheduler_service:
        return {"status": "not_running", "jobs": []}
    
    jobs = scheduler_service.get_jobs()
    return {
        "status": "running",
        "jobs": jobs
    }

@app.post("/scheduler/pause/{job_id}")
async def pause_job(job_id: str):
    """Pause a scheduled job."""
    global scheduler_service
    
    if not scheduler_service:
        return {"status": "error", "message": "Scheduler not running"}
    
    success = scheduler_service.pause_job(job_id)
    
    if success:
        return {"status": "success", "message": f"Job {job_id} paused"}
    else:
        return {"status": "error", "message": f"Failed to pause job {job_id}"}

@app.post("/scheduler/resume/{job_id}")
async def resume_job(job_id: str):
    """Resume a scheduled job."""
    global scheduler_service
    
    if not scheduler_service:
        return {"status": "error", "message": "Scheduler not running"}
    
    success = scheduler_service.resume_job(job_id)
    
    if success:
        return {"status": "success", "message": f"Job {job_id} resumed"}
    else:
        return {"status": "error", "message": f"Failed to resume job {job_id}"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)