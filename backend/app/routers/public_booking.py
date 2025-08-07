from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.services.user_service import get_user_by_scheduling_slug
from app.services.availability_service import get_availability_slots_for_user
from app.services.booking_service import create_booking

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

@router.get("/{scheduling_slug}", response_class=HTMLResponse)
async def get_public_booking_page(
    request: Request,
    scheduling_slug: str,
    db: Session = Depends(get_db),
):
    """Public booking page for a user's scheduling link"""
    try:
        # Get user by scheduling slug
        user = get_user_by_scheduling_slug(db, scheduling_slug)
        
        if not user:
            return templates.TemplateResponse("404.html", {"request": request})
        
        # Get user's availability slots
        availability_slots = get_availability_slots_for_user(db, user.id)
        
        return templates.TemplateResponse("public_booking.html", {
            "request": request,
            "user": user,
            "availability_slots": availability_slots
        })
        
    except Exception as e:
        print(f"Public booking page error: {e}")
        return templates.TemplateResponse("404.html", {"request": request}) 