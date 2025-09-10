#!/usr/bin/env python3
"""
Railway startup script for FastAPI backend only
"""
import os
import subprocess
import sys
import uvicorn

def run_migrations():
    """Run Alembic migrations before starting the app"""
    try:
        print("🔄 Running database migrations...")
        print(f"Current working directory: {os.getcwd()}")
        
        # Change to the directory containing alembic.ini
        os.chdir("/app")  # Railway workdir
        print(f"Changed to directory: {os.getcwd()}")
        
        result = subprocess.run(["alembic", "upgrade", "head"], 
                              capture_output=True, text=True, check=True)
        print("✅ Migrations completed successfully")
        if result.stdout.strip():
            print(f"STDOUT: {result.stdout}")
    except subprocess.CalledProcessError as e:
        print(f"❌ Migration failed: {e}")
        print(f"STDOUT: {e.stdout}")
        print(f"STDERR: {e.stderr}")
        sys.exit(1)

# Import the main app
from app.main import app

# Get port from Railway environment
port = int(os.environ.get("PORT", 8000))

if __name__ == "__main__":
    print(f"🚀 Starting FastAPI backend on port {port}")
    print(f"🌍 Environment: {os.environ.get('RAILWAY_ENVIRONMENT', 'development')}")
    
    # Run migrations first
    run_migrations()
    
    # Start the app
    uvicorn.run(
        "railway_start:app",
        host="0.0.0.0",
        port=port,
        log_level="info"
    )