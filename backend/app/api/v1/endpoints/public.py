from typing import Any, List
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from app.models.models import User as UserModel
from app.services.user_service import get_user_by_scheduling_slug
from app.services.availability_service import get_available_slots_for_booking, AvailabilityService
from app.services.booking_service import create_booking
from app.schemas.schemas import PublicBookingCreate, BookingConfirmation
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.timezone_utils import TimezoneManager
from zoneinfo import ZoneInfo

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/{scheduling_slug}", response_class=HTMLResponse)
async def get_public_scheduling_page(
    request: Request,
    scheduling_slug: str,
    db: Session = Depends(get_db),
) -> Any:
    """Render the public booking page for a given scheduling slug."""
    user = await get_user_by_scheduling_slug(db, scheduling_slug)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return templates.TemplateResponse(
        "public_scheduling_page.html", {
            "request": request, 
            "user": user
        }
    )


@router.get("/{scheduling_slug}/availability")
async def get_user_availability(
    scheduling_slug: str,
    date: str,
    db: Session = Depends(get_db),
) -> JSONResponse:
    """Get available time slots for a specific date."""
    user = await get_user_by_scheduling_slug(db, scheduling_slug)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    try:
        # Parse the date and treat it as local time (user's timezone)
        selected_date = datetime.strptime(date, "%Y-%m-%d")
        
        # Get available slots for this date
        availability_service = AvailabilityService(db)
        available_slots = availability_service.get_user_availability_slots(
            user_id=user.id,
            date=selected_date,
            duration_minutes=30
        )
        
        # Get user's timezone
        host_timezone = TimezoneManager.get_user_timezone(user.timezone)
        
        # Format slots for frontend with timezone conversion
        formatted_slots = []
        for slot in available_slots:
            # Parse the ISO string back to datetime
            start_time = datetime.fromisoformat(slot['start_time'])
            end_time = datetime.fromisoformat(slot['end_time'])
            
            # Ensure times are timezone-aware (should be UTC from database)
            if start_time.tzinfo is None:
                start_time = start_time.replace(tzinfo=timezone.utc)
            if end_time.tzinfo is None:
                end_time = end_time.replace(tzinfo=timezone.utc)
            
            # Convert to user's timezone for display
            user_start_time = start_time.astimezone(ZoneInfo(host_timezone))
            user_end_time = end_time.astimezone(ZoneInfo(host_timezone))
            
            formatted_slots.append({
                'start_time': user_start_time.strftime('%I:%M %p'),
                'end_time': user_end_time.strftime('%I:%M %p'),
                'start_time_iso': slot['start_time'],
                'end_time_iso': slot['end_time'],
                'slot_id': slot.get('id')
            })
        
        return JSONResponse({
            "available_slots": formatted_slots,
            "date": date,
            "timezone": host_timezone
        })
        
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")


@router.post("/{scheduling_slug}/book")
async def create_public_scheduling(
    scheduling_slug: str,
    guest_name: str = Form(...),
    guest_email: str = Form(...),
    guest_phone: str = Form(None),
    guest_notes: str = Form(None),
    selected_date: str = Form(...),
    selected_time: str = Form(...),
    guest_timezone: str = Form(None),  # Guest's timezone
    db: Session = Depends(get_db),
) -> JSONResponse:
    """Create a booking for the public interface."""
    user = await get_user_by_scheduling_slug(db, scheduling_slug)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    try:
        # Get host's timezone
        host_timezone = TimezoneManager.get_user_timezone(user.timezone)
        
        # Parse the selected date and time from guest's timezone
        guest_tz = guest_timezone or "UTC"
        
        # Parse the datetime from guest's timezone and convert to UTC
        guest_start_utc = None
        try:
            # Parse the selected_time (it's already an ISO string from the frontend)
            guest_start_time = datetime.fromisoformat(selected_time)
            
            # The selected_time is already timezone-aware, so convert directly to UTC
            guest_start_utc = guest_start_time.astimezone(timezone.utc)
            
            # Convert UTC to host timezone for display purposes
            host_start_time = guest_start_utc.astimezone(ZoneInfo(host_timezone))
            host_end_time = host_start_time + timedelta(minutes=30)
        except Exception as timezone_error:
            # Fallback: try to parse as naive datetime and assume UTC
            try:
                host_start_time = datetime.fromisoformat(selected_time)
                if host_start_time.tzinfo is None:
                    host_start_time = host_start_time.replace(tzinfo=timezone.utc)
                guest_start_utc = host_start_time
                host_end_time = host_start_time + timedelta(minutes=30)
            except Exception as fallback_error:
                raise HTTPException(status_code=400, detail=f"Invalid time format: {str(fallback_error)}")
        
        # Find the availability slot
        availability_service = AvailabilityService(db)
        available_slots = availability_service.get_user_availability_slots(
            user_id=user.id,
            date=host_start_time.date(),
            duration_minutes=30
        )
        
        # Find matching slot
        matching_slot = None
        
        for slot in available_slots:
            try:
                slot_start = datetime.fromisoformat(slot['start_time'])
                # Ensure slot_start is timezone-aware
                if slot_start.tzinfo is None:
                    slot_start = slot_start.replace(tzinfo=timezone.utc)
                
                # Convert both times to UTC for comparison
                slot_start_utc = slot_start.astimezone(timezone.utc) if slot_start.tzinfo else slot_start.replace(tzinfo=timezone.utc)
                
                # Compare times in UTC (allow 5-minute tolerance)
                time_diff = abs((slot_start_utc - guest_start_utc).total_seconds())
                
                if time_diff <= 300:  # 5 minutes tolerance
                    matching_slot = slot
                    break
            except Exception as slot_error:
                continue
        
        if not matching_slot:
            raise HTTPException(status_code=400, detail="Selected time slot is not available")
        
        # Get the actual availability slot from database
        slot_id = matching_slot.get('id')
        if not slot_id:
            raise HTTPException(status_code=400, detail="Invalid slot data")
        
        # Verify the slot is still available
        from app.services.availability_service import check_slot_availability
        try:
            if not check_slot_availability(db, slot_id):
                raise HTTPException(status_code=400, detail="Selected time slot is no longer available")
        except Exception as slot_error:
            raise HTTPException(status_code=400, detail=f"Error checking slot availability: {str(slot_error)}")
        
        # Create booking data
        booking_data = PublicBookingCreate(
            guest_name=guest_name,
            guest_email=guest_email,
            guest_message=guest_notes or ""
        )
        
        # Create the booking
        try:
            booking = create_booking(db, booking_data, slot_id, user)
            
            if not booking:
                raise HTTPException(status_code=400, detail="Unable to create booking. Slot may no longer be available.")
        except Exception as booking_error:
            raise HTTPException(status_code=500, detail=f"Error creating booking: {str(booking_error)}")
        
        return JSONResponse({
            "success": True,
            "message": "Booking confirmed successfully!",
            "booking_id": booking.id,
            "email_sent": True,
            "host_timezone": host_timezone,
            "guest_timezone": guest_tz
        })
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date/time format: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Booking failed: {str(e)}")



