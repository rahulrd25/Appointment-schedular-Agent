from typing import Any, List
from datetime import datetime, timedelta

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
from app.core.timezone_utils import TimezoneManager, parse_user_datetime

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/{scheduling_slug}", response_class=HTMLResponse)
async def get_public_booking_page(
    request: Request,
    scheduling_slug: str,
    db: Session = Depends(get_db),
) -> Any:
    """Render the public booking page for a given scheduling slug."""
    user = get_user_by_scheduling_slug(db, scheduling_slug)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return templates.TemplateResponse(
        "public_booking_all_in_one.html", {
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
    
    user = get_user_by_scheduling_slug(db, scheduling_slug)
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
        
        # Format slots for frontend
        formatted_slots = []
        for slot in available_slots:
            # Parse the ISO string back to datetime
            start_time = datetime.fromisoformat(slot['start_time'])
            end_time = datetime.fromisoformat(slot['end_time'])
            
            formatted_slots.append({
                'start_time': start_time.strftime('%I:%M %p'),
                'end_time': end_time.strftime('%I:%M %p'),
                'start_time_iso': slot['start_time'],
                'end_time_iso': slot['end_time'],
                'slot_id': slot.get('id')
            })
        
        return JSONResponse({
            "available_slots": formatted_slots,
            "date": date
        })
        
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")


@router.post("/{scheduling_slug}/book")
async def create_public_booking(
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
    user = get_user_by_scheduling_slug(db, scheduling_slug)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    try:
        # Get host's timezone
        host_timezone = TimezoneManager.get_user_timezone(user.timezone)
        
        # Parse the selected date and time from guest's timezone
        guest_tz = guest_timezone or "UTC"
        
        # Parse the datetime from guest's timezone and convert to host's timezone
        if selected_time.endswith('Z') or '+' in selected_time:
            # Already in UTC, convert to host timezone
            start_time = datetime.fromisoformat(selected_time.replace('Z', '+00:00'))
            host_start_time = TimezoneManager.convert_from_utc(start_time, host_timezone)
        else:
            # Parse as guest's local time and convert to host timezone
            # selected_time is already an ISO datetime string, so parse it directly
            guest_start_time = datetime.fromisoformat(selected_time)
            # Check if it's already timezone-aware
            if guest_start_time.tzinfo is None:
                # Make it timezone-aware in guest's timezone
                guest_start_time = TimezoneManager.make_timezone_aware(guest_start_time, guest_tz)
            # Convert to host timezone
            host_start_time = TimezoneManager.convert_to_utc(guest_start_time, host_timezone)
        
        # Ensure timezone-aware for consistency
        host_start_time = TimezoneManager.make_timezone_aware(host_start_time, host_timezone)
        host_end_time = host_start_time + timedelta(minutes=30)
        
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
            slot_start = datetime.fromisoformat(slot['start_time'])
            # Convert slot time to host timezone for comparison
            slot_start_host = TimezoneManager.make_timezone_aware(slot_start, host_timezone)
            
            # Compare times (allow 5-minute tolerance for timezone conversion)
            time_diff = abs((slot_start_host - host_start_time).total_seconds())
            if time_diff <= 300:  # 5 minutes tolerance
                matching_slot = slot
                break
        
        if not matching_slot:
            raise HTTPException(status_code=400, detail="Selected time slot is not available")
        
        # Create booking data
        booking_data = PublicBookingCreate(
            guest_name=guest_name,
            guest_email=guest_email,
            guest_message=guest_notes or ""
        )
        
        # Create the booking
        booking = create_booking(db, booking_data, matching_slot['id'], user)
        
        if not booking:
            raise HTTPException(status_code=400, detail="Unable to create booking. Slot may no longer be available.")
        
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



