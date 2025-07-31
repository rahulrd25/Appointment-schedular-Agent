from fastapi import APIRouter, Request, Form, HTTPException, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from fastapi.templating import Jinja2Templates
from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.database import get_db
from app.services.user_service import get_user_by_scheduling_slug
from app.services.availability_service import get_available_slots_for_date
from app.services.booking_service import create_booking

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/{scheduling_slug}", response_class=HTMLResponse)
async def get_public_booking_page(
    request: Request,
    scheduling_slug: str,
    db: Session = Depends(get_db),
) -> Any:
    """Public booking page for a user's scheduling link"""
    try:
        # Get user by scheduling slug
        user = get_user_by_scheduling_slug(db, scheduling_slug)
        
        if not user:
            raise HTTPException(status_code=404, detail="Scheduling page not found")
        
        return templates.TemplateResponse("public_booking_all_in_one.html", {
            "request": request,
            "user": user,
            "scheduling_slug": scheduling_slug
        })
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        print(f"Public booking page error: {e}")
        raise HTTPException(status_code=500, detail="Failed to load booking page")


@router.get("/api/v1/public/{user_slug}/availability")
async def get_public_available_slots(
    user_slug: str,
    date: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """Get available slots for public booking page"""
    try:
        # Get user by slug
        user = get_user_by_scheduling_slug(db, user_slug)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Parse date
        try:
            date_obj = datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format")
        
        # Get available slots
        slots = get_available_slots_for_date(db, user.id, date_obj)
        
        # Format slots for API response (matching template expectations)
        available_slots = []
        for slot in slots:
            # Create ISO time string for the template
            slot_datetime = datetime.combine(date_obj, slot.start_time.time())
            available_slots.append({
                "id": slot.id,
                "start_time": slot.start_time.strftime("%H:%M"),
                "start_time_iso": slot_datetime.strftime("%H:%M"),
                "end_time": slot.end_time.strftime("%H:%M"),
                "duration": int((slot.end_time - slot.start_time).total_seconds() / 60)
            })
        
        return {
            "date": date,
            "available_slots": available_slots
        }
        
    except Exception as e:
        print(f"Error getting available slots: {e}")
        raise HTTPException(status_code=500, detail="Failed to get available slots")


@router.post("/api/v1/public/{user_slug}/book")
async def book_slot_with_calendar(
    user_slug: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """Book a slot with calendar integration"""
    try:
        # Get user by slug
        user = get_user_by_scheduling_slug(db, user_slug)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Get form data
        form_data = await request.form()
        guest_name = form_data.get("guest_name")
        guest_email = form_data.get("guest_email")
        selected_date = form_data.get("selected_date")
        selected_time = form_data.get("selected_time")
        guest_message = form_data.get("guest_message", "")
        
        if not all([guest_name, guest_email, selected_date, selected_time]):
            raise HTTPException(status_code=400, detail="Missing required fields")
        
        # Parse date and time
        try:
            datetime_str = f"{selected_date} {selected_time}"
            start_time = datetime.strptime(datetime_str, "%Y-%m-%d %H:%M")
            end_time = start_time + timedelta(minutes=user.meeting_duration or 30)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date/time format")
        
        # Create booking
        booking_data = {
            "guest_name": guest_name,
            "guest_email": guest_email,
            "start_time": start_time,
            "end_time": end_time,
            "guest_message": guest_message,
            "user_id": user.id
        }
        
        result = create_booking(db, booking_data)
        
        if result["success"]:
            return {
                "success": True,
                "message": "Booking created successfully",
                "booking_id": result["booking_id"]
            }
        else:
            raise HTTPException(status_code=400, detail=result["message"])
        
    except Exception as e:
        print(f"Error booking slot: {e}")
        raise HTTPException(status_code=500, detail="Failed to book slot") 