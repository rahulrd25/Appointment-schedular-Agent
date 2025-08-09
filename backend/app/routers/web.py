from fastapi import APIRouter
from app.routers import auth, dashboard, bookings, availability, settings, landing_page

# Create main web router
web_router = APIRouter()

# Include all web page routers
web_router.include_router(auth.router, tags=["auth"])
web_router.include_router(dashboard.router, tags=["dashboard"])
web_router.include_router(bookings.router, tags=["bookings"])
web_router.include_router(availability.router, tags=["availability"])
web_router.include_router(settings.router, tags=["settings"])
web_router.include_router(landing_page.router, tags=["landing_page"]) 