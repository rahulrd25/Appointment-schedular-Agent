from fastapi import APIRouter, Request, Form, Depends, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import pytz

from app.api.deps import get_db
from app.core.security import verify_token
from app.services.user_service import get_user_by_email
from app.services.availability_service import create_availability_slot
from app.schemas.schemas import AvailabilitySlotCreate

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/availability")
async def availability_page(request: Request, db: Session = Depends(get_db)):
    """Availability management page"""
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

        # Get all availability slots (including unavailable ones from imported calendar events)
        from app.services.availability_service import get_availability_slots_for_user
        availability_slots = get_availability_slots_for_user(db, user.id, include_unavailable=True)
        
        # Convert slots to user's timezone for display
        user_timezone = pytz.timezone(user.timezone or 'UTC')
        
        for slot in availability_slots:
            # Convert UTC times to user's timezone for display
            slot.start_time_local = slot.start_time.astimezone(user_timezone)
            slot.end_time_local = slot.end_time.astimezone(user_timezone)
        
        return templates.TemplateResponse("availability.html", {
            "request": request,
            "current_user": user,
            "availability_slots": availability_slots
        })

    except Exception as e:
        print(f"Availability page error: {e}")
        return RedirectResponse(url="/", status_code=302)


@router.post("/dashboard/api/availability/")
async def add_dashboard_availability_slot(
    request: Request, 
    date: str = Form(...),
    start_time: str = Form(...),
    period: int = Form(30),
    db: Session = Depends(get_db)
):
    """Add a single availability slot from dashboard"""
    access_token = request.cookies.get("access_token")
    if not access_token:
        return templates.TemplateResponse("availability_response_fragment.html", {
            "request": request,
            "message": "Authentication required. Please log in again.",
            "success": False
        })
    
    try:
        payload = verify_token(access_token)
        if not payload:
            return templates.TemplateResponse("availability_response_fragment.html", {
                "request": request,
                "message": "Invalid session. Please log in again.",
                "success": False
            })
        
        user_email = payload.get("sub")
        user = get_user_by_email(db, user_email)
        if not user:
            return templates.TemplateResponse("availability_response_fragment.html", {
                "request": request,
                "message": "User not found. Please log in again.",
                "success": False
            })
        
        # Parse date and time in user's timezone
        try:
            # Get user's timezone (default to UTC if not set)
            user_timezone = pytz.timezone(user.timezone or 'UTC')
            
            # Parse the datetime in user's timezone
            naive_datetime = datetime.strptime(f"{date} {start_time}", "%Y-%m-%d %H:%M")
            local_datetime = user_timezone.localize(naive_datetime)
            
            # Calculate end time in user's local timezone first
            local_end_datetime = local_datetime + timedelta(minutes=period)
            
            # Convert both to UTC for database storage
            start_datetime = local_datetime.astimezone(pytz.UTC)
            end_datetime = local_end_datetime.astimezone(pytz.UTC)
            
        except ValueError as e:
            return templates.TemplateResponse("availability_response_fragment.html", {
                "request": request,
                "message": f"Invalid date or time format: {str(e)}",
                "success": False
            })
        except Exception as e:
            return templates.TemplateResponse("availability_response_fragment.html", {
                "request": request,
                "message": f"Timezone error: {str(e)}",
                "success": False
            })
        
        # Create the availability slot
        slot_data = AvailabilitySlotCreate(
            user_id=user.id,
            start_time=start_datetime,
            end_time=end_datetime
        )
        
        result = create_availability_slot(db, slot_data, user.id)
        
        if result.get("success"):
            return templates.TemplateResponse("availability_response_fragment.html", {
                "request": request,
                "message": f"✅ Availability slot created successfully for {date} at {start_time}",
                "success": True
            })
        else:
            return templates.TemplateResponse("availability_response_fragment.html", {
                "request": request,
                "message": result.get("message", "❌ Failed to create availability slot. Please try again."),
                "success": False
            })
            
    except Exception as e:
        return templates.TemplateResponse("availability_response_fragment.html", {
            "request": request,
            "message": f"❌ Error: {str(e)}",
            "success": False
        })


@router.post("/dashboard/api/availability/recurring")
async def add_recurring_availability_slots(
    request: Request, 
    start_date: str = Form(...),
    end_date: str = Form(...),
    start_time: str = Form(...),
    end_time: str = Form(...),
    slot_duration: int = Form(30),
    days: list = Form(...),
    db: Session = Depends(get_db)
):
    """Add recurring availability slots"""
    access_token = request.cookies.get("access_token")
    if not access_token:
        return templates.TemplateResponse("availability_response_fragment.html", {
            "request": request,
            "message": "Authentication required. Please log in again.",
            "success": False
        })
    
    try:
        payload = verify_token(access_token)
        if not payload:
            return templates.TemplateResponse("availability_response_fragment.html", {
                "request": request,
                "message": "Invalid session. Please log in again.",
                "success": False
            })
        
        user_email = payload.get("sub")
        user = get_user_by_email(db, user_email)
        if not user:
            return templates.TemplateResponse("availability_response_fragment.html", {
                "request": request,
                "message": "User not found. Please log in again.",
                "success": False
            })
        
        # Parse dates and times
        try:
            start_date_obj = datetime.strptime(start_date, "%Y-%m-%d")
            end_date_obj = datetime.strptime(end_date, "%Y-%m-%d")
            start_time_obj = datetime.strptime(start_time, "%H:%M").time()
            end_time_obj = datetime.strptime(end_time, "%H:%M").time()
        except ValueError as e:
            return templates.TemplateResponse("availability_response_fragment.html", {
                "request": request,
                "message": f"Invalid date or time format: {str(e)}",
                "success": False
            })
        
        # Convert days to integers
        try:
            selected_days = [int(day) for day in days]
        except ValueError:
            return templates.TemplateResponse("availability_response_fragment.html", {
                "request": request,
                "message": "Invalid day selection",
                "success": False
            })
        
        # Generate slots for each selected day
        current_date = start_date_obj
        created_slots = 0
        failed_slots = []
        
        while current_date <= end_date_obj:
            if current_date.weekday() in selected_days:
                # Create slots for this day
                current_time = datetime.combine(current_date, start_time_obj)
                end_time_combined = datetime.combine(current_date, end_time_obj)
                
                while current_time + timedelta(minutes=slot_duration) <= end_time_combined:
                    slot_end = current_time + timedelta(minutes=slot_duration)
                    
                    # Only create slots in the future
                    if current_time > datetime.utcnow():
                        slot_data = AvailabilitySlotCreate(
                            user_id=user.id,
                            start_time=current_time,
                            end_time=slot_end
                        )
                        
                        result = create_availability_slot(db, slot_data, user.id)
                        if result.get("success"):
                            created_slots += 1
                        else:
                            failed_slots.append(f"{current_time.strftime('%Y-%m-%d %H:%M')} - {result.get('message', 'Unknown error')}")
                    
                    current_time = slot_end
            
            current_date += timedelta(days=1)
        
        if created_slots > 0:
            message = f"✅ Created {created_slots} availability slots"
            if failed_slots:
                message += f" ({len(failed_slots)} failed)"
            return templates.TemplateResponse("availability_response_fragment.html", {
                "request": request,
                "message": message,
                "success": True
            })
        else:
            return templates.TemplateResponse("availability_response_fragment.html", {
                "request": request,
                "message": f"Failed to create any slots. {len(failed_slots)} errors occurred.",
                "success": False
            })
            
    except Exception as e:
        return templates.TemplateResponse("availability_response_fragment.html", {
            "request": request,
            "message": f"❌ Error: {str(e)}",
            "success": False
        })


@router.post("/dashboard/api/availability/bulk")
async def add_bulk_availability_slots(
    request: Request, 
    template: str = Form(...),
    start_date: str = Form(...),
    end_date: str = Form(...),
    start_time: str = Form(...),
    end_time: str = Form(...),
    slot_duration: int = Form(30),
    days: list = Form(...),
    db: Session = Depends(get_db)
):
    """Add bulk availability slots using templates"""
    access_token = request.cookies.get("access_token")
    if not access_token:
        return templates.TemplateResponse("availability_response_fragment.html", {
            "request": request,
            "message": "Authentication required. Please log in again.",
            "success": False
        })
    
    try:
        payload = verify_token(access_token)
        if not payload:
            return templates.TemplateResponse("availability_response_fragment.html", {
                "request": request,
                "message": "Invalid session. Please log in again.",
                "success": False
            })
        
        user_email = payload.get("sub")
        user = get_user_by_email(db, user_email)
        if not user:
            return templates.TemplateResponse("availability_response_fragment.html", {
                "request": request,
                "message": "User not found. Please log in again.",
                "success": False
            })
        
        # Parse dates and times
        try:
            start_date_obj = datetime.strptime(start_date, "%Y-%m-%d")
            end_date_obj = datetime.strptime(end_date, "%Y-%m-%d")
            start_time_obj = datetime.strptime(start_time, "%H:%M").time()
            end_time_obj = datetime.strptime(end_time, "%H:%M").time()
        except ValueError as e:
            return templates.TemplateResponse("availability_response_fragment.html", {
                "request": request,
                "message": f"Invalid date or time format: {str(e)}",
                "success": False
            })
        
        # Convert days to integers
        try:
            selected_days = [int(day) for day in days]
        except ValueError:
            return templates.TemplateResponse("availability_response_fragment.html", {
                "request": request,
                "message": "Invalid day selection",
                "success": False
            })
        
        # Generate slots for each selected day
        current_date = start_date_obj
        created_slots = 0
        failed_slots = []
        
        while current_date <= end_date_obj:
            if current_date.weekday() in selected_days:
                # Create slots for this day
                current_time = datetime.combine(current_date, start_time_obj)
                end_time_combined = datetime.combine(current_date, end_time_obj)
                
                while current_time + timedelta(minutes=slot_duration) <= end_time_combined:
                    slot_end = current_time + timedelta(minutes=slot_duration)
                    
                    # Only create slots in the future
                    if current_time > datetime.utcnow():
                        slot_data = AvailabilitySlotCreate(
                            user_id=user.id,
                            start_time=current_time,
                            end_time=slot_end
                        )
                        
                        result = create_availability_slot(db, slot_data, user.id)
                        if result.get("success"):
                            created_slots += 1
                        else:
                            failed_slots.append(f"{current_time.strftime('%Y-%m-%d %H:%M')} - {result.get('message', 'Unknown error')}")
                    
                    current_time = slot_end
            
            current_date += timedelta(days=1)
        
        if created_slots > 0:
            message = f"✅ Created {created_slots} availability slots using {template} template"
            if failed_slots:
                message += f" ({len(failed_slots)} failed)"
            return templates.TemplateResponse("availability_response_fragment.html", {
                "request": request,
                "message": message,
                "success": True
            })
        else:
            return templates.TemplateResponse("availability_response_fragment.html", {
                "request": request,
                "message": f"Failed to create any slots. {len(failed_slots)} errors occurred.",
                "success": False
            })
            
    except Exception as e:
        return templates.TemplateResponse("availability_response_fragment.html", {
            "request": request,
            "message": f"❌ Error: {str(e)}",
            "success": False
        })


@router.post("/dashboard/api/availability/quick")
async def add_quick_availability_slots(
    request: Request,
    db: Session = Depends(get_db)
):
    """Add quick availability slots based on frontend request"""
    access_token = request.cookies.get("access_token")
    if not access_token:
        return JSONResponse({
            "success": False,
            "message": "Authentication required. Please log in again."
        })
    
    try:
        payload = verify_token(access_token)
        if not payload:
            return JSONResponse({
                "success": False,
                "message": "Invalid session. Please log in again."
            })
        
        user_email = payload.get("sub")
        user = get_user_by_email(db, user_email)
        if not user:
            return JSONResponse({
                "success": False,
                "message": "User not found. Please log in again."
            })
        
        # Parse JSON request body
        body = await request.json()
        slots_data = body.get("slots", [])
        
        if not slots_data:
            return JSONResponse({
                "success": False,
                "message": "No slots provided"
            })
        
        created_slots = 0
        failed_slots = []
        
        for slot_data in slots_data:
            try:
                # Parse date and time
                date_str = slot_data.get("date")
                time_str = slot_data.get("start_time")
                period = slot_data.get("period", 30)
                
                if not date_str or not time_str:
                    failed_slots.append(f"Invalid slot data: {slot_data}")
                    continue
                
                # Combine date and time
                datetime_str = f"{date_str} {time_str}"
                start_time = datetime.strptime(datetime_str, "%Y-%m-%d %H:%M")
                end_time = start_time + timedelta(minutes=period)
                
                # Only create slots in the future
                if start_time > datetime.utcnow():
                    slot_create_data = AvailabilitySlotCreate(
                        user_id=user.id,
                        start_time=start_time,
                        end_time=end_time
                    )
                    
                    result = create_availability_slot(db, slot_create_data, user.id)
                    if result.get("success"):
                        created_slots += 1
                    else:
                        failed_slots.append(f"{start_time.strftime('%Y-%m-%d %H:%M')} - {result.get('message', 'Unknown error')}")
                else:
                    failed_slots.append(f"{start_time.strftime('%Y-%m-%d %H:%M')} - Slot is in the past")
                    
            except Exception as e:
                failed_slots.append(f"Error processing slot {slot_data}: {str(e)}")
        
        if created_slots > 0:
            message = f"✅ Created {created_slots} availability slots"
            if failed_slots:
                message += f" ({len(failed_slots)} failed)"
            return JSONResponse({
                "success": True,
                "message": message,
                "slots_created": created_slots,
                "failed_count": len(failed_slots)
            })
        else:
            return JSONResponse({
                "success": False,
                "message": f"Failed to create any slots. {len(failed_slots)} errors occurred.",
                "failed_count": len(failed_slots)
            })
            
    except Exception as e:
        return JSONResponse({
            "success": False,
            "message": f"❌ Error: {str(e)}"
        }) 