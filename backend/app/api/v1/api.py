from fastapi import APIRouter

from app.api.v1.endpoints import web_auth, auth, calendar, users, availability, bookings, agent, public

api_router = APIRouter()
# Note: web_auth router should NOT include Google OAuth routes anymore

# API endpoints (with prefix)
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(calendar.router, prefix="/calendar", tags=["calendar"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(availability.router, prefix="/availability", tags=["availability"])
api_router.include_router(bookings.router, prefix="/bookings", tags=["bookings"])
# Public booking routes
api_router.include_router(public.router, prefix="/public", tags=["public"])
api_router.include_router(agent.router, prefix="/agent", tags=["agent"])