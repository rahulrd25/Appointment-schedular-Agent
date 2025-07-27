import os
from datetime import datetime
from pathlib import Path
from fastapi import FastAPI, Request, Form, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse, HTMLResponse
from sqlalchemy.orm import Session
import requests
import json

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
        "scope=openid email profile https://www.googleapis.com/auth/calendar.events&"
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
                "start_time": booking.start_time.isoformat(),
                "end_time": booking.end_time.isoformat(),
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
    excluded_paths = ["agent", "dashboard", "login", "register", "logout", "verify-email", "auth"]
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
        "public_booking.html", {
            "request": request, 
            "user": user,
            "availability_slots": availability_slots
        }
    )
