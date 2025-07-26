from fastapi import APIRouter

from app.api.v1.endpoints import auth, calendar, public, users, web_auth, web_pages

api_router = APIRouter()

# Web pages (no auth required)
api_router.include_router(web_pages.router, tags=["web_pages"])

# Web authentication (HTML forms, Google OAuth)
api_router.include_router(web_auth.router, tags=["web_auth"])

# API endpoints (JSON responses)
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(calendar.router, prefix="/calendar", tags=["calendar"])

# Public pages (some require auth)
api_router.include_router(public.router, tags=["public"])