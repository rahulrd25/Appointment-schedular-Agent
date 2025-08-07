from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import Dict, Any
import json

from app.core.database import get_db
from app.services.intelligent_agent_service import IntelligentAgentService
from app.services.google_calendar_service import GoogleCalendarService
from app.api.deps import get_current_user_from_cookie
from app.models.models import User

router = APIRouter()

@router.get("/knowledge")
async def get_knowledge(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_cookie)
):
    """
    Get knowledge summary for the user
    """
    try:
        agent_service = IntelligentAgentService(db)
        summary = agent_service.get_knowledge_summary(current_user.id)
        return {"knowledge": summary}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting knowledge: {str(e)}")

@router.get("/calendar/events")
async def get_calendar_events(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_cookie)
):
    """
    Get calendar events for the agent dashboard
    """
    try:
        if not current_user.google_access_token:
            return {"events": []}
        
        service = GoogleCalendarService(
            current_user.google_access_token, 
            current_user.google_refresh_token,
            db=db,
            user_id=current_user.id
        )
        events = service.get_events()
        return {"events": events}
    except Exception as e:
        # Return empty events if there's an error
        return {"events": []}

@router.get("/stats")
async def get_user_stats_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_cookie)
):
    """
    Get user statistics for the agent dashboard
    """
    try:
        stats = get_user_stats(db, current_user.id)
        return stats
    except Exception as e:
        return {
            "available_slots": 0,
            "upcoming_meetings": 0,
            "today_meetings": 0
        }

def get_user_stats(db: Session, user_id: int) -> Dict[str, Any]:
    """
    Get user statistics for the dashboard
    """
    try:
        from app.services import availability_service
        from app.services import booking_service
        from datetime import datetime, date
        
        # Get available slots count
        available_slots = availability_service.get_available_slots_for_booking(db, user_id)
        available_slots_count = len(available_slots)
        
        # Get upcoming meetings count
        upcoming_bookings = booking_service.get_upcoming_bookings(db, user_id)
        upcoming_meetings_count = len(upcoming_bookings)
        
        # Get today's meetings count
        today = date.today()
        today_bookings = [b for b in upcoming_bookings if b.date == today]
        today_meetings_count = len(today_bookings)
        
        return {
            "available_slots": available_slots_count,
            "upcoming_meetings": upcoming_meetings_count,
            "today_meetings": today_meetings_count
        }
        
    except Exception as e:
        # Return default values if there's an error
        return {
            "available_slots": 0,
            "upcoming_meetings": 0,
            "today_meetings": 0
        } 