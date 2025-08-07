from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.services.user_service import get_user_by_email
from app.core.security import verify_token
from app.services.booking_service import get_bookings_for_user

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

@router.get("/bookings")
async def bookings_page(request: Request, db: Session = Depends(get_db)):
    """Bookings management page"""
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

        return templates.TemplateResponse("bookings.html", {
            "request": request,
            "current_user": user
        })

    except Exception as e:
        print(f"Bookings page error: {e}")
        return RedirectResponse(url="/", status_code=302)

@router.get("/bookings/api/list")
async def bookings_list(request: Request, db: Session = Depends(get_db)):
    """Get user's bookings list"""
    access_token = request.cookies.get("access_token")
    
    if not access_token:
        return {"error": "Not authenticated"}

    # Remove "Bearer " prefix if present
    if access_token.startswith("Bearer "):
        access_token = access_token[7:]
    
    try:
        payload = verify_token(access_token)
        if not payload:
            return {"error": "Invalid token"}
        
        user_email = payload.get("sub")
        user = get_user_by_email(db, user_email)
        
        if not user:
            return {"error": "User not found"}
        
        # Get user's bookings
        bookings = get_bookings_for_user(db, user.id)
        
        return {
            "bookings": [
                {
                    "id": booking.id,
                    "guest_name": booking.guest_name,
                    "guest_email": booking.guest_email,
                    "start_time": booking.start_time.isoformat(),
                    "end_time": booking.end_time.isoformat(),
                    "status": booking.status,
                    "guest_message": booking.guest_message,
                    "created_at": booking.created_at.isoformat()
                } for booking in bookings
            ]
        }
    except Exception as e:
        return {"error": str(e)}

# Booking stats endpoint removed - function not available 