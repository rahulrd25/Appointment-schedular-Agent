from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import and_
from datetime import datetime, timezone, timedelta
import logging

from app.core.database import get_db
from app.core.security import verify_token
from app.services.user_service import get_user_by_email
from app.models.models import User, AvailabilitySlot, Booking
from app.services.availability_service import get_availability_slots_for_user, AvailabilityService
from app.services.booking_service import get_upcoming_bookings
from app.core.timezone_utils import TimezoneManager
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

@router.get("/agent")
async def agent_redirect(request: Request):
    """Redirect /agent to /dashboard preserving query parameters"""
    query_string = request.url.query
    redirect_url = f"/dashboard{'?' + query_string if query_string else ''}"
    return RedirectResponse(url=redirect_url, status_code=302)

@router.get("/dashboard")
async def dashboard(request: Request, db: Session = Depends(get_db)):
    """Dashboard Interface"""
    access_token = request.cookies.get("access_token")

    if not access_token:
        return RedirectResponse(url="/", status_code=302)

    # Remove "Bearer " prefix if present
    if access_token.startswith("Bearer "):
        access_token = access_token[7:]

    try:
        payload = verify_token(access_token)
        if not payload:
            return RedirectResponse(url="/", status_code=302)

        user_email = payload.get("sub")
        user = get_user_by_email(db, user_email)

        if not user:
            return RedirectResponse(url="/", status_code=302)

        # Get user's availability slots (including booked ones)
        availability_slots = get_availability_slots_for_user(db, user.id, include_unavailable=True)
        
        # Get user's timezone
        user_timezone = TimezoneManager.get_user_timezone(user.timezone)

        # Convert times to user's timezone for display
        for slot in availability_slots:
            # Ensure times are timezone-aware
            if slot.start_time.tzinfo is None:
                slot.start_time = slot.start_time.replace(tzinfo=timezone.utc)
            if slot.end_time.tzinfo is None:
                slot.end_time = slot.end_time.replace(tzinfo=timezone.utc)
            
            # Convert to user's timezone
            slot.start_time = slot.start_time.astimezone(ZoneInfo(user_timezone))
            slot.end_time = slot.end_time.astimezone(ZoneInfo(user_timezone))
        
        # Get upcoming bookings
        upcoming_bookings = get_upcoming_bookings(db, user.id, limit=5)

        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "current_user": user,
            "availability_slots": availability_slots,
            "upcoming_bookings": upcoming_bookings
        })

    except Exception as e:
        return RedirectResponse(url="/", status_code=302)

@router.get("/dashboard/api/user/status")
async def dashboard_user_status(request: Request, db: Session = Depends(get_db)):
    """Get user status for dashboard"""
    access_token = request.cookies.get("access_token")
    
    if not access_token:
        return {"authenticated": False}
    
    # Remove "Bearer " prefix if present
    if access_token.startswith("Bearer "):
        access_token = access_token[7:]
    
    try:
        payload = verify_token(access_token)
        if not payload:
            return {"authenticated": False}
        
        user_email = payload.get("sub")
        user = get_user_by_email(db, user_email)
        
        if not user:
            return {"authenticated": False}
        
        return {
            "authenticated": True,
            "user": {
                "id": user.id,
                "email": user.email,
                "name": user.full_name,
                "google_calendar_connected": user.google_calendar_connected,
                "scheduling_slug": user.scheduling_slug
            }
        }
    except Exception as e:
        return {"authenticated": False, "error": str(e)}

@router.get("/dashboard/api/data")
async def dashboard_data(request: Request, db: Session = Depends(get_db)):
    """Get dashboard data"""
    access_token = request.cookies.get("access_token")
    
    if not access_token:
        return {"error": "Not authenticated"}

    # Remove "Bearer " prefix if present
    if access_token.startswith("Bearer "):
        access_token = access_token[7:]
    
    try:
        payload = verify_token(access_token)
        if not payload:
            return {"error": "Invalid token"}
        
        user_email = payload.get("sub")
        user = get_user_by_email(db, user_email)
        
        if not user:
            return {"error": "User not found"}
        
        # Get availability slots with error handling (including booked ones)
        try:
            availability_slots = get_availability_slots_for_user(db, user.id, include_unavailable=True)
            logger.debug(f"Successfully retrieved {len(availability_slots)} availability slots for user {user.id}")
        except Exception as e:
            logger.error(f"Error getting availability slots for user {user.id}: {e}")
            availability_slots = []
        
        # Get user's timezone
        user_timezone = TimezoneManager.get_user_timezone(user.timezone)
        
        # Convert times to user's timezone for display
        for slot in availability_slots:
            # Ensure times are timezone-aware
            if slot.start_time.tzinfo is None:
                slot.start_time = slot.start_time.replace(tzinfo=timezone.utc)
            if slot.end_time.tzinfo is None:
                slot.end_time = slot.end_time.replace(tzinfo=timezone.utc)
            
            # Convert to user's timezone
            slot.start_time = slot.start_time.astimezone(ZoneInfo(user_timezone))
            slot.end_time = slot.end_time.astimezone(ZoneInfo(user_timezone))
        
        # Get upcoming bookings with error handling
        try:
            upcoming_bookings = get_upcoming_bookings(db, user.id, limit=10)
            logger.debug(f"Successfully retrieved {len(upcoming_bookings)} upcoming bookings for user {user.id}")
        except Exception as e:
            logger.error(f"Error getting upcoming bookings for user {user.id}: {e}")
            upcoming_bookings = []
        
        # Format data to match frontend expectations
        formatted_bookings = []
        for booking in upcoming_bookings:
            # Ensure times are timezone-aware
            if booking.start_time.tzinfo is None:
                booking.start_time = booking.start_time.replace(tzinfo=timezone.utc)
            if booking.end_time.tzinfo is None:
                booking.end_time = booking.end_time.replace(tzinfo=timezone.utc)
            
            # Convert to user's timezone
            booking_start_time = booking.start_time.astimezone(ZoneInfo(user_timezone))
            booking_end_time = booking.end_time.astimezone(ZoneInfo(user_timezone))
            
            # Format date and time for display
            start_date = booking_start_time.strftime('%Y-%m-%d')
            start_time = booking_start_time.strftime('%H:%M')
            
            formatted_bookings.append({
                "id": booking.id,
                "title": f"Meeting with {booking.guest_name}",
                "date": start_date,
                "time": start_time,
                "email": booking.guest_email,
                "location": None,  # Add location if available in future
                "description": booking.guest_message,
                "status": booking.status,
                "source": "booking"  # Distinguish from calendar events
            })
        
        # Format availability slots
        formatted_slots = []
        for slot in availability_slots:
            formatted_slots.append({
                "id": slot.id,
                "start_time": slot.start_time.isoformat(),
                "end_time": slot.end_time.isoformat(),
                "is_available": slot.is_available,
                "date": slot.start_time.strftime('%Y-%m-%d'),
                "start_time_formatted": slot.start_time.strftime('%H:%M'),
                "end_time_formatted": slot.end_time.strftime('%H:%M')
            })
        
        return {
            "availability_slots": formatted_slots,
            "upcoming_bookings": formatted_bookings,
            "upcomingCount": len(formatted_bookings),
            "totalBookings": len(formatted_bookings),
            "availableCount": len(formatted_slots),
            "calendarConnected": user.google_calendar_connected
        }
    except Exception as e:
        return {"error": str(e)}

@router.post("/dashboard/api/chat")
async def dashboard_chat(request: Request, db: Session = Depends(get_db)):
    """Handle dashboard chat with AI agent"""
    access_token = request.cookies.get("access_token")
    
    if not access_token:
        return {"error": "Not authenticated"}

    # Remove "Bearer " prefix if present
    if access_token.startswith("Bearer "):
        access_token = access_token[7:]
    
    try:
        payload = verify_token(access_token)
        if not payload:
            return {"error": "Invalid token"}
        
        user_email = payload.get("sub")
        user = get_user_by_email(db, user_email)
        
        if not user:
            return {"error": "User not found"}
        
        # Parse request body
        body = await request.body()
        data = json.loads(body)
        message = data.get("message", "")
        
        # Initialize AI agent service
        agent_service = AdvancedAIAgentService(db)
        
        # Process message
        response = agent_service.process_message(user.id, message)
        
        return response
    except Exception as e:
        return {"error": str(e)}

@router.post("/dashboard/api/calendar/connect")
async def dashboard_calendar_connect(request: Request, db: Session = Depends(get_db)):
    """Connect Google Calendar"""
    access_token = request.cookies.get("access_token")
    
    if not access_token:
        return {"error": "Not authenticated"}

    # Remove "Bearer " prefix if present
    if access_token.startswith("Bearer "):
        access_token = access_token[7:]
    
    try:
        payload = verify_token(access_token)
        if not payload:
            return {"error": "Invalid token"}
        
        user_email = payload.get("sub")
        user = get_user_by_email(db, user_email)
        
        if not user:
            return {"error": "User not found"}
        
        # Parse request body
        body = await request.body()
        data = json.loads(body)
        auth_code = data.get("code")
        
        if not auth_code:
            return {"error": "No authorization code provided"}
        
        # Handle Google Calendar connection
        from app.services.oauth_service import handle_google_calendar_callback
        result = await handle_google_calendar_callback(auth_code, user.id, db)
        
        return result
    except Exception as e:
        return {"error": str(e)}

@router.post("/dashboard/api/availability/quick")
async def dashboard_availability_quick(request: Request, db: Session = Depends(get_db)):
    """Quick availability setup"""
    access_token = request.cookies.get("access_token")
    
    if not access_token:
        return {"error": "Not authenticated"}

    # Remove "Bearer " prefix if present
    if access_token.startswith("Bearer "):
        access_token = access_token[7:]
    
    try:
        payload = verify_token(access_token)
        if not payload:
            return {"error": "Invalid token"}
        
        user_email = payload.get("sub")
        user = get_user_by_email(db, user_email)
        
        if not user:
            return {"error": "User not found"}
        
        # Parse request body
        body = await request.body()
        data = json.loads(body)
        
        # Handle quick availability setup
        from app.services.availability_service import create_availability_slots_bulk
        
        # Extract slots from the request data
        slots_data = data.get('slots', [])
        if not slots_data:
            return {"success": False, "message": "No slots provided"}
        
        result = create_availability_slots_bulk(db, user.id, slots_data)
        
        return result
    except Exception as e:
        return {"error": str(e)} 