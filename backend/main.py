import os
import logging
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

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

# Import routers
from app.routers import auth, dashboard, bookings, settings as settings_router, public, availability

# Create database tables (only create if they don't exist)
Base.metadata.create_all(bind=engine)

# Configure logging
logging.basicConfig(level=logging.INFO)
# Reduce uvicorn access log verbosity
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

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

# Include all routers
app.include_router(auth.router, tags=["Authentication"])
app.include_router(dashboard.router, tags=["Dashboard"])
app.include_router(bookings.router, tags=["Bookings"])
app.include_router(settings_router.router, tags=["Settings"])
app.include_router(availability.router, tags=["Availability"])
app.include_router(public.router, tags=["Public"])

# Root redirect
@app.get("/")
async def root():
    """Redirect root to login page"""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/login", status_code=302)

# Agent redirect
@app.get("/agent")
async def agent_redirect():
    """Redirect /agent to /dashboard"""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/dashboard", status_code=302)

# Exception handlers
@app.exception_handler(404)
async def not_found_handler(request, exc):
    """Handle 404 errors"""
    from fastapi.responses import HTMLResponse
    from fastapi.templating import Jinja2Templates
    templates = Jinja2Templates(directory="app/templates")
    return templates.TemplateResponse("404.html", {"request": request})

@app.exception_handler(500)
async def internal_error_handler(request, exc):
    """Handle 500 errors"""
    from fastapi.responses import HTMLResponse
    from fastapi.templating import Jinja2Templates
    templates = Jinja2Templates(directory="app/templates")
    return templates.TemplateResponse("500.html", {"request": request})

