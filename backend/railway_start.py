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
        print("🧱 Running Alembic migrations...")
        
        # Change to backend directory where alembic.ini is located
        os.chdir("/app/backend")
        
        # First, mark the problematic migration as complete without running it
        print("📋 Marking organizations migration as complete...")
        result = subprocess.run(
            ["alembic", "stamp", "20250909_201123"], 
            capture_output=True, text=True, check=True
        )
        
        # Now run remaining migrations
        print("🔄 Running remaining migrations...")
        result = subprocess.run(
            ["alembic", "upgrade", "head"], 
            capture_output=True, text=True, check=True
        )
        
        print("✅ Migrations completed successfully")
        if result.stdout.strip():
            print(result.stdout)
            
    except subprocess.CalledProcessError as e:
        print(f"❌ Migration failed: {e}")
        if e.stdout:
            print(f"STDOUT: {e.stdout}")
        if e.stderr:
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