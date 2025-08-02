from datetime import timedelta
from typing import Any
from datetime import datetime
import requests
import secrets

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_access_token, verify_token
from app.schemas.schemas import UserCreate
from app.services.user_service import authenticate_user, create_user, get_user_by_email
from app.models.models import User

router = APIRouter()


@router.post("/login/access-token", response_model=dict)
async def login_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
) -> Any:
    """OAuth2 compatible token login, get an access token for future requests"""
    user = await authenticate_user(email=form_data.username, password=form_data.password)
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return {"access_token": create_access_token(data={"sub": user.email}, expires_delta=access_token_expires), "token_type": "bearer"}


@router.get("/google")
async def google_auth():
    """Start Google OAuth flow for signup/login"""
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=500, detail="Google OAuth not configured")
    
    google_auth_url = (
        "https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={settings.GOOGLE_CLIENT_ID}&"
        "response_type=code&"
        "scope=openid email profile https://www.googleapis.com/auth/calendar https://www.googleapis.com/auth/calendar.events https://www.googleapis.com/auth/calendar.readonly https://www.googleapis.com/auth/gmail.send&"
        f"redirect_uri={settings.GOOGLE_REDIRECT_URI}&"
        "access_type=offline&"
        "prompt=consent&"
        "state=signup"
    )
    
    return RedirectResponse(url=google_auth_url)


@router.get("/google/calendar")
async def google_calendar_auth():
    """Start Google Calendar OAuth flow with calendar permissions"""
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=500, detail="Google OAuth not configured")
    
    google_auth_url = (
        "https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={settings.GOOGLE_CLIENT_ID}&"
        "response_type=code&"
        "scope=openid email profile https://www.googleapis.com/auth/calendar https://www.googleapis.com/auth/calendar.events https://www.googleapis.com/auth/calendar.readonly https://www.googleapis.com/auth/gmail.send&"
        f"redirect_uri={settings.GOOGLE_REDIRECT_URI}&"
        "access_type=offline&"
        "prompt=consent&"
        "state=calendar_connection"
    )
    
    return RedirectResponse(url=google_auth_url)


@router.get("/google/callback")
async def google_auth_callback(
    code: str = Query(...),
    state: str = Query(None),
    db: Session = Depends(get_db)
):
    """Handle Google OAuth callback"""
    is_calendar_connection = state == "calendar_connection"
    
    try:
        token_url = "https://oauth2.googleapis.com/token"
        token_data = {
            "code": code,
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "redirect_uri": settings.GOOGLE_REDIRECT_URI,
            "grant_type": "authorization_code",
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        
        token_response = requests.post(token_url, data=token_data, headers=headers)
        token_response.raise_for_status()
        tokens = token_response.json()
        access_token = tokens.get("access_token")
        refresh_token = tokens.get("refresh_token")
        scope = tokens.get("scope", "")
        
        if not access_token:
            raise Exception("No access token in response")
        
        # Get user info from Google
        user_info_url = "https://www.googleapis.com/oauth2/v2/userinfo"
        user_response = requests.get(user_info_url, headers={"Authorization": f"Bearer {access_token}"})
        user_response.raise_for_status()
        user_info = user_response.json()
        
        # Check if user exists
        user = get_user_by_email(db, user_info["email"])
        
        if is_calendar_connection:
            # Calendar connection flow - allows connecting any Google account for calendar
            calendar_email = user_info.get("email")
            calendar_name = user_info.get("name")
            
            # Check if calendar scope is present
            if "calendar" not in scope.lower():
                return RedirectResponse(url="/dashboard?calendar_error=no_calendar_scope", status_code=302)
            
            # For calendar connection, we need to get the current logged-in user
            # The user will be authenticated via cookie in the complete_calendar_connection endpoint
            # So we'll just store the connection data and let the completion endpoint handle the user
            
            # Store calendar connection in database
            try:
                from app.services.pending_connection_service import PendingConnectionService
                
                connection_id = PendingConnectionService.create_pending_connection(
                    db=db,
                    calendar_email=calendar_email,
                    calendar_name=calendar_name,
                    access_token=access_token,
                    refresh_token=refresh_token,
                    scope=scope
                )
                
                # Redirect to agent dashboard with connection ID
                redirect_url = f"/dashboard?calendar_connection_id={connection_id}"
                return RedirectResponse(url=redirect_url, status_code=302)
                
            except Exception as e:
                return RedirectResponse(url="/dashboard?calendar_error=storage_failed", status_code=302)
        
        else:
            # Regular signup flow
            if not user:
                # Create new user
                user_data = UserCreate(
                    email=user_info["email"],
                    password="",  # Google users don't need password
                    full_name=user_info.get("name", ""),
                    google_id=user_info["id"]
                )
                user = create_user(db, user_data)
            else:
                # Update existing user's Google ID and full name if not set
                updated = False
                if not user.google_id:
                    user.google_id = user_info["id"]
                    updated = True
                if not user.full_name and user_info.get("name"):
                    user.full_name = user_info["name"]
                    updated = True
                if updated:
                    db.commit()
            
            # Store Google credentials and mark calendar as connected (since signup includes calendar permissions)
            user.google_access_token = access_token
            if refresh_token:
                user.google_refresh_token = refresh_token
            user.google_calendar_connected = True
            user.google_calendar_email = user.email
            db.commit()
            
            # Create access token for our app
            jwt_token = create_access_token(data={"sub": user.email})
            
            # Redirect to dashboard page with cookie
            response = RedirectResponse(url="/dashboard", status_code=302)
            response.set_cookie(
                key="access_token",
                value=jwt_token,
                httponly=True,
                max_age=1800,
                secure=False,
                samesite="lax"
            )
            return response
        
    except Exception as e:
        error_url = "/dashboard?calendar_error=true" if is_calendar_connection else "/login?error=google_auth_failed"
        return RedirectResponse(url=error_url, status_code=302)


@router.post("/calendar/connect")
async def complete_calendar_connection(
    request: Request, 
    connection_id: str = Form(...), 
    db: Session = Depends(get_db)
):
    """Complete the calendar connection process"""
    access_token = request.cookies.get("access_token")
    if not access_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        payload = verify_token(access_token)
        if not payload:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        user_email = payload.get("sub")
        user = get_user_by_email(db, user_email)
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        
        # Get the pending calendar connection from database
        from app.services.pending_connection_service import PendingConnectionService
        
        pending_connection = PendingConnectionService.get_pending_connection(db, connection_id)
        if not pending_connection:
            raise HTTPException(status_code=404, detail="Calendar connection not found or expired")
        
        # Update the pending connection with the user_id
        pending_connection.user_id = user.id
        db.commit()
        
        # Update user with calendar credentials
        user.google_access_token = pending_connection.access_token
        user.google_refresh_token = pending_connection.refresh_token
        user.google_calendar_connected = True
        user.google_calendar_email = pending_connection.calendar_email
        
        db.commit()
        
        # Clean up the pending connection
        PendingConnectionService.delete_pending_connection(db, connection_id)
        
        # Initialize calendar sync for the user
        try:
            from app.services.sync.background_sync import BackgroundSyncService
            from app.core.calendar_architecture import CalendarSyncService, create_calendar_provider, CalendarProviderType
            
            # Create calendar sync service for the user
            sync_service = CalendarSyncService(db, user.id)
            
            # Register Google Calendar provider
            google_provider = create_calendar_provider(
                CalendarProviderType.GOOGLE,
                access_token=user.google_access_token,
                refresh_token=user.google_refresh_token,
                db=db,
                user_id=user.id
            )
            sync_service.register_provider(google_provider)
            
            print(f"✅ Calendar sync initialized for user {user.email}")
            
        except Exception as e:
            print(f"⚠️ Calendar sync initialization failed for {user.email}: {str(e)}")
            # Don't fail the connection if sync initialization fails
        
        return {"success": True, "calendar_email": pending_connection.calendar_email}
        
    except Exception as e:
        print(f"❌ Calendar connection failed: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Calendar connection failed: {str(e)}")
