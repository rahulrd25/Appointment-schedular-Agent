from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from app.api.deps import get_current_active_user
from app.schemas.schemas import User
from app.services.google_calendar_service import GoogleCalendarService

router = APIRouter()


@router.get("/calendar/events")
async def get_calendar_events(
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Get calendar events for the authenticated user."""
    if not current_user.google_access_token:
        raise HTTPException(status_code=400, detail="Google Calendar not connected.")

    service = GoogleCalendarService(current_user.google_access_token, current_user.google_refresh_token)
    events = service.get_events()
    return {"events": events}


@router.post("/calendar/connect")
async def connect_google_calendar(
    current_user: User = Depends(get_current_active_user),
    auth_code: str = None,
) -> Any:
    """Connect Google Calendar for the authenticated user."""
    if not auth_code:
        raise HTTPException(status_code=400, detail="Authorization code is required.")

    service = GoogleCalendarService(None, None)  # Initialize without tokens to get new ones
    credentials = service.get_tokens_from_auth_code(auth_code)

    # Save credentials to the user in the database
    current_user.google_access_token = credentials["access_token"]
    current_user.google_refresh_token = credentials.get("refresh_token", current_user.google_refresh_token)
    # In a real application, you would save these to your database via a user service
    # For now, we'll just return success

    return {"message": "Google Calendar connected successfully."}
