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
    # Mount static assets (CSS, JS, images, etc.)
    assets_path = os.path.join(frontend_build_path, "assets")
    if os.path.exists(assets_path):
        app.mount("/assets", StaticFiles(directory=assets_path), name="assets")
    
    # Mount favicon and other root-level static files
    app.mount("/static", StaticFiles(directory=frontend_build_path), name="static")
    
    print(f"✅ Serving frontend from: {frontend_build_path}")
    print(f"📁 Assets path: {assets_path}")
    
    # List contents to debug
    try:
        dist_contents = os.listdir(frontend_build_path)
        print(f"📂 Dist contents: {dist_contents}")
        if os.path.exists(assets_path):
            assets_contents = os.listdir(assets_path)
            print(f"🎨 Assets contents: {assets_contents}")
    except Exception as e:
        print(f"❌ Error listing contents: {e}")
    
else:
    print(f"⚠️  Frontend build not found at: {frontend_build_path}")

# This should be the LAST route to catch all remaining paths
@app.get("/{full_path:path}")
async def catch_all(full_path: str):
    """Serve the frontend for all non-API routes"""
    # Skip API routes, docs, and static files
    if (full_path.startswith(("docs", "redoc", "openapi.json", "health", "users", "transactions", "whatsapp", "stripe", "reports", "assets", "static")) 
        or full_path.endswith((".js", ".css", ".png", ".jpg", ".ico", ".svg"))):
        # This should not be reached due to mounted static files and API routes
        return {"error": "Route not found"}
    
    # Serve index.html for all frontend routes (SPA routing)
    index_path = os.path.join(frontend_build_path, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path, media_type="text/html")
    else:
        return {"message": "Frontend not available", "path": full_path}

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