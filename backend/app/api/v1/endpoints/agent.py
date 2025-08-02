from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import Dict, Any
import json

from app.core.database import get_db
from app.services.agent.intelligent_agent_service import IntelligentAgentService
from app.api.deps import get_current_user_from_cookie
from app.models.models import User
from app.services.google_calendar_service import GoogleCalendarService

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
async def get_knowledge_base(
    category: str = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_cookie)
):
    """
    Get knowledge base Q&A and best practices
    """
    try:
        agent_service = IntelligentAgentService(db)
        knowledge_base = agent_service.knowledge_base
        
        if category:
            # Get specific category
            qa = knowledge_base.get_relevant_qa("", category)
            patterns = knowledge_base.get_common_patterns(category)
            best_practices = knowledge_base.get_best_practices(category)
        else:
            # Get all knowledge
            qa = knowledge_base.get_relevant_qa("")
            patterns = knowledge_base.get_common_patterns()
            best_practices = knowledge_base.get_best_practices()
        
        return {
            "qa": qa,
            "patterns": patterns,
            "best_practices": best_practices,
            "categories": ["scheduling", "time_management", "calendar_integration", "troubleshooting"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting knowledge base: {str(e)}")

@router.get("/knowledge/search")
async def search_knowledge(
    query: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_cookie)
):
    """
    Search knowledge base for relevant Q&A
    """
    try:
        agent_service = IntelligentAgentService(db)
        knowledge_base = agent_service.knowledge_base
        
        similar_questions = knowledge_base.find_similar_questions(query)
        relevant_qa = knowledge_base.get_relevant_qa(query)
        
        return {
            "query": query,
            "similar_questions": similar_questions,
            "relevant_qa": relevant_qa
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error searching knowledge base: {str(e)}")

@router.get("/calendar/events")
async def get_calendar_events(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_cookie)
):
    """
    Get calendar events for the agent dashboard from database
    """
    try:
        # Get all bookings from database (includes both local and calendar-synced)
        from app.services.booking_service import get_bookings_for_user
        all_bookings = get_bookings_for_user(db, current_user.id)
        
        # Filter for calendar-synced bookings (those with google_event_id)
        calendar_bookings = [booking for booking in all_bookings if booking.google_event_id]
        
        # Convert to event format
        events = []
        for booking in calendar_bookings:
            events.append({
                "id": booking.google_event_id,
                "summary": booking.guest_name,
                "start": {"dateTime": booking.start_time.isoformat()},
                "end": {"dateTime": booking.end_time.isoformat()},
                "description": booking.guest_message,
                "organizer": {"email": booking.guest_email}
            })
        
        return {"events": events}
    except Exception as e:
        # Return empty events if there's an error
        return {"events": []}

@router.get("/status")
async def get_agent_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_cookie)
):
    """
    Get AI agent status and capabilities
    """
    try:
        agent_service = IntelligentAgentService(db)
        capabilities = agent_service.get_agent_capabilities()
        analysis_mode = agent_service.get_analysis_mode()
        llm_available = agent_service.is_llm_available()
        
        return {
            "status": "active",
            "analysis_mode": analysis_mode,
            "llm_available": llm_available,
            "capabilities": capabilities,
            "user_id": current_user.id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting agent status: {str(e)}")

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

@router.post("/knowledge/load")
async def load_knowledge_base(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_cookie)
):
    """
    Load knowledge base from file or API
    """
    try:
        body = await request.json()
        source_type = body.get("source_type")  # "json", "csv", "api"
        source_path = body.get("source_path")  # file path or API URL
        api_key = body.get("api_key")  # for API sources
        
        agent_service = IntelligentAgentService(db)
        knowledge_base = agent_service.knowledge_base
        
        success = False
        if source_type == "json":
            success = knowledge_base.load_knowledge_from_json(source_path)
        elif source_type == "csv":
            success = knowledge_base.load_knowledge_from_csv(source_path)
        elif source_type == "api":
            success = knowledge_base.load_knowledge_from_api(source_path, api_key)
        else:
            raise HTTPException(status_code=400, detail="Invalid source type")
        
        if success:
            stats = knowledge_base.get_knowledge_stats()
            return {
                "success": True,
                "message": f"Knowledge base loaded successfully",
                "stats": stats
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to load knowledge base")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading knowledge base: {str(e)}")

@router.post("/knowledge/add")
async def add_knowledge_item(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_cookie)
):
    """
    Add a single Q&A pair to knowledge base
    """
    try:
        body = await request.json()
        category = body.get("category", "general")
        question = body.get("question")
        answer = body.get("answer")
        keywords = body.get("keywords", [])
        intent = body.get("intent", "general_query")
        
        if not question or not answer:
            raise HTTPException(status_code=400, detail="Question and answer are required")
        
        agent_service = IntelligentAgentService(db)
        knowledge_base = agent_service.knowledge_base
        
        success = knowledge_base.add_qa_pair(category, question, answer, keywords, intent)
        
        if success:
            return {
                "success": True,
                "message": "Q&A pair added successfully"
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to add Q&A pair")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error adding knowledge item: {str(e)}")

@router.post("/knowledge/bulk-add")
async def bulk_add_knowledge(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_cookie)
):
    """
    Add multiple Q&A pairs to knowledge base
    """
    try:
        body = await request.json()
        qa_pairs = body.get("qa_pairs", [])
        
        if not qa_pairs:
            raise HTTPException(status_code=400, detail="No Q&A pairs provided")
        
        agent_service = IntelligentAgentService(db)
        knowledge_base = agent_service.knowledge_base
        
        success = knowledge_base.bulk_add_qa_pairs(qa_pairs)
        
        if success:
            stats = knowledge_base.get_knowledge_stats()
            return {
                "success": True,
                "message": f"Added {len(qa_pairs)} Q&A pairs successfully",
                "stats": stats
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to add Q&A pairs")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error bulk adding knowledge: {str(e)}")

@router.get("/knowledge/stats")
async def get_knowledge_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_cookie)
):
    """
    Get knowledge base statistics
    """
    try:
        agent_service = IntelligentAgentService(db)
        knowledge_base = agent_service.knowledge_base
        
        stats = knowledge_base.get_knowledge_stats()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting knowledge stats: {str(e)}")

@router.get("/knowledge/search/advanced")
async def advanced_search_knowledge(
    query: str,
    limit: int = 5,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_cookie)
):
    """
    Advanced search with relevance scoring
    """
    try:
        agent_service = IntelligentAgentService(db)
        knowledge_base = agent_service.knowledge_base
        
        results = knowledge_base.search_knowledge_advanced(query, limit)
        
        return {
            "query": query,
            "results": results,
            "total_found": len(results)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error searching knowledge: {str(e)}") 

@router.post("/knowledge/load-md")
async def load_knowledge_from_markdown(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_cookie)
):
    """
    Load knowledge base from Markdown file or content
    """
    try:
        body = await request.json()
        source_type = body.get("source_type")  # "file" or "content"
        source_path = body.get("source_path")  # file path
        md_content = body.get("md_content")  # markdown content string
        
        agent_service = IntelligentAgentService(db)
        knowledge_base = agent_service.knowledge_base
        
        success = False
        if source_type == "file" and source_path:
            success = knowledge_base.load_knowledge_from_markdown(source_path)
        elif source_type == "content" and md_content:
            success = knowledge_base.load_knowledge_from_md_content(md_content)
        else:
            raise HTTPException(status_code=400, detail="Invalid source type or missing content")
        
        if success:
            stats = knowledge_base.get_knowledge_stats()
            return {
                "success": True,
                "message": f"Knowledge base loaded successfully from markdown",
                "stats": stats
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to load knowledge base from markdown")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading knowledge base from markdown: {str(e)}") 

@router.post("/knowledge/load-custom-qa")
async def load_knowledge_from_custom_qa(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_cookie)
):
    """
    Load knowledge base from custom Q&A format file or content
    """
    try:
        body = await request.json()
        source_type = body.get("source_type")  # "file" or "content"
        source_path = body.get("source_path")  # file path
        qa_content = body.get("qa_content")  # Q&A content string
        
        agent_service = IntelligentAgentService(db)
        knowledge_base = agent_service.knowledge_base
        
        success = False
        if source_type == "file" and source_path:
            success = knowledge_base.load_knowledge_from_custom_qa(source_path)
        elif source_type == "content" and qa_content:
            success = knowledge_base.load_knowledge_from_custom_qa_content(qa_content)
        else:
            raise HTTPException(status_code=400, detail="Invalid source type or missing content")
        
        if success:
            stats = knowledge_base.get_knowledge_stats()
            return {
                "success": True,
                "message": f"Knowledge base loaded successfully from custom Q&A format",
                "stats": stats
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to load knowledge base from custom Q&A format")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading knowledge base from custom Q&A format: {str(e)}") 