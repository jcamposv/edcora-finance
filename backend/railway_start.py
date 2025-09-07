#!/usr/bin/env python3
"""
Railway startup script for serving both FastAPI backend and built frontend
"""
import os
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Import the main app
from app.main import app

# Get port from Railway environment
port = int(os.environ.get("PORT", 8000))

# Mount static files from frontend build
frontend_build_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "dist")

if os.path.exists(frontend_build_path):
    # Mount static assets
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_build_path, "assets")), name="assets")
    
    # Serve index.html for all frontend routes
    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        # If it's an API route, let FastAPI handle it
        if full_path.startswith(("docs", "redoc", "openapi.json", "health", "users", "transactions", "whatsapp", "stripe", "reports")):
            return None  # Let FastAPI handle these routes
        
        # For all other routes, serve the frontend
        index_path = os.path.join(frontend_build_path, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
        else:
            return {"message": "Frontend not found"}
    
    print(f"✅ Serving frontend from: {frontend_build_path}")
else:
    print(f"⚠️  Frontend build not found at: {frontend_build_path}")

if __name__ == "__main__":
    print(f"🚀 Starting server on port {port}")
    print(f"📁 Frontend path: {frontend_build_path}")
    print(f"🌍 Environment: {os.environ.get('RAILWAY_ENVIRONMENT', 'development')}")
    
    uvicorn.run(
        "railway_start:app",
        host="0.0.0.0",
        port=port,
        log_level="info"
    )