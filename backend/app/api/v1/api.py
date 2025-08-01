from fastapi import APIRouter

from app.api.v1.endpoints import web_auth, web_pages, auth, calendar, users, availability, bookings, agent, public

api_router = APIRouter()

# Web pages (no prefix)
api_router.include_router(web_pages.router, tags=["web_pages"])
# Note: web_auth router should NOT include Google OAuth routes anymore

# API endpoints (with prefix)
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(calendar.router, prefix="/api/v1", tags=["calendar"])
api_router.include_router(users.router, prefix="/api/v1", tags=["users"])
<<<<<<< HEAD
api_router.include_router(availability.router, prefix="/api/v1/availability", tags=["availability"])
api_router.include_router(bookings.router, prefix="/api/v1/bookings", tags=["bookings"])
=======
api_router.include_router(availability.router, prefix="/availability", tags=["availability"])
# api_router.include_router(bookings.router, prefix="/bookings", tags=["bookings"])
>>>>>>> e3b999cd02f578d5176e7dbc287d1a2a1f5f3840
api_router.include_router(public.router, prefix="/public", tags=["public"])
api_router.include_router(agent.router, prefix="/agent", tags=["agent"])