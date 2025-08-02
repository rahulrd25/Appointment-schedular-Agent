from fastapi import APIRouter, Request, Form, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from fastapi.templating import Jinja2Templates
from datetime import datetime, timezone

from app.core.database import get_db
from app.core.security import verify_token
from app.services.user_service import get_user_by_email
from app.services.booking_service import (
    get_bookings_for_user, 
    get_booking, 
    cancel_booking_by_id,
    reschedule_booking_by_id,
    get_booking_details
)
from app.services.availability_service import get_available_slots_for_booking
from app.services.notification_service import NotificationService

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/bookings")
async def bookings_page(request: Request, db: Session = Depends(get_db)):
    """Bookings page for user account management"""
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

        return templates.TemplateResponse("bookings.html", {
            "request": request,
            "current_user": user
        })

    except Exception as e:
        print(f"Bookings error: {e}")
        return RedirectResponse(url="/", status_code=302)


@router.get("/bookings/api/data")
async def get_bookings_data(request: Request, db: Session = Depends(get_db)):
    """Get bookings data for the bookings page"""
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
        
        # Get user's bookings from database
        from app.services.booking_service import get_bookings_for_user
        db_bookings = get_bookings_for_user(db, user.id)
        
        # Convert database bookings to bookings format
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
                "guest_message": booking.guest_message
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
    """Get booking statistics"""
    access_token = request.cookies.get("access_token")
    if not access_token:
        return HTMLResponse('<div class="text-red-600 text-sm">Not authenticated</div>', status_code=401)
    
    try:
        payload = verify_token(access_token)
        if not payload:
            return HTMLResponse('<div class="text-red-600 text-sm">Invalid token</div>', status_code=401)
        
        user_email = payload.get("sub")
        user = get_user_by_email(db, user_email)
        
        if not user:
            return HTMLResponse('<div class="text-red-600 text-sm">User not found</div>', status_code=404)
        
        # Get database bookings
        from app.services.booking_service import get_bookings_for_user
        db_bookings = get_bookings_for_user(db, user.id)
        
        # Count database bookings by status
        total_db = len(db_bookings)
        confirmed_db = len([b for b in db_bookings if b.status == "confirmed"])
        cancelled_db = len([b for b in db_bookings if b.status == "cancelled"])
        upcoming_db = len([b for b in db_bookings if b.start_time > datetime.now(timezone.utc)])
        
        # Calculate total stats (database only for now)
        total_bookings = total_db
        total_upcoming = upcoming_db
        total_confirmed = confirmed_db
        total_cancelled = cancelled_db
        
        # Return HTML for stats cards
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
        return HTMLResponse(f'<div class="text-red-600 text-sm">Error: {str(e)}</div>', status_code=500)


@router.get("/bookings/api/list")
async def get_bookings_list(request: Request, db: Session = Depends(get_db)):
    """Get formatted bookings list for display"""
    access_token = request.cookies.get("access_token")
    if not access_token:
        return HTMLResponse('<div class="text-red-600 text-sm">Not authenticated</div>', status_code=401)
    
    try:
        payload = verify_token(access_token)
        if not payload:
            return HTMLResponse('<div class="text-red-600 text-sm">Invalid token</div>', status_code=401)
        
        user_email = payload.get("sub")
        user = get_user_by_email(db, user_email)
        
        if not user:
            return HTMLResponse('<div class="text-red-600 text-sm">User not found</div>', status_code=404)
        
        # Get all bookings from database
        all_bookings = get_bookings_for_user(db, user.id)
        
        if not all_bookings:
            return HTMLResponse("""
                <div class="text-center py-8">
                    <div class="text-gray-500 text-lg mb-2">No bookings found</div>
                    <div class="text-gray-400 text-sm">Create some availability slots to start receiving bookings</div>
                </div>
            """)
        
        # Generate HTML for bookings list
        bookings_html = ""
        for booking in all_bookings:
            status_color = {
                "confirmed": "bg-green-100 text-green-800",
                "pending": "bg-yellow-100 text-yellow-800", 
                "cancelled": "bg-red-100 text-red-800"
            }.get(booking.status, "bg-gray-100 text-gray-800")
            
            bookings_html += f"""
                <div class="booking-card bg-white rounded-lg shadow-sm border border-gray-200 p-4 mb-4">
                    <div class="flex items-center justify-between">
                        <div class="flex-1">
                            <div class="flex items-center gap-3 mb-2">
                                <h3 class="text-lg font-semibold text-gray-900">{booking.guest_name}</h3>
                                <span class="px-2 py-1 rounded-full text-xs font-medium {status_color}">
                                    {booking.status.title()}
                                </span>
                            </div>
                            <div class="text-sm text-gray-600 mb-1">
                                <span class="font-medium">Email:</span> {booking.guest_email}
                            </div>
                            <div class="text-sm text-gray-600 mb-1">
                                <span class="font-medium">Time:</span> {booking.start_time.strftime('%B %d, %Y at %I:%M %p')} - {booking.end_time.strftime('%I:%M %p')}
                            </div>
                            {f'<div class="text-sm text-gray-600 mb-2"><span class="font-medium">Message:</span> {booking.guest_message}</div>' if booking.guest_message else ''}
                        </div>
                        <div class="flex items-center gap-2">
                            <button onclick="showBookingDetails('{booking.id}')" 
                                    class="btn-secondary px-3 py-1 text-sm">
                                Details
                            </button>
                            {f'<button onclick="showRescheduleForm(\'{booking.id}\')" class="btn-secondary px-3 py-1 text-sm">Reschedule</button>' if booking.status == 'confirmed' else ''}
                            {f'<button onclick="showCancelConfirmation(\'{booking.id}\')" class="btn-danger px-3 py-1 text-sm">Cancel</button>' if booking.status == 'confirmed' else ''}
                        </div>
                    </div>
                </div>
            """
        
        return HTMLResponse(bookings_html)
        
    except Exception as e:
        print(f"Error in get_bookings_list: {e}")
        return HTMLResponse(f'<div class="text-red-600 text-sm">Error: {str(e)}</div>', status_code=500)


@router.post("/bookings/api/{booking_id}/cancel")
async def cancel_booking_endpoint(
    booking_id: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """Cancel a booking"""
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
        
        # Cancel the booking
        result = cancel_booking_by_id(db, booking_id, user)
        
        if result["success"]:
            return {"success": True, "message": "Booking cancelled successfully"}
        else:
            return {"success": False, "error": result["error"]}
        
    except Exception as e:
        print(f"Error cancelling booking: {e}")
        return {"success": False, "error": str(e)}


@router.post("/bookings/api/{booking_id}/reschedule")
async def reschedule_booking_endpoint(
    booking_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """Reschedule a booking"""
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
        
        # Get form data
        form_data = await request.form()
        new_start_time = form_data.get("new_start_time")
        new_end_time = form_data.get("new_end_time")
        reason = form_data.get("reason", "")
        
        if not new_start_time or not new_end_time:
            return {"success": False, "error": "New start and end times are required"}
        
        # Parse datetime
        from datetime import datetime
        try:
            new_start = datetime.fromisoformat(new_start_time.replace('Z', '+00:00'))
            new_end = datetime.fromisoformat(new_end_time.replace('Z', '+00:00'))
        except ValueError:
            return {"success": False, "error": "Invalid datetime format"}
        
        # Reschedule the booking
        result = reschedule_booking_by_id(db, booking_id, new_start, new_end, user, reason)
        
        if result["success"]:
            return {"success": True, "message": "Booking rescheduled successfully"}
        else:
            return {"success": False, "error": result["error"]}
        
    except Exception as e:
        print(f"Error rescheduling booking: {e}")
        return {"success": False, "error": str(e)}


@router.get("/bookings/api/{booking_id}/details")
async def get_booking_details_modal(
    booking_id: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """Get booking details for modal"""
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
        
        # Get booking details
        booking_details = get_booking_details(db, booking_id, user)
        
        if booking_details:
            return templates.TemplateResponse("booking_details_modal.html", {
                "request": request,
                "booking": booking_details,
                "current_user": user
            })
        else:
            return {"error": "Booking not found"}
        
    except Exception as e:
        print(f"Error getting booking details: {e}")
        return {"error": str(e)}


@router.get("/bookings/api/{booking_id}/reschedule-form")
async def get_reschedule_form(
    booking_id: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """Get reschedule form for modal"""
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
        
        # Get booking details
        booking_details = get_booking_details(db, booking_id, user)
        
        if booking_details:
            return templates.TemplateResponse("reschedule_form.html", {
                "request": request,
                "booking": booking_details,
                "current_user": user
            })
        else:
            return {"error": "Booking not found"}
        
    except Exception as e:
        print(f"Error getting reschedule form: {e}")
        return {"error": str(e)}


@router.get("/bookings/api/{booking_id}/cancel-confirmation")
async def get_cancel_confirmation(
    booking_id: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """Get cancel confirmation modal"""
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
        
        # Get booking details
        booking_details = get_booking_details(db, booking_id, user)
        
        if booking_details:
            return templates.TemplateResponse("cancel_confirmation.html", {
                "request": request,
                "booking": booking_details,
                "current_user": user
            })
        else:
            return {"error": "Booking not found"}
        
    except Exception as e:
        print(f"Error getting cancel confirmation: {e}")
        return {"error": str(e)}


@router.get("/bookings/api/{booking_id}/send-email-form")
async def get_send_email_form(
    booking_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """Get send email form for modal"""
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
        
        # Get booking details
        booking_details = get_booking_details(db, str(booking_id), user)
        
        if booking_details:
            return templates.TemplateResponse("send_email_modal.html", {
                "request": request,
                "booking": booking_details,
                "current_user": user
            })
        else:
            return {"error": "Booking not found"}
        
    except Exception as e:
        print(f"Error getting send email form: {e}")
        return {"error": str(e)}


@router.post("/bookings/api/{booking_id}/send-email")
async def send_email_to_guest(
    booking_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """Send email to guest"""
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
        
        # Get form data
        form_data = await request.form()
        subject = form_data.get("subject", "")
        message = form_data.get("message", "")
        
        if not subject or not message:
            return {"success": False, "error": "Subject and message are required"}
        
        # Get booking details
        booking_details = get_booking_details(db, str(booking_id), user)
        
        if not booking_details:
            return {"success": False, "error": "Booking not found"}
        
        # Send email
        notification_service = NotificationService()
        result = notification_service.send_custom_email(
            to_email=booking_details["guest_email"],
            subject=subject,
            message=message,
            host_email=user.email,
            host_name=user.full_name
        )
        
        if result["success"]:
            return {"success": True, "message": "Email sent successfully"}
        else:
            return {"success": False, "error": result["error"]}
        
    except Exception as e:
        print(f"Error sending email: {e}")
        return {"success": False, "error": str(e)}


@router.get("/bookings/api/{booking_id}/available-slots")
async def get_available_slots_for_reschedule(
    booking_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """Get available slots for rescheduling"""
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
        available_slots = get_available_slots_for_booking(db, user.id)
        
        # Format slots for display
        formatted_slots = []
        for slot in available_slots:
            formatted_slots.append({
                "id": slot.id,
                "start_time": slot.start_time.strftime('%Y-%m-%dT%H:%M:%S'),
                "end_time": slot.end_time.strftime('%Y-%m-%dT%H:%M:%S'),
                "duration": int((slot.end_time - slot.start_time).total_seconds() / 60)
            })
        
        return {"slots": formatted_slots}
        
    except Exception as e:
        print(f"Error getting available slots: {e}")
        return {"error": str(e)}


@router.post("/bookings/api/{booking_id}/select-time")
async def select_time_for_reschedule(
    booking_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """Select new time for rescheduling"""
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
        
        # Get form data
        form_data = await request.form()
        new_start_time = form_data.get("new_start_time")
        new_end_time = form_data.get("new_end_time")
        reason = form_data.get("reason", "")
        
        if not new_start_time or not new_end_time:
            return {"success": False, "error": "New start and end times are required"}
        
        # Parse datetime
        from datetime import datetime
        try:
            new_start = datetime.fromisoformat(new_start_time.replace('Z', '+00:00'))
            new_end = datetime.fromisoformat(new_end_time.replace('Z', '+00:00'))
        except ValueError:
            return {"success": False, "error": "Invalid datetime format"}
        
        # Reschedule the booking
        result = reschedule_booking_by_id(db, booking_id, new_start, new_end, user, reason)
        
        if result["success"]:
            return templates.TemplateResponse("reschedule_success.html", {
                "request": request,
                "booking": result["booking"],
                "current_user": user
            })
        else:
            return {"success": False, "error": result["error"]}
        
    except Exception as e:
        print(f"Error selecting time for reschedule: {e}")
        return {"success": False, "error": str(e)} 