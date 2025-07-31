from fastapi import APIRouter, Request, Form, HTTPException, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from fastapi.templating import Jinja2Templates
from datetime import datetime, timedelta, timezone

from app.core.database import get_db
from app.services.user_service import get_user_by_email
from app.core.security import verify_token
from app.services.availability_service import (
    get_availability_slots_for_user,
    create_availability_slot
)

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/availability")
async def availability_page(request: Request, db: Session = Depends(get_db)):
    """Availability page"""
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

        # Get user's availability slots
        from app.services.availability_service import get_availability_slots_for_user
        availability_slots = get_availability_slots_for_user(db, user.id)
        
        return templates.TemplateResponse("availability.html", {
            "request": request,
            "current_user": user,
            "availability_slots": availability_slots
        })

    except Exception as e:
        print(f"Availability page error: {e}")
        return RedirectResponse(url="/login", status_code=302)


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


@router.post("/dashboard/api/availability/")
async def add_dashboard_availability_slot(
    request: Request, 
    date: str = Form(...),
    start_time: str = Form(...),
    period: int = Form(30),
    db: Session = Depends(get_db)
):
    """Add a single availability slot"""
    access_token = request.cookies.get("access_token")
    if not access_token:
        from fastapi.responses import HTMLResponse
        return HTMLResponse(content="""
        <div class="bg-red-50 border border-red-200 rounded-lg p-4 mb-4">
            <div class="flex items-center">
                <svg class="w-5 h-5 text-red-400 mr-2" fill="currentColor" viewBox="0 0 20 20">
                    <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd"></path>
                </svg>
                <p class="text-red-800 text-sm font-medium">Not authenticated</p>
            </div>
        </div>
        """)
    
    try:
        payload = verify_token(access_token)
        if not payload:
            from fastapi.responses import HTMLResponse
            return HTMLResponse(content="""
            <div class="bg-red-50 border border-red-200 rounded-lg p-4 mb-4">
                <div class="flex items-center">
                    <svg class="w-5 h-5 text-red-400 mr-2" fill="currentColor" viewBox="0 0 20 20">
                        <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd"></path>
                    </svg>
                    <p class="text-red-800 text-sm font-medium">Invalid token</p>
                </div>
            </div>
            """)
        
        user_email = payload.get("sub")
        user = get_user_by_email(db, user_email)
        
        if not user:
            from fastapi.responses import HTMLResponse
            return HTMLResponse(content="""
            <div class="bg-red-50 border border-red-200 rounded-lg p-4 mb-4">
                <div class="flex items-center">
                    <svg class="w-5 h-5 text-red-400 mr-2" fill="currentColor" viewBox="0 0 20 20">
                        <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd"></path>
                    </svg>
                    <p class="text-red-800 text-sm font-medium">User not found</p>
                </div>
            </div>
            """)
        
        # Parse date and time
        try:
            datetime_str = f"{date} {start_time}"
            start_datetime = datetime.strptime(datetime_str, "%Y-%m-%d %H:%M")
            end_datetime = start_datetime + timedelta(minutes=period)
        except ValueError:
            from fastapi.responses import HTMLResponse
            return HTMLResponse(content="""
            <div class="bg-red-50 border border-red-200 rounded-lg p-4 mb-4">
                <div class="flex items-center">
                    <svg class="w-5 h-5 text-red-400 mr-2" fill="currentColor" viewBox="0 0 20 20">
                        <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd"></path>
                    </svg>
                    <p class="text-red-800 text-sm font-medium">Invalid date/time format</p>
                </div>
            </div>
            """)
        
        # Create availability slot
        from app.schemas.schemas import AvailabilitySlotCreate
        
        slot_data = AvailabilitySlotCreate(
            start_time=start_datetime,
            end_time=end_datetime,
            is_available=True
        )
        
        result = create_availability_slot(db, slot_data, user.id)
        
        if result["success"]:
            # Return HTML success message for HTMX
            from fastapi.responses import HTMLResponse
            success_html = f"""
            <div class="bg-green-50 border border-green-200 rounded-lg p-4 mb-4">
                <div class="flex items-center">
                    <svg class="w-5 h-5 text-green-400 mr-2" fill="currentColor" viewBox="0 0 20 20">
                        <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd"></path>
                    </svg>
                    <p class="text-green-800 text-sm font-medium">Availability slot created successfully!</p>
                </div>
            </div>
            """
            return HTMLResponse(content=success_html)
        else:
            # Return HTML error message for HTMX
            from fastapi.responses import HTMLResponse
            error_html = f"""
            <div class="bg-red-50 border border-red-200 rounded-lg p-4 mb-4">
                <div class="flex items-center">
                    <svg class="w-5 h-5 text-red-400 mr-2" fill="currentColor" viewBox="0 0 20 20">
                        <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd"></path>
                    </svg>
                    <p class="text-red-800 text-sm font-medium">{result["message"]}</p>
                </div>
            </div>
            """
            return HTMLResponse(content=error_html)
        
    except Exception as e:
        print(f"Error creating availability slot: {e}")
        # Return HTML error message for HTMX
        from fastapi.responses import HTMLResponse
        error_html = f"""
        <div class="bg-red-50 border border-red-200 rounded-lg p-4 mb-4">
            <div class="flex items-center">
                <svg class="w-5 h-5 text-red-400 mr-2" fill="currentColor" viewBox="0 0 20 20">
                    <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd"></path>
                </svg>
                <p class="text-red-800 text-sm font-medium">Error: {str(e)}</p>
            </div>
        </div>
        """
        return HTMLResponse(content=error_html)


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
    """Add recurring availability slots - TODO: Implement this function"""
    return {"error": "Recurring availability slots not implemented yet"}


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
    """Add bulk availability slots using templates - TODO: Implement this function"""
    return {"error": "Bulk availability slots not implemented yet"}


@router.post("/dashboard/api/availability/quick")
async def add_quick_availability_slots(
    request: Request, 
    db: Session = Depends(get_db)
):
    """Add quick availability slots for next week"""
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
        
        # Get JSON data from request
        data = await request.json()
        slots_data = data.get("slots", [])
        
        if not slots_data:
            return {"error": "No slots provided"}
        
        # Create availability slots
        slots_created = 0
        errors = []
        
        for slot_data in slots_data:
            try:
                # Parse date and time
                datetime_str = f"{slot_data['date']} {slot_data['start_time']}"
                start_datetime = datetime.strptime(datetime_str, "%Y-%m-%d %H:%M")
                end_datetime = start_datetime + timedelta(minutes=slot_data.get('period', 30))
                
                # Create slot data
                from app.schemas.schemas import AvailabilitySlotCreate
                slot_create_data = AvailabilitySlotCreate(
                    start_time=start_datetime,
                    end_time=end_datetime,
                    is_available=True
                )
                
                # Create slot
                result = create_availability_slot(db, slot_create_data, user.id)
                
                if result["success"]:
                    slots_created += 1
                else:
                    errors.append(f"Slot {slot_data['date']} {slot_data['start_time']}: {result['message']}")
                    
            except Exception as e:
                errors.append(f"Slot {slot_data['date']} {slot_data['start_time']}: {str(e)}")
        
        if slots_created > 0:
            return {
                "success": True,
                "slots_created": slots_created,
                "message": f"Successfully created {slots_created} availability slots!",
                "errors": errors if errors else None
            }
        else:
            return {
                "success": False,
                "message": "Failed to create any slots",
                "errors": errors
            }
        
    except Exception as e:
        print(f"Error in add_quick_availability_slots: {e}")
        return {"error": str(e)} 