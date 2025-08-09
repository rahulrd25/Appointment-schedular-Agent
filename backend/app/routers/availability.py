from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.services.user_service import get_user_by_email
from app.core.security import verify_token
from app.services.availability_service import get_availability_slots_for_user
from app.core.timezone_utils import TimezoneManager
from datetime import timezone
from zoneinfo import ZoneInfo

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

@router.get("/availability")
async def availability_page(request: Request, db: Session = Depends(get_db)):
    """Availability management page"""
    access_token = request.cookies.get("access_token")

    if not access_token:
        return RedirectResponse(url="/", status_code=302)

    # Remove "Bearer " prefix if present
    if access_token.startswith("Bearer "):
        access_token = access_token[7:]

    try:
        payload = verify_token(access_token)
        if not payload:
            return RedirectResponse(url="/", status_code=302)

        user_email = payload.get("sub")
        user = get_user_by_email(db, user_email)

        if not user:
            return RedirectResponse(url="/", status_code=302)

        # Get user's availability slots (including booked ones)
        availability_slots = get_availability_slots_for_user(db, user.id, include_unavailable=True)

        # Get user's timezone
        user_timezone = TimezoneManager.get_user_timezone(user.timezone)

        # Convert times to user's timezone for display
        for slot in availability_slots:
            # Ensure times are timezone-aware
            if slot.start_time.tzinfo is None:
                slot.start_time = slot.start_time.replace(tzinfo=timezone.utc)
            if slot.end_time.tzinfo is None:
                slot.end_time = slot.end_time.replace(tzinfo=timezone.utc)
            
            # Convert to user's timezone
            slot.start_time = slot.start_time.astimezone(ZoneInfo(user_timezone))
            slot.end_time = slot.end_time.astimezone(ZoneInfo(user_timezone))

        return templates.TemplateResponse("availability.html", {
            "request": request,
            "current_user": user,
            "availability_slots": availability_slots
        })

    except Exception as e:
        print(f"Availability page error: {e}")
        return RedirectResponse(url="/", status_code=302) 