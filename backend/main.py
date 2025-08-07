import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from fastapi import FastAPI, Request, Form, HTTPException, Depends, Query, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse, HTMLResponse, PlainTextResponse
from sqlalchemy.orm import Session
import requests
import json
import pytz
import asyncio
from typing import Any

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
from app.core.database import Base, engine, get_db
from app.services.user_service import authenticate_user, create_user, get_user_by_email, verify_user_email
from app.core.security import create_access_token, verify_token
from app.schemas.schemas import UserCreate
from app.models.models import User

# Create database tables (only create if they don't exist)
Base.metadata.create_all(bind=engine)  # Create all tables with updated schema

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

# Templates for HTML responses
templates = Jinja2Templates(directory="app/templates")

# Define routes early to avoid conflicts
@app.get("/agent")
async def agent_redirect(request: Request):
    """Redirect /agent to /dashboard preserving query parameters"""
    query_string = request.url.query
    redirect_url = f"/dashboard{'?' + query_string if query_string else ''}"
    return RedirectResponse(url=redirect_url, status_code=302)

@app.get("/dashboard")
async def dashboard(request: Request, db: Session = Depends(get_db)):
    """Dashboard Interface"""
    print("Dashboard route accessed!")
    access_token = request.cookies.get("access_token")

    if not access_token:
        return RedirectResponse(url="/", status_code=302)

    try:
        payload = verify_token(access_token)
        if not payload:
            return RedirectResponse(url="/", status_code=302)

        user_email = payload.get("sub")
        user = get_user_by_email(db, user_email)

        if not user:
            return RedirectResponse(url="/", status_code=302)

        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "current_user": user
        })

    except Exception as e:
        print(f"Dashboard error: {e}")
        return RedirectResponse(url="/", status_code=302)

# Google OAuth routes
@app.get("/auth/google/calendar")
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

@app.get("/auth/google")
async def google_auth():
    """Start Google OAuth flow"""
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=500, detail="Google OAuth not configured")
    
    google_auth_url = (
        "https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={settings.GOOGLE_CLIENT_ID}&"
        "response_type=code&"
        "scope=openid email profile&"
        f"redirect_uri={settings.GOOGLE_REDIRECT_URI}&"
        "access_type=offline"
    )
    
    return RedirectResponse(url=google_auth_url)

@app.get("/api/v1/auth/google/callback")
async def google_auth_callback_api(
    code: str = Query(...),
    state: str = Query(None),
    db: Session = Depends(get_db)
):
    is_calendar_connection = state == "calendar_connection"
    
    try:
        if is_calendar_connection:
            print("=== GOOGLE CALENDAR OAUTH CALLBACK STARTED ===")
        else:
            print("=== GOOGLE OAUTH CALLBACK STARTED ===")
            
        print("Received code:", code)
        print("State:", state)
        print("Using redirect_uri:", settings.GOOGLE_REDIRECT_URI)
        print("Client ID:", settings.GOOGLE_CLIENT_ID)
        print("Client Secret:", settings.GOOGLE_CLIENT_SECRET)
        
        token_url = "https://oauth2.googleapis.com/token"
        token_data = {
            "code": code,
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "redirect_uri": settings.GOOGLE_REDIRECT_URI,
            "grant_type": "authorization_code",
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        print("Token data:", token_data)
        
        token_response = requests.post(token_url, data=token_data, headers=headers)
        print("Token response status:", token_response.status_code)
        print("Token response text:", token_response.text)
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
        print("User info response status:", user_response.status_code)
        print("User info response text:", user_response.text)
        user_response.raise_for_status()
        user_info = user_response.json()
        
        print("User info:", user_info)
        print("Scopes granted:", scope)
        
        # Check if user exists
        user = get_user_by_email(db, user_info["email"])
        
        if is_calendar_connection:
            # Calendar connection flow - allows connecting any Google account for calendar
            calendar_email = user_info.get("email")
            calendar_name = user_info.get("name")
            
            print(f"Calendar connection request for Google account: {calendar_email}")
            print(f"Available scopes: {scope}")
            
            # Check if calendar scope is present
            if "calendar" not in scope.lower():
                print(f"ERROR: Calendar scope not found in: {scope}")
                return RedirectResponse(url="/dashboard?calendar_error=no_calendar_scope", status_code=302)
            
            # Create a secure temporary storage for calendar connection data
            # We'll use a simple approach: store in a temporary table or session
            # For now, let's store the calendar connection data in a way that can be claimed by the logged-in user
            
            # Store calendar tokens temporarily with a unique identifier
            import secrets
            connection_id = secrets.token_urlsafe(32)
            
            # Store temporarily in a simple dict (in production, use Redis or database)
            if not hasattr(app.state, 'pending_calendar_connections'):
                app.state.pending_calendar_connections = {}
            
            app.state.pending_calendar_connections[connection_id] = {
                'calendar_email': calendar_email,
                'calendar_name': calendar_name,
                'access_token': access_token,
                'refresh_token': refresh_token,
                'created_at': datetime.now(),
                'scope': scope
            }
            
            print(f"Stored calendar connection with ID: {connection_id}")
            
            # Redirect to dashboard with connection ID
            return RedirectResponse(url=f"/dashboard?calendar_connection_id={connection_id}", status_code=302)
        
        else:
            # Regular signup flow
            if not user:
                # Create new user
                print("Creating new user...")
                user_data = UserCreate(
                    email=user_info["email"],
                    password="",  # Google users don't need password
                    full_name=user_info.get("name", ""),
                    google_id=user_info["id"]
                )
                user = create_user(db, user_data)
                print("New user created:", user.email)
            else:
                # Update existing user's Google ID and full name if not set
                print("User exists, updating if needed...")
                updated = False
                if not user.google_id:
                    user.google_id = user_info["id"]
                    updated = True
                if not user.full_name and user_info.get("name"):
                    user.full_name = user_info["name"]
                    updated = True
                if updated:
                    db.commit()
                    print("User updated")
            
            # Store basic Google credentials (but don't mark calendar as connected)
            user.google_access_token = access_token
            if refresh_token:
                user.google_refresh_token = refresh_token
            db.commit()
            
            # Create access token for our app
            jwt_token = create_access_token(data={"sub": user.email})
            print("JWT token created for user:", user.email)
            
            # Redirect to dashboard with cookie
            response = RedirectResponse(url="/dashboard", status_code=302)
            response.set_cookie(
                key="access_token",
                value=jwt_token,
                httponly=True,
                max_age=1800,
                secure=False,
                samesite="lax"
            )
            print("Redirecting to dashboard...")
            return response
        
    except Exception as e:
        print(f"=== GOOGLE OAUTH ERROR ===")
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        error_url = "/dashboard?calendar_error=true" if is_calendar_connection else "/dashboard?error=google_auth_failed"
        return RedirectResponse(url=error_url, status_code=302)

# Add web routes directly

@app.get("/verify-email")
async def verify_email(request: Request, token: str, db: Session = Depends(get_db)):
    user = verify_user_email(db, token)
    if user:
        return templates.TemplateResponse(
            "email_verified.html", 
            {"request": request, "success": "Email verified successfully! You can now log in."}
        )
    else:
        return templates.TemplateResponse(
            "email_verified.html", 
            {"request": request, "error": "Invalid or expired verification token."}
        )

@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/", status_code=302)
    response.delete_cookie("access_token")
    return response

@app.get("/")
async def root(request: Request):
    """Root endpoint - redirect to landing page"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/settings")
async def settings_page(request: Request, db: Session = Depends(get_db)):
    """Settings page for user account management"""
    access_token = request.cookies.get("access_token")

    if not access_token:
        return RedirectResponse(url="/", status_code=302)

    try:
        payload = verify_token(access_token)
        if not payload:
            return RedirectResponse(url="/", status_code=302)

        user_email = payload.get("sub")
        user = get_user_by_email(db, user_email)

        if not user:
            return RedirectResponse(url="/", status_code=302)

        return templates.TemplateResponse("settings.html", {
            "request": request,
            "current_user": user
        })

    except Exception as e:
        print(f"Settings error: {e}")
        return RedirectResponse(url="/", status_code=302)

@app.get("/availability")
async def availability_page(request: Request, db: Session = Depends(get_db)):
    """Availability management page for setting up available time slots"""
    access_token = request.cookies.get("access_token")

    if not access_token:
        return RedirectResponse(url="/", status_code=302)

    try:
        payload = verify_token(access_token)
        if not payload:
            return RedirectResponse(url="/", status_code=302)

        user_email = payload.get("sub")
        user = get_user_by_email(db, user_email)

        if not user:
            return RedirectResponse(url="/", status_code=302)

        # Get user's availability slots
        from app.services.availability_service import get_availability_slots_for_user
        availability_slots = get_availability_slots_for_user(db, user.id)

        from datetime import datetime
        today = datetime.now().strftime('%Y-%m-%d')
        
        return templates.TemplateResponse("availability.html", {
            "request": request,
            "current_user": user,
            "availability_slots": availability_slots,
            "today": today
        })

    except Exception as e:
        print(f"Availability page error: {e}")
        return RedirectResponse(url="/", status_code=302)

@app.get("/bookings")
async def bookings_page(request: Request, db: Session = Depends(get_db)):
    """Bookings management page for viewing and managing appointments"""
    access_token = request.cookies.get("access_token")

    if not access_token:
        return RedirectResponse(url="/", status_code=302)

    try:
        payload = verify_token(access_token)
        if not payload:
            return RedirectResponse(url="/", status_code=302)

        user_email = payload.get("sub")
        user = get_user_by_email(db, user_email)

        if not user:
            return RedirectResponse(url="/", status_code=302)

        return templates.TemplateResponse("bookings.html", {
            "request": request,
            "current_user": user
        })

    except Exception as e:
        print(f"Bookings page error: {e}")
        return RedirectResponse(url="/", status_code=302)

# Public booking route - added directly to main app (MUST be last to avoid conflicts)
@app.get("/{scheduling_slug}", response_class=HTMLResponse)
async def get_public_booking_page(
    request: Request,
    scheduling_slug: str,
    db: Session = Depends(get_db),
) -> Any:
    """Public booking page for a specific user's scheduling link."""
    try:
        from app.services.user_service import get_user_by_scheduling_slug
        user = await get_user_by_scheduling_slug(db, scheduling_slug)
        
        if not user:
            return templates.TemplateResponse("404.html", {"request": request})
        
        # Check if user has availability slots (either calendar connected or manual slots)
        from app.services.availability_service import get_availability_slots_for_user
        availability_slots = get_availability_slots_for_user(db, user.id)
        
        if not availability_slots and not user.google_calendar_connected:
            return templates.TemplateResponse(
                "public_booking_unavailable.html", {
                    "request": request, 
                    "user": user,
                    "reason": "no_availability"
                }
            )
        
        # Calendar is connected - show booking page
        return templates.TemplateResponse("public_booking_all_in_one.html", {
            "request": request,
            "user": user
        })
        
    except Exception as e:
        print(f"Public booking page error: {e}")
        return templates.TemplateResponse("500.html", {"request": request})

@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    """Handle 404 errors"""
    return templates.TemplateResponse(
        "404.html", 
        {"request": request}, 
        status_code=404
    )

# Dashboard API endpoints
@app.get("/dashboard/api/user/status")
async def dashboard_user_status(request: Request, db: Session = Depends(get_db)):
    """Check if user is authenticated and exists"""
    access_token = request.cookies.get("access_token")
    
    if not access_token:
        return {"user_exists": False}
    
    try:
        payload = verify_token(access_token)
        if not payload:
            return {"user_exists": False}
        
        user_email = payload.get("sub")
        user = get_user_by_email(db, user_email)
        
        if not user:
            return {"user_exists": False}
        
        return {
            "user_exists": True,
            "user": {
                "email": user.email,
                "full_name": user.full_name,
                "google_calendar_connected": user.google_calendar_connected
            }
        }
    except Exception as e:
        print(f"User status error: {e}")
        return {"user_exists": False}

@app.get("/dashboard/api/data")
async def dashboard_data(request: Request, db: Session = Depends(get_db)):
    """Get dashboard data including bookings and availability"""
    access_token = request.cookies.get("access_token")
    
    if not access_token:
        return {"error": "Not authenticated"}
    
    try:
        payload = verify_token(access_token)
        if not payload:
            return {"error": "Invalid token"}
        
        user_email = payload.get("sub")
        user = get_user_by_email(db, user_email)
        
        if not user:
            return {"error": "User not found"}
        
        # Get upcoming bookings
        from app.services.booking_service import get_upcoming_bookings
        upcoming_bookings = get_upcoming_bookings(db, user.id, limit=5)
        
        # Get all bookings
        from app.services.booking_service import get_bookings_for_user
        all_bookings = get_bookings_for_user(db, user.id)
        
        # Get available slots
        from app.services.availability_service import get_available_slots_for_booking
        available_slots = get_available_slots_for_booking(db, user.id)
        
        return {
            "upcomingBookings": [
                {
                    "id": booking.id,
                    "guest_name": booking.guest_name,
                    "guest_email": booking.guest_email,
                    "start_time": booking.start_time.isoformat(),
                    "end_time": booking.end_time.isoformat(),
                    "status": booking.status
                } for booking in upcoming_bookings
            ],
            "allBookings": [
                {
                    "id": booking.id,
                    "guest_name": booking.guest_name,
                    "guest_email": booking.guest_email,
                    "start_time": booking.start_time.isoformat(),
                    "end_time": booking.end_time.isoformat(),
                    "status": booking.status
                } for booking in all_bookings
            ],
            "availableSlots": [
                {
                    "id": slot.id,
                    "start_time": slot.start_time.isoformat(),
                    "end_time": slot.end_time.isoformat(),
                    "is_available": slot.is_available
                } for slot in available_slots
            ],
            "calendarConnected": user.google_calendar_connected
        }
    except Exception as e:
        print(f"Dashboard data error: {e}")
        return {"error": str(e)}

@app.post("/dashboard/api/chat")
async def dashboard_chat(request: Request, db: Session = Depends(get_db)):
    """Handle chat messages for the dashboard"""
    access_token = request.cookies.get("access_token")
    
    if not access_token:
        return {"error": "Not authenticated"}
    
    try:
        payload = verify_token(access_token)
        if not payload:
            return {"error": "Invalid token"}
        
        user_email = payload.get("sub")
        user = get_user_by_email(db, user_email)
        
        if not user:
            return {"error": "User not found"}
        
        # Get the message from the request
        form_data = await request.form()
        message = form_data.get("message", "")
        
        if not message:
            return {"error": "No message provided"}
        
        # For now, return a simple response
        # In the future, this could integrate with an AI service
        return {
            "response": f"I received your message: '{message}'. This is a placeholder response. AI integration coming soon!"
        }
    except Exception as e:
        print(f"Dashboard chat error: {e}")
        return {"error": str(e)}

@app.post("/dashboard/api/calendar/connect")
async def dashboard_calendar_connect(request: Request, db: Session = Depends(get_db)):
    """Connect Google Calendar for the user"""
    access_token = request.cookies.get("access_token")
    
    if not access_token:
        return {"error": "Not authenticated"}
    
    try:
        payload = verify_token(access_token)
        if not payload:
            return {"error": "Invalid token"}
        
        user_email = payload.get("sub")
        user = get_user_by_email(db, user_email)
        
        if not user:
            return {"error": "User not found"}
        
        # Redirect to Google Calendar OAuth
        return {"redirect_url": "/auth/google/calendar"}
    except Exception as e:
        print(f"Calendar connect error: {e}")
        return {"error": str(e)}

# Bookings API endpoints
@app.get("/bookings/api/list")
async def bookings_list(request: Request, db: Session = Depends(get_db)):
    """Get list of bookings for the user"""
    access_token = request.cookies.get("access_token")
    
    if not access_token:
        return {"error": "Not authenticated"}
    
    try:
        payload = verify_token(access_token)
        if not payload:
            return {"error": "Invalid token"}
        
        user_email = payload.get("sub")
        user = get_user_by_email(db, user_email)
        
        if not user:
            return {"error": "User not found"}
        
        # Get bookings for the user
        from app.services.booking_service import get_bookings_for_user
        bookings = get_bookings_for_user(db, user.id)
        
        return {
            "bookings": [
                {
                    "id": booking.id,
                    "guest_name": booking.guest_name,
                    "guest_email": booking.guest_email,
                    "start_time": booking.start_time.isoformat(),
                    "end_time": booking.end_time.isoformat(),
                    "status": booking.status,
                    "guest_message": booking.guest_message
                } for booking in bookings
            ]
        }
    except Exception as e:
        print(f"Bookings list error: {e}")
        return {"error": str(e)}

@app.get("/bookings/api/stats")
async def bookings_stats(request: Request, db: Session = Depends(get_db)):
    """Get booking statistics for the user"""
    access_token = request.cookies.get("access_token")
    
    if not access_token:
        return {"error": "Not authenticated"}
    
    try:
        payload = verify_token(access_token)
        if not payload:
            return {"error": "Invalid token"}
        
        user_email = payload.get("sub")
        user = get_user_by_email(db, user_email)
        
        if not user:
            return {"error": "User not found"}
        
        # Get bookings for the user
        from app.services.booking_service import get_bookings_for_user
        all_bookings = get_bookings_for_user(db, user.id)
        
        # Calculate stats
        total_bookings = len(all_bookings)
        confirmed_bookings = len([b for b in all_bookings if b.status == "confirmed"])
        cancelled_bookings = len([b for b in all_bookings if b.status == "cancelled"])
        
        return {
            "total_bookings": total_bookings,
            "confirmed_bookings": confirmed_bookings,
            "cancelled_bookings": cancelled_bookings
        }
    except Exception as e:
        print(f"Bookings stats error: {e}")
        return {"error": str(e)}

@app.exception_handler(500)
async def internal_error_handler(request: Request, exc):
    """Handle 500 errors"""
    return templates.TemplateResponse(
        "500.html", 
        {"request": request}, 
        status_code=500
    )

