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
        
        # Check if alembic.ini exists
        alembic_config = "/app/alembic.ini"
        if os.path.exists(alembic_config):
            print(f"✅ Found alembic config at: {alembic_config}")
        else:
            print(f"❌ No alembic.ini found at: {alembic_config}")
            # List files in /app to debug
            print("Files in /app:")
            for item in os.listdir("/app"):
                print(f"  {item}")
            return
        
        # Run alembic with explicit config file
        result = subprocess.run([
            "alembic", "-c", alembic_config, "upgrade", "head"
        ], capture_output=True, text=True, check=True)
        
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