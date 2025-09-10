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
        
        # Check if alembic.ini exists in backend directory
        alembic_config = "/app/backend/alembic.ini"
        if os.path.exists(alembic_config):
            print(f"✅ Found alembic config at: {alembic_config}")
        else:
            print(f"❌ No alembic.ini found at: {alembic_config}")
            # List files in /app/backend to debug
            backend_path = "/app/backend"
            if os.path.exists(backend_path):
                print("Files in /app/backend:")
                for item in os.listdir(backend_path):
                    print(f"  {item}")
            return
        
        # Change to backend directory for alembic to work properly
        os.chdir("/app/backend")
        print(f"Changed to backend directory: {os.getcwd()}")
        
        # Set environment variable for alembic to use DATABASE_URL
        env = os.environ.copy()
        database_url = os.environ.get('DATABASE_URL')
        if database_url:
            print(f"✅ Using DATABASE_URL for migration")
            # Override the alembic.ini database URL with environment variable
            result = subprocess.run([
                "alembic", "-c", "alembic.ini", 
                "-x", f"sqlalchemy.url={database_url}",
                "upgrade", "head"
            ], capture_output=True, text=True, check=True, env=env)
        else:
            print("❌ No DATABASE_URL found in environment")
            return
        
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