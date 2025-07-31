import json
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from sqlalchemy.orm import Session
from app.models.models import User, AvailabilitySlot, Booking
from app.services import availability_service
from app.services import booking_service
from app.services.google_calendar_service import GoogleCalendarService


class AIAgentService:
    """
    AI Agent Service - The brain of the scheduling system
    Handles natural language processing, conversation management, and intelligent scheduling
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.calendar_service = GoogleCalendarService()
        
        # Conversation context storage
        self.conversation_contexts: Dict[str, Dict] = {}
        
        # Intent patterns for natural language processing
        self.intent_patterns = {
            'schedule_meeting': [
                r'schedule.*meeting',
                r'book.*appointment',
                r'meet.*with',
                r'arrange.*meeting',
                r'plan.*meeting'
            ],
            'check_availability': [
                r'when.*available',
                r'check.*availability',
                r'what.*times.*free',
                r'free.*time',
                r'available.*slots'
            ],
            'reschedule': [
                r'reschedule',
                r'move.*meeting',
                r'change.*time',
                r'postpone',
                r'different.*time'
            ],
            'cancel': [
                r'cancel',
                r'delete.*meeting',
                r'remove.*appointment',
                r'not.*meeting'
            ],
            'meeting_info': [
                r'what.*meeting',
                r'meeting.*details',
                r'when.*meeting',
                r'meeting.*time'
            ]
        }
    
    def process_message(self, user_id: int, message: str, context_id: str = None) -> Dict[str, Any]:
        """
        Process a user message and return an appropriate response
        """
        # Get or create conversation context
        if not context_id:
            context_id = f"user_{user_id}_{datetime.now().timestamp()}"
        
        context = self.conversation_contexts.get(context_id, {
            'user_id': user_id,
            'messages': [],
            'current_intent': None,
            'pending_actions': [],
            'extracted_info': {}
        })
        
        # Add user message to context
        context['messages'].append({
            'role': 'user',
            'content': message,
            'timestamp': datetime.now()
        })
        
        # Analyze intent
        intent = self._analyze_intent(message)
        context['current_intent'] = intent
        
        # Extract relevant information
        extracted_info = self._extract_information(message, intent)
        context['extracted_info'].update(extracted_info)
        
        # Generate response based on intent
        response = self._generate_response(intent, context, extracted_info)
        
        # Add agent response to context
        context['messages'].append({
            'role': 'agent',
            'content': response['message'],
            'timestamp': datetime.now()
        })
        
        # Update conversation context
        self.conversation_contexts[context_id] = context
        
        return {
            'message': response['message'],
            'context_id': context_id,
            'intent': intent,
            'actions': response.get('actions', []),
            'suggestions': response.get('suggestions', [])
        }
    
    def _analyze_intent(self, message: str) -> str:
        """Analyze user intent from message"""
        message_lower = message.lower()
        
        for intent, patterns in self.intent_patterns.items():
            for pattern in patterns:
                if re.search(pattern, message_lower):
                    return intent
        
        return 'general_inquiry'
    
    def _extract_information(self, message: str, intent: str) -> Dict[str, Any]:
        """Extract relevant information from user message"""
        extracted = {}
        message_lower = message.lower()
        
        # Extract time information
        time_patterns = {
            'today': datetime.now().date(),
            'tomorrow': (datetime.now() + timedelta(days=1)).date(),
            'next week': (datetime.now() + timedelta(days=7)).date(),
            'this week': datetime.now().date(),
            'next month': (datetime.now() + timedelta(days=30)).date()
        }
        
        for time_key, time_value in time_patterns.items():
            if time_key in message_lower:
                extracted['date'] = time_value
                break
        
        # Extract time of day
        time_of_day_patterns = {
            'morning': '09:00',
            'afternoon': '14:00',
            'evening': '18:00',
            'night': '20:00'
        }
        
        for time_key, time_value in time_of_day_patterns.items():
            if time_key in message_lower:
                extracted['time'] = time_value
                break
        
        # Extract duration
        duration_match = re.search(r'(\d+)\s*(hour|hr|minute|min)', message_lower)
        if duration_match:
            value = int(duration_match.group(1))
            unit = duration_match.group(2)
            if unit in ['hour', 'hr']:
                extracted['duration'] = value * 60
            else:
                extracted['duration'] = value
        
        # Extract person name
        name_match = re.search(r'with\s+([A-Za-z]+)', message)
        if name_match:
            extracted['person'] = name_match.group(1)
        
        return extracted
    
    def _generate_response(self, intent: str, context: Dict, extracted_info: Dict) -> Dict[str, Any]:
        """Generate appropriate response based on intent and context"""
        
        if intent == 'schedule_meeting':
            return self._handle_schedule_meeting(context, extracted_info)
        elif intent == 'check_availability':
            return self._handle_check_availability(context, extracted_info)
        elif intent == 'reschedule':
            return self._handle_reschedule(context, extracted_info)
        elif intent == 'cancel':
            return self._handle_cancel(context, extracted_info)
        elif intent == 'meeting_info':
            return self._handle_meeting_info(context, extracted_info)
        else:
            return self._handle_general_inquiry(context, extracted_info)
    
    def _handle_schedule_meeting(self, context: Dict, extracted_info: Dict) -> Dict[str, Any]:
        """Handle meeting scheduling requests"""
        user_id = context['user_id']
        
        # Get user's availability
        available_slots = availability_service.get_available_slots_for_booking(
            self.db, user_id, 
            from_date=extracted_info.get('date')
        )
        
        if not available_slots:
            return {
                'message': "I don't see any available slots for that time. Would you like me to check for different times or help you set up your availability?",
                'suggestions': [
                    "Check availability for next week",
                    "Set up my availability",
                    "Show me my calendar"
                ]
            }
        
        # Format available slots for response
        slot_text = []
        for slot in available_slots[:5]:  # Show first 5 slots
            start_time = slot.start_time.strftime('%I:%M %p')
            slot_text.append(f"{start_time}")
        
        slots_str = ", ".join(slot_text)
        
        return {
            'message': f"I found several available slots: {slots_str}. Which time works best for you?",
            'suggestions': slot_text,
            'actions': [{'type': 'show_availability', 'slots': [{'id': slot.id, 'start_time': slot.start_time.isoformat(), 'end_time': slot.end_time.isoformat()} for slot in available_slots]}]
        }
    
    def _handle_check_availability(self, context: Dict, extracted_info: Dict) -> Dict[str, Any]:
        """Handle availability check requests"""
        user_id = context['user_id']
        
        # Get upcoming availability
        upcoming_slots = availability_service.get_available_slots_for_booking(
            self.db, user_id,
            from_date=extracted_info.get('date')
        )
        
        if not upcoming_slots:
            return {
                'message': "I don't see any upcoming availability set. Would you like me to help you set up your availability?",
                'suggestions': [
                    "Set up my availability",
                    "Connect my Google Calendar",
                    "Show me how to get started"
                ]
            }
        
        # Format response
        if extracted_info.get('date'):
            date_str = extracted_info['date'].strftime('%A, %B %d')
            return {
                'message': f"Here's your availability for {date_str}. You have {len(upcoming_slots)} slots available.",
                'actions': [{'type': 'show_availability', 'slots': [{'id': slot.id, 'start_time': slot.start_time.isoformat(), 'end_time': slot.end_time.isoformat()} for slot in upcoming_slots]}]
            }
        else:
            return {
                'message': f"You have {len(upcoming_slots)} upcoming available slots. Would you like me to show you the details?",
                'suggestions': [
                    "Show me the slots",
                    "Schedule a meeting",
                    "Set up recurring availability"
                ]
            }
    
    def _handle_reschedule(self, context: Dict, extracted_info: Dict) -> Dict[str, Any]:
        """Handle rescheduling requests"""
        user_id = context['user_id']
        
        # Get upcoming bookings
        upcoming_bookings = booking_service.get_upcoming_bookings(self.db, user_id)
        
        if not upcoming_bookings:
            return {
                'message': "I don't see any upcoming meetings to reschedule. Would you like to schedule a new meeting instead?",
                'suggestions': [
                    "Schedule a new meeting",
                    "Check my availability",
                    "View my calendar"
                ]
            }
        
        return {
            'message': f"I found {len(upcoming_bookings)} upcoming meetings. Which one would you like to reschedule?",
            'actions': [{'type': 'show_bookings', 'bookings': [{'id': booking.id, 'guest_name': booking.guest_name, 'start_time': booking.start_time.isoformat(), 'end_time': booking.end_time.isoformat()} for booking in upcoming_bookings]}]
        }
    
    def _handle_cancel(self, context: Dict, extracted_info: Dict) -> Dict[str, Any]:
        """Handle cancellation requests"""
        user_id = context['user_id']
        
        # Get upcoming bookings
        upcoming_bookings = booking_service.get_upcoming_bookings(self.db, user_id)
        
        if not upcoming_bookings:
            return {
                'message': "I don't see any upcoming meetings to cancel. Is there anything else I can help you with?",
                'suggestions': [
                    "Schedule a new meeting",
                    "Check my availability",
                    "View my calendar"
                ]
            }
        
        return {
            'message': f"I found {len(upcoming_bookings)} upcoming meetings. Which one would you like to cancel?",
            'actions': [{'type': 'show_bookings', 'bookings': [{'id': booking.id, 'guest_name': booking.guest_name, 'start_time': booking.start_time.isoformat(), 'end_time': booking.end_time.isoformat()} for booking in upcoming_bookings]}]
        }
    
    def _handle_meeting_info(self, context: Dict, extracted_info: Dict) -> Dict[str, Any]:
        """Handle meeting information requests"""
        user_id = context['user_id']
        
        # Get upcoming bookings
        upcoming_bookings = booking_service.get_upcoming_bookings(self.db, user_id)
        
        if not upcoming_bookings:
            return {
                'message': "You don't have any upcoming meetings scheduled. Would you like to schedule one?",
                'suggestions': [
                    "Schedule a meeting",
                    "Check my availability",
                    "Set up my calendar"
                ]
            }
        
        # Show next meeting
        next_meeting = upcoming_bookings[0]
        meeting_time = next_meeting.start_time.strftime('%A, %B %d at %I:%M %p')
        
        return {
            'message': f"Your next meeting is with {next_meeting.client_name} on {meeting_time}. Would you like to see all your upcoming meetings?",
            'suggestions': [
                "Show all meetings",
                "Reschedule this meeting",
                "Cancel this meeting"
            ]
        }
    
    def _handle_general_inquiry(self, context: Dict, extracted_info: Dict) -> Dict[str, Any]:
        """Handle general inquiries"""
        return {
            'message': "I'm your AI scheduling assistant! I can help you schedule meetings, check availability, reschedule appointments, and manage your calendar. What would you like to do?",
            'suggestions': [
                "Schedule a meeting",
                "Check my availability",
                "View my calendar",
                "Set up my availability"
            ]
        }
    
    def get_conversation_history(self, context_id: str) -> List[Dict]:
        """Get conversation history for a context"""
        context = self.conversation_contexts.get(context_id, {})
        return context.get('messages', [])
    
    def clear_conversation_context(self, context_id: str):
        """Clear conversation context"""
        if context_id in self.conversation_contexts:
            del self.conversation_contexts[context_id] 