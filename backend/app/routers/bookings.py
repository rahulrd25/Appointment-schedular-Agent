from fastapi import APIRouter, Request, Form, HTTPException, Depends, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from fastapi.templating import Jinja2Templates
from datetime import datetime, timedelta, timezone

from app.core.database import get_db
from app.services.user_service import get_user_by_email
from app.core.security import verify_token
from app.services.booking_service import (
    get_filtered_bookings_for_template,
    get_booking_details,
    can_cancel_booking,
    can_reschedule_booking,
    cancel_booking_by_id,
    reschedule_booking_by_id
)
from app.services.availability_service import get_available_slots_for_booking

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/bookings")
async def bookings_page(request: Request, db: Session = Depends(get_db)):
    """Bookings page"""
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


@router.get("/bookings/api/list")
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
        
        # Get filtered bookings from service
        all_bookings_for_template = get_filtered_bookings_for_template(
            db, user.id, user, status_filter, time_filter, search_filter
        )
        
        return templates.TemplateResponse("bookings_list.html", {
            "request": request,
            "bookings": all_bookings_for_template
        })
        
    except Exception as e:
        print(f"Error in get_bookings_list: {e}")
        return {"error": str(e)}


@router.get("/bookings/api/data")
async def get_bookings_data(request: Request, db: Session = Depends(get_db)):
    """Get bookings data for dashboard with calendar integration."""
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
        all_db_bookings = get_bookings_for_user(db, user.id)
        
        # Use timezone-aware current time for database comparisons
        current_time = datetime.now()
        upcoming_bookings = []
        
        for booking in all_db_bookings:
            # Ensure both times are timezone-aware for comparison
            booking_time = booking.start_time
            if booking_time.tzinfo is None:
                # If booking time is naive, assume UTC
                booking_time = booking_time.replace(tzinfo=timezone.utc)
            
            if current_time.tzinfo is None:
                # If current time is naive, assume UTC
                current_time = current_time.replace(tzinfo=timezone.utc)
            
            if booking_time > current_time:
                upcoming_bookings.append(booking)
        
        # Convert all bookings to dashboard format (both database and calendar-synced)
        all_bookings = []
        for booking in upcoming_bookings:
            all_bookings.append({
                "id": booking.id,
                "title": booking.guest_name,
                "date": booking.start_time.strftime("%Y-%m-%d"),
                "time": booking.start_time.strftime("%H:%M"),
                "end_time": booking.end_time.strftime("%H:%M"),
                "email": booking.guest_email,
                "status": booking.status,
                "source": "calendar" if booking.google_event_id else "database",
                "guest_message": booking.guest_message,
                "datetime": booking.start_time,
                "calendar_id": booking.google_event_id if booking.google_event_id else None,
                "description": None,  # Database bookings don't have description field
                "location": None      # Database bookings don't have location field
            })
        
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


@router.get("/bookings/api/stats")
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
        
        # Get all bookings from database (includes both local and calendar-synced)
        from app.services.booking_service import get_bookings_for_user
        all_bookings = get_bookings_for_user(db, user.id)
        
        # Count all bookings by status
        total_bookings = len(all_bookings)
        confirmed_bookings = len([b for b in all_bookings if b.status == "confirmed"])
        cancelled_bookings = len([b for b in all_bookings if b.status == "cancelled"])
        upcoming_bookings = len([b for b in all_bookings if b.start_time > datetime.now(timezone.utc)])
        
        # Count calendar vs database bookings
        calendar_bookings = len([b for b in all_bookings if b.google_event_id])
        database_bookings = len([b for b in all_bookings if not b.google_event_id])
        
        # Render the stats template
        from fastapi.templating import Jinja2Templates
        templates = Jinja2Templates(directory="app/templates")
        
        return templates.TemplateResponse("booking_stats.html", {
            "request": request,
            "total": total_bookings,
            "confirmed": confirmed_bookings,
            "cancelled": cancelled_bookings,
            "upcoming": upcoming_bookings,
            "calendarBookings": calendar_bookings,
            "databaseBookings": database_bookings
        })
        
    except Exception as e:
        print(f"Error in get_bookings_stats: {e}")
        return {"error": str(e)}


@router.get("/bookings/api/{booking_id}/details")
async def get_booking_details_modal(
    booking_id: str,
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

        booking_details = get_booking_details(db, booking_id, user)
        if not booking_details:
            raise HTTPException(status_code=404, detail="Booking not found")

        return templates.TemplateResponse("booking_details_modal.html", {
            "request": request,
            "booking": booking_details,
            "current_user": user
        })

    except Exception as e:
        print(f"Get booking details error: {e}")
        raise HTTPException(status_code=500, detail="Failed to load booking details")


@router.get("/bookings/api/{booking_id}/reschedule-form")
async def get_reschedule_form(
    booking_id: str,
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

        # Check if booking can be rescheduled
        if not can_reschedule_booking(db, booking_id, user):
            raise HTTPException(status_code=400, detail="Booking cannot be rescheduled")
        
        booking_details = get_booking_details(db, booking_id, user)
        if not booking_details:
            raise HTTPException(status_code=404, detail="Booking not found")

        return templates.TemplateResponse("reschedule_form.html", {
            "request": request,
            "booking_id": booking_id,
            "booking": booking_details,
            "current_user": user,
            "today": datetime.now().strftime('%Y-%m-%d')
        })

    except Exception as e:
        print(f"Get reschedule form error: {e}")
        raise HTTPException(status_code=500, detail="Failed to load reschedule form")


@router.get("/bookings/api/{booking_id}/cancel-confirmation")
async def get_cancel_confirmation(
    booking_id: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """Get cancel confirmation form for modal display"""
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

        # Check if booking can be cancelled
        if not can_cancel_booking(db, booking_id, user):
            raise HTTPException(status_code=400, detail="Booking cannot be cancelled")
        
        booking_details = get_booking_details(db, booking_id, user)
        if not booking_details:
            raise HTTPException(status_code=404, detail="Booking not found")

        return templates.TemplateResponse("cancel_confirmation.html", {
            "request": request,
            "booking_id": booking_id,
            "booking": booking_details,
            "current_user": user
        })

    except Exception as e:
        print(f"Get cancel confirmation error: {e}")
        raise HTTPException(status_code=500, detail="Failed to load cancel confirmation")


@router.post("/bookings/api/{booking_id}/cancel")
async def cancel_booking_endpoint(
    booking_id: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """Cancel a booking"""
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

        # Cancel the booking
        result = cancel_booking_by_id(db, booking_id, user)
        
        if result["success"]:
            return templates.TemplateResponse("cancel_success.html", {
                "request": request,
                "status": "success",
                "message": result["message"],
                "current_user": user
            })
        else:
            return templates.TemplateResponse("cancel_success.html", {
                "request": request,
                "status": "failed",
                "message": result["message"],
                "current_user": user
            })

    except Exception as e:
        print(f"Cancel booking error: {e}")
        return templates.TemplateResponse("cancel_success.html", {
            "request": request,
            "status": "failed",
            "message": f"Failed to cancel booking: {str(e)}",
            "current_user": user
        })


@router.post("/bookings/api/{booking_id}/reschedule")
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

        # Get form data
        form_data = await request.form()
        new_date = form_data.get("new_date")
        new_time = form_data.get("new_time")
        reason = form_data.get("reason", "")

        if not new_date or not new_time:
            raise HTTPException(status_code=400, detail="Missing date or time")

        # Parse new date and time
        try:
            # Combine date and time
            datetime_str = f"{new_date} {new_time}"
            new_start_time = datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
            
            # Calculate end time (assuming 30 minutes duration)
            new_end_time = new_start_time + timedelta(minutes=30)
            
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid date/time format: {str(e)}")

        # Reschedule the booking
        result = reschedule_booking_by_id(db, booking_id, new_start_time, new_end_time, user, reason)
        
        if result["success"]:
            return templates.TemplateResponse("reschedule_success.html", {
                "request": request,
                "status": "success",
                "message": result["message"],
                "current_user": user
            })
        else:
            return templates.TemplateResponse("reschedule_success.html", {
                "request": request,
                "status": "failed",
                "message": result["message"],
                "current_user": user
            })

    except Exception as e:
        print(f"Reschedule booking error: {e}")
        return templates.TemplateResponse("reschedule_success.html", {
            "request": request,
            "status": "failed",
            "message": f"Failed to reschedule booking: {str(e)}",
            "current_user": user
        })


@router.get("/bookings/api/{booking_id}/available-slots")
async def get_available_slots_for_reschedule(
    booking_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """Get available slots for rescheduling"""
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
        date = request.query_params.get("date")
        if not date:
            raise HTTPException(status_code=400, detail="Date parameter required")

        # Parse date
        try:
            date_obj = datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format")

        # Get available slots for the date
        slots = get_available_slots_for_booking(db, user.id, date_obj)
        
        return templates.TemplateResponse("reschedule_time_slots.html", {
            "request": request,
            "slots": slots,
            "booking_id": booking_id,
            "selected_time_display": "",
            "current_date": date
        })

    except Exception as e:
        print(f"Get available slots error: {e}")
        return templates.TemplateResponse("reschedule_time_slots.html", {
            "request": request,
            "slots": [],
            "error": f"Failed to load available slots: {str(e)}",
            "selected_time_display": ""
        })


@router.post("/bookings/api/{booking_id}/select-time")
async def select_time_for_reschedule(
    booking_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """Handle time slot selection for rescheduling"""
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
        selected_time = form_data.get("selected_time")
        selected_date = form_data.get("selected_date")
        
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
            "selected_time_display": selected_time_display,
            "current_date": selected_date
        })

    except Exception as e:
        print(f"Select time error: {e}")
        return templates.TemplateResponse("reschedule_time_slots.html", {
            "request": request,
            "slots": [],
            "error": f"Failed to process time selection: {str(e)}",
            "selected_time_display": ""
        }) 