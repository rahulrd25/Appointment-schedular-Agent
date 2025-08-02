import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from fastapi import FastAPI, Request, Form, HTTPException, Depends, Query, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse, HTMLResponse, PlainTextResponse
from sqlalchemy.orm import Session
import pytz
import asyncio
from typing import Any

# Load environment variables from .env file if it exists
env_file = Path(".env")
if env_file.exists():
    with open(env_file, "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ[key] = value

from app.api.v1.api import api_router
from app.core.config import settings
from app.core.database import Base, engine, get_db
from app.services.user_service import authenticate_user, create_user, get_user_by_email
from app.core.security import create_access_token, verify_token
from app.schemas.schemas import UserCreate
from app.models.models import User
from app.services.sync.background_sync import BackgroundSyncService

# Create database tables (only create if they don't exist)
Base.metadata.create_all(bind=engine)  # Create all tables with updated schema

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="AI-powered appointment scheduling agent",
    version="1.0.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
)

# Define dashboard routes early to avoid conflicts

# Dashboard route is now handled by the modular dashboard router
# See app/routers/dashboard.py for the correct implementation

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Include API router (with prefix for API endpoints)
app.include_router(api_router, prefix=settings.API_V1_STR)

# Include other routers FIRST (specific routes)
from app.routers import dashboard, auth, settings, bookings, availability
app.include_router(dashboard.router, tags=["dashboard"])
app.include_router(auth.router, tags=["auth"])
app.include_router(settings.router, tags=["settings"])
app.include_router(bookings.router, tags=["bookings"])
app.include_router(availability.router, tags=["availability"])

# Include public router for page rendering (without prefix)
from app.api.v1.endpoints import public
app.include_router(public.router, tags=["public_pages"])

# Public booking API routes are handled by api_router (public.py)

# Include webhooks router for Google Calendar sync
from app.api.v1.endpoints import webhooks
app.include_router(webhooks.router, prefix="/api/v1/webhooks", tags=["webhooks"])

# Templates for HTML responses
templates = Jinja2Templates(directory="app/templates")

# Initialize background sync service
background_sync_service = BackgroundSyncService()


@app.on_event("startup")
async def startup_event():
    """Start background sync service on application startup"""
    print("🚀 Starting Appointment Agent with background sync service...")
    
    # Start background sync service
    asyncio.create_task(background_sync_service.start_periodic_sync())
    print("🔄 Background sync service started")


@app.on_event("shutdown")
async def shutdown_event():
    """Stop background sync service on application shutdown"""
    print("🛑 Shutting down Appointment Agent...")
    
    # Stop background sync service
    await background_sync_service.stop_periodic_sync()
    print("🛑 Background sync service stopped")


@app.get("/")
async def root(request: Request):
    """Root endpoint - redirect to landing page"""
    return templates.TemplateResponse("index.html", {"request": request})

# Agent redirect
@app.get("/agent")
async def agent_redirect(request: Request):
    """Redirect to agent page"""
    return RedirectResponse(url="/dashboard", status_code=302)









# Error handlers
@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    """Handle 404 errors"""
    return templates.TemplateResponse("404.html", {"request": request})

@app.exception_handler(500)
async def internal_error_handler(request: Request, exc):
    """Handle 500 errors"""
    return templates.TemplateResponse("500.html", {"request": request})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 