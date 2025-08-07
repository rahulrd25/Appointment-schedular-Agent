from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.services.user_service import get_user_by_email
from app.core.security import verify_token
from app.services.advanced_ai_agent_service import AdvancedAIAgentService
from app.services.availability_service import get_availability_slots_for_user
from app.services.booking_service import get_upcoming_bookings
from app.services.google_calendar_service import GoogleCalendarService
import json

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

        # Get user's availability slots
        availability_slots = get_availability_slots_for_user(db, user.id)
        
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
        
        # Get availability slots
        try:
            availability_slots = get_availability_slots_for_user(db, user.id)
        except Exception as e:
            print(f"Error getting availability slots: {e}")
            availability_slots = []
        
        # Get upcoming bookings
        try:
            upcoming_bookings = get_upcoming_bookings(db, user.id, limit=10)
        except Exception as e:
            print(f"Error getting upcoming bookings: {e}")
            upcoming_bookings = []
        
        return {
            "availability_slots": [
                {
                    "id": slot.id,
                    "start_time": slot.start_time.isoformat(),
                    "end_time": slot.end_time.isoformat(),
                    "is_available": slot.is_available
                } for slot in availability_slots
            ],
            "upcoming_bookings": [
                {
                    "id": booking.id,
                    "guest_name": booking.guest_name,
                    "guest_email": booking.guest_email,
                    "start_time": booking.start_time.isoformat(),
                    "end_time": booking.end_time.isoformat(),
                    "status": booking.status
                } for booking in upcoming_bookings
            ]
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
        agent_service = AdvancedAIAgentService(db, user.id)
        
        # Process message
        response = await agent_service.process_message(message, user.id)
        
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
        from app.services.availability_service import create_availability_slot
        result = create_availability_slot(db, user.id, data)
        
        return result
    except Exception as e:
        return {"error": str(e)} 