from fastapi import APIRouter

from app.api.v1.endpoints import web_auth, web_pages, auth, calendar, public, users

api_router = APIRouter()

# Web pages (no prefix)
api_router.include_router(web_pages.router, tags=["web_pages"])
# Note: web_auth router should NOT include Google OAuth routes anymore

# API endpoints (with prefix)
api_router.include_router(auth.router, prefix="/api/v1", tags=["auth"])
api_router.include_router(calendar.router, prefix="/api/v1", tags=["calendar"])
api_router.include_router(public.router, prefix="/api/v1", tags=["public"])
api_router.include_router(users.router, prefix="/api/v1", tags=["users"])