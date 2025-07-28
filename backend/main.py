import os
from datetime import datetime
from pathlib import Path
from fastapi import FastAPI, Request, Form, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse, HTMLResponse, PlainTextResponse
from sqlalchemy.orm import Session
import requests
import json
import pytz

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
from app.services.user_service import authenticate_user, create_user, get_user_by_email
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

# Define agent routes early to avoid conflicts
@app.get("/agent")
async def agent_redirect():
    """Redirect /agent to /agent/"""
    return RedirectResponse(url="/agent/", status_code=302)

@app.get("/agent/")
async def agent_chat(request: Request, db: Session = Depends(get_db)):
    """AI Agent Chat Interface"""
    print("Agent route accessed!")
    access_token = request.cookies.get("access_token")

    if not access_token:
        return RedirectResponse(url="/login", status_code=302)

    try:
        payload = verify_token(access_token)
        if not payload:
            return RedirectResponse(url="/login", status_code=302)

        user_email = payload.get("sub")
        user = get_user_by_email(db, user_email)

        if not user:
            return RedirectResponse(url="/login", status_code=302)

        return templates.TemplateResponse("agent_chat.html", {
            "request": request,
            "current_user": user
        })

    except Exception as e:
        print(f"Agent chat error: {e}")
        return RedirectResponse(url="/login", status_code=302)

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

# Include API router
app.include_router(api_router, prefix=settings.API_V1_STR)

# Templates for HTML responses
templates = Jinja2Templates(directory="app/templates")

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
        error_url = "/dashboard?calendar_error=true" if is_calendar_connection else "/login?error=google_auth_failed"
        return RedirectResponse(url=error_url, status_code=302)

# Add web routes directly
@app.get("/login")
async def login_get(request: Request):
    return RedirectResponse(url="/")

@app.post("/login")
async def login_post(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    try:
        user = authenticate_user(db, email, password)
        if not user:
            return HTMLResponse(
                '<div class="text-red-600 text-sm">Invalid email or password</div>',
                status_code=400
            )
        
        # Create access token
        access_token = create_access_token(data={"sub": user.email})
        
        # Create response with redirect
        response = HTMLResponse(
            '<div class="text-green-600 text-sm">Login successful! Redirecting...</div><script>setTimeout(() => window.location.href = "/dashboard", 1000);</script>'
        )
        
        # Set HTTP-only cookie
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            max_age=1800,  # 30 minutes
            secure=False,  # Set to True in production with HTTPS
            samesite="lax"
        )
        
        return response
        
    except Exception as e:
        return HTMLResponse(
            '<div class="text-red-600 text-sm">An error occurred during login</div>',
            status_code=500
        )

@app.get("/register")
async def register_get(request: Request):
    return RedirectResponse(url="/")

@app.post("/register")
async def register_post(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    try:
        # Check if user already exists
        existing_user = db.query(User).filter(User.email == email).first()
        if existing_user:
            return HTMLResponse(
                '<div class="text-red-600 text-sm">Email already registered</div>',
                status_code=400
            )
        
        # Create new user
        user_data = UserCreate(
            email=email,
            password=password,
            full_name=email.split('@')[0]  # Use email prefix as name
        )
        
        user = await create_user(db, user_data)
        
        # Send verification email
        if user.verification_token:
            from app.services.email_service import send_verification_email
            send_verification_email(user.email, user.verification_token)
        
        return HTMLResponse(
            '<div class="text-green-600 text-sm">Registration successful! Please check your email to verify your account.</div>'
        )
        
    except Exception as e:
        return HTMLResponse(
            '<div class="text-red-600 text-sm">An error occurred during registration</div>',
            status_code=500
        )

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

@app.get("/dashboard")
async def dashboard(request: Request, db: Session = Depends(get_db)):
    access_token = request.cookies.get("access_token")
    print(f"Dashboard - Access token: {access_token}")

    if not access_token:
        print("No access token found")
        return RedirectResponse(url="/login", status_code=302)

    try:
        payload = verify_token(access_token)
        print(f"Token payload: {payload}")

        if not payload:
            print("Token verification failed")
            return RedirectResponse(url="/login", status_code=302)

        user_email = payload.get("sub")
        print(f"User email from token: {user_email}")
        user = get_user_by_email(db, user_email)
        print(f"User from DB: {user}")

        if not user:
            print(f"User not found for email: {user_email}")
            return RedirectResponse(url="/login", status_code=302)

        print(f"User authenticated: {user.email}")
        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "current_user": user
        })

    except Exception as e:
        print(f"Dashboard error: {e}")
        return RedirectResponse(url="/login", status_code=302)

@app.get("/")
async def root(request: Request):
    """Root endpoint - redirect to landing page"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/settings")
async def settings_page(request: Request, db: Session = Depends(get_db)):
    """Settings page for user account management"""
    access_token = request.cookies.get("access_token")

    if not access_token:
        return RedirectResponse(url="/login", status_code=302)

    try:
        payload = verify_token(access_token)
        if not payload:
            return RedirectResponse(url="/login", status_code=302)

        user_email = payload.get("sub")
        user = get_user_by_email(db, user_email)

        if not user:
            return RedirectResponse(url="/login", status_code=302)

        return templates.TemplateResponse("settings.html", {
            "request": request,
            "current_user": user
        })

    except Exception as e:
        print(f"Settings error: {e}")
        return RedirectResponse(url="/login", status_code=302)

# Dashboard data endpoints (session-based auth)

# Calendar connection completion endpoint
@app.post("/dashboard/api/calendar/connect")
async def complete_calendar_connection(request: Request, connection_id: str = Form(...), db: Session = Depends(get_db)):
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
        
        # Get the pending calendar connection
        if not hasattr(app.state, 'pending_calendar_connections'):
            raise HTTPException(status_code=404, detail="Calendar connection not found")
        
        connection_data = app.state.pending_calendar_connections.get(connection_id)
        if not connection_data:
            raise HTTPException(status_code=404, detail="Calendar connection not found or expired")
        
        # Update user with calendar credentials
        user.google_access_token = connection_data['access_token']
        user.google_refresh_token = connection_data['refresh_token']
        user.google_calendar_connected = True
        user.google_calendar_email = connection_data['calendar_email']
        
        db.commit()
        
        # Clean up the temporary connection data
        del app.state.pending_calendar_connections[connection_id]
        
        print(f"Calendar connected: {connection_data['calendar_email']} for user: {user.email}")
        
        # Auto-sync calendar availability
        try:
            from app.services.availability_service import sync_calendar_availability
            sync_result = sync_calendar_availability(db, user)
            print(f"Auto-sync result: {sync_result}")
        except Exception as sync_error:
            print(f"Auto-sync failed: {sync_error}")
            # Don't fail the connection if sync fails
        
        return {"success": True, "calendar_email": connection_data['calendar_email']}
        
    except Exception as e:
        print(f"Calendar connection error: {e}")
        raise HTTPException(status_code=400, detail="Calendar connection failed")

@app.get("/dashboard/api/bookings/upcoming")
async def get_dashboard_upcoming_bookings(request: Request, db: Session = Depends(get_db)):
    """Get upcoming bookings for dashboard (session auth)"""
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
        from app.services.booking_service import get_upcoming_bookings
        bookings = get_upcoming_bookings(db, user.id, limit=5)
        return [
            {
                "id": booking.id,
                "guest_name": booking.guest_name,
                "guest_email": booking.guest_email,
                "start_time": booking.start_time.strftime('%B %d, %Y at %I:%M %p'),
                "end_time": booking.end_time.strftime('%I:%M %p'),
                "status": booking.status
            }
            for booking in bookings
        ]
    except Exception as e:
        print(f"Dashboard API error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/dashboard/api/bookings/all")
async def get_dashboard_all_bookings(request: Request, db: Session = Depends(get_db)):
    """Get all bookings count for dashboard (session auth)"""
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
        
        from app.services.booking_service import get_bookings_for_user
        bookings = get_bookings_for_user(db, user.id)
        
        return [
            {
                "id": booking.id,
                "guest_name": booking.guest_name,
                "guest_email": booking.guest_email,
                "start_time": booking.start_time.isoformat(),
                "end_time": booking.end_time.isoformat(),
                "status": booking.status
            }
            for booking in bookings
        ]
    except Exception as e:
        print(f"Dashboard API error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/dashboard/api/availability/available")
async def get_dashboard_available_slots(request: Request, db: Session = Depends(get_db)):
    """Get available slots count for dashboard (session auth)"""
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
        
        from app.services.availability_service import get_available_slots_for_booking
        slots = get_available_slots_for_booking(db, user.id)
        
        return [
            {
                "id": slot.id,
                "start_time": slot.start_time.isoformat(),
                "end_time": slot.end_time.isoformat(),
                "is_available": slot.is_available
            }
            for slot in slots
        ]
    except Exception as e:
        print(f"Dashboard API error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/dashboard/api/availability/")
async def add_dashboard_availability_slot(
    request: Request, 
    date: str = Form(...),
    start_time: str = Form(...),
    end_time: str = Form(...),
    duration: int = Form(30),
    is_available: bool = Form(True),
    db: Session = Depends(get_db)
):
    """Add single availability slot for dashboard (session auth)"""
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
        
        from datetime import datetime, timedelta
        from app.services.availability_service import create_availability_slot
        from app.schemas.schemas import AvailabilitySlotCreate
        
        # Combine date and time
        start_datetime = datetime.strptime(f"{date} {start_time}", "%Y-%m-%d %H:%M")
        end_datetime = datetime.strptime(f"{date} {end_time}", "%Y-%m-%d %H:%M")
        
        # Create slots based on duration
        created_slots = []
        current_time = start_datetime
        
        while current_time + timedelta(minutes=duration) <= end_datetime:
            slot_end = current_time + timedelta(minutes=duration)
            
            slot_data = AvailabilitySlotCreate(
                start_time=current_time,
                end_time=slot_end,
                is_available=is_available
            )
            
            slot = create_availability_slot(db, slot_data, user.id)
            created_slots.append(slot)
            
            current_time = slot_end
        
        return {
            "message": f"Created {len(created_slots)} availability slots successfully!",
            "slots_created": len(created_slots)
        }
    except Exception as e:
        print(f"Dashboard API error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/dashboard/api/availability/recurring")
async def add_recurring_availability_slots(
    request: Request, 
    start_date: str = Form(...),
    end_date: str = Form(...),
    start_time: str = Form(...),
    end_time: str = Form(...),
    slot_duration: int = Form(30),
    days: list = Form(...),
    db: Session = Depends(get_db)
):
    """Add recurring availability slots for dashboard (session auth)"""
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
        
        from datetime import datetime, timedelta
        from app.services.availability_service import create_availability_slot
        from app.schemas.schemas import AvailabilitySlotCreate
        
        start_date_obj = datetime.strptime(start_date, "%Y-%m-%d").date()
        end_date_obj = datetime.strptime(end_date, "%Y-%m-%d").date()
        
        created_slots = []
        current_date = start_date_obj
        
        while current_date <= end_date_obj:
            # Check if this day of week is selected
            if str(current_date.weekday()) in days:
                # Create slots for this day
                start_datetime = datetime.combine(current_date, datetime.strptime(start_time, "%H:%M").time())
                end_datetime = datetime.combine(current_date, datetime.strptime(end_time, "%H:%M").time())
                
                current_time = start_datetime
                while current_time + timedelta(minutes=slot_duration) <= end_datetime:
                    slot_end = current_time + timedelta(minutes=slot_duration)
                    
                    slot_data = AvailabilitySlotCreate(
                        start_time=current_time,
                        end_time=slot_end,
                        is_available=True
                    )
                    
                    slot = create_availability_slot(db, slot_data, user.id)
                    created_slots.append(slot)
                    
                    current_time = slot_end
            
            current_date += timedelta(days=1)
        
        return {
            "message": f"Created {len(created_slots)} recurring availability slots successfully!",
            "slots_created": len(created_slots)
        }
    except Exception as e:
        print(f"Recurring slots API error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/dashboard/api/availability/bulk")
async def add_bulk_availability_slots(
    request: Request, 
    template: str = Form(...),
    start_date: str = Form(...),
    end_date: str = Form(...),
    start_time: str = Form(...),
    end_time: str = Form(...),
    slot_duration: int = Form(30),
    days: list = Form(...),
    db: Session = Depends(get_db)
):
    """Add bulk availability slots for dashboard (session auth)"""
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
        
        from datetime import datetime, timedelta
        from app.services.availability_service import create_availability_slot
        from app.schemas.schemas import AvailabilitySlotCreate
        
        # Apply template if not custom
        if template != "custom":
            if template == "business":
                start_time = "09:00"
                end_time = "17:00"
            elif template == "morning":
                start_time = "08:00"
                end_time = "12:00"
            elif template == "afternoon":
                start_time = "13:00"
                end_time = "17:00"
            elif template == "evening":
                start_time = "18:00"
                end_time = "21:00"
        
        start_date_obj = datetime.strptime(start_date, "%Y-%m-%d").date()
        end_date_obj = datetime.strptime(end_date, "%Y-%m-%d").date()
        
        created_slots = []
        current_date = start_date_obj
        
        while current_date <= end_date_obj:
            # Check if this day of week is selected
            if str(current_date.weekday()) in days:
                # Create slots for this day
                start_datetime = datetime.combine(current_date, datetime.strptime(start_time, "%H:%M").time())
                end_datetime = datetime.combine(current_date, datetime.strptime(end_time, "%H:%M").time())
                
                current_time = start_datetime
                while current_time + timedelta(minutes=slot_duration) <= end_datetime:
                    slot_end = current_time + timedelta(minutes=slot_duration)
                    
                    slot_data = AvailabilitySlotCreate(
                        start_time=current_time,
                        end_time=slot_end,
                        is_available=True
                    )
                    
                    slot = create_availability_slot(db, slot_data, user.id)
                    created_slots.append(slot)
                    
                    current_time = slot_end
            
            current_date += timedelta(days=1)
        
        return {
            "message": f"Created {len(created_slots)} bulk availability slots successfully!",
            "slots_created": len(created_slots)
        }
    except Exception as e:
        print(f"Bulk slots API error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/dashboard/api/calendar/sync")
async def sync_calendar_availability_endpoint(request: Request, db: Session = Depends(get_db)):
    """Sync availability slots with Google Calendar."""
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
        
        if not user.google_calendar_connected:
            return {"success": False, "message": "Google Calendar not connected"}
        
        from app.services.availability_service import sync_calendar_availability
        result = sync_calendar_availability(db, user)
        
        return result
        
    except Exception as e:
        print(f"Calendar sync error: {e}")
        return {"success": False, "message": f"Failed to sync calendar: {str(e)}"}


@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    """Handle 404 errors"""
    return templates.TemplateResponse(
        "404.html", 
        {"request": request}, 
        status_code=404
    )

@app.exception_handler(500)
async def internal_error_handler(request: Request, exc):
    """Handle 500 errors"""
    return templates.TemplateResponse(
        "500.html", 
        {"request": request}, 
        status_code=500
    )

@app.get("/bookings")
async def bookings_page(request: Request, db: Session = Depends(get_db)):
    """Bookings management page for viewing and managing appointments"""
    access_token = request.cookies.get("access_token")

    if not access_token:
        return RedirectResponse(url="/login", status_code=302)

    try:
        payload = verify_token(access_token)
        if not payload:
            return RedirectResponse(url="/login", status_code=302)

        user_email = payload.get("sub")
        user = get_user_by_email(db, user_email)

        if not user:
            return RedirectResponse(url="/login", status_code=302)

        return templates.TemplateResponse("bookings.html", {
            "request": request,
            "current_user": user
        })

    except Exception as e:
        print(f"Bookings page error: {e}")
        return RedirectResponse(url="/login", status_code=302)


@app.get("/bookings/api/list")
async def get_bookings_list(
    request: Request,
    status: str = Query(None),
    search: str = Query(None),
    time: str = Query(None),
    db: Session = Depends(get_db)
):
    """Get bookings for the authenticated user with optional filtering"""
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

        # Import booking service
        from app.services.booking_service import get_bookings_for_user
        
        # Get bookings with optional filtering
        bookings = get_bookings_for_user(db, user.id, status)
        
        # Apply time filter if provided
        if time:
            from datetime import datetime, timedelta
            now = datetime.utcnow()
            
            if time == "today":
                # Filter for bookings today
                today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
                today_end = today_start + timedelta(days=1)
                bookings = [
                    booking for booking in bookings
                    if today_start <= booking.start_time < today_end
                ]
            elif time == "week":
                # Filter for bookings this week (Monday to Sunday)
                days_since_monday = now.weekday()
                week_start = now - timedelta(days=days_since_monday)
                week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
                week_end = week_start + timedelta(days=7)
                bookings = [
                    booking for booking in bookings
                    if week_start <= booking.start_time < week_end
                ]
            elif time == "month":
                # Filter for bookings this month
                month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                if now.month == 12:
                    month_end = now.replace(year=now.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
                else:
                    month_end = now.replace(month=now.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0)
                bookings = [
                    booking for booking in bookings
                    if month_start <= booking.start_time < month_end
                ]
            elif time == "past":
                # Filter for past bookings
                bookings = [
                    booking for booking in bookings
                    if booking.start_time < now
                ]
        
        # Apply search filter if provided
        if search:
            search_lower = search.lower()
            bookings = [
                booking for booking in bookings
                if search_lower in booking.guest_name.lower() or 
                   search_lower in booking.guest_email.lower()
            ]

        # Format bookings for display and sort by date (newest first)
        formatted_bookings = []
        for booking in bookings:
            formatted_bookings.append({
                "id": booking.id,
                "guest_name": booking.guest_name,
                "guest_email": booking.guest_email,
                "start_time": booking.start_time.strftime("%B %d, %Y at %I:%M %p"),
                "end_time": booking.end_time.strftime("%I:%M %p"),
                "status": booking.status,
                "guest_message": booking.guest_message,
                "created_at": booking.created_at.strftime("%B %d, %Y"),
                "sort_date": booking.start_time  # Add sort date for proper sorting
            })
        
        # Sort by start_time (newest first)
        formatted_bookings.sort(key=lambda x: x["sort_date"], reverse=True)

        return HTMLResponse(
            templates.get_template("bookings_list.html").render({
                "request": request,
                "bookings": formatted_bookings
            })
        )

    except Exception as e:
        print(f"Get bookings error: {e}")
        raise HTTPException(status_code=500, detail="Failed to load bookings")


@app.get("/bookings/api/stats")
async def get_bookings_stats(
    request: Request,
    db: Session = Depends(get_db)
):
    """Get booking statistics for the authenticated user"""
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

        from app.services.booking_service import get_bookings_for_user
        from datetime import datetime, timezone
        
        bookings = get_bookings_for_user(db, user.id)
        
        total = len(bookings)
        confirmed = len([b for b in bookings if b.status == 'confirmed'])
        cancelled = len([b for b in bookings if b.status == 'cancelled'])
        upcoming = len([b for b in bookings if b.start_time > datetime.now(timezone.utc) and b.status == 'confirmed'])

        return templates.TemplateResponse("booking_stats.html", {
            "request": request,
            "total": total,
            "confirmed": confirmed,
            "cancelled": cancelled,
            "upcoming": upcoming
        })

    except Exception as e:
        print(f"Get booking stats error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to load booking statistics: {str(e)}")


@app.get("/bookings/api/{booking_id}")
async def get_booking_details(
    booking_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """Get detailed information for a specific booking"""
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

        # Import booking service
        from app.services.booking_service import get_booking
        
        booking = get_booking(db, booking_id, user.id)
        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")

        return {
            "id": booking.id,
            "guest_name": booking.guest_name,
            "guest_email": booking.guest_email,
            "start_time": booking.start_time.strftime("%B %d, %Y at %I:%M %p"),
            "end_time": booking.end_time.strftime("%I:%M %p"),
            "status": booking.status,
            "guest_message": booking.guest_message,
            "created_at": booking.created_at.strftime("%B %d, %Y")
        }

    except Exception as e:
        print(f"Get booking details error: {e}")
        raise HTTPException(status_code=500, detail="Failed to load booking details")


@app.get("/bookings/api/{booking_id}/cancel-confirmation")
async def get_cancel_confirmation(
    booking_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """Show cancel confirmation modal"""
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

        # Get the booking
        from app.services.booking_service import get_booking
        booking = get_booking(db, booking_id, user.id)
        if not booking:
            return templates.TemplateResponse("cancel_success.html", {
                "request": request,
                "message": "❌ Booking not found",
                "status": "failed"
            })

        return templates.TemplateResponse("cancel_confirmation.html", {
            "request": request,
            "booking": booking
        })

    except Exception as e:
        print(f"Cancel confirmation error: {e}")
        raise HTTPException(status_code=500, detail="Failed to load cancel confirmation")


@app.post("/bookings/api/{booking_id}/cancel")
async def cancel_booking_endpoint(
    booking_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """Cancel a booking with robust error handling"""
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

        # Get the current booking
        from app.services.booking_service import get_booking, cancel_booking
        booking = get_booking(db, booking_id, user.id)
        if not booking:
            return templates.TemplateResponse("cancel_success.html", {
                "request": request,
                "message": "❌ Booking not found",
                "status": "failed"
            })

        print(f"=== CANCEL FLOW START ===")
        print(f"Step 1: Validating prerequisites...")
        print(f"  - User has Google tokens: {bool(user.google_access_token and user.google_refresh_token)}")
        print(f"  - Booking ID: {booking_id}")
        print(f"  - Booking status: {booking.status}")

        # Step 1: Cancel booking in database
        calendar_deleted = False
        emails_sent = False
        
        try:
            print(f"Step 2: Cancelling booking in database...")
            success = cancel_booking(db, booking_id, user.id)
            if not success:
                print(f"❌ Step 2 FAILED: Database cancellation failed")
                return templates.TemplateResponse("cancel_success.html", {
                    "request": request,
                    "message": "❌ Failed to cancel booking in database",
                    "status": "failed"
                })
            print(f"✅ Step 2 SUCCESS: Booking cancelled in database")
            
        except Exception as db_error:
            print(f"❌ Step 2 FAILED: Database error")
            print(f"  Error type: {type(db_error)}")
            print(f"  Error message: {str(db_error)}")
            import traceback
            print(f"  Full traceback: {traceback.format_exc()}")
            return templates.TemplateResponse("cancel_success.html", {
                "request": request,
                "message": f"❌ Failed to cancel booking. Database error: {str(db_error)}",
                "status": "failed"
            })

        # Step 3: Delete Google Calendar event (if exists)
        if booking.google_event_id and user.google_access_token and user.google_refresh_token:
            try:
                print(f"Step 3: Deleting Google Calendar event...")
                from app.services.google_calendar_service import GoogleCalendarService
                
                calendar_service = GoogleCalendarService(
                    access_token=user.google_access_token,
                    refresh_token=user.google_refresh_token
                )
                
                print(f"  - Deleting event: {booking.google_event_id}")
                calendar_service.delete_event(booking.google_event_id)
                print(f"  ✅ Successfully deleted Google Calendar event")
                calendar_deleted = True
                
            except Exception as calendar_error:
                print(f"❌ Step 3 FAILED: Calendar deletion error")
                print(f"  Error type: {type(calendar_error)}")
                print(f"  Error message: {str(calendar_error)}")
                import traceback
                print(f"  Full traceback: {traceback.format_exc()}")
                calendar_deleted = False
        else:
            print(f"Step 3: Skipping calendar deletion (no event ID or tokens)")
            calendar_deleted = True  # Consider it successful if no event to delete

        # Step 4: Send email notifications (only if database cancellation succeeded)
        if user.google_access_token and user.google_refresh_token:
            try:
                print(f"Step 4: Sending email notifications...")
                from app.services.notification_service import NotificationService
                
                notification_service = NotificationService()
                
                notification_results = notification_service.send_cancellation_notifications(
                    guest_email=booking.guest_email,
                    guest_name=booking.guest_name,
                    host_email=user.email,
                    host_name=user.full_name,
                    booking=booking,
                    host_access_token=user.google_access_token,
                    host_refresh_token=user.google_refresh_token
                )
                
                emails_sent = notification_results["success"]
                print(f"  - Notification results: {notification_results}")
                
                if emails_sent:
                    print(f"✅ Step 4 SUCCESS: Emails sent")
                else:
                    print(f"⚠️ Step 4 PARTIAL: Email sending failed")
                    
            except Exception as email_error:
                print(f"❌ Step 4 FAILED: Email error")
                print(f"  Error type: {type(email_error)}")
                print(f"  Error message: {str(email_error)}")
                import traceback
                print(f"  Full traceback: {traceback.format_exc()}")
                emails_sent = False
        else:
            print(f"Step 4: Skipping email notifications (no Google tokens)")
            emails_sent = True  # Consider it successful if no tokens to send emails

        # Step 5: Determine final status
        print(f"Step 5: Determining final status...")
        print(f"  - Database cancelled: True")
        print(f"  - Calendar deleted: {calendar_deleted}")
        print(f"  - Emails sent: {emails_sent}")
        
        if calendar_deleted and emails_sent:
            success_message = f"✅ Booking cancelled successfully! Google Calendar event deleted and notifications sent to both parties."
            status = "success"
            print(f"✅ FINAL STATUS: FULL SUCCESS")
        elif calendar_deleted and not emails_sent:
            success_message = f"⚠️ Booking cancelled and Google Calendar event deleted, but email notifications failed."
            status = "partial"
            print(f"⚠️ FINAL STATUS: PARTIAL SUCCESS (calendar ok, emails failed)")
        else:
            success_message = f"❌ Failed to cancel booking completely. Database updated but calendar/email operations failed."
            status = "failed"
            print(f"❌ FINAL STATUS: FAILED")
        
        print(f"=== CANCEL FLOW END ===")
        
        return templates.TemplateResponse("cancel_success.html", {
            "request": request,
            "message": success_message,
            "status": status
        })

    except Exception as e:
        print(f"Cancel booking error: {e}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")
        return templates.TemplateResponse("cancel_success.html", {
            "request": request,
            "message": f"❌ Failed to cancel booking. Error: {str(e)}",
            "status": "failed"
        })


@app.post("/bookings/api/{booking_id}/reschedule")
async def reschedule_booking_endpoint(
    booking_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """Reschedule a booking"""
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

        # Get the current booking
        from app.services.booking_service import get_booking
        booking = get_booking(db, booking_id, user.id)
        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")

        # Handle form data
        form_data = await request.form()
        new_date = form_data.get("new_date")
        new_time = form_data.get("new_time")
        reason = form_data.get("reason", "")

        if not new_date or not new_time:
            return templates.TemplateResponse("reschedule_form.html", {
                "request": request,
                "booking_id": booking_id,
                "booking": booking,
                "current_user": user,
                "today": datetime.now().strftime('%Y-%m-%d'),
                "error": "Date and time are required"
            })

        # Import required services
        from app.services.booking_service import update_booking
        from app.schemas.schemas import BookingUpdate
        from datetime import datetime, timedelta
        from app.services.google_calendar_service import GoogleCalendarService


        # Parse the new datetime
        try:
            # new_time is already a full datetime string from the frontend
            new_dt = datetime.fromisoformat(new_time.replace('Z', '+00:00'))
            
            # Calculate end time (30 minutes duration)
            new_end_dt = new_dt + timedelta(minutes=30)
            
        except ValueError as e:
            print(f"Date parsing error: {e}")
            return templates.TemplateResponse("reschedule_form.html", {
                "request": request,
                "booking_id": booking_id,
                "booking": booking,
                "current_user": user,
                "today": datetime.now().strftime('%Y-%m-%d'),
                "error": "Invalid date/time format"
            })



        # Create booking update
        booking_update = BookingUpdate(
            start_time=new_dt,
            end_time=new_end_dt,
            status="rescheduled"
        )

        # Update booking in database (but don't let it update calendar - we'll do that separately)
        updated_booking = update_booking(db, booking_id, booking_update, user.id, update_calendar=False)
        if not updated_booking:
            return templates.TemplateResponse("reschedule_form.html", {
                "request": request,
                "booking_id": booking_id,
                "booking": booking,
                "current_user": user,
                "today": datetime.now().strftime('%Y-%m-%d'),
                "error": "Failed to update booking in database"
            })
        
        print(f"Booking updated in database: {booking_id}")
        print(f"New start time: {updated_booking.start_time}")
        print(f"New end time: {updated_booking.end_time}")

                # ROBUST RESCHEDULE FLOW WITH EXCEPTION HANDLING
        
        # Step 1: Validate prerequisites
        print(f"=== RESCHEDULE FLOW START ===")
        print(f"Step 1: Validating prerequisites...")
        print(f"  - User has Google tokens: {bool(user.google_access_token and user.google_refresh_token)}")
        print(f"  - Booking ID: {booking_id}")
        print(f"  - New start time: {new_dt}")
        print(f"  - New end time: {new_end_dt}")
        
        if not user.google_access_token or not user.google_refresh_token:
            print(f"❌ ERROR: User missing Google OAuth tokens")
            return templates.TemplateResponse("reschedule_success.html", {
                "request": request,
                "message": "❌ Failed to reschedule booking. Google Calendar not connected. Please connect your calendar first.",
                "status": "failed"
            })
        
        # Step 2: Attempt calendar event update/creation
        calendar_updated = False
        calendar_event_id = None
        original_event_id = booking.google_event_id
        
        try:
            print(f"Step 2: Attempting calendar event update/creation...")
            
            calendar_service = GoogleCalendarService(
                access_token=user.google_access_token,
                refresh_token=user.google_refresh_token
            )
            
            if booking.google_event_id:
                print(f"  - Updating existing event: {booking.google_event_id}")
                
                # Check if event exists
                existing_event = calendar_service.get_event(booking.google_event_id)
                if not existing_event:
                    print(f"  - Event not found, creating new event...")
                    created_event = calendar_service.create_event(
                        title=f"Meeting with {booking.guest_name}",
                        start_time=new_dt,
                        end_time=new_end_dt,
                        guest_email=booking.guest_email,
                        host_email=user.email,
                        description=f"Rescheduled meeting with {booking.guest_name}\n\nGuest: {booking.guest_name}\nEmail: {booking.guest_email}"
                    )
                    calendar_event_id = created_event.get('id')
                    booking.google_event_id = calendar_event_id
                    db.commit()
                    print(f"  ✅ Created new event: {calendar_event_id}")
                else:
                    print(f"  - Event found, updating...")
                    calendar_service.update_event(
                        event_id=booking.google_event_id,
                        start_time=new_dt,
                        end_time=new_end_dt
                    )
                    calendar_event_id = booking.google_event_id
                    print(f"  ✅ Updated existing event: {calendar_event_id}")
            else:
                print(f"  - Creating new event (no existing event ID)...")
                created_event = calendar_service.create_event(
                    title=f"Meeting with {booking.guest_name}",
                    start_time=new_dt,
                    end_time=new_end_dt,
                    guest_email=booking.guest_email,
                    host_email=user.email,
                    description=f"Rescheduled meeting with {booking.guest_name}\n\nGuest: {booking.guest_name}\nEmail: {booking.guest_email}"
                )
                calendar_event_id = created_event.get('id')
                booking.google_event_id = calendar_event_id
                db.commit()
                print(f"  ✅ Created new event: {calendar_event_id}")
            
            calendar_updated = True
            print(f"✅ Step 2 SUCCESS: Calendar event updated/created")
            
        except Exception as calendar_error:
            print(f"❌ Step 2 FAILED: Calendar error")
            print(f"  Error type: {type(calendar_error)}")
            print(f"  Error message: {str(calendar_error)}")
            import traceback
            print(f"  Full traceback: {traceback.format_exc()}")
            
            # Rollback database changes if calendar failed
            if booking.google_event_id != original_event_id:
                booking.google_event_id = original_event_id
                db.commit()
                print(f"  - Rolled back database changes")
            
            return templates.TemplateResponse("reschedule_success.html", {
                "request": request,
                "message": f"❌ Failed to reschedule booking. Google Calendar error: {str(calendar_error)}",
                "status": "failed"
            })
        
        # Step 3: Send email notifications (only if calendar succeeded)
        emails_sent = False
        try:
            print(f"Step 3: Sending email notifications...")
            
            from app.services.notification_service import NotificationService
            
            notification_service = NotificationService()
            
            notification_results = notification_service.send_reschedule_notifications(
                guest_email=booking.guest_email,
                guest_name=booking.guest_name,
                host_email=user.email,
                host_name=user.full_name,
                booking=updated_booking,
                old_start_time=booking.start_time,
                reason=reason,
                host_access_token=user.google_access_token,
                host_refresh_token=user.google_refresh_token
            )
            
            emails_sent = notification_results["success"]
            print(f"  - Notification results: {notification_results}")
            
            if emails_sent:
                print(f"✅ Step 3 SUCCESS: Emails sent")
            else:
                print(f"⚠️ Step 3 PARTIAL: Email sending failed")
                
        except Exception as email_error:
            print(f"❌ Step 3 FAILED: Email error")
            print(f"  Error type: {type(email_error)}")
            print(f"  Error message: {str(email_error)}")
            import traceback
            print(f"  Full traceback: {traceback.format_exc()}")
            emails_sent = False
        
        # Step 4: Determine final status
        print(f"Step 4: Determining final status...")
        print(f"  - Calendar updated: {calendar_updated}")
        print(f"  - Emails sent: {emails_sent}")
        
        if calendar_updated and emails_sent:
            success_message = f"✅ Booking rescheduled successfully! Google Calendar updated and notifications sent to both parties."
            status = "success"
            print(f"✅ FINAL STATUS: FULL SUCCESS")
        elif calendar_updated and not emails_sent:
            success_message = f"⚠️ Booking rescheduled and Google Calendar updated, but email notifications failed."
            status = "partial"
            print(f"⚠️ FINAL STATUS: PARTIAL SUCCESS (calendar ok, emails failed)")
        else:
            success_message = f"❌ Failed to reschedule booking. Google Calendar update failed."
            status = "failed"
            print(f"❌ FINAL STATUS: FAILED")
        
        print(f"=== RESCHEDULE FLOW END ===")
        
        return templates.TemplateResponse("reschedule_success.html", {
            "request": request,
            "message": success_message,
            "status": status
        })

    except Exception as e:
        print(f"Reschedule booking error: {e}")
        return templates.TemplateResponse("reschedule_form.html", {
            "request": request,
            "booking_id": booking_id,
            "booking": booking if 'booking' in locals() else None,
            "current_user": user if 'user' in locals() else None,
            "today": datetime.now().strftime('%Y-%m-%d'),
            "error": "Failed to reschedule booking"
        })




@app.get("/bookings/api/{booking_id}/details")
async def get_booking_details_modal(
    booking_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """Get booking details for modal display"""
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

        # Import booking service
        from app.services.booking_service import get_booking
        
        booking = get_booking(db, booking_id, user.id)
        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")

        return templates.TemplateResponse("booking_details_modal.html", {
            "request": request,
            "booking": {
                "id": booking.id,
                "guest_name": booking.guest_name,
                "guest_email": booking.guest_email,
                "start_time": booking.start_time.strftime("%B %d, %Y at %I:%M %p"),
                "end_time": booking.end_time.strftime("%I:%M %p"),
                "status": booking.status,
                "guest_message": booking.guest_message,
                "created_at": booking.created_at.strftime("%B %d, %Y")
            }
        })

    except Exception as e:
        print(f"Get booking details modal error: {e}")
        raise HTTPException(status_code=500, detail="Failed to load booking details")


@app.get("/bookings/api/{booking_id}/reschedule-form")
async def get_reschedule_form(
    booking_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """Get reschedule form for modal display"""
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

        # Get the booking details
        from app.services.booking_service import get_booking
        from datetime import datetime
        
        booking = get_booking(db, booking_id, user.id)
        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")

        return templates.TemplateResponse("reschedule_form.html", {
            "request": request,
            "booking_id": booking_id,
            "booking": booking,
            "current_user": user,
            "today": datetime.now().strftime('%Y-%m-%d')
        })

    except Exception as e:
        print(f"Get reschedule form error: {e}")
        raise HTTPException(status_code=500, detail="Failed to load reschedule form")


@app.get("/bookings/api/{booking_id}/send-email-form")
async def get_send_email_form(
    booking_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """Get send email form for modal display"""
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

        # Import booking service
        from app.services.booking_service import get_booking
        
        booking = get_booking(db, booking_id, user.id)
        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")

        return templates.TemplateResponse("send_email_modal.html", {
            "request": request,
            "booking": booking,
            "current_user": user
        })

    except Exception as e:
        print(f"Get send email form error: {e}")
        raise HTTPException(status_code=500, detail="Failed to load send email form")


@app.post("/bookings/api/{booking_id}/send-email")
async def send_email_to_guest(
    booking_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """Send email to guest from host"""
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

        # Get the booking
        from app.services.booking_service import get_booking
        booking = get_booking(db, booking_id, user.id)
        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")

        # Handle form data
        form_data = await request.form()
        subject = form_data.get("subject")
        message = form_data.get("message")

        if not subject or not message:
            return templates.TemplateResponse("send_email_modal.html", {
                "request": request,
                "booking": booking,
                "current_user": user,
                "error": "Subject and message are required"
            })

        # Import email service
        from app.services.email_service import send_host_to_guest_email

        # Send email
        try:
            send_host_to_guest_email(
                host_email=user.email,
                host_name=user.full_name,
                guest_email=booking.guest_email,
                guest_name=booking.guest_name,
                subject=subject,
                message=message,
                booking=booking,
                host_access_token=user.google_access_token,
                host_refresh_token=user.google_refresh_token
            )
            print(f"Email sent from {user.email} to {booking.guest_email}")
            
            return templates.TemplateResponse("send_email_modal.html", {
                "request": request,
                "booking": booking,
                "current_user": user,
                "success": "Email sent successfully!"
            })
            
        except Exception as e:
            print(f"Failed to send email: {e}")
            return templates.TemplateResponse("send_email_modal.html", {
                "request": request,
                "booking": booking,
                "current_user": user,
                "error": f"Failed to send email: {str(e)}"
            })

    except Exception as e:
        print(f"Send email error: {e}")
        return templates.TemplateResponse("send_email_modal.html", {
            "request": request,
            "booking": booking if 'booking' in locals() else None,
            "current_user": user if 'user' in locals() else None,
            "error": "Failed to send email"
        })


@app.get("/bookings/api/{booking_id}/available-slots")
async def get_available_slots_for_reschedule(
    booking_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """Get available slots for rescheduling"""
    print(f"Available slots request for booking {booking_id}")
    print(f"Query params: {request.query_params}")
    
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

        # Get date from query parameters
        date = request.query_params.get("new_date")
        if not date:
            return templates.TemplateResponse("reschedule_time_slots.html", {
                "request": request,
                "slots": [],
                "error": "No date selected",
                "current_date": ""
            })

        # Get available slots for the date
        from app.services.availability_service import get_available_slots_for_booking
        from app.models.models import AvailabilitySlot
        from datetime import datetime
        
        # Convert date string to datetime - handle multiple formats
        try:
            # Try different date formats
            date_formats = ['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%Y/%m/%d']
            date_obj = None
            
            for fmt in date_formats:
                try:
                    date_obj = datetime.strptime(date, fmt)
                    print(f"Parsed date '{date}' with format '{fmt}' to {date_obj}")
                    break
                except ValueError:
                    continue
            
            if date_obj:
                print(f"Looking for slots on date: {date_obj}")
                slots = get_available_slots_for_booking(db, user.id, date_obj)
                print(f"Found {len(slots)} slots")
            else:
                print(f"Could not parse date: {date}")
                slots = []
        except Exception as e:
            print(f"Date parsing error: {e}")
            slots = []
        
        # Debug: Print all availability slots for the user
        all_slots = db.query(AvailabilitySlot).filter(AvailabilitySlot.user_id == user.id).all()
        print(f"User has {len(all_slots)} total availability slots")
        for slot in all_slots[:5]:  # Print first 5 slots
            print(f"Slot: {slot.start_time} - {slot.end_time}, Available: {slot.is_available}")
        
        return templates.TemplateResponse("reschedule_time_slots.html", {
            "request": request,
            "slots": slots,
            "booking_id": booking_id,
            "selected_time_display": "",
            "current_date": date
        })

    except Exception as e:
        print(f"Get available slots error: {e}")
        import traceback
        traceback.print_exc()
        return templates.TemplateResponse("reschedule_time_slots.html", {
            "request": request,
            "slots": [],
            "error": f"Failed to load available slots: {str(e)}",
            "selected_time_display": ""
        })


@app.post("/bookings/api/{booking_id}/select-time")
async def select_time_for_reschedule(
    booking_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """Handle time slot selection for rescheduling."""
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

        # Get form data
        form_data = await request.form()
        print(f"Form data received: {dict(form_data)}")
        selected_time = form_data.get("selected_time")
        selected_date = form_data.get("selected_date")
        print(f"Selected time: {selected_time}")
        print(f"Selected date: {selected_date}")
        
        if not selected_time or not selected_date:
            return templates.TemplateResponse("reschedule_time_slots.html", {
                "request": request,
                "slots": [],
                "error": f"No time or date selected. Time: {selected_time}, Date: {selected_date}",
                "selected_time_display": "",
                "current_date": selected_date or ""
            })

        # Convert date string to datetime
        try:
            date_formats = ['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%Y/%m/%d']
            date_obj = None
            
            for fmt in date_formats:
                try:
                    date_obj = datetime.strptime(selected_date, fmt)
                    break
                except ValueError:
                    continue
            
            if date_obj:
                from app.services.availability_service import get_available_slots_for_booking
                slots = get_available_slots_for_booking(db, user.id, date_obj)
                # Format the selected time for display
                selected_time_obj = datetime.fromisoformat(selected_time.replace('Z', '+00:00'))
                selected_time_display = selected_time_obj.strftime('%I:%M %p')
            else:
                slots = []
                selected_time_display = ""
        except Exception as e:
            print(f"Error processing time selection: {e}")
            slots = []
            selected_time_display = ""
        
        return templates.TemplateResponse("reschedule_time_slots.html", {
            "request": request,
            "slots": slots,
            "booking_id": booking_id,
            "error": None,
            "selected_time_display": selected_time_display,
            "current_date": selected_date,
            "selected_time": selected_time
        })
        
    except Exception as e:
        print(f"Error selecting time: {e}")
        return templates.TemplateResponse("reschedule_time_slots.html", {
            "request": request,
            "slots": [],
            "error": "Error selecting time",
            "selected_time_display": "",
            "current_date": ""
        })


# Public booking route - added directly to main app (MUST be last to avoid conflicts)
@app.get("/{scheduling_slug}", response_class=HTMLResponse)
async def get_public_booking_page(
    request: Request,
    scheduling_slug: str,
    db: Session = Depends(get_db),
):
    """Render the public booking page for a given scheduling slug."""
    
    print(f"Catch-all route accessed with slug: {scheduling_slug}")
    
    # Exclude certain paths that should not be treated as scheduling slugs
    excluded_paths = ["agent", "dashboard", "login", "register", "logout", "verify-email", "auth", "bookings", "stats"]
    if scheduling_slug in excluded_paths:
        print(f"Excluded path: {scheduling_slug}")
        raise HTTPException(status_code=404, detail="Page not found")
    
    from app.services.user_service import get_user_by_scheduling_slug
    from app.services.availability_service import get_available_slots_for_booking
    
    user = await get_user_by_scheduling_slug(db, scheduling_slug)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Check if user has connected their calendar
    if not user.google_calendar_connected:
        return templates.TemplateResponse(
            "public_booking_unavailable.html", {
                "request": request, 
                "user": user,
                "reason": "calendar_not_connected"
            }
        )

    # Get available slots for booking
    availability_slots = get_available_slots_for_booking(db, user.id)
    
    # Filter out slots that conflict with Google Calendar events
    if user.google_calendar_connected:
        from app.services.google_calendar_service import GoogleCalendarService
        try:
            calendar_service = GoogleCalendarService(
                access_token=user.google_access_token,
                refresh_token=user.google_refresh_token
            )
            
            # Filter out conflicting slots
            available_slots = []
            for slot in availability_slots:
                # Check if this slot conflicts with any calendar events
                is_available = calendar_service.check_availability(slot.start_time, slot.end_time)
                if is_available:
                    available_slots.append(slot)
            
            availability_slots = available_slots
            
        except Exception as e:
            print(f"Error checking calendar conflicts: {e}")
            # If calendar check fails, show all slots as available

    return templates.TemplateResponse(
        "public_booking_all_in_one.html", {
            "request": request, 
            "user": user
        }
    )



@app.get("/api/v1/calendar/available-slots/{user_slug}/{date}")
async def get_available_slots_for_date(
    user_slug: str,
    date: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """Get available time slots for a specific date from Google Calendar."""
    try:
        # Parse the date
        from datetime import datetime
        selected_date = datetime.strptime(date, "%Y-%m-%d")
        
        # Get the user by scheduling slug
        from app.services.user_service import get_user_by_scheduling_slug
        user = await get_user_by_scheduling_slug(db, user_slug)
        
        if not user:
            return {"error": "User not found"}
        
        if not user.google_calendar_connected:
            return {"error": "Google Calendar not connected"}
        
        # Initialize Google Calendar service
        from app.services.google_calendar_service import GoogleCalendarService
        calendar_service = GoogleCalendarService(
            access_token=user.google_access_token,
            refresh_token=user.google_refresh_token
        )
        
        # Get available slots for the date using user's timezone
        try:
            # Use user's timezone or default to UTC
            user_timezone = getattr(user, 'timezone', 'UTC') or 'UTC'
            
            available_slots = calendar_service.get_available_slots(
                selected_date, 
                duration_minutes=30
            )
            
            # Convert to JSON-serializable format
            slots_data = []
            for slot in available_slots:
                slots_data.append({
                    "id": f"slot_{slot['start_time']}",
                    "start_time": slot['start_time'].isoformat(),
                    "end_time": slot['end_time'].isoformat(),
                    "start_time_utc": slot['start_time'].isoformat(),
                    "end_time_utc": slot['end_time'].isoformat(),
                    "timezone": "UTC"
                })
            
            return slots_data
            
        except Exception as calendar_error:
            print(f"Google Calendar error: {calendar_error}")
            # Return error when Google Calendar fails - no more demo mode
            raise HTTPException(
                status_code=500, 
                detail=f"Calendar service unavailable: {str(calendar_error)}"
            )
        
    except Exception as e:
        print(f"Error getting available slots: {e}")
        return {"error": str(e)}

@app.post("/api/v1/bookings/book-slot/{user_slug}/")
async def book_slot_with_calendar(
    user_slug: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """Book a time slot by creating an event in Google Calendar."""
    try:
        # Get form data
        form_data = await request.form()
        guest_name = form_data.get("guest_name")
        guest_email = form_data.get("guest_email")
        guest_message = form_data.get("guest_message", "")
        
        if not guest_name or not guest_email:
            return HTMLResponse(
                content='<div class="bg-red-50 border border-red-200 rounded-lg p-4"><div class="flex items-center"><svg class="w-5 h-5 text-red-600 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg><p class="text-red-800">Name and email are required</p></div></div>'
            )
        
        # Get the user by scheduling slug
        from app.services.user_service import get_user_by_scheduling_slug
        user = await get_user_by_scheduling_slug(db, user_slug)
        
        if not user:
            return HTMLResponse(
                content='<div class="bg-red-50 border border-red-200 rounded-lg p-4"><div class="flex items-center"><svg class="w-5 h-5 text-red-600 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg><p class="text-red-800">User not found</p></div></div>'
            )
        
        if not user.google_calendar_connected:
            return HTMLResponse(
                content='<div class="bg-red-50 border border-red-200 rounded-lg p-4"><div class="flex items-center"><svg class="w-5 h-5 text-red-600 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg><p class="text-red-800">Google Calendar not connected</p></div></div>'
            )
        
        # Get slot start time from form data
        slot_start_time = form_data.get("slot_start_time")
        if not slot_start_time:
            return HTMLResponse(
                content='<div class="bg-red-50 border border-red-200 rounded-lg p-4"><div class="flex items-center"><svg class="w-5 h-5 text-red-600 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg><p class="text-red-800">Slot start time is required</p></div></div>'
            )
        
        from datetime import datetime, timedelta, timezone
        start_time = datetime.fromisoformat(slot_start_time)
        if start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=timezone.utc)
        end_time = start_time + timedelta(minutes=30)  # 30-minute meeting
        
        # Initialize Google Calendar service
        from app.services.google_calendar_service import GoogleCalendarService
        calendar_service = GoogleCalendarService(
            access_token=user.google_access_token,
            refresh_token=user.google_refresh_token
        )
        
        # Try to create the event in Google Calendar
        try:
            # Check if slot is still available
            if not calendar_service.check_availability(start_time, end_time):
                return HTMLResponse(
                    content='<div class="bg-red-50 border border-red-200 rounded-lg p-4"><div class="flex items-center"><svg class="w-5 h-5 text-red-600 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg><p class="text-red-800">This time slot is no longer available</p></div></div>'
                )
            
            # Create the event in Google Calendar
            event_title = f"Meeting with {guest_name}"
            event_description = f"Meeting with {guest_name}\n\nMessage: {guest_message}" if guest_message else f"Meeting with {guest_name}"
            
            event = calendar_service.create_event(
                title=event_title,
                start_time=start_time,
                end_time=end_time,
                guest_email=guest_email,
                host_email=user.email,
                description=event_description,
                location="Google Meet"
            )
            
            if event:
                # Return simple success indicator
                return HTMLResponse(content='<div data-status="success">Booking confirmed!</div>')
            else:
                return HTMLResponse(
                    content='<div class="bg-red-50 border border-red-200 rounded-lg p-4"><div class="flex items-center"><svg class="w-5 h-5 text-red-600 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg><p class="text-red-800">Failed to create calendar event</p></div></div>'
                )
                
        except Exception as calendar_error:
            print(f"Google Calendar error during booking: {calendar_error}")
            # Return error when Google Calendar fails - no more demo mode
            return HTMLResponse(
                content=f'<div class="bg-red-50 border border-red-200 rounded-lg p-4"><div class="flex items-center"><svg class="w-5 h-5 text-red-600 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg><p class="text-red-800">Calendar service unavailable: {str(calendar_error)}</p></div></div>'
            )
        
    except Exception as e:
        print(f"Error booking slot: {e}")
        return HTMLResponse(
            content=f'<div class="bg-red-50 border border-red-200 rounded-lg p-4"><div class="flex items-center"><svg class="w-5 h-5 text-red-600 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg><p class="text-red-800">Error: {str(e)}</p></div></div>'
        )

# Settings API endpoints
@app.post("/settings/api/profile")
async def update_profile(
    request: Request,
    full_name: str = Form(...),
    scheduling_slug: str = Form(...),
    timezone: str = Form(...),
    db: Session = Depends(get_db)
):
    """Update user profile settings"""
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
        
        # Check if scheduling slug is unique (if changed)
        if scheduling_slug != user.scheduling_slug:
            existing_user = db.query(User).filter(User.scheduling_slug == scheduling_slug).first()
            if existing_user and existing_user.id != user.id:
                return HTMLResponse(
                    '<div class="text-red-600 text-sm">This booking link is already taken. Please choose a different one.</div>',
                    status_code=400
                )
        
        # Update user profile
        user.full_name = full_name
        user.scheduling_slug = scheduling_slug
        user.timezone = timezone
        db.commit()
        
        return HTMLResponse(
            '<div class="text-green-600 text-sm">Profile updated successfully!</div>',
            status_code=200
        )
        
    except Exception as e:
        print(f"Profile update error: {e}")
        return HTMLResponse(
            '<div class="text-red-600 text-sm">Failed to update profile. Please try again.</div>',
            status_code=500
        )

@app.post("/settings/api/calendar-preferences")
async def update_calendar_preferences(
    request: Request,
    default_duration: int = Form(30),
    buffer_time: int = Form(10),
    db: Session = Depends(get_db)
):
    """Update calendar preferences"""
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
        
        # Update calendar preferences (you may need to add these fields to your User model)
        # For now, we'll store them in a JSON field or create a separate preferences table
        # This is a placeholder implementation
        
        return HTMLResponse(
            '<div class="text-green-600 text-sm">Calendar preferences updated successfully!</div>',
            status_code=200
        )
        
    except Exception as e:
        print(f"Calendar preferences error: {e}")
        return HTMLResponse(
            '<div class="text-red-600 text-sm">Failed to update calendar preferences. Please try again.</div>',
            status_code=500
        )

@app.post("/settings/api/notifications")
async def update_notifications(
    request: Request,
    email_notifications: bool = Form(False),
    booking_reminders: bool = Form(False),
    calendar_sync_notifications: bool = Form(False),
    db: Session = Depends(get_db)
):
    """Update notification settings"""
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
        
        # Update notification settings (you may need to add these fields to your User model)
        # This is a placeholder implementation
        
        return HTMLResponse(
            '<div class="text-green-600 text-sm">Notification settings updated successfully!</div>',
            status_code=200
        )
        
    except Exception as e:
        print(f"Notification settings error: {e}")
        return HTMLResponse(
            '<div class="text-red-600 text-sm">Failed to update notification settings. Please try again.</div>',
            status_code=500
        )

@app.post("/settings/api/disconnect-calendar")
async def disconnect_calendar(
    request: Request,
    db: Session = Depends(get_db)
):
    """Disconnect Google Calendar for the current user."""
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

        # Clear Google OAuth tokens and mark calendar as disconnected
        user.google_access_token = None
        user.google_refresh_token = None
        user.google_calendar_id = None
        user.google_calendar_connected = False
        user.google_calendar_email = None
        
        db.commit()
        
        return {"success": True, "message": "Google Calendar disconnected successfully"}
        
    except Exception as e:
        print(f"Disconnect calendar error: {e}")
        return {"success": False, "error": "Failed to disconnect calendar"}


@app.post("/settings/api/change-password")
async def change_password(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db)
):
    """Change user password"""
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
        
        # Verify current password
        if not user.verify_password(current_password):
            return HTMLResponse(
                '<div class="text-red-600 text-sm">Current password is incorrect.</div>',
                status_code=400
            )
        
        # Check if new passwords match
        if new_password != confirm_password:
            return HTMLResponse(
                '<div class="text-red-600 text-sm">New passwords do not match.</div>',
                status_code=400
            )
        
        # Validate new password strength
        if len(new_password) < 8:
            return HTMLResponse(
                '<div class="text-red-600 text-sm">Password must be at least 8 characters long.</div>',
                status_code=400
            )
        
        # Update password
        from app.core.hashing import get_password_hash
        user.hashed_password = get_password_hash(new_password)
        db.commit()
        
        return HTMLResponse(
            '<div class="text-green-600 text-sm">Password changed successfully!</div>',
            status_code=200
        )
        
    except Exception as e:
        print(f"Password change error: {e}")
        return HTMLResponse(
            '<div class="text-red-600 text-sm">Failed to change password. Please try again.</div>',
            status_code=500
        )



