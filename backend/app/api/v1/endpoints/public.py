from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.models.models import User as UserModel
from app.services.user_service import get_user_by_scheduling_slug
from app.services.availability_service import get_available_slots_for_booking
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

    # Get available slots for booking
    availability_slots = get_available_slots_for_booking(db, user.id)

    return templates.TemplateResponse(
        "public_booking.html", {
            "request": request, 
            "user": user,
            "availability_slots": availability_slots
        }
    )



