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

# Define dashboard routes early to avoid conflicts
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
        return RedirectResponse(url="/login", status_code=302)

    try:
        payload = verify_token(access_token)
        if not payload:
            return RedirectResponse(url="/login", status_code=302)

        user_email = payload.get("sub")
        user = get_user_by_email(db, user_email)

        if not user:
            return RedirectResponse(url="/login", status_code=302)

        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "current_user": user
        })

    except Exception as e:
        print(f"Dashboard error: {e}")
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
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Include API router
app.include_router(api_router, prefix=settings.API_V1_STR)

# Templates for HTML responses
templates = Jinja2Templates(directory="app/templates")



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
        
        # Automatically log in the user and redirect to agent page
        from app.core.security import create_access_token
        access_token = create_access_token(data={"sub": user.email})
        response = RedirectResponse(url="/agent/", status_code=302)
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
    period: int = Form(30),
    db: Session = Depends(get_db)
):
    """Add single availability slot for dashboard (session auth)"""
    access_token = request.cookies.get("access_token")
    if not access_token:
        return templates.TemplateResponse("availability_response.html", {
            "request": request,
            "message": "Authentication required. Please log in again.",
            "success": False
        })
    
    try:
        payload = verify_token(access_token)
        if not payload:
            return templates.TemplateResponse("availability_response.html", {
                "request": request,
                "message": "Invalid session. Please log in again.",
                "success": False
            })
        
        user_email = payload.get("sub")
        user = get_user_by_email(db, user_email)
        if not user:
            return templates.TemplateResponse("availability_response.html", {
                "request": request,
                "message": "User not found. Please log in again.",
                "success": False
            })
        
        from datetime import datetime, timedelta
        from app.services.availability_service import create_availability_slot
        from app.schemas.schemas import AvailabilitySlotCreate
        
        # Parse date and time
        try:
            start_datetime = datetime.strptime(f"{date} {start_time}", "%Y-%m-%d %H:%M")
            end_datetime = start_datetime + timedelta(minutes=period)
        except ValueError as e:
            return templates.TemplateResponse("availability_response.html", {
                "request": request,
                "message": f"Invalid date or time format: {str(e)}",
                "success": False
            })
        
        # Validate that the slot is in the future
        if start_datetime <= datetime.utcnow():
            return templates.TemplateResponse("availability_response.html", {
                "request": request,
                "message": "Cannot create slots in the past. Please select a future date and time.",
                "success": False
            })
        
        # Create the availability slot
        slot_data = AvailabilitySlotCreate(
            start_time=start_datetime,
            end_time=end_datetime,
            is_available=True
        )
        
        result = create_availability_slot(db, slot_data, user.id)
        
        if not result["success"]:
            return templates.TemplateResponse("availability_response.html", {
                "request": request,
                "message": result["message"],
                "success": False
            })
        
        # Prepare success message based on calendar creation
        message = "Slot created successfully in app"
        if result["calendar_created"] is True:
            message += " and Google Calendar!"
        elif result["calendar_created"] is False:
            message += f" but failed to create in Google Calendar: {result.get('calendar_error', 'Unknown error')}"
        else:
            message += " (Google Calendar not connected)."
        
        return templates.TemplateResponse("availability_response.html", {
            "request": request,
            "message": message,
            "success": True,
            "slot": result["slot"],
            "calendar_created": result["calendar_created"]
        })
        
    except Exception as e:
        print(f"Dashboard API error: {e}")
        return templates.TemplateResponse("availability_response.html", {
            "request": request,
            "message": f"Failed to create availability slot: {str(e)}",
            "success": False
        })


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
                    
                    slot_result = create_availability_slot(db, slot_data, user.id)
                    if not slot_result["success"]:
                        return templates.TemplateResponse("availability_response.html", {
                            "request": request,
                            "message": slot_result["message"],
                            "success": False
                        })
                    created_slots.append(slot_result["slot"])
                    
                    current_time = slot_end
            
            current_date += timedelta(days=1)
        
        return templates.TemplateResponse("availability_response.html", {
            "request": request,
            "message": f"Created {len(created_slots)} recurring availability slots successfully!",
            "slots_created": len(created_slots),
            "success": True
        })
    except Exception as e:
        print(f"Recurring slots API error: {e}")
        return templates.TemplateResponse("availability_response.html", {
            "request": request,
            "message": f"Error creating recurring slots: {str(e)}"
        })


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
                    
                    slot_result = create_availability_slot(db, slot_data, user.id)
                    if not slot_result["success"]:
                        return templates.TemplateResponse("availability_response.html", {
                            "request": request,
                            "message": slot_result["message"],
                            "success": False
                        })
                    created_slots.append(slot_result["slot"])
                    
                    current_time = slot_end
            
            current_date += timedelta(days=1)
        
        return templates.TemplateResponse("availability_response.html", {
            "request": request,
            "message": f"Created {len(created_slots)} bulk availability slots successfully!",
            "slots_created": len(created_slots),
            "success": True
        })
    except Exception as e:
        print(f"Bulk slots API error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/dashboard/api/availability/quick")
async def add_quick_availability_slots(
    request: Request, 
    db: Session = Depends(get_db)
):
    """Add quick availability slots from the quick selection interface"""
    access_token = request.cookies.get("access_token")
    if not access_token:
        return {"success": False, "message": "Not authenticated"}
    
    try:
        payload = verify_token(access_token)
        if not payload:
            return {"success": False, "message": "Invalid token"}
        
        user_email = payload.get("sub")
        user = get_user_by_email(db, user_email)
        if not user:
            return {"success": False, "message": "User not found"}
        
        # Parse JSON body
        body = await request.json()
        slots_data = body.get("slots", [])
        
        if not slots_data:
            return {"success": False, "message": "No slots provided"}
        
        from datetime import datetime, timedelta
        from app.services.availability_service import create_availability_slot
        from app.schemas.schemas import AvailabilitySlotCreate
        
        created_slots = []
        failed_slots = []
        
        for slot_data in slots_data:
            try:
                # Parse date and time
                date_str = slot_data.get("date")
                time_str = slot_data.get("start_time")
                period = slot_data.get("period", 30)
                
                if not date_str or not time_str:
                    failed_slots.append(f"Invalid slot data: {slot_data}")
                    continue
                
                # Create datetime objects
                start_datetime = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
                end_datetime = start_datetime + timedelta(minutes=period)
                
                # Check if slot already exists
                from app.services.availability_service import get_availability_slots_for_user
                existing_slots = get_availability_slots_for_user(db, user.id)
                
                # Check for overlap
                slot_exists = False
                for existing_slot in existing_slots:
                    if (existing_slot.start_time.date() == start_datetime.date() and
                        existing_slot.start_time.time() == start_datetime.time()):
                        slot_exists = True
                        break
                
                if slot_exists:
                    failed_slots.append(f"Slot already exists for {date_str} at {time_str}")
                    continue
                
                # Create the slot
                slot_create_data = AvailabilitySlotCreate(
                    start_time=start_datetime,
                    end_time=end_datetime,
                    is_available=True
                )
                
                slot_result = create_availability_slot(db, slot_create_data, user.id)
                if slot_result["success"]:
                    created_slots.append(slot_result["slot"])
                else:
                    failed_slots.append(slot_result["message"])
                    
            except Exception as e:
                failed_slots.append(f"Error creating slot: {str(e)}")
        
        # Return response
        if created_slots:
            message = f"Successfully created {len(created_slots)} availability slots!"
            if failed_slots:
                message += f" Failed to create {len(failed_slots)} slots."
            
            return {
                "success": True,
                "message": message,
                "slots_created": len(created_slots),
                "slots_failed": len(failed_slots),
                "failed_details": failed_slots
            }
        else:
            return {
                "success": False,
                "message": f"Failed to create any slots. {len(failed_slots)} errors occurred.",
                "failed_details": failed_slots
            }
            
    except Exception as e:
        return {"success": False, "message": "Internal server error"}

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
                    refresh_token=user.google_refresh_token,
                    db=db,
                    user_id=user.id
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
                refresh_token=user.google_refresh_token,
                db=db,
                user_id=user.id
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


@app.get("/availability")
async def availability_page(request: Request, db: Session = Depends(get_db)):
    """Availability management page for setting up available time slots"""
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
        return RedirectResponse(url="/login", status_code=302)

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



@app.get("/api/v1/calendar/available-slots/{user_slug}/{date}")
async def get_available_slots_for_date(
    user_slug: str,
    date: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """Get available time slots for a specific date for a user's public booking page."""
    try:
        from app.services.user_service import get_user_by_scheduling_slug
        user = await get_user_by_scheduling_slug(db, user_slug)
        
        if not user:
            return {"error": "User not found"}
        
        # Check if user has availability slots or calendar connected
        from app.services.availability_service import get_availability_slots_for_user
        availability_slots = get_availability_slots_for_user(db, user.id)
        
        if not availability_slots and not user.google_calendar_connected:
            return {"error": "No availability slots found"}
        
        # Initialize Google Calendar service
        from app.services.google_calendar_service import GoogleCalendarService
        calendar_service = GoogleCalendarService(
            access_token=user.google_access_token,
            refresh_token=user.google_refresh_token,
            db=db,
            user_id=user.id
        )
        
        # Parse the date
        try:
            target_date = datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            return {"error": "Invalid date format"}
        
        # Get available slots from calendar
        try:
            available_slots = calendar_service.get_available_slots(target_date)
            return {"slots": available_slots}
        except Exception as e:
            print(f"Error getting available slots: {e}")
            return {"error": "Failed to get available slots"}
            
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
            refresh_token=user.google_refresh_token,
            db=db,
            user_id=user.id
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

@app.post("/settings/api/personalization")
async def update_personalization(
    request: Request,
    profile_image_url: str = Form(None),
    meeting_title: str = Form(...),
    meeting_description: str = Form(...),
    meeting_duration: int = Form(...),
    theme_color: str = Form(...),
    accent_color: str = Form(...),
    db: Session = Depends(get_db)
):
    """Update personalization settings"""
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
        
        # Validate meeting duration
        if meeting_duration < 15 or meeting_duration > 480:
            return HTMLResponse(
                '<div class="text-red-600 text-sm">Meeting duration must be between 15 and 480 minutes.</div>',
                status_code=400
            )
        
        # Update personalization settings
        # Only update profile_image_url if it's a URL (not a file upload)
        if profile_image_url and (profile_image_url.startswith('http') or profile_image_url.startswith('/uploads/')):
            user.profile_image_url = profile_image_url
        elif not profile_image_url:
            user.profile_image_url = None
        
        user.meeting_title = meeting_title
        user.meeting_description = meeting_description
        user.meeting_duration = meeting_duration
        user.theme_color = theme_color
        user.accent_color = accent_color
        db.commit()
        
        return HTMLResponse(
            '<div class="text-green-600 text-sm">Personalization settings updated successfully!</div>',
            status_code=200
        )
        
    except Exception as e:
        print(f"Personalization update error: {e}")
        return HTMLResponse(
            '<div class="text-red-600 text-sm">Failed to update personalization settings. Please try again.</div>',
            status_code=500
        )

@app.post("/settings/api/upload-profile-image")
async def upload_profile_image(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Upload profile image"""
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
        
        # Import file upload service
        from app.services.file_upload_service import save_uploaded_file, delete_file
        
        # Delete old profile image if exists
        if user.profile_image_url and not user.profile_image_url.startswith('http'):
            delete_file(user.profile_image_url)
        
        # Save new file
        file_path = save_uploaded_file(file, "profile_images")
        if not file_path:
            return HTMLResponse(
                '<div class="text-red-600 text-sm">Failed to upload image. Please try again.</div>',
                status_code=500
            )
        
        # Update user profile
        user.profile_image_url = file_path
        db.commit()
        
        return HTMLResponse(
            f'<div class="text-green-600 text-sm">Profile image uploaded successfully!</div>',
            status_code=200
        )
        
    except Exception as e:
        print(f"Profile image upload error: {e}")
        return HTMLResponse(
            '<div class="text-red-600 text-sm">Failed to upload image. Please try again.</div>',
            status_code=500
        )

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

@app.post("/dashboard/api/calendar/refresh-tokens")
async def refresh_calendar_tokens_endpoint(request: Request, db: Session = Depends(get_db)):
    """Check calendar connection status."""
    access_token = request.cookies.get("access_token")
    if not access_token:
        return {"success": False, "message": "Not authenticated"}
    
    try:
        payload = verify_token(access_token)
        if not payload:
            return {"success": False, "message": "Invalid token"}
        
        user_email = payload.get("sub")
        user = get_user_by_email(db, user_email)
        if not user:
            return {"success": False, "message": "User not found"}
        
        from app.services.availability_service import check_calendar_connection
        result = check_calendar_connection(db, user)
        
        return result
        
    except Exception as e:
        return {"success": False, "message": f"Failed to check calendar connection: {str(e)}"}

@app.get("/dashboard/api/user/status")
async def get_user_status(request: Request, db: Session = Depends(get_db)):
    """Check if user exists and calendar connection status."""
    access_token = request.cookies.get("access_token")
    if not access_token:
        return {"user_exists": False, "calendar_connected": False}
    
    try:
        payload = verify_token(access_token)
        if not payload:
            return {"user_exists": False, "calendar_connected": False}
        
        user_email = payload.get("sub")
        user = get_user_by_email(db, user_email)
        
        if not user:
            return {"user_exists": False, "calendar_connected": False}
        
        return {
            "user_exists": True,
            "calendar_connected": user.google_calendar_connected and user.google_access_token is not None
        }
        
    except Exception as e:
        return {"user_exists": False, "calendar_connected": False}

@app.get("/bookings/api/data")
async def get_bookings_data(request: Request, db: Session = Depends(get_db)):
    """Get bookings data with calendar integration for the bookings page."""
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
        
        # Initialize data structures
        all_bookings = []
        
        # Get user's bookings from database
        from app.services.booking_service import get_bookings_for_user
        db_bookings = get_bookings_for_user(db, user.id)
        
        # Convert database bookings to bookings format
        for booking in db_bookings:
            all_bookings.append({
                "id": booking.id,
                "title": booking.guest_name,
                "date": booking.start_time.strftime("%Y-%m-%d"),
                "time": booking.start_time.strftime("%H:%M"),
                "end_time": booking.end_time.strftime("%H:%M"),
                "email": booking.guest_email,
                "status": booking.status,
                "source": "database",
                "guest_message": booking.guest_message
            })
        
        # If user has Google Calendar connected, get real calendar data
        if user.google_calendar_connected and user.google_access_token:
            try:
                from app.services.google_calendar_service import GoogleCalendarService
                
                # Initialize Google Calendar service
                calendar_service = GoogleCalendarService(
                    access_token=user.google_access_token,
                    refresh_token=user.google_refresh_token,
                    db=db,
                    user_id=user.id
                )
                
                # Get events from past 7 days to next 30 days (reduced range for performance)
                start_date = datetime.now(timezone.utc) - timedelta(days=7)
                end_date = datetime.now(timezone.utc) + timedelta(days=30)
                calendar_events = calendar_service.get_events(start_date, end_date)
                
                # Process calendar events
                for event in calendar_events:
                    event_start = event.get('start', {}).get('dateTime')
                    event_end = event.get('end', {}).get('dateTime')
                    
                    if event_start and event_end:
                        # Handle timezone-aware datetime parsing
                        if event_start.endswith('Z'):
                            event_start_dt = datetime.fromisoformat(event_start.replace('Z', '+00:00'))
                        else:
                            event_start_dt = datetime.fromisoformat(event_start)
                        
                        if event_end.endswith('Z'):
                            event_end_dt = datetime.fromisoformat(event_end.replace('Z', '+00:00'))
                        else:
                            event_end_dt = datetime.fromisoformat(event_end)
                        
                        event_date = event_start_dt.strftime("%Y-%m-%d")
                        event_start_time = event_start_dt.strftime("%H:%M")
                        event_end_time = event_end_dt.strftime("%H:%M")
                        
                        # Add to all bookings
                        all_bookings.append({
                            "id": f"calendar_{event.get('id')}",
                            "title": event.get('summary', 'Untitled Event'),
                            "date": event_date,
                            "time": event_start_time,
                            "end_time": event_end_time,
                            "email": event.get('organizer', {}).get('email', ''),
                            "status": "confirmed",
                            "source": "calendar",
                            "calendar_id": event.get('id'),
                            "description": event.get('description', ''),
                            "location": event.get('location', ''),
                            "guest_message": None
                        })
                
            except Exception as e:
                print(f"Error accessing Google Calendar: {e}")
                # Continue with database data only
        
        # Sort all bookings by date and time
        all_bookings.sort(key=lambda x: (x['date'], x['time']), reverse=True)
        
        return {
            "bookings": all_bookings,
            "totalBookings": len(all_bookings),
            "calendarConnected": user.google_calendar_connected
        }
        
    except Exception as e:
        print(f"Error in get_bookings_data: {e}")
        return {"error": str(e)}

@app.get("/bookings/api/stats")
async def get_bookings_stats(request: Request, db: Session = Depends(get_db)):
    """Get booking statistics with calendar integration."""
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
        
        # Get database bookings
        from app.services.booking_service import get_bookings_for_user
        db_bookings = get_bookings_for_user(db, user.id)
        
        # Count database bookings by status
        total_db = len(db_bookings)
        confirmed_db = len([b for b in db_bookings if b.status == "confirmed"])
        cancelled_db = len([b for b in db_bookings if b.status == "cancelled"])
        upcoming_db = len([b for b in db_bookings if b.start_time > datetime.now(timezone.utc)])
        
        # Get calendar events if connected
        calendar_events = []
        if user.google_calendar_connected and user.google_access_token:
            try:
                from app.services.google_calendar_service import GoogleCalendarService
                calendar_service = GoogleCalendarService(
                    access_token=user.google_access_token,
                    refresh_token=user.google_refresh_token,
                    db=db,
                    user_id=user.id
                )
                
                # Get events from past 30 days to next 30 days
                start_date = datetime.now(timezone.utc) - timedelta(days=30)
                end_date = datetime.now(timezone.utc) + timedelta(days=30)
                calendar_events = calendar_service.get_events(start_date, end_date)
                
            except Exception as e:
                print(f"Error accessing Google Calendar: {e}")
        
        # Count calendar events
        total_calendar = len(calendar_events)
        upcoming_calendar = 0
        for event in calendar_events:
            event_start = event.get('start', {}).get('dateTime')
            if event_start:
                if event_start.endswith('Z'):
                    event_datetime = datetime.fromisoformat(event_start.replace('Z', '+00:00'))
                else:
                    event_datetime = datetime.fromisoformat(event_start)
                
                if event_datetime > datetime.now(timezone.utc):
                    upcoming_calendar += 1
        
        # Combine totals
        total_bookings = total_db + total_calendar
        total_confirmed = confirmed_db + total_calendar  # Calendar events are always confirmed
        total_cancelled = cancelled_db  # Calendar events can't be cancelled through our system
        total_upcoming = upcoming_db + upcoming_calendar
        
        return HTMLResponse(f"""
            <div class="stat-card">
                <div class="stat-icon" style="background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);">
                    <svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"></path>
                    </svg>
                </div>
                <div class="stat-title">Total Bookings</div>
                <div class="stat-value">{total_bookings}</div>
            </div>
            
            <div class="stat-card">
                <div class="stat-icon" style="background: linear-gradient(135deg, #059669 0%, #10b981 100%);">
                    <svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                    </svg>
                </div>
                <div class="stat-title">Confirmed</div>
                <div class="stat-value">{total_confirmed}</div>
            </div>
            
            <div class="stat-card">
                <div class="stat-icon" style="background: linear-gradient(135deg, #d97706 0%, #f59e0b 100%);">
                    <svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                    </svg>
                </div>
                <div class="stat-title">Upcoming</div>
                <div class="stat-value">{total_upcoming}</div>
            </div>
            
            <div class="stat-card">
                <div class="stat-icon" style="background: linear-gradient(135deg, #dc2626 0%, #ef4444 100%);">
                    <svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                    </svg>
                </div>
                <div class="stat-title">Cancelled</div>
                <div class="stat-value">{total_cancelled}</div>
            </div>
        """)
        
    except Exception as e:
        print(f"Error in get_bookings_stats: {e}")
        return {"error": str(e)}

@app.get("/bookings/api/list")
async def get_bookings_list(request: Request, db: Session = Depends(get_db)):
    """Get bookings list with calendar integration and filtering."""
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
        
        # Get query parameters for filtering
        status_filter = request.query_params.get("status", "")
        time_filter = request.query_params.get("time", "")
        search_filter = request.query_params.get("search", "").lower()
        
        # Get database bookings
        from app.services.booking_service import get_bookings_for_user
        db_bookings = get_bookings_for_user(db, user.id)
        
        # Convert database bookings to list format
        all_bookings = []
        for booking in db_bookings:
            all_bookings.append({
                "id": booking.id,
                "title": booking.guest_name,
                "date": booking.start_time.strftime("%Y-%m-%d"),
                "time": booking.start_time.strftime("%H:%M"),
                "end_time": booking.end_time.strftime("%H:%M"),
                "email": booking.guest_email,
                "status": booking.status,
                "source": "database",
                "guest_message": booking.guest_message,
                "datetime": booking.start_time
            })
        
        # Get calendar events if connected
        if user.google_calendar_connected and user.google_access_token:
            try:
                from app.services.google_calendar_service import GoogleCalendarService
                calendar_service = GoogleCalendarService(
                    access_token=user.google_access_token,
                    refresh_token=user.google_refresh_token,
                    db=db,
                    user_id=user.id
                )
                
                # Get events from past 30 days to next 30 days
                start_date = datetime.now(timezone.utc) - timedelta(days=30)
                end_date = datetime.now(timezone.utc) + timedelta(days=30)
                calendar_events = calendar_service.get_events(start_date, end_date)
                
                # Process calendar events
                for event in calendar_events:
                    event_start = event.get('start', {}).get('dateTime')
                    event_end = event.get('end', {}).get('dateTime')
                    
                    if event_start and event_end:
                        # Handle timezone-aware datetime parsing
                        if event_start.endswith('Z'):
                            event_start_dt = datetime.fromisoformat(event_start.replace('Z', '+00:00'))
                        else:
                            event_start_dt = datetime.fromisoformat(event_start)
                        
                        if event_end.endswith('Z'):
                            event_end_dt = datetime.fromisoformat(event_end.replace('Z', '+00:00'))
                        else:
                            event_end_dt = datetime.fromisoformat(event_end)
                        
                        event_date = event_start_dt.strftime("%Y-%m-%d")
                        event_start_time = event_start_dt.strftime("%H:%M")
                        event_end_time = event_end_dt.strftime("%H:%M")
                        
                        # Add to all bookings
                        all_bookings.append({
                            "id": f"calendar_{event.get('id')}",
                            "title": event.get('summary', 'Untitled Event'),
                            "date": event_date,
                            "time": event_start_time,
                            "end_time": event_end_time,
                            "email": event.get('organizer', {}).get('email', ''),
                            "status": "confirmed",
                            "source": "calendar",
                            "calendar_id": event.get('id'),
                            "description": event.get('description', ''),
                            "location": event.get('location', ''),
                            "guest_message": None,
                            "datetime": event_start_dt
                        })
                
            except Exception as e:
                print(f"Error accessing Google Calendar: {e}")
        
        # Apply filters
        filtered_bookings = all_bookings
        
        # Status filter
        if status_filter:
            filtered_bookings = [b for b in filtered_bookings if b['status'] == status_filter]
        
        # Time filter
        if time_filter:
            today = datetime.now().date()
            if time_filter == "today":
                filtered_bookings = [b for b in filtered_bookings if b['date'] == today.strftime("%Y-%m-%d")]
            elif time_filter == "week":
                week_start = today - timedelta(days=today.weekday())
                week_end = week_start + timedelta(days=6)
                filtered_bookings = [b for b in filtered_bookings if week_start.strftime("%Y-%m-%d") <= b['date'] <= week_end.strftime("%Y-%m-%d")]
            elif time_filter == "month":
                month_start = today.replace(day=1)
                if today.month == 12:
                    month_end = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
                else:
                    month_end = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
                filtered_bookings = [b for b in filtered_bookings if month_start.strftime("%Y-%m-%d") <= b['date'] <= month_end.strftime("%Y-%m-%d")]
            elif time_filter == "past":
                filtered_bookings = [b for b in filtered_bookings if b['date'] < today.strftime("%Y-%m-%d")]
        
        # Search filter
        if search_filter:
            filtered_bookings = [b for b in filtered_bookings if 
                               search_filter in b['title'].lower() or 
                               search_filter in b['email'].lower()]
        
        # Sort by date and time (newest first)
        filtered_bookings.sort(key=lambda x: (x['date'], x['time']), reverse=True)
        
        # Prepare data for template
        all_bookings_for_template = []
        if filtered_bookings:
            for booking in filtered_bookings:
                # Format date for display
                display_date = booking['date']
                today = datetime.now().date()
                booking_date = datetime.strptime(booking['date'], "%Y-%m-%d").date()
                
                if booking_date == today:
                    display_date = "Today"
                elif booking_date == today + timedelta(days=1):
                    display_date = "Tomorrow"
                elif booking_date < today:
                    display_date = f"{booking_date.strftime('%b %d')} (Past)"
                else:
                    display_date = booking_date.strftime('%b %d')
                
                # Convert booking data to template format
                booking_data = {
                    'id': booking['id'],
                    'guest_name': booking['title'],
                    'guest_email': booking['email'],
                    'start_time': f"{display_date} at {booking['time']}",
                    'end_time': booking['end_time'],
                    'status': booking['status'],
                    'guest_message': booking.get('guest_message', ''),
                    'source': booking['source']
                }
                all_bookings_for_template.append(booking_data)
        
        # Use template instead of generating HTML
        from fastapi.templating import Jinja2Templates
        templates = Jinja2Templates(directory="app/templates")
        
        return templates.TemplateResponse("bookings_list.html", {
            "request": request,
            "bookings": all_bookings_for_template
        })
        
    except Exception as e:
        print(f"Error in get_bookings_list: {e}")
        return {"error": str(e)}

@app.get("/dashboard/api/data")
async def get_dashboard_data(request: Request, db: Session = Depends(get_db)):
    """Get dashboard data for connected users with real calendar integration."""
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
        
        # Initialize data structures
        upcoming_bookings = []
        all_bookings = []
        available_slots = []
        
        # Get user's bookings from database
        from app.services.booking_service import get_bookings_for_user
        db_bookings = get_bookings_for_user(db, user.id)
        
        # Use timezone-aware current time for database comparisons
        current_time = datetime.now()
        upcoming_db_bookings = []
        
        for booking in db_bookings:
            # Ensure both times are timezone-aware for comparison
            booking_time = booking.start_time
            if booking_time.tzinfo is None:
                # If booking time is naive, assume UTC
                booking_time = booking_time.replace(tzinfo=timezone.utc)
            
            if current_time.tzinfo is None:
                # If current time is naive, assume UTC
                current_time = current_time.replace(tzinfo=timezone.utc)
            
            if booking_time > current_time:
                upcoming_db_bookings.append(booking)
        
        # Convert database bookings to dashboard format
        for booking in upcoming_db_bookings:
            upcoming_bookings.append({
                "id": booking.id,
                "title": booking.guest_name,
                "date": booking.start_time.strftime("%Y-%m-%d"),
                "time": booking.start_time.strftime("%H:%M"),
                "email": booking.guest_email,
                "source": "database"
            })
        
        for booking in db_bookings:
            all_bookings.append({
                "id": booking.id,
                "title": booking.guest_name,
                "date": booking.start_time.strftime("%Y-%m-%d"),
                "time": booking.start_time.strftime("%H:%M"),
                "email": booking.guest_email,
                "source": "database"
            })
        
        # If user has Google Calendar connected, get real calendar data
        if user.google_calendar_connected and user.google_access_token:
            try:
                from app.services.google_calendar_service import GoogleCalendarService
                
                # Initialize Google Calendar service
                calendar_service = GoogleCalendarService(
                    access_token=user.google_access_token,
                    refresh_token=user.google_refresh_token,
                    db=db,
                    user_id=user.id
                )
                
                # Get events from today to next 30 days
                start_date = datetime.now()
                end_date = start_date + timedelta(days=30)
                
                calendar_events = calendar_service.get_events(start_date, end_date)
                
                # Process calendar events
                for event in calendar_events:
                    event_start = event.get('start', {}).get('dateTime')
                    if event_start:
                        # Handle timezone-aware datetime parsing
                        if event_start.endswith('Z'):
                            event_datetime = datetime.fromisoformat(event_start.replace('Z', '+00:00'))
                        else:
                            event_datetime = datetime.fromisoformat(event_start)
                        
                        # Make current time timezone-aware for comparison
                        current_time = datetime.now(event_datetime.tzinfo)
                        
                        event_date = event_datetime.strftime("%Y-%m-%d")
                        event_time = event_datetime.strftime("%H:%M")
                        
                        # Add to upcoming bookings if it's in the future
                        if event_datetime > current_time:
                            upcoming_bookings.append({
                                "id": f"calendar_{event.get('id')}",
                                "title": event.get('summary', 'Untitled Event'),
                                "date": event_date,
                                "time": event_time,
                                "email": event.get('organizer', {}).get('email', ''),
                                "source": "calendar",
                                "calendar_id": event.get('id'),
                                "description": event.get('description', ''),
                                "location": event.get('location', '')
                            })
                        
                        # Add to all bookings
                        all_bookings.append({
                            "id": f"calendar_{event.get('id')}",
                            "title": event.get('summary', 'Untitled Event'),
                            "date": event_date,
                            "time": event_time,
                            "email": event.get('organizer', {}).get('email', ''),
                            "source": "calendar",
                            "calendar_id": event.get('id'),
                            "description": event.get('description', ''),
                            "location": event.get('location', '')
                        })
                
                # Get available slots for today and tomorrow
                today = datetime.now().date()
                tomorrow = today + timedelta(days=1)
                
                for date in [today, tomorrow]:
                    try:
                        slots = calendar_service.get_available_slots(date, 30)
                        for slot in slots:
                            available_slots.append({
                                "date": date.strftime("%Y-%m-%d"),
                                "start_time": slot['start_time'].strftime("%H:%M"),
                                "end_time": slot['end_time'].strftime("%H:%M"),
                                "duration": 30
                            })
                    except Exception as e:
                        print(f"Error getting available slots for {date}: {e}")
                        continue
                
            except Exception as e:
                print(f"Error accessing Google Calendar: {e}")
                # Continue with database data only
        
        # Sort upcoming bookings by date and time
        upcoming_bookings.sort(key=lambda x: (x['date'], x['time']))
        
        return {
            "upcomingBookings": upcoming_bookings,
            "allBookings": all_bookings,
            "availableSlots": available_slots,
            "calendarConnected": user.google_calendar_connected,
            "totalBookings": len(all_bookings),
            "upcomingCount": len(upcoming_bookings),
            "availableCount": len(available_slots)
        }
        
    except Exception as e:
        print(f"Error in get_dashboard_data: {e}")
        return {"error": str(e)}







@app.post("/dashboard/api/chat")
async def chat_with_ai(request: Request, db: Session = Depends(get_db)):
    """Chat with AI agent using real calendar data."""
    access_token = request.cookies.get("access_token")
    if not access_token:
        return {"error": "Not authenticated"}
    
    try:
        payload = verify_token(access_token)
        if not payload:
            return {"error": "Invalid token"}
        
        body = await request.json()
        message = body.get("message", "")
        
        if not message:
            return {"error": "No message provided"}
        
        user_email = payload.get("sub")
        user = get_user_by_email(db, user_email)
        
        if not user:
            return {"error": "User not found"}
        
        # Get real calendar data for context
        calendar_context = ""
        if user.google_calendar_connected and user.google_access_token:
            try:
                from app.services.google_calendar_service import GoogleCalendarService
                calendar_service = GoogleCalendarService(
                    access_token=user.google_access_token,
                    refresh_token=user.google_refresh_token,
                    db=db,
                    user_id=user.id
                )
                
                # Get today's events
                today = datetime.now()
                tomorrow = today + timedelta(days=1)
                events = calendar_service.get_events(today, tomorrow)
                
                if events:
                    calendar_context = f"You have {len(events)} events today/tomorrow: "
                    for event in events[:3]:  # Show first 3 events
                        event_start = event.get('start', {}).get('dateTime')
                        if event_start:
                            event_datetime = datetime.fromisoformat(event_start.replace('Z', '+00:00') if event_start.endswith('Z') else event_start)
                            calendar_context += f"{event.get('summary', 'Untitled')} at {event_datetime.strftime('%H:%M')}, "
                    calendar_context = calendar_context.rstrip(", ")
                else:
                    calendar_context = "You have no events scheduled for today or tomorrow."
                    
            except Exception as e:
                calendar_context = "I can't access your calendar right now."
        
        # Generate intelligent response based on message and calendar context
        message_lower = message.lower()
        
        if any(word in message_lower for word in ['schedule', 'book', 'appointment', 'meeting']):
            response = f"I can help you schedule appointments! {calendar_context} What type of meeting would you like to schedule?"
        elif any(word in message_lower for word in ['availability', 'free', 'when', 'time']):
            response = f"Let me check your availability for you. {calendar_context} When would you like to check availability for?"
        elif any(word in message_lower for word in ['today', 'tomorrow', 'events', 'meetings']):
            response = f"Here's what's on your schedule: {calendar_context}"
        elif any(word in message_lower for word in ['cancel', 'reschedule']):
            response = f"I can help you cancel or reschedule meetings. {calendar_context} Which meeting would you like to modify?"
        else:
            response = f"I'm your AI scheduling assistant! {calendar_context} How can I help you with your schedule today?"
        
        return {"response": response}
        
    except Exception as e:
        return {"error": str(e)}

