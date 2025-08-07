from fastapi import APIRouter, Request, Depends, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.services.user_service import get_user_by_email
from app.core.security import verify_token
from app.services.google_calendar_service import GoogleCalendarService
from app.core.config import settings
import os

router = APIRouter()

@router.get("/auth/google/calendar")
async def google_calendar_auth():
    """Google Calendar OAuth endpoint"""
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI")
    scope = "https://www.googleapis.com/auth/calendar https://www.googleapis.com/auth/calendar.events"
    
    auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?client_id={client_id}&redirect_uri={redirect_uri}&response_type=code&scope={scope}&access_type=offline&prompt=consent"
    return RedirectResponse(url=auth_url)

@router.get("/auth/google")
async def google_auth():
    """Google OAuth endpoint"""
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI")
    scope = "https://www.googleapis.com/auth/userinfo.email https://www.googleapis.com/auth/userinfo.profile"
    
    auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?client_id={client_id}&redirect_uri={redirect_uri}&response_type=code&scope={scope}&access_type=offline&prompt=consent"
    return RedirectResponse(url=auth_url)

@router.get("/api/v1/auth/google/callback")
async def google_auth_callback_api(
    code: str = Query(...),
    state: str = Query(None),
    db: Session = Depends(get_db)
):
    """Google OAuth callback for API"""
    try:
        from app.services.oauth_service import handle_google_callback
        result = await handle_google_callback(code, state, db)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}

@router.get("/verify-email")
async def verify_email(request: Request, token: str, db: Session = Depends(get_db)):
    """Verify user email with token"""
    try:
        from app.services.user_service import verify_user_email
        result = verify_user_email(db, token)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}

@router.get("/logout")
async def logout():
    """Logout user"""
    response = RedirectResponse(url="/", status_code=302)
    response.delete_cookie("access_token")
    return response 