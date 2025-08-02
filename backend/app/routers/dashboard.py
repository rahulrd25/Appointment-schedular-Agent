from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from fastapi.templating import Jinja2Templates
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List

from app.core.database import get_db
from app.core.security import verify_token
from app.services.user_service import get_user_by_email
from app.services.booking_service import get_bookings_for_user, get_upcoming_bookings
from app.services.availability_service import get_availability_slots_for_user

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")




@router.get("/dashboard")
async def dashboard(request: Request, db: Session = Depends(get_db)):
    """Dashboard Interface"""
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


@router.get("/dashboard/api/bookings/upcoming")
async def get_dashboard_upcoming_bookings(request: Request, db: Session = Depends(get_db)):
    """Get upcoming bookings for dashboard"""
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
        upcoming_bookings = get_upcoming_bookings(db, user.id, limit=5)
        
        # Format for dashboard
        formatted_bookings = []
        for booking in upcoming_bookings:
            formatted_bookings.append({
                "id": booking.id,
                "title": booking.guest_name,
                "date": booking.start_time.strftime("%Y-%m-%d"),
                "time": booking.start_time.strftime("%H:%M"),
                "end_time": booking.end_time.strftime("%H:%M"),
                "email": booking.guest_email,
                "status": booking.status
            })
        
        return {"bookings": formatted_bookings}
        
    except Exception as e:
        print(f"Error in get_dashboard_upcoming_bookings: {e}")
        return {"error": str(e)}


@router.get("/dashboard/api/bookings/all")
async def get_dashboard_all_bookings(request: Request, db: Session = Depends(get_db)):
    """Get all bookings for dashboard"""
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
        
        # Get all bookings
        all_bookings = get_bookings_for_user(db, user.id)
        
        # Format for dashboard
        formatted_bookings = []
        for booking in all_bookings:
            formatted_bookings.append({
                "id": booking.id,
                "title": booking.guest_name,
                "date": booking.start_time.strftime("%Y-%m-%d"),
                "time": booking.start_time.strftime("%H:%M"),
                "end_time": booking.end_time.strftime("%H:%M"),
                "email": booking.guest_email,
                "status": booking.status
            })
        
        return {"bookings": formatted_bookings}
        
    except Exception as e:
        print(f"Error in get_dashboard_all_bookings: {e}")
        return {"error": str(e)}


@router.get("/dashboard/api/availability/available")
async def get_dashboard_available_slots(request: Request, db: Session = Depends(get_db)):
    """Get available slots for dashboard"""
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
        
        # Get available slots
        available_slots = get_availability_slots_for_user(db, user.id)
        
        # Format for dashboard
        formatted_slots = []
        for slot in available_slots:
            formatted_slots.append({
                "id": slot.id,
                "date": slot.start_time.strftime("%Y-%m-%d"),
                "time": slot.start_time.strftime("%H:%M"),
                "end_time": slot.end_time.strftime("%H:%M"),
                "duration": int((slot.end_time - slot.start_time).total_seconds() / 60)
            })
        
        return {"slots": formatted_slots}
        
    except Exception as e:
        print(f"Error in get_dashboard_available_slots: {e}")
        return {"error": str(e)}


@router.get("/dashboard/api/data")
async def get_dashboard_data(request: Request, db: Session = Depends(get_db)):
    """Get combined dashboard data including stats and bookings"""
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
        
        # Get all bookings from database (includes both local and calendar-synced)
        from app.services.booking_service import get_bookings_for_user
        all_bookings = get_bookings_for_user(db, user.id)
        
        # Get upcoming bookings (next 7 days)
        from datetime import datetime, timezone, timedelta
        upcoming_start = datetime.now(timezone.utc)
        upcoming_end = datetime.now(timezone.utc) + timedelta(days=7)
        
        upcoming_bookings = [
            booking for booking in all_bookings 
            if booking.start_time >= upcoming_start and booking.start_time <= upcoming_end
        ]
        
        # Get available slots
        from app.services.availability_service import get_availability_slots_for_user
        available_slots = get_availability_slots_for_user(db, user.id)
        
        # Format upcoming bookings (both database and calendar-synced)
        formatted_upcoming = []
        for booking in upcoming_bookings:
            formatted_upcoming.append({
                "id": booking.id,
                "title": booking.guest_name,
                "date": booking.start_time.strftime("%Y-%m-%d"),
                "time": booking.start_time.strftime("%H:%M"),
                "end_time": booking.end_time.strftime("%H:%M"),
                "email": booking.guest_email,
                "status": booking.status,
                "source": "calendar" if booking.google_event_id else "database"
            })
        
        # Format available slots
        formatted_slots = []
        for slot in available_slots:
            formatted_slots.append({
                "id": slot.id,
                "date": slot.start_time.strftime("%Y-%m-%d"),
                "start_time": slot.start_time.strftime("%H:%M"),
                "end_time": slot.end_time.strftime("%H:%M"),
                "duration": int((slot.end_time - slot.start_time).total_seconds() / 60)
            })
        
        # Calculate stats from database
        upcoming_count = len(formatted_upcoming)
        total_bookings = len(all_bookings)
        available_count = len(formatted_slots)
        
        # Count calendar vs database bookings
        calendar_bookings = len([b for b in all_bookings if b.google_event_id])
        database_bookings = len([b for b in all_bookings if not b.google_event_id])
        
        return {
            "upcomingBookings": formatted_upcoming,
            "allBookings": all_bookings,
            "availableSlots": formatted_slots,
            "upcomingCount": upcoming_count,
            "totalBookings": total_bookings,
            "availableCount": available_count,
            "calendarConnected": user.google_calendar_connected,
            "calendarBookings": calendar_bookings,
            "databaseBookings": database_bookings
        }
        
    except Exception as e:
        print(f"Error in get_dashboard_data: {e}")
        return {"error": str(e)}


@router.get("/dashboard/api/user/status")
async def get_user_status(request: Request, db: Session = Depends(get_db)):
    """Get user status and calendar connection info"""
    access_token = request.cookies.get("access_token")
    if not access_token:
        return {"user_exists": False, "error": "Not authenticated"}
    
    try:
        payload = verify_token(access_token)
        if not payload:
            return {"user_exists": False, "error": "Invalid token"}
        
        user_email = payload.get("sub")
        user = get_user_by_email(db, user_email)
        
        if not user:
            return {"user_exists": False, "error": "User not found"}
        
        # Check calendar connection
        calendar_connected = bool(user.google_access_token and user.google_refresh_token)
        
        return {
            "user_exists": True,
            "user_id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "calendar_connected": calendar_connected,
            "is_verified": user.is_verified
        }
        
    except Exception as e:
        print(f"Error in get_user_status: {e}")
        return {"user_exists": False, "error": str(e)}


@router.post("/dashboard/api/calendar/refresh-tokens")
async def refresh_calendar_tokens_endpoint(request: Request, db: Session = Depends(get_db)):
    """Refresh Google Calendar tokens"""
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
        
        if not user.google_access_token or not user.google_refresh_token:
            return {"error": "No Google Calendar tokens found"}
        
        # Refresh tokens
        # calendar_service = GoogleCalendarService(
        #     access_token=user.google_access_token,
        #     refresh_token=user.google_refresh_token,
        #     db=db,
        #     user_id=user.id
        # )
        
        # # This will automatically refresh tokens if needed
        # try:
        #     # Test the connection
        #     calendar_service.get_events(
        #         start_date=datetime.now(timezone.utc),
        #         end_date=datetime.now(timezone.utc) + timedelta(days=1)
        #     )
        #     return {"success": True, "message": "Calendar connection refreshed successfully"}
        # except Exception as e:
        #     return {"error": f"Failed to refresh calendar connection: {str(e)}"}
        
        # Placeholder for actual token refresh logic if needed
        return {"success": True, "message": "Calendar connection refresh is not yet implemented."}
        
    except Exception as e:
        print(f"Error in refresh_calendar_tokens: {e}")
        return {"error": str(e)}


@router.post("/dashboard/api/sync-calendar")
async def sync_calendar_endpoint(request: Request, db: Session = Depends(get_db)):
    """Sync calendar events to database"""
    print("🔄 SYNC START: Calendar sync endpoint called")
    
    access_token = request.cookies.get("access_token")
    if not access_token:
        print("❌ SYNC ERROR: No access token")
        return {"success": False, "error": "Not authenticated"}
    
    try:
        print("🔍 SYNC STEP 1: Verifying token...")
        payload = verify_token(access_token)
        if not payload:
            print("❌ SYNC ERROR: Invalid token")
            return {"success": False, "error": "Invalid token"}
        
        user_email = payload.get("sub")
        print(f"👤 SYNC STEP 2: Getting user for email: {user_email}")
        user = get_user_by_email(db, user_email)
        
        if not user:
            print("❌ SYNC ERROR: User not found")
            return {"success": False, "error": "User not found"}
        
        print(f"✅ SYNC STEP 3: User found - ID: {user.id}, Calendar connected: {user.google_calendar_connected}")
        
        if not user.google_access_token or not user.google_refresh_token:
            print("❌ SYNC ERROR: Calendar not connected - missing tokens")
            return {"success": False, "error": "Calendar not connected"}
        
        print("🔗 SYNC STEP 4: Calendar tokens found, initializing sync service...")
        
        # Import and use the background sync service
        from app.services.sync.background_sync import BackgroundSyncService
        sync_service = BackgroundSyncService()
        
        print("🚀 SYNC STEP 5: Starting calendar to database sync...")
        
        # Perform calendar to database sync
        import asyncio
        try:
            sync_result = await sync_service.sync_calendar_to_database(db, user.id)
            print(f"📊 SYNC STEP 6: Sync completed - Result: {sync_result}")
        except Exception as e:
            print(f"❌ SYNC ERROR: Exception during sync: {str(e)}")
            return {
                "success": False,
                "error": f"Sync failed: {str(e)}"
            }
        
        if not sync_result.get("success"):
            print(f"❌ SYNC ERROR: Sync returned failure: {sync_result}")
            return {
                "success": False, 
                "error": sync_result.get("error", "Unknown sync error")
            }
        
        print(f"✅ SYNC SUCCESS: Events created: {sync_result.get('events_created', 0)}, Updated: {sync_result.get('events_updated', 0)}, Total: {sync_result.get('total_events_processed', 0)}")
        
        return {
            "success": True,
            "message": "Calendar synced successfully",
            "events_created": sync_result.get("events_created", 0),
            "events_updated": sync_result.get("events_updated", 0),
            "total_events_processed": sync_result.get("total_events_processed", 0)
        }
        
    except Exception as e:
        print(f"❌ SYNC ERROR: Unexpected error in sync_calendar_endpoint: {e}")
        return {"success": False, "error": str(e)}


@router.post("/dashboard/api/chat")
async def chat_with_ai(request: Request, db: Session = Depends(get_db)):
    """Chat with AI agent"""
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
        
        # Get JSON data
        body = await request.json()
        message = body.get("message", "")
        
        if not message:
            return {"error": "No message provided"}
        
        # Initialize AI agent service
        from app.services.agent.intelligent_agent_service import IntelligentAgentService
        agent_service = IntelligentAgentService(db)
        
        # Process message with AI agent
        result = await agent_service.process_message(
            user_id=user.id,
            message=message
        )
        
        # Extract response from AI agent
        ai_response = result.get("message", "I'm here to help with your scheduling needs!")
        
        return {
            "response": ai_response,
            "success": True,
            "data": result
        }
        
    except Exception as e:
        print(f"Error in chat_with_ai: {e}")
        return {"error": str(e)} 