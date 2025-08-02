from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session
import json
import re
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import logging

from app.models.models import User, AvailabilitySlot, Booking
from app.services import availability_service, booking_service, user_service
from app.schemas.schemas import PublicBookingCreate

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class IntentType(Enum):
    SCHEDULE_MEETING = "schedule_meeting"
    CHECK_AVAILABILITY = "check_availability"
    RESCHEDULE = "reschedule"
    CANCEL = "cancel"
    MEETING_INFO = "meeting_info"
    GENERAL_QUERY = "general_query"
    CALENDAR_SYNC = "calendar_sync"
    SETTINGS = "settings"

@dataclass
class ExtractedInfo:
    """Structured information extracted from user message"""
    intent: IntentType
    confidence: float
    entities: Dict[str, Any]
    context: Dict[str, Any]
    sentiment: str
    urgency: str

@dataclass
class AgentResponse:
    """Structured agent response"""
    message: str
    action_taken: Optional[str]
    suggestions: List[str]
    data: Dict[str, Any]
    confidence: float
    requires_confirmation: bool

class AdvancedAIAgentService:
    """
    Advanced AI Agent Service with NLP, context understanding, and intelligent decision making
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.conversation_contexts: Dict[str, Dict] = {}
        
        # Load appointment examples for learning (inline data)
        self.examples = self._get_conversation_examples()
        self.entity_patterns = self._get_entity_patterns()
        self.context_rules = self._get_context_rules()
        self.action_patterns = self._get_action_patterns()
        
        # Knowledge base for different domains
        self.knowledge_base = {
            "scheduling": {
                "best_practices": [
                    "Schedule meetings during business hours (9 AM - 5 PM)",
                    "Allow buffer time between meetings",
                    "Consider time zones for remote participants",
                    "Send calendar invites with clear agendas"
                ],
                "common_patterns": [
                    "meeting with {person}",
                    "call about {topic}",
                    "discussion on {subject}",
                    "review {project}"
                ]
            },
            "calendar_management": {
                "tips": [
                    "Block time for deep work",
                    "Schedule breaks between meetings",
                    "Use recurring slots for regular meetings",
                    "Set up automatic reminders"
                ]
            }
        }
        
        # Advanced intent patterns with context
        self.intent_patterns = {
            IntentType.SCHEDULE_MEETING: {
                "patterns": [
                    r"(schedule|book|arrange|set up|plan)\s+(a\s+)?(meeting|call|appointment|discussion)",
                    r"(meet|call|discuss)\s+(with|about)",
                    r"(have|need)\s+(a\s+)?(meeting|call)",
                    r"(let's|we should)\s+(meet|call|discuss)"
                ],
                "confidence_threshold": 0.7
            },
            IntentType.CHECK_AVAILABILITY: {
                "patterns": [
                    r"(when|what times?)\s+(am\s+i\s+)?(available|free)",
                    r"(check|show|see)\s+(my\s+)?(availability|schedule|calendar)",
                    r"(free\s+time|open\s+slots)",
                    r"(busy|booked)\s+(when|times?)"
                ],
                "confidence_threshold": 0.6
            },
            IntentType.RESCHEDULE: {
                "patterns": [
                    r"(reschedule|move|change|postpone)\s+(meeting|call|appointment)",
                    r"(different|another)\s+time",
                    r"(can't make|conflict|busy)\s+(at|on)"
                ],
                "confidence_threshold": 0.8
            },
            IntentType.CANCEL: {
                "patterns": [
                    r"(cancel|delete|remove)\s+(meeting|call|appointment)",
                    r"(can't attend|won't make|not available)",
                    r"(call off|postpone indefinitely)"
                ],
                "confidence_threshold": 0.9
            }
        }
        
        # Entity extraction patterns
        self.entity_patterns = {
            "person": [
                r"(with|meet)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",
                r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(meeting|call)"
            ],
            "time": [
                r"(tomorrow|today|next\s+week|this\s+week|monday|tuesday|wednesday|thursday|friday|saturday|sunday)",
                r"(\d{1,2}:\d{2}\s*(?:am|pm)?)",
                r"(\d{1,2}\s*(?:am|pm))"
            ],
            "duration": [
                r"(\d+)\s*(?:min|minute|hour|hr)",
                r"(half\s+hour|hour|30\s+min|60\s+min)"
            ],
            "topic": [
                r"(about|regarding|concerning)\s+([^,\.]+)",
                r"(discuss|talk\s+about)\s+([^,\.]+)"
            ]
        }
    
    def process_message(self, user_id: int, message: str, context_id: str = None) -> Dict[str, Any]:
        """
        Process user message with advanced NLP and context understanding
        """
        try:
            # Get or create conversation context
            if not context_id:
                context_id = f"user_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            context = self.conversation_contexts.get(context_id, {
                "user_id": user_id,
                "conversation_history": [],
                "current_state": "idle",
                "pending_actions": [],
                "user_preferences": self._get_user_preferences(user_id)
            })
            
            # Add user message to context for action detection
            context["user_message"] = message
            
            # Analyze message with advanced NLP
            extracted_info = self._analyze_message(message, context)
            
            # Update context
            context["conversation_history"].append({
                "timestamp": datetime.now().isoformat(),
                "user_message": message,
                "extracted_info": extracted_info
            })
            
            # Generate intelligent response with example-based learning
            response = self._generate_response_with_examples(extracted_info, context)
            
            # Update context with response
            context["conversation_history"].append({
                "timestamp": datetime.now().isoformat(),
                "agent_response": response,
                "action_taken": response.action_taken
            })
            
            # Store updated context
            self.conversation_contexts[context_id] = context
            
            return {
                "message": response.message,
                "action_taken": response.action_taken,
                "suggestions": response.suggestions,
                "data": response.data,
                "confidence": response.confidence,
                "requires_confirmation": response.requires_confirmation,
                "context_id": context_id
            }
            
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            return {
                "message": "I apologize, but I encountered an error processing your request. Could you please try rephrasing your message?",
                "action_taken": None,
                "suggestions": ["Try asking about your availability", "Schedule a meeting", "Check your calendar"],
                "data": {},
                "confidence": 0.0,
                "requires_confirmation": False,
                "context_id": context_id
            }
    
    def _analyze_message(self, message: str, context: Dict) -> ExtractedInfo:
        """
        Advanced message analysis with NLP techniques
        """
        message_lower = message.lower()
        
        # Intent recognition with confidence scoring
        intent_scores = {}
        
        # Check for negative responses first
        negative_patterns = [
            r"\bno\b", r"\bnot\b", r"\bnever\b", r"\bdon't\b", r"\bdoesn't\b",
            r"\bwon't\b", r"\bcancel\b", r"\bstop\b", r"\bend\b", r"\bquit\b"
        ]
        
        negative_score = 0.0
        for pattern in negative_patterns:
            if re.search(pattern, message_lower, re.IGNORECASE):
                negative_score += 0.5
        
        if negative_score > 0:
            # This is likely a negative response, check context
            context_history = context.get("conversation_history", [])
            if context_history:
                last_response = context_history[-1].get("agent_response", {})
                if "?" in last_response.get("message", ""):
                    # If last response was a question, this is likely a negative answer
                    intent_scores[IntentType.GENERAL_QUERY] = 0.8
                    intent_scores[IntentType.CANCEL] = 0.6
        
        # Regular intent patterns
        for intent_type, config in self.intent_patterns.items():
            score = 0.0
            for pattern in config["patterns"]:
                matches = re.findall(pattern, message_lower, re.IGNORECASE)
                if matches:
                    score += len(matches) * 0.3
                    score += len(message_lower) / 100  # Length bonus
            
            intent_scores[intent_type] = min(score, 1.0)
        
        # Determine primary intent
        primary_intent = max(intent_scores.items(), key=lambda x: x[1])
        
        # Entity extraction
        entities = self._extract_entities(message)
        
        # Context analysis
        context_info = self._analyze_context(message, context)
        
        # Sentiment analysis (basic)
        sentiment = self._analyze_sentiment(message)
        
        # Urgency detection
        urgency = self._detect_urgency(message)
        
        return ExtractedInfo(
            intent=primary_intent[0],
            confidence=primary_intent[1],
            entities=entities,
            context=context_info,
            sentiment=sentiment,
            urgency=urgency
        )
    
    def _extract_entities(self, message: str) -> Dict[str, Any]:
        """
        Extract named entities from message with enhanced patterns
        """
        entities = {}
        message_lower = message.lower()
        
        # Enhanced date extraction
        date_patterns = [
            r"monday|tuesday|wednesday|thursday|friday|saturday|sunday",
            r"tomorrow|today|next week|this week",
            r"next monday|next tuesday|next wednesday|next thursday|next friday",
            r"upcoming monday|upcoming tuesday|upcoming wednesday|upcoming thursday|upcoming friday",
            r"(\d{1,2})[/-](\d{1,2})",  # MM/DD or DD/MM
            r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})"  # MM/DD/YYYY
        ]
        
        for pattern in date_patterns:
            matches = re.findall(pattern, message_lower, re.IGNORECASE)
            if matches:
                if isinstance(matches[0], tuple):
                    # Handle date formats like MM/DD
                    if len(matches[0]) == 2:
                        entities["date"] = f"{matches[0][0]}/{matches[0][1]}"
                    elif len(matches[0]) == 3:
                        entities["date"] = f"{matches[0][0]}/{matches[0][1]}/{matches[0][2]}"
                else:
                    # Handle day names and relative dates
                    entities["date"] = matches[0]
                break
        
        # Enhanced time extraction
        time_patterns = [
            r"(\d{1,2}):(\d{2})\s*(am|pm)?",
            r"(\d{1,2})\s*(am|pm)",
            r"morning|afternoon|evening|night"
        ]
        
        for pattern in time_patterns:
            matches = re.findall(pattern, message_lower, re.IGNORECASE)
            if matches:
                if isinstance(matches[0], tuple):
                    time_str = " ".join(matches[0])
                else:
                    time_str = matches[0]
                entities["time"] = time_str
                break
        
        # Enhanced person extraction
        person_patterns = [
            r"(?:with|meet|call|discuss)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",
            r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:meeting|call|discussion)",
            r"(?:schedule|book|arrange)\s+(?:meeting|call)\s+with\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+on\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)",
            r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+at\s+\d{1,2}(?:am|pm)?"
        ]
        
        for pattern in person_patterns:
            matches = re.findall(pattern, message, re.IGNORECASE)
            if matches:
                # Clean up the person name
                person_name = matches[0].strip()
                if person_name and len(person_name) > 1:  # Avoid single letters
                    entities["person"] = person_name
                    break
        
        # Enhanced topic extraction
        topic_patterns = [
            r"(about|regarding|concerning)\s+([^,\.]+)",
            r"(discuss|talk\s+about)\s+([^,\.]+)",
            r"(meeting|call)\s+(for|about)\s+([^,\.]+)",
            r"(project|review|discussion)\s+([^,\.]+)"
        ]
        
        for pattern in topic_patterns:
            matches = re.findall(pattern, message_lower, re.IGNORECASE)
            if matches:
                entities["topic"] = matches[0][-1].strip()
                break
        
        # Email extraction
        email_patterns = [
            r"([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})",
            r"email\s+(?:is\s+)?([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})",
            r"([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\s+email"
        ]
        
        for pattern in email_patterns:
            matches = re.findall(pattern, message, re.IGNORECASE)
            if matches:
                entities["guest_email"] = matches[0]
                break
        
        # Enhanced duration extraction
        duration_patterns = [
            r"(\d+)\s*(hour|hr|minute|min)",
            r"(\d+)\s*(hour|hr)s?",
            r"(\d+)\s*(minute|min)s?"
        ]
        
        for pattern in duration_patterns:
            matches = re.findall(pattern, message_lower)
            if matches:
                entities["duration"] = f"{matches[0][0]} {matches[0][1]}"
                break
        
        return entities
    
    def _analyze_context(self, message: str, context: Dict) -> Dict[str, Any]:
        """
        Analyze conversation context and carry forward information
        """
        context_info = {
            "complete_info": {},
            "missing_info": [],
            "conversation_history": context.get("conversation_history", []),
            "asked_questions": context.get("asked_questions", [])
        }
        
        # Get entities from current message
        current_entities = self._extract_entities(message)
        
        # Get entities from previous messages in this conversation
        previous_entities = {}
        for conv in context.get("conversation_history", []):
            if "extracted_info" in conv and conv["extracted_info"].entities:
                for key, value in conv["extracted_info"].entities.items():
                    if value and key not in previous_entities:
                        previous_entities[key] = value
        
        # Combine current and previous entities (current takes precedence)
        all_entities = {**previous_entities, **current_entities}
        
        # Determine what information we have and what's missing
        required_info = ["person", "date", "time", "topic"]
        
        for info_type in required_info:
            if all_entities.get(info_type):
                context_info["complete_info"][info_type] = all_entities[info_type]
            else:
                context_info["missing_info"].append(info_type)
        
        # Special handling for date parsing
        if "date" in all_entities:
            date_value = all_entities["date"]
            if "next" in date_value.lower() or "upcoming" in date_value.lower():
                # Convert "next Monday" to actual date
                from datetime import datetime, timedelta
                today = datetime.now()
                
                if "monday" in date_value.lower():
                    days_ahead = 0 - today.weekday()  # Monday is 0
                    if days_ahead <= 0:  # Target day already happened this week
                        days_ahead += 7
                    target_date = today + timedelta(days=days_ahead)
                    context_info["complete_info"]["date"] = target_date.strftime("%Y-%m-%d")
                elif "tuesday" in date_value.lower():
                    days_ahead = 1 - today.weekday()
                    if days_ahead <= 0:
                        days_ahead += 7
                    target_date = today + timedelta(days=days_ahead)
                    context_info["complete_info"]["date"] = target_date.strftime("%Y-%m-%d")
                elif "wednesday" in date_value.lower():
                    days_ahead = 2 - today.weekday()
                    if days_ahead <= 0:
                        days_ahead += 7
                    target_date = today + timedelta(days=days_ahead)
                    context_info["complete_info"]["date"] = target_date.strftime("%Y-%m-%d")
                elif "thursday" in date_value.lower():
                    days_ahead = 3 - today.weekday()
                    if days_ahead <= 0:
                        days_ahead += 7
                    target_date = today + timedelta(days=days_ahead)
                    context_info["complete_info"]["date"] = target_date.strftime("%Y-%m-%d")
                elif "friday" in date_value.lower():
                    days_ahead = 4 - today.weekday()
                    if days_ahead <= 0:
                        days_ahead += 7
                    target_date = today + timedelta(days=days_ahead)
                    context_info["complete_info"]["date"] = target_date.strftime("%Y-%m-%d")
            elif date_value.lower() == "monday":
                # Convert "Monday" to next Monday
                from datetime import datetime, timedelta
                today = datetime.now()
                days_ahead = 0 - today.weekday()  # Monday is 0
                if days_ahead <= 0:  # Target day already happened this week
                    days_ahead += 7
                target_date = today + timedelta(days=days_ahead)
                context_info["complete_info"]["date"] = target_date.strftime("%Y-%m-%d")
            elif date_value.lower() == "tomorrow":
                # Convert "tomorrow" to actual date
                from datetime import datetime, timedelta
                tomorrow = datetime.now() + timedelta(days=1)
                context_info["complete_info"]["date"] = tomorrow.strftime("%Y-%m-%d")
        
        # Check if we have enough info to take action
        if len(context_info["missing_info"]) == 0:
            context_info["can_schedule"] = True
        else:
            context_info["can_schedule"] = False
        
        return context_info
    
    def _analyze_sentiment(self, message: str) -> str:
        """
        Basic sentiment analysis
        """
        positive_words = ["great", "good", "perfect", "excellent", "thanks", "thank you"]
        negative_words = ["bad", "terrible", "awful", "hate", "dislike", "problem"]
        
        message_lower = message.lower()
        positive_count = sum(1 for word in positive_words if word in message_lower)
        negative_count = sum(1 for word in negative_words if word in message_lower)
        
        if positive_count > negative_count:
            return "positive"
        elif negative_count > positive_count:
            return "negative"
        else:
            return "neutral"
    
    def _detect_urgency(self, message: str) -> str:
        """
        Detect urgency level in message
        """
        urgent_words = ["urgent", "asap", "immediately", "now", "quick", "emergency"]
        message_lower = message.lower()
        
        if any(word in message_lower for word in urgent_words):
            return "high"
        elif "soon" in message_lower or "today" in message_lower:
            return "medium"
        else:
            return "low"
    
    def _generate_response(self, extracted_info: ExtractedInfo, context: Dict) -> AgentResponse:
        """
        Generate response based on intent and context
        """
        # Use our agent logic first, not LLM responses
        if extracted_info.intent == IntentType.SCHEDULE_MEETING:
            return self._handle_schedule_meeting(extracted_info, context)
        elif extracted_info.intent == IntentType.CHECK_AVAILABILITY:
            return self._handle_check_availability(extracted_info, context)
        elif extracted_info.intent == IntentType.CANCEL:
            return self._handle_cancel(extracted_info, context)
        elif extracted_info.intent == IntentType.RESCHEDULE:
            return self._handle_reschedule(extracted_info, context)
        elif extracted_info.intent == IntentType.GENERAL_QUERY:
            return self._handle_general_query(extracted_info, context)
        else:
            return self._generate_clarification_response(extracted_info, context)
    
    def _generate_response_with_examples(self, extracted_info: ExtractedInfo, context: Dict) -> AgentResponse:
        """
        Generate response using example-based learning
        """
        # Find similar examples
        similar_examples = self._find_similar_examples(extracted_info, context)
        
        # Use examples to guide response generation
        if similar_examples:
            return self._generate_response_from_examples(extracted_info, context, similar_examples)
        else:
            return self._generate_response(extracted_info, context)
    
    def _find_similar_examples(self, extracted_info: ExtractedInfo, context: Dict) -> List[Dict]:
        """
        Find similar examples from the training data
        """
        similar_examples = []
        
        for example in self.examples:
            for turn in example["conversation"]:
                # Check if intent matches
                if turn.get("action_taken") == extracted_info.intent.value:
                    # Check if entities are similar
                    entity_similarity = self._calculate_entity_similarity(
                        extracted_info.entities, 
                        turn.get("entities", {})
                    )
                    
                    if entity_similarity > 0.5:  # Similarity threshold
                        similar_examples.append(turn)
        
        return similar_examples[:3]  # Return top 3 similar examples
    
    def _calculate_entity_similarity(self, entities1: Dict, entities2: Dict) -> float:
        """
        Calculate similarity between two entity sets
        """
        if not entities1 or not entities2:
            return 0.0
        
        common_keys = set(entities1.keys()) & set(entities2.keys())
        if not common_keys:
            return 0.0
        
        matches = 0
        total = len(common_keys)
        
        for key in common_keys:
            if entities1[key] == entities2[key]:
                matches += 1
        
        return matches / total
    
    def _generate_response_from_examples(self, extracted_info: ExtractedInfo, context: Dict, examples: List[Dict]) -> AgentResponse:
        """
        Generate response based on similar examples
        """
        # Use the most similar example as a template
        best_example = examples[0]
        
        # Check if we have complete information for the action
        action_pattern = self.action_patterns.get(extracted_info.intent.value)
        if action_pattern:
            required_entities = action_pattern.get("required_entities", [])
            missing_entities = []
            
            for entity in required_entities:
                if not extracted_info.entities.get(entity):
                    missing_entities.append(entity)
            
            if not missing_entities:
                # We have complete info, take action
                return self._take_action_based_on_example(extracted_info, context, best_example)
            else:
                # Ask for missing info
                return self._ask_for_missing_info(extracted_info, context, missing_entities)
        
        # Fallback to regular response generation
        return self._generate_response(extracted_info, context)
    
    def _take_action_based_on_example(self, extracted_info: ExtractedInfo, context: Dict, example: Dict) -> AgentResponse:
        """
        Take action based on example pattern
        """
        if extracted_info.intent == IntentType.SCHEDULE_MEETING:
            return self._handle_schedule_meeting(extracted_info, context)
        elif extracted_info.intent == IntentType.CHECK_AVAILABILITY:
            return self._handle_check_availability(extracted_info, context)
        elif extracted_info.intent == IntentType.CANCEL:
            return self._handle_cancel(extracted_info, context)
        else:
            return self._generate_response(extracted_info, context)
    
    def _ask_for_missing_info(self, extracted_info: ExtractedInfo, context: Dict, missing_entities: List[str]) -> AgentResponse:
        """
        Ask for missing information based on examples
        """
        if "person" in missing_entities:
            question = "Who would you like to meet with?"
        elif "date" in missing_entities:
            question = f"What date would you like to schedule the meeting?"
        elif "time" in missing_entities:
            question = f"What time would you like to meet?"
        elif "topic" in missing_entities:
            question = f"What would you like to discuss?"
        else:
            question = f"Please provide: {', '.join(missing_entities)}"
        
        return AgentResponse(
            message=f"❓ {question}",
            action_taken="asking_for_info",
            suggestions=["Provide the missing information", "Check availability first"],
            data={"missing_info": missing_entities, "current_entities": extracted_info.entities},
            confidence=0.7,
            requires_confirmation=True
        )
    
    def _handle_schedule_meeting(self, extracted_info: ExtractedInfo, context: Dict) -> AgentResponse:
        """
        Handle meeting scheduling with intelligent context awareness
        """
        user_id = context["user_id"]
        entities = extracted_info.entities
        context_info = extracted_info.context
        
        # Use combined entities from context analysis
        all_entities = {**context_info.get("complete_info", {}), **entities}
        
        # Check if we have enough information to schedule
        required_info = ["person", "date", "time", "topic"]
        missing_info = context_info.get("missing_info", [])
        
        # Also check if we have guest email (optional but preferred)
        if not all_entities.get("guest_email"):
            missing_info.append("guest_email")
        
        # If we have all required info, attempt to schedule
        if len(missing_info) == 0:
            try:
                # Extract meeting details
                person = all_entities.get("person", "Unknown")
                date = all_entities.get("date", "Unknown")
                time = all_entities.get("time", "Unknown")
                topic = all_entities.get("topic", "General discussion")
                duration = all_entities.get("duration", "30 minutes")
                
                # Create the meeting
                meeting_data = {
                    "title": f"Meeting with {person} - {topic}",
                    "start_time": f"{date} {time}",
                    "duration": duration,
                    "description": f"Meeting with {person} to discuss {topic}",
                    "attendees": [person]
                }
                
                # ACTUALLY CREATE THE BOOKING
                try:
                    # First, find an available slot for the requested time
                    from app.models.models import User, AvailabilitySlot
                    from datetime import datetime, timedelta
                    
                    # Get user
                    user = self.db.query(User).filter(User.id == user_id).first()
                    if not user:
                        return AgentResponse(
                            message="❌ User not found",
                            action_taken="scheduling_failed",
                            suggestions=["Try again", "Check your account"],
                            data={"error": "User not found"},
                            confidence=0.5,
                            requires_confirmation=True
                        )
                    
                    # Parse the date and time
                    try:
                        # Handle different date formats
                        if isinstance(date, str):
                            if date.lower() == "monday":
                                # Find next Monday
                                today = datetime.now()
                                days_ahead = 0 - today.weekday()  # Monday is 0
                                if days_ahead <= 0:  # Target day already happened this week
                                    days_ahead += 7
                                target_date = today + timedelta(days=days_ahead)
                            elif date.lower() == "tomorrow":
                                target_date = datetime.now() + timedelta(days=1)
                            else:
                                # Try to parse as YYYY-MM-DD
                                target_date = datetime.strptime(date, "%Y-%m-%d")
                        else:
                            target_date = date
                        
                        # Parse time (e.g., "6pm" -> 18:00)
                        time_str = time.lower().replace("pm", "").replace("am", "")
                        hour = int(time_str)
                        if "pm" in time.lower() and hour != 12:
                            hour += 12
                        elif "am" in time.lower() and hour == 12:
                            hour = 0
                        
                        start_time = target_date.replace(hour=hour, minute=0, second=0, microsecond=0)
                        end_time = start_time + timedelta(minutes=30)  # Default 30 minutes
                        
                    except Exception as e:
                        return AgentResponse(
                            message=f"❌ Could not parse date/time: {str(e)}",
                            action_taken="scheduling_failed",
                            suggestions=["Try again with clearer date/time", "Check availability first"],
                            data={"error": f"Date/time parsing error: {str(e)}"},
                            confidence=0.5,
                            requires_confirmation=True
                        )
                    
                    # Create or find an availability slot
                    slot = self.db.query(AvailabilitySlot).filter(
                        AvailabilitySlot.host_user_id == user_id,
                        AvailabilitySlot.start_time == start_time,
                        AvailabilitySlot.is_available == True
                    ).first()
                    
                    if not slot:
                        # Create a new availability slot
                        slot = AvailabilitySlot(
                            host_user_id=user_id,
                            start_time=start_time,
                            end_time=end_time,
                            is_available=True
                        )
                        self.db.add(slot)
                        self.db.commit()
                        self.db.refresh(slot)
                    
                    # Create the booking
                    from app.schemas.schemas import PublicBookingCreate
                    guest_email = all_entities.get("guest_email", f"{person.lower()}@example.com")
                    booking_data = PublicBookingCreate(
                        guest_name=person,
                        guest_email=guest_email,
                        guest_message=f"Meeting about: {topic}"
                    )
                    
                    # Use the actual booking service
                    from app.services.booking_service import create_booking
                    booking = create_booking(
                        db=self.db,
                        booking_data=booking_data,
                        slot_id=slot.id,
                        host_user=user
                    )
                    
                    if booking:
                        return AgentResponse(
                            message=f"✅ **Meeting ACTUALLY scheduled!**\n📅 {date} at {time}\n👤 {person}\n📝 {topic}\n🔗 Booking ID: {booking.id}\n📧 Guest email: {booking.guest_email}",
                            action_taken="meeting_scheduled",
                            suggestions=["Check your calendar", "Send calendar invite", "Set reminders"],
                            data={"meeting_details": meeting_data, "booking_id": booking.id},
                            confidence=0.9,
                            requires_confirmation=False
                        )
                    else:
                        return AgentResponse(
                            message="❌ Failed to create booking - slot may not be available",
                            action_taken="scheduling_failed",
                            suggestions=["Try again", "Check availability first"],
                            data={"error": "Slot not available"},
                            confidence=0.5,
                            requires_confirmation=True
                        )
                        
                except Exception as e:
                    return AgentResponse(
                        message=f"❌ Error scheduling meeting: {str(e)}",
                        action_taken="scheduling_failed",
                        suggestions=["Try again", "Check availability first"],
                        data={"error": str(e)},
                        confidence=0.5,
                        requires_confirmation=True
                    )
                    
            except Exception as e:
                return AgentResponse(
                    message=f"❌ Error processing meeting request: {str(e)}",
                    action_taken="scheduling_failed",
                    suggestions=["Try again", "Check availability first"],
                    data={"error": str(e)},
                    confidence=0.5,
                    requires_confirmation=True
                )
        
        # If missing information, ask for it intelligently
        else:
            # Prioritize what to ask for
            if "topic" in missing_info:
                question = f"What would you like to discuss with {all_entities.get('person', 'them')}?"
            elif "guest_email" in missing_info:
                question = f"What is {all_entities.get('person', 'their')} email address?"
            elif "person" in missing_info:
                question = f"Who would you like to meet with?"
            elif "date" in missing_info:
                question = f"What date would you like to schedule the meeting with {all_entities.get('person', 'them')}?"
            elif "time" in missing_info:
                question = f"What time would you like to meet with {all_entities.get('person', 'them')} on {all_entities.get('date', 'that date')}?"
            else:
                question = f"Please provide: {', '.join(missing_info)}"
            
            return AgentResponse(
                message=f"❓ {question}",
                action_taken="asking_for_info",
                suggestions=["Provide the missing information", "Check availability first"],
                data={"missing_info": missing_info, "current_entities": all_entities},
                confidence=0.7,
                requires_confirmation=True
            )
    
    def _handle_check_availability(self, extracted_info: ExtractedInfo, context: Dict) -> AgentResponse:
        """
        Handle availability checking with intelligent insights
        """
        user_id = context["user_id"]
        available_slots = availability_service.get_available_slots_for_booking(self.db, user_id)
        upcoming_bookings = booking_service.get_upcoming_bookings(self.db, user_id)
        
        # Get REAL calendar events if calendar is connected
        calendar_events = []
        try:
            from app.models.models import User
            user = self.db.query(User).filter(User.id == user_id).first()
            if user and user.google_access_token:
                from app.services import google_calendar_service
                calendar_service = google_calendar_service.GoogleCalendarService(
                    access_token=user.google_access_token,
                    refresh_token=user.google_refresh_token
                )
                calendar_events = calendar_service.get_events()
        except Exception as e:
            logger.warning(f"Could not fetch calendar events: {e}")
        
        # Analyze availability patterns
        availability_insights = self._analyze_availability_patterns(available_slots, upcoming_bookings)
        
        if available_slots:
            response_message = f"📅 **Available time slots:** {len(available_slots)} slots\n"
            response_message += f"⏰ **Best time:** {availability_insights['best_time']}\n"
            response_message += f"📊 **Busy:** {availability_insights['busy_percentage']}% booked this week\n\n"
            
            # Show actual available slots
            if available_slots[:5]:
                response_message += "**Next available slots:**\n"
                for slot in available_slots[:5]:
                    response_message += f"• {slot.get('date', 'Unknown')} {slot.get('start_time', '')} - {slot.get('end_time', '')}\n"
            
            # Show calendar events if available
            if calendar_events:
                response_message += f"\n**📅 Calendar events today:**\n"
                for event in calendar_events[:3]:
                    event_time = event.get('start', {}).get('dateTime', 'No time')
                    if event_time != 'No time':
                        event_time = event_time.split('T')[1][:5]  # Extract time only
                    response_message += f"• {event.get('summary', 'No title')} - {event_time}\n"
            
            return AgentResponse(
                message=response_message,
                action_taken="availability_checked",
                suggestions=[
                    "Schedule a meeting",
                    "Show detailed calendar",
                    "Add more availability"
                ],
                data={
                    "available_slots": available_slots[:5],
                    "upcoming_bookings": upcoming_bookings[:5],
                    "calendar_events": calendar_events,
                    "insights": availability_insights
                },
                confidence=extracted_info.confidence,
                requires_confirmation=False
            )
        else:
            return AgentResponse(
                message="❌ **You're fully booked!** No available time slots in your calendar.\n\nWould you like me to help you add some availability or reschedule existing meetings?",
                action_taken="no_availability",
                suggestions=[
                    "Add availability slots",
                    "Reschedule existing meetings",
                    "Check next week's availability"
                ],
                data={"upcoming_bookings": upcoming_bookings[:5], "calendar_events": calendar_events},
                confidence=extracted_info.confidence,
                requires_confirmation=False
            )
    
    def _find_best_slots(self, available_slots: List[Dict], time_preferences: List[str]) -> List[Dict]:
        """
        Find the best available slots based on user preferences
        """
        if not available_slots:
            return []
        
        # Score slots based on preferences
        scored_slots = []
        for slot in available_slots:
            score = 0
            
            # Prefer business hours
            start_hour = int(slot['start_time'].split(':')[0])
            if 9 <= start_hour <= 17:
                score += 2
            
            # Prefer today/tomorrow if mentioned
            slot_date = slot['date']
            if "today" in time_preferences and slot_date == datetime.now().strftime('%Y-%m-%d'):
                score += 3
            elif "tomorrow" in time_preferences and slot_date == (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d'):
                score += 3
            
            scored_slots.append((slot, score))
        
        # Sort by score and return top slots
        scored_slots.sort(key=lambda x: x[1], reverse=True)
        return [slot for slot, score in scored_slots[:5]]
    
    def _analyze_availability_patterns(self, available_slots: List[Dict], upcoming_bookings: List[Dict]) -> Dict[str, Any]:
        """
        Analyze availability patterns and provide insights
        """
        if not available_slots:
            return {"best_time": "No availability", "busy_percentage": 100}
        
        # Find most common available time
        time_counts = {}
        for slot in available_slots:
            hour = slot['start_time'].split(':')[0]
            time_counts[hour] = time_counts.get(hour, 0) + 1
        
        best_hour = max(time_counts.items(), key=lambda x: x[1])[0]
        best_time = f"{best_hour}:00"
        
        # Calculate busy percentage
        total_slots = len(available_slots) + len(upcoming_bookings)
        busy_percentage = round((len(upcoming_bookings) / total_slots) * 100) if total_slots > 0 else 0
        
        return {
            "best_time": best_time,
            "busy_percentage": busy_percentage,
            "total_available": len(available_slots),
            "total_booked": len(upcoming_bookings)
        }
    
    def _get_user_preferences(self, user_id: int) -> Dict[str, Any]:
        """
        Get user preferences for personalization
        """
        # This would typically come from a user preferences table
        return {
            "preferred_meeting_duration": 30,
            "preferred_meeting_times": ["9:00", "14:00", "16:00"],
            "timezone": "UTC",
            "notification_preferences": "email"
        }
    
    def _generate_clarification_response(self, extracted_info: ExtractedInfo, context: Dict) -> AgentResponse:
        """
        Generate response when intent is unclear
        """
        return AgentResponse(
            message="I'm not quite sure what you'd like me to help you with. Could you please clarify? I can help you schedule meetings, check your availability, or manage your calendar.",
            action_taken="asked_for_clarification",
            suggestions=[
                "Schedule a meeting",
                "Check my availability",
                "Show my calendar",
                "Reschedule a meeting"
            ],
            data={},
            confidence=0.0,
            requires_confirmation=False
        )
    
    def _handle_reschedule(self, extracted_info: ExtractedInfo, context: Dict) -> AgentResponse:
        """
        Handle meeting rescheduling
        """
        return AgentResponse(
            message="I'd be happy to help you reschedule a meeting. Which meeting would you like to move?",
            action_taken="reschedule_requested",
            suggestions=[
                "Show my upcoming meetings",
                "Reschedule my next meeting",
                "Cancel instead"
            ],
            data={},
            confidence=extracted_info.confidence,
            requires_confirmation=False
        )
    
    def _handle_cancel(self, extracted_info: ExtractedInfo, context: Dict) -> AgentResponse:
        """
        Handle meeting cancellation with REAL action
        """
        user_id = context["user_id"]
        entities = extracted_info.entities
        
        # Get upcoming bookings
        upcoming_bookings = booking_service.get_upcoming_bookings(self.db, user_id)
        
        if upcoming_bookings:
            # Find the booking to cancel
            booking_to_cancel = None
            for booking in upcoming_bookings:
                if entities.get("person") and entities["person"].lower() in booking.get("guest_name", "").lower():
                    booking_to_cancel = booking
                    break
                elif entities.get("date") and entities["date"] in booking.get("start_time", ""):
                    booking_to_cancel = booking
                    break
            
            if booking_to_cancel:
                # Check if user confirmed cancellation
                user_message = context.get("user_message", "").lower()
                if "yes" in user_message or "confirm" in user_message or "cancel" in user_message:
                    # ACTUALLY CANCEL THE BOOKING
                    try:
                        from app.models.models import Booking
                        booking_id = booking_to_cancel.get("id")
                        if booking_id:
                            booking = self.db.query(Booking).filter(Booking.id == booking_id).first()
                            if booking:
                                # Delete from database
                                self.db.delete(booking)
                                self.db.commit()
                                
                                # Try to delete from Google Calendar if connected
                                try:
                                    from app.models.models import User
                                    user = self.db.query(User).filter(User.id == user_id).first()
                                    if user and user.google_access_token and booking.google_event_id:
                                        from app.services import google_calendar_service
                                        calendar_service = google_calendar_service.GoogleCalendarService(
                                            access_token=user.google_access_token,
                                            refresh_token=user.google_refresh_token
                                        )
                                        calendar_service.delete_event(booking.google_event_id)
                                except Exception as e:
                                    logger.warning(f"Could not delete from Google Calendar: {e}")
                                
                                return AgentResponse(
                                    message=f"✅ **Meeting ACTUALLY cancelled!**\n👤 {booking_to_cancel.get('guest_name')}\n📅 {booking_to_cancel.get('start_time')}\n🗑️ Removed from calendar",
                                    action_taken="meeting_cancelled",
                                    suggestions=["Schedule a new meeting", "Check availability", "View calendar"],
                                    data={"cancelled_booking": booking_to_cancel},
                                    confidence=0.9,
                                    requires_confirmation=False
                                )
                    except Exception as e:
                        return AgentResponse(
                            message=f"❌ **Failed to cancel meeting:** {str(e)}",
                            action_taken="cancellation_failed",
                            suggestions=["Try again", "Contact support"],
                            data={"error": str(e)},
                            confidence=0.5,
                            requires_confirmation=True
                        )
                else:
                    return AgentResponse(
                        message=f"❓ **Confirm cancellation:**\n👤 {booking_to_cancel.get('guest_name')}\n📅 {booking_to_cancel.get('start_time')}\n\nReply 'yes' to confirm cancellation.",
                        action_taken="cancellation_confirmation",
                        suggestions=["Reply 'yes' to confirm", "Reply 'no' to keep meeting"],
                        data={"booking_to_cancel": booking_to_cancel},
                        confidence=0.8,
                        requires_confirmation=True
                    )
            else:
                return AgentResponse(
                    message="❌ **No matching meeting found.**\n\n**Upcoming meetings:**\n" + "\n".join([f"• {b.get('guest_name')} - {b.get('start_time')}" for b in upcoming_bookings[:3]]),
                    action_taken="cancellation_failed",
                    suggestions=["Specify the meeting", "Show all meetings", "Check calendar"],
                    data={"upcoming_bookings": upcoming_bookings},
                    confidence=0.5,
                    requires_confirmation=False
                )
        else:
            return AgentResponse(
                message="📅 **No upcoming meetings found.**\n\nYou don't have any meetings to cancel.",
                action_taken="no_meetings",
                suggestions=["Schedule a new meeting", "Check your calendar"],
                data={},
                confidence=0.9,
                requires_confirmation=False
            )
    
    def _handle_general_query(self, extracted_info: ExtractedInfo, context: Dict) -> AgentResponse:
        """Handle general queries about the system"""
        response = AgentResponse(
            message="I'm here to help you with scheduling! I can help you book meetings, check availability, reschedule, or cancel appointments. What would you like to do?",
            action_taken=None,
            suggestions=[
                "Schedule a meeting",
                "Check my availability", 
                "Reschedule an appointment",
                "Cancel a meeting"
            ],
            data={},
            confidence=0.8,
            requires_confirmation=False
        )
        return response
    
    def _get_conversation_examples(self) -> List[Dict]:
        """Get conversation examples for learning"""
        return [
            {
                "user_message": "I need to schedule a meeting with John tomorrow",
                "intent": IntentType.SCHEDULE_MEETING,
                "entities": {"person": "John", "time": "tomorrow"},
                "response": "I'll help you schedule a meeting with John tomorrow. What time works best for you?",
                "action": "schedule_meeting"
            },
            {
                "user_message": "When am I free this week?",
                "intent": IntentType.CHECK_AVAILABILITY,
                "entities": {"time": "this week"},
                "response": "Let me check your availability for this week. Here are your free time slots:",
                "action": "check_availability"
            },
            {
                "user_message": "Can we reschedule our meeting to Friday?",
                "intent": IntentType.RESCHEDULE,
                "entities": {"time": "Friday"},
                "response": "I'll help you reschedule the meeting to Friday. What time works best?",
                "action": "reschedule_meeting"
            }
        ]
    
    def _get_entity_patterns(self) -> Dict[str, List[str]]:
        """Get entity extraction patterns"""
        return {
            "person": [
                r"(with|meet)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",
                r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(meeting|call)"
            ],
            "time": [
                r"(tomorrow|today|next\s+week|this\s+week|monday|tuesday|wednesday|thursday|friday|saturday|sunday)",
                r"(\d{1,2}:\d{2}\s*(?:am|pm)?)",
                r"(\d{1,2}\s*(?:am|pm))"
            ],
            "duration": [
                r"(\d+)\s*(?:min|minute|hour|hr)",
                r"(half\s+hour|hour|30\s+min|60\s+min)"
            ],
            "topic": [
                r"(about|regarding|concerning)\s+([^,\.]+)",
                r"(discuss|talk\s+about)\s+([^,\.]+)"
            ]
        }
    
    def _get_context_rules(self) -> Dict[str, Any]:
        """Get context analysis rules"""
        return {
            "urgency_indicators": ["urgent", "asap", "immediately", "right away"],
            "confirmation_indicators": ["yes", "confirm", "okay", "sure"],
            "cancellation_indicators": ["no", "cancel", "never mind", "forget it"],
            "time_preferences": ["morning", "afternoon", "evening", "business hours"]
        }
    
    def _get_action_patterns(self) -> Dict[str, List[str]]:
        """Get action patterns for different intents"""
        return {
            IntentType.SCHEDULE_MEETING: [
                "schedule_meeting",
                "create_booking", 
                "book_slot"
            ],
            IntentType.CHECK_AVAILABILITY: [
                "check_availability",
                "show_slots",
                "get_free_times"
            ],
            IntentType.RESCHEDULE: [
                "reschedule_meeting",
                "update_booking",
                "change_time"
            ],
            IntentType.CANCEL: [
                "cancel_meeting",
                "delete_booking",
                "remove_slot"
            ]
        } 