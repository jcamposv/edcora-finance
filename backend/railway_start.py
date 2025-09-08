#!/usr/bin/env python3
"""
Railway startup script for FastAPI backend only
"""
import os
import uvicorn

# Import the main app
from app.main import app

# Get port from Railway environment
port = int(os.environ.get("PORT", 8000))

if __name__ == "__main__":
    print(f"🚀 Starting FastAPI backend on port {port}")
    print(f"🌍 Environment: {os.environ.get('RAILWAY_ENVIRONMENT', 'development')}")
    
    uvicorn.run(
        "railway_start:app",
        host="0.0.0.0",
        port=port,
        log_level="info"
    )