from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import Dict, Any
import json

from app.core.database import get_db
from app.services.intelligent_agent_service import IntelligentAgentService
from app.api.deps import get_current_user_from_cookie
from app.models.models import User
<<<<<<< HEAD
=======
from app.services.google_calendar_service import GoogleCalendarService
>>>>>>> e3b999cd02f578d5176e7dbc287d1a2a1f5f3840

router = APIRouter()

@router.post("/chat")
async def chat_with_agent(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_cookie)
):
    """
    Chat with the AI agent
    """
    try:
        # Parse JSON body
        body = await request.json()
        message = body.get("message", "")
        context_id = body.get("context_id")
        
        if not message:
            raise HTTPException(status_code=400, detail="Message is required")
        
        # Initialize intelligent agent service
        agent_service = IntelligentAgentService(db)
        
        # Process message
        response = await agent_service.process_message(
            user_id=current_user.id,
            message=message,
            context_id=context_id
        )
        
        # Get user stats for the response
        stats = get_user_stats(db, current_user.id)
        response['stats'] = stats
        
        return response
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing message: {str(e)}")

@router.get("/stats")
async def get_agent_stats(
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
        raise HTTPException(status_code=500, detail=f"Error getting stats: {str(e)}")

@router.get("/conversation/{context_id}")
async def get_conversation_history(
    context_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_cookie)
):
    """
    Get conversation history for a specific context
    """
    try:
        agent_service = IntelligentAgentService(db)
        history = agent_service.conversation_contexts.get(context_id, {}).get("conversation_history", [])
        return {"conversation": history}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting conversation: {str(e)}")

@router.delete("/conversation/{context_id}")
async def clear_conversation(
    context_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_cookie)
):
    """
    Clear conversation context
    """
    try:
        agent_service = IntelligentAgentService(db)
        if context_id in agent_service.conversation_contexts:
            del agent_service.conversation_contexts[context_id]
        return {"message": "Conversation cleared successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error clearing conversation: {str(e)}")

@router.post("/schedule")
async def schedule_meeting(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_cookie)
):
    """
    Schedule a meeting through the agent
    """
    try:
        body = await request.json()
        
        # Extract scheduling information
        slot_id = body.get("slot_id")
        client_name = body.get("client_name")
        client_email = body.get("client_email")
        notes = body.get("notes", "")
        
        if not all([slot_id, client_name, client_email]):
            raise HTTPException(status_code=400, detail="Missing required fields")
        
        # Use booking service to create the booking
        from app.services import booking_service
        from app.schemas.schemas import PublicBookingCreate
        
        booking_data = PublicBookingCreate(
            guest_name=client_name,
            guest_email=client_email,
            guest_message=notes
        )
        
        booking = booking_service.create_booking(
            db, booking_data, slot_id, current_user
        )
        
        return {
            "message": f"Meeting scheduled successfully with {client_name}",
            "booking": {
                "id": booking.id,
                "client_name": booking.client_name,
                "date": booking.date.isoformat(),
                "start_time": booking.start_time.isoformat(),
                "duration": booking.duration
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error scheduling meeting: {str(e)}")

@router.get("/availability")
async def get_availability(
    date: str = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_cookie)
):
    """
    Get user availability through the agent
    """
    try:
        from app.services import availability_service
        
        available_slots = availability_service.get_available_slots_for_booking(
            db, user_id=current_user.id,
            from_date=date
        )
        
        return {
            "available_slots": available_slots,
            "total_slots": len(available_slots)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting availability: {str(e)}")

@router.get("/insights")
async def get_user_insights(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_cookie)
):
    """
    Get personalized insights and learning about the user
    """
    try:
        agent_service = IntelligentAgentService(db)
        insights = agent_service.get_user_insights(current_user.id)
        return insights
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting insights: {str(e)}")

@router.get("/capabilities")
async def get_agent_capabilities(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_cookie)
):
    """
    Get agent capabilities and status
    """
    try:
        agent_service = IntelligentAgentService(db)
        capabilities = agent_service.get_agent_capabilities()
        return capabilities
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting capabilities: {str(e)}")

@router.post("/learn")
async def add_knowledge(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_cookie)
):
    """
    Add new knowledge to the agent's knowledge base
    """
    try:
        body = await request.json()
        category = body.get("category")
        content = body.get("content")
        tags = body.get("tags", [])
        
        if not category or not content:
            raise HTTPException(status_code=400, detail="Category and content are required")
        
        agent_service = IntelligentAgentService(db)
        agent_service.knowledge_base.add_knowledge(
            category=category,
            content=content,
            source="user",
            tags=tags
        )
        
        return {"message": "Knowledge added successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error adding knowledge: {str(e)}")

@router.get("/knowledge")
async def get_knowledge_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_cookie)
):
    """
<<<<<<< HEAD
    Get knowledge base summary
    """
    try:
        agent_service = IntelligentAgentService(db)
        summary = agent_service.knowledge_base.get_knowledge_summary()
        return summary
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting knowledge summary: {str(e)}")
=======
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
>>>>>>> e3b999cd02f578d5176e7dbc287d1a2a1f5f3840

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