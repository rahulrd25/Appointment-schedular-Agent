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
        
        # Get database bookings
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
        all_bookings = []
        for booking in upcoming_db_bookings:
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
                    event_start_dt = datetime.fromisoformat(event_start.replace('Z', '+00:00'))
                else:
                    event_start_dt = datetime.fromisoformat(event_start)
                
                if event_start_dt > datetime.now(timezone.utc):
                    upcoming_calendar += 1
        
        # Calculate totals
        total_bookings = total_db + total_calendar
        total_upcoming = upcoming_db + upcoming_calendar
        
        # Render the stats template
        from fastapi.templating import Jinja2Templates
        templates = Jinja2Templates(directory="app/templates")
        
        return templates.TemplateResponse("booking_stats.html", {
            "request": request,
            "total": total_bookings,
            "confirmed": confirmed_db,
            "cancelled": cancelled_db,
            "upcoming": total_upcoming
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