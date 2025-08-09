import os
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import asyncio

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
from app.core.database import Base, engine

# Create database tables (only create if they don't exist)
Base.metadata.create_all(bind=engine)  # Create all tables with updated schema

# Import background sync service
from app.services.sync.background_sync import background_sync_service

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="AI-powered appointment scheduling agent",
    version="1.0.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
)

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

# Include API router
app.include_router(api_router, prefix=settings.API_V1_STR)

# Include web page routers
from app.routers.web import web_router
from app.routers.public_scheduling import router as public_scheduling_router

app.include_router(web_router)
app.include_router(public_scheduling_router)

# Templates for HTML responses
templates = Jinja2Templates(directory="app/templates")

@app.on_event("startup")
async def startup_event():
    """Start background sync service on application startup"""
    print("[STARTUP] Starting background sync service...")
    try:
        # Start background sync in a separate task
        asyncio.create_task(background_sync_service.start_periodic_sync())
        print("[STARTUP] Background sync service started successfully")
    except Exception as e:
        print(f"[STARTUP ERROR] Failed to start background sync service: {e}")

@app.exception_handler(500)
async def internal_error_handler(request: Request, exc):
    """Handle 500 errors"""
    return templates.TemplateResponse(
        "500.html", 
        {"request": request}, 
        status_code=500
    )

