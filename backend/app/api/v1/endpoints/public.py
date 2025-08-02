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

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/{scheduling_slug}", response_class=HTMLResponse)
async def get_public_booking_page(
    request: Request,
    scheduling_slug: str,
    db: Session = Depends(get_db),
) -> Any:
    """Render the public booking page for a given scheduling slug."""
    user = await get_user_by_scheduling_slug(db, scheduling_slug)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return templates.TemplateResponse(
        "public_booking_all_in_one.html", {
            "request": request, 
            "user": user
        }
    )


@router.get("/api/v1/public/{scheduling_slug}/availability")
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
        
        # Get available slots for this date using database-first approach
        from app.services.availability_service import get_available_slots_for_booking
        available_slots = get_available_slots_for_booking(db, user.id, selected_date)
        
        # Format slots for frontend with timezone conversion
        formatted_slots = []
        import pytz
        user_timezone = pytz.timezone(user.timezone or 'UTC')
        
        for slot in available_slots:
            # Convert to host's timezone for consistent display
            start_local = slot.start_time.astimezone(user_timezone)
            end_local = slot.end_time.astimezone(user_timezone)
            
            formatted_slots.append({
                'start_time': start_local.strftime('%I:%M %p'),
                'end_time': end_local.strftime('%I:%M %p'),
                'start_time_iso': slot.start_time.isoformat(),
                'end_time_iso': slot.end_time.isoformat(),
                'slot_id': slot.id,
                'timezone': user.timezone
            })
        
        return JSONResponse({
            "available_slots": formatted_slots,
            "date": date
        })
        
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")


@router.post("/api/v1/public/{scheduling_slug}/book")
async def create_public_booking(
    scheduling_slug: str,
    guest_name: str = Form(...),
    guest_email: str = Form(...),
    guest_phone: str = Form(None),
    guest_notes: str = Form(None),
    selected_date: str = Form(...),
    selected_time: str = Form(...),
    db: Session = Depends(get_db),
) -> JSONResponse:
    """Create a booking for the public interface."""
    user = await get_user_by_scheduling_slug(db, scheduling_slug)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    try:
        # Parse the selected date and time (now using ISO format)
        date_obj = datetime.strptime(selected_date, "%Y-%m-%d")
        start_time = datetime.fromisoformat(selected_time)
        
        # Ensure timezone-naive for consistency
        start_time = start_time.replace(tzinfo=None) if start_time.tzinfo else start_time
        end_time = start_time + timedelta(minutes=30)
        
        # Find the availability slot
        availability_service = AvailabilityService(db)
        available_slots = availability_service.get_user_availability_slots(
            user_id=user.id,
            date=date_obj,
            duration_minutes=30
        )
        
        # Find matching slot
        matching_slot = None
        for slot in available_slots:
            slot_start = datetime.fromisoformat(slot['start_time'])
            # Ensure both are timezone-naive for comparison
            slot_start_naive = slot_start.replace(tzinfo=None) if slot_start.tzinfo else slot_start
            start_time_naive = start_time.replace(tzinfo=None) if start_time.tzinfo else start_time
            
            # Compare the full datetime (date + time)
            if slot_start_naive == start_time_naive:
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
            "email_sent": True
        })
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date/time format: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Booking failed: {str(e)}")



