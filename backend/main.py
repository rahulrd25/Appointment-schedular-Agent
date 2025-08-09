import os
from pathlib import Path
import logging

# Configure logging FIRST - before any database imports
log_level = getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO)
logging.basicConfig(
    level=log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("app.log") if os.getenv("ENVIRONMENT") == "production" else logging.NullHandler()
    ]
)

# Suppress SQLAlchemy logging in production or when explicitly requested
environment = os.getenv("ENVIRONMENT", "development")
if environment == "production" or os.getenv("SUPPRESS_SQL_LOGS", "false").lower() == "true":
    logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
    logging.getLogger('sqlalchemy.pool').setLevel(logging.WARNING)
    logging.getLogger('sqlalchemy.dialects').setLevel(logging.WARNING)
    logging.getLogger('sqlalchemy.orm').setLevel(logging.WARNING)

# Load environment variables from .env file if it exists
env_file = Path(".env")
if env_file.exists():
    with open(env_file, "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ[key] = value

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.trustedhost import TrustedHostMiddleware
import asyncio

# Import database and models
from app.api.v1.api import api_router
from app.core.config import settings
from app.core.database import Base, engine

# Create database tables (only create if they don't exist)
Base.metadata.create_all(bind=engine)

# Import background sync service
from app.services.sync.background_sync import background_sync_service

# Import routers
from app.routers.web import web_router
from app.routers.public_scheduling import router as public_scheduling_router

# Get logger for this module
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="AI-powered appointment scheduling agent",
    version="1.0.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs" if settings.DEBUG else None,  # Disable docs in production
    redoc_url="/redoc" if settings.DEBUG else None,  # Disable redoc in production
)

# CORS middleware - Configure appropriately for production
allowed_origins = [
    settings.FRONTEND_URL,
    "http://localhost:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://127.0.0.1:3000",
]

# Add production origins if configured
if settings.ENVIRONMENT == "production":
    # Add your production domain here
    production_origins = os.getenv("ALLOWED_ORIGINS", "").split(",")
    allowed_origins.extend([origin.strip() for origin in production_origins if origin.strip()])
    
    # Ensure HTTPS in production
    if not any(origin.startswith("https://") for origin in allowed_origins):
        logger.warning("No HTTPS origins configured for production environment")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins if settings.ENVIRONMENT == "production" else ["http://localhost:3000", "http://localhost:8000", "http://127.0.0.1:8000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    
    # Security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    
    # HSTS header (only for HTTPS)
    if settings.ENVIRONMENT == "production" and request.url.scheme == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    
    # Content Security Policy
    csp_policy = "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self' data:;"
    response.headers["Content-Security-Policy"] = csp_policy
    
    return response

# Static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Include API router
app.include_router(api_router, prefix=settings.API_V1_STR)

# Include web page routers
app.include_router(web_router)
app.include_router(public_scheduling_router)

# Templates for HTML responses
templates = Jinja2Templates(directory="app/templates")

# Configure logging based on environment
# log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
# logging.basicConfig(
#     level=log_level,
#     format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
#     handlers=[
#         logging.StreamHandler(),
#         logging.FileHandler("app.log") if settings.ENVIRONMENT == "production" else logging.NullHandler()
#     ]
# )
# logger = logging.getLogger(__name__)

@app.on_event("startup")
async def startup_event():
    """Start background sync service on application startup"""
    logger.info("Starting background sync service...")
    try:
        # Start background sync in a separate task
        asyncio.create_task(background_sync_service.start_periodic_sync())
        logger.info("Background sync service started successfully")
    except Exception as e:
        logger.error(f"Failed to start background sync service: {e}")

@app.exception_handler(500)
async def internal_error_handler(request: Request, exc):
    """Handle 500 errors"""
    return templates.TemplateResponse(
        "500.html", 
        {"request": request}, 
        status_code=500
    )

