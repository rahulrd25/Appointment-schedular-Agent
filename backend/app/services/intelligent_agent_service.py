from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
import json
import logging
from datetime import datetime

from app.services.advanced_ai_agent_service import AdvancedAIAgentService, ExtractedInfo, AgentResponse
from app.services.knowledge_base_service import KnowledgeBaseService
from app.services.llm_provider import LLMService
from app.services.llm_calendar_service import LLMCalendarService
from app.models.models import User, AvailabilitySlot, Booking
from app.services import availability_service, booking_service, user_service
from app.services.advanced_ai_agent_service import IntentType

logger = logging.getLogger(__name__)

class IntelligentAgentService:
    """
    Intelligent Agent Service - The brain of the scheduling system
    Combines advanced NLP, knowledge base, learning, and intelligent decision making
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.ai_agent = AdvancedAIAgentService(db)
        self.knowledge_base = KnowledgeBaseService(db)
        
        # Initialize LLM service with debug logging
        try:
            self.llm_service = LLMService()  # Initialize LLM service
            logger.info(f"LLM Service initialized successfully with provider: {self.llm_service.provider_name}")
        except Exception as e:
            logger.error(f"Failed to initialize LLM service: {e}")
            logger.warning("AI agent will operate in rule-based mode only. Set OPENAI_API_KEY environment variable for LLM capabilities.")
            self.llm_service = None
        
        # Calendar service will be initialized per user when needed
        self.calendar_service = None
        
        self.conversation_contexts: Dict[str, Dict] = {}
        
        # Agent personality and capabilities
        self.agent_capabilities = {
            "natural_language_processing": True,
            "context_understanding": True,
            "learning_from_interactions": True,
            "personalization": True,
            "proactive_suggestions": True,
            "conflict_resolution": True,
            "multi_step_reasoning": True,
            "llm_enhanced": True,
            "calendar_integration": True
        }
    
    def _initialize_calendar_service(self, user_id: int):
        """Initialize calendar service for a specific user"""
        try:
            self.calendar_service = LLMCalendarService(self.db, user_id)
            logger.info(f"Calendar service initialized for user {user_id}")
        except Exception as e:
            logger.error(f"Failed to initialize calendar service for user {user_id}: {e}")
            self.calendar_service = None
    
    async def process_message(self, user_id: int, message: str, context_id: str = None) -> Dict[str, Any]:
        """
        Process user message with full intelligent capabilities including LLM
        """
        try:
            # Initialize calendar service for this user
            self._initialize_calendar_service(user_id)
            
            # Get or create conversation context
            if not context_id:
                context_id = f"user_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            context = self.conversation_contexts.get(context_id, {
                "user_id": user_id,
                "conversation_history": [],
                "current_state": "idle",
                "pending_actions": [],
                "user_preferences": self._get_user_preferences(user_id),
                "session_start": datetime.now().isoformat()
            })
            
            # Add calendar context if available
            if self.calendar_service:
                calendar_status = self.calendar_service.get_calendar_status()
                context["calendar_status"] = calendar_status
                
                if calendar_status["connected"]:
                    # Get calendar summary for context
                    calendar_summary = self.calendar_service.get_calendar_summary()
                    context["calendar_summary"] = calendar_summary
            
            # Add conversation history to prevent repetition
            context["recent_messages"] = context.get("conversation_history", [])[-5:]  # Last 5 messages
            context["asked_questions"] = context.get("asked_questions", [])  # Track what we've already asked
            
            # Add conversation summary for better context
            context["conversation_summary"] = self._generate_conversation_summary(context)
            
            # Add user preferences and patterns
            context["user_preferences"] = self._get_user_preferences(user_id)
            context["user_patterns"] = self.knowledge_base.get_user_patterns(user_id)
            
            # Step 1: Advanced NLP Analysis (with LLM enhancement)
            extracted_info = self.ai_agent._analyze_message(message, context)
            
            # Step 1.5: LLM Intent Analysis (ENABLED with better integration)
            if self.llm_service:
                try:
                    logger.info("Attempting LLM intent analysis...")
                    llm_intent_analysis = await self.llm_service.analyze_intent(message, context)
                    logger.info(f"LLM intent analysis successful: {llm_intent_analysis}")
                    # Merge LLM analysis with rule-based analysis (but prioritize our logic)
                    extracted_info = self._merge_intent_analysis(extracted_info, llm_intent_analysis)
                except Exception as e:
                    logger.warning(f"LLM analysis failed, using rule-based only: {e}")
                    # Continue with rule-based analysis only
            else:
                logger.warning("LLM service not available, using rule-based analysis only")
            
            # Step 2: Retrieve relevant knowledge
            relevant_knowledge = self.knowledge_base.get_relevant_knowledge(
                message, user_id, context
            )
            
            # Step 3: Get user patterns for personalization
            user_patterns = self.knowledge_base.get_user_patterns(user_id)
            
            # Step 4: Enhance context with knowledge and patterns
            enhanced_context = self._enhance_context_with_knowledge(
                context, relevant_knowledge, user_patterns, extracted_info
            )
            
            # Step 3: Generate intelligent response (ENABLED with better integration)
            if self.llm_service and extracted_info.confidence > 0.3:
                try:
                    response = await self._generate_intelligent_response(
                        extracted_info, enhanced_context, relevant_knowledge, user_patterns, message
                    )
                except Exception as e:
                    logger.warning(f"LLM response generation failed, using agent logic: {e}")
                    response = self.ai_agent._generate_response(extracted_info, context)
            else:
                # Use our agent logic for low confidence or when LLM is not available
                response = self.ai_agent._generate_response(extracted_info, context)
            
            # Step 6: Learn from this interaction
            conversation_data = {
                "user_id": user_id,
                "context_id": context_id,
                "conversation_history": context["conversation_history"] + [{
                    "timestamp": datetime.now().isoformat(),
                    "user_message": message,
                    "extracted_info": extracted_info,
                    "agent_response": response
                }],
                "extracted_info": extracted_info,
                "response": response,
                "llm_provider": self.llm_service.provider_name if self.llm_service else "rule-based",
                "entities": extracted_info.entities,
                "sentiment": extracted_info.sentiment,
                "urgency": extracted_info.urgency,
                "action_taken": response.action_taken,
                "conversation_context": context.get("conversation_summary", ""),
                "user_preferences": context.get("user_preferences", {}),
                "knowledge_used": [k.id for k in relevant_knowledge],
                "patterns_identified": [p.pattern_type for p in user_patterns]
            }
            
            self.knowledge_base.learn_from_conversation(user_id, conversation_data)
            
            # Update user patterns based on this interaction
            self._update_user_patterns(user_id, extracted_info, context)
            
            # Step 7: Update conversation context
            context["conversation_history"].append({
                "timestamp": datetime.now().isoformat(),
                "user_message": message,
                "extracted_info": extracted_info,
                "agent_response": response,
                "knowledge_used": [k.id for k in relevant_knowledge]
            })
            
            # Track asked questions to prevent repetition
            if "?" in response.message:
                if "asked_questions" not in context:
                    context["asked_questions"] = []
                context["asked_questions"].append({
                    "question": response.message,
                    "intent": extracted_info.intent,
                    "timestamp": datetime.now().isoformat()
                })
                # Keep only recent questions (last 5)
                context["asked_questions"] = context["asked_questions"][-5:]
            
            self.conversation_contexts[context_id] = context
            
            # Step 8: Prepare final response
            return {
                "message": response.message,
                "action_taken": response.action_taken,
                "suggestions": response.suggestions,
                "data": response.data,
                "confidence": response.confidence,
                "requires_confirmation": response.requires_confirmation,
                "context_id": context_id,
                "knowledge_used": [k.id for k in relevant_knowledge],
                "personalization_level": self._calculate_personalization_level(user_patterns),
                "learning_insights": self._generate_learning_insights(conversation_data)
            }
            
        except Exception as e:
            logger.error(f"Error in intelligent agent processing: {e}")
            return {
                "message": "I apologize, but I encountered an error processing your request. Let me try to help you with something else.",
                "action_taken": "error_handling",
                "suggestions": ["Try asking about your availability", "Schedule a meeting", "Check your calendar"],
                "data": {},
                "confidence": 0.0,
                "requires_confirmation": False,
                "context_id": context_id,
                "knowledge_used": [],
                "personalization_level": "basic",
                "learning_insights": []
            }
    
    def _enhance_context_with_knowledge(
        self, 
        context: Dict, 
        knowledge: List, 
        patterns: List, 
        extracted_info: ExtractedInfo
    ) -> Dict:
        """
        Enhance conversation context with knowledge and patterns
        """
        enhanced_context = context.copy()
        
        # Add knowledge insights
        enhanced_context["relevant_knowledge"] = {
            entry.id: entry.content for entry in knowledge
        }
        
        # Add user patterns
        enhanced_context["user_patterns"] = {
            pattern.pattern_type: pattern.pattern_data for pattern in patterns
        }
        
        # Add extracted information
        enhanced_context["current_intent"] = extracted_info.intent
        enhanced_context["current_entities"] = extracted_info.entities
        enhanced_context["sentiment"] = extracted_info.sentiment
        enhanced_context["urgency"] = extracted_info.urgency
        
        return enhanced_context
    
    async def _generate_intelligent_response(
        self, 
        extracted_info: ExtractedInfo, 
        context: Dict, 
        knowledge: List, 
        patterns: List,
        user_message: str
    ) -> AgentResponse:
        """
        Generate intelligent response using LLM with our context logic
        """
        try:
            # Use our context analysis to determine what to do
            context_info = extracted_info.context
            
            # If we have complete information for scheduling, use our logic
            if extracted_info.intent == IntentType.SCHEDULE_MEETING and context_info.get("can_schedule", False):
                return self.ai_agent._handle_schedule_meeting(extracted_info, context)
            
            # If we have missing information, ask for it using our logic
            if extracted_info.intent == IntentType.SCHEDULE_MEETING and context_info.get("missing_info"):
                return self.ai_agent._ask_for_missing_info(extracted_info, context, context_info["missing_info"])
            
            # For other cases, use LLM with enhanced context
            enhanced_prompt = self._create_enhanced_prompt(extracted_info, context, knowledge, patterns, user_message)
            
            if self.llm_service:
                llm_response = await self.llm_service.generate_response(enhanced_prompt)
                
                # Parse LLM response and create AgentResponse
                return self._parse_llm_response(llm_response, extracted_info, context)
            else:
                # Fallback to our agent logic
                return self.ai_agent._generate_response(extracted_info, context)
                
        except Exception as e:
            logger.error(f"Error in intelligent response generation: {e}")
            # Fallback to our agent logic
            return self.ai_agent._generate_response(extracted_info, context)
    
    def _create_enhanced_prompt(self, extracted_info: ExtractedInfo, context: Dict, knowledge: List, patterns: List, user_message: str) -> str:
        """
        Create enhanced prompt with our context information
        """
        context_info = extracted_info.context
        
        prompt = f"""
Role:
You are a reliable, context-aware appointment scheduling assistant. Your job is to understand user intent, keep track of context throughout the conversation, and handle the following tasks smoothly:

Schedule new meetings
Cancel meetings
Modify or reschedule meetings (including change, postpone, update details)

Your core priorities:

Minimize asking users the same questions repeatedly.

Extract information from user statements, even if details are implied (e.g., "book it next Friday at 4PM").

Clearly ask for only missing or ambiguous information, not for details already given.

Maintain context and reference previous replies in the conversation (never forget them).

Execute each user command (schedule, change, cancel, etc.) and confirm completion only after performing the necessary calendar action.

When scheduling, always gather:

The user's email address (for calendar and confirmation)
Date and time (accurately extract from natural language or day references—e.g., "this Saturday at 3")
Meeting subject or purpose
Time-zone (if not clear from the user's profile or inputs)
Preferred timeslot (if multiple options are available)

If details are missing or unclear:

Politely prompt ONLY for those specific missing or ambiguous pieces.

For relative dates ("next Monday"), always confirm the exact date as you interpret it before proceeding ("Just confirming, you mean [exact date]?").

When modifying or canceling:

Identify the relevant calendar entry (match by date, subject, or ID based on user's description).

Confirm with the user before deleting/modifying if there is ambiguity ("Do you mean the meeting scheduled on [date] about [subject]?").

Upon successful calendar action (schedule, cancel, change):

Confirm the specific action and details back to the user ("Your meeting '[subject]' has been scheduled for [date], [time]. You'll get a confirmation at [email].")

Never claim an action is 'done' before it is actually performed in the calendar system. If an API or action fails, explain the error.

You should:

Understand natural language, slang, and partially given details.

Adapt to corrections or clarifications quickly without starting over.

Maintain memory of the current scheduling session until the task is completed.

**KEY INSTRUCTIONS:**
- Do NOT ask the same detail twice in a session.
- Do NOT lose context—remember previous answers within the same conversation.
- Always extract date/time from relative references using today's date.
- Do NOT say a meeting is booked unless you've called the API or written to the calendar.
- After any action, summarize clearly to the user, citing subject, date, time, and email.

**EXAMPLE USER REQUESTS AND IDEAL HANDLING:**

**Example 1 - Basic Scheduling:**
User: "Book a call for Monday at 3."
You: "To confirm: you want to schedule a meeting on [exact date: Monday, July 28], at 3PM. What should be the meeting subject and your email for the invite?"

**Example 2 - Rescheduling:**
User: "Move my call next Friday to 6PM instead."
You: "Found 'Project Update Call' on [previous date] at 5PM. Would you like to reschedule it to Friday, August 1, at 6PM?"

**Example 3 - Cancellation:**
User: "Cancel my call about taxes."
You: "Canceling 'Taxes' meeting scheduled on [date/time]. Is that correct?"

**Example 4 - Relative Time:**
User: "Book for tomorrow evening."
You: "Confirming: should I book your meeting for [exact date/time: July 28, 6PM]? What's your email and the meeting subject?"

**Example 5 - Complete Info:**
User: "Schedule meeting with John tomorrow 2pm for project review"
You: "✅ Meeting scheduled! Your meeting 'project review' has been scheduled for tomorrow at 2pm with John. You'll get a confirmation at john@email.com."

CURRENT CONTEXT:
User Message: {user_message}
Intent: {extracted_info.intent.value}
Confidence: {extracted_info.confidence}

Complete Information: {context_info.get('complete_info', {})}
Missing Information: {context_info.get('missing_info', [])}
Can Schedule: {context_info.get('can_schedule', False)}

Conversation History (last 3 messages):
{self._format_conversation_history(context.get('conversation_history', [])[-3:])}

RESPONSE FORMAT:
- For scheduling with complete info: "✅ Meeting scheduled! [details with confirmation]"
- For missing info: "❓ [specific question about missing info only]"
- For confirmation: "Just confirming, you mean [exact details]?"
- For general help: "[helpful response with suggestions]"
- For errors: "❌ [specific error explanation]"

Remember: Only ask for what's actually missing, never repeat questions, and always confirm actions before claiming they're done.
"""
        return prompt
    
    def _format_conversation_history(self, history: List[Dict]) -> str:
        """
        Format conversation history for LLM prompt
        """
        formatted = []
        for entry in history:
            user_msg = entry.get('user_message', '')
            agent_msg = entry.get('agent_response', {}).get('message', '')
            if user_msg:
                formatted.append(f"User: {user_msg}")
            if agent_msg:
                formatted.append(f"Agent: {agent_msg}")
        return "\n".join(formatted)
    
    def _parse_llm_response(self, llm_response: str, extracted_info: ExtractedInfo, context: Dict) -> AgentResponse:
        """
        Parse LLM response and create AgentResponse
        """
        # Simple parsing - can be enhanced
        if "✅" in llm_response or "scheduled" in llm_response.lower():
            return AgentResponse(
                message=llm_response,
                action_taken="meeting_scheduled",
                suggestions=["Check your calendar", "Send calendar invite"],
                data={},
                confidence=0.8,
                requires_confirmation=False
            )
        elif "❓" in llm_response or "?" in llm_response:
            return AgentResponse(
                message=llm_response,
                action_taken="asking_for_info",
                suggestions=["Provide the missing information"],
                data={},
                confidence=0.7,
                requires_confirmation=True
            )
        else:
            return AgentResponse(
                message=llm_response,
                action_taken="general_help",
                suggestions=["Schedule a meeting", "Check availability"],
                data={},
                confidence=0.6,
                requires_confirmation=False
            )
    
    async def handle_calendar_action(self, user_id: int, action: str, **kwargs) -> Dict[str, Any]:
        """
        Handle calendar-specific actions like checking availability, scheduling, etc.
        """
        if not self.calendar_service or not self.calendar_service.is_calendar_connected():
            return {
                "success": False,
                "message": "Calendar not connected. Please connect your Google Calendar first.",
                "action_required": "connect_calendar"
            }
        
        try:
            if action == "check_availability":
                start_time = kwargs.get("start_time")
                end_time = kwargs.get("end_time")
                if start_time and end_time:
                    return self.calendar_service.check_availability(start_time, end_time)
                else:
                    return {"success": False, "message": "Start and end times required"}
            
            elif action == "get_available_slots":
                date = kwargs.get("date")
                duration = kwargs.get("duration_minutes", 30)
                slots = self.calendar_service.get_available_slots(date, duration)
                return {
                    "success": True,
                    "slots": slots,
                    "count": len(slots)
                }
            
            elif action == "get_upcoming_events":
                days = kwargs.get("days", 7)
                events = self.calendar_service.get_upcoming_events(days)
                return {
                    "success": True,
                    "events": events,
                    "count": len(events)
                }
            
            elif action == "schedule_meeting":
                title = kwargs.get("title")
                start_time = kwargs.get("start_time")
                end_time = kwargs.get("end_time")
                guest_email = kwargs.get("guest_email")
                description = kwargs.get("description")
                
                if not all([title, start_time, end_time, guest_email]):
                    return {"success": False, "message": "Missing required fields for scheduling"}
                
                return self.calendar_service.schedule_meeting(
                    title, start_time, end_time, guest_email, description
                )
            
            elif action == "get_calendar_summary":
                return {
                    "success": True,
                    "summary": self.calendar_service.get_calendar_summary()
                }
            
            elif action == "refresh_credentials":
                return self.calendar_service.refresh_calendar_credentials()
            
            else:
                return {"success": False, "message": f"Unknown calendar action: {action}"}
                
        except Exception as e:
            logger.error(f"Error handling calendar action {action}: {e}")
            return {"success": False, "message": f"Error: {str(e)}"}
    
    def _enhance_message_with_knowledge(
        self, 
        base_message: str, 
        knowledge: List, 
        context: Dict
    ) -> str:
        """
        Enhance message with relevant knowledge
        """
        enhanced_message = base_message
        
        # Add scheduling best practices if relevant
        scheduling_knowledge = [k for k in knowledge if "scheduling" in k.tags]
        if scheduling_knowledge and "schedule" in base_message.lower():
            best_practice = scheduling_knowledge[0].content.get("business_hours", "")
            if best_practice:
                enhanced_message += f" (Best practice: {best_practice})"
        
        # Add productivity tips if relevant
        productivity_knowledge = [k for k in knowledge if "productivity" in k.tags]
        if productivity_knowledge and "availability" in base_message.lower():
            tip = productivity_knowledge[0].content.get("deep_work_blocks", "")
            if tip:
                enhanced_message += f" 💡 Tip: {tip}"
        
        return enhanced_message
    
    def _personalize_suggestions(
        self, 
        base_suggestions: List[str], 
        patterns: List, 
        context: Dict
    ) -> List[str]:
        """
        Personalize suggestions based on user patterns
        """
        personalized = base_suggestions.copy()
        
        # Add personalized suggestions based on patterns
        for pattern in patterns:
            if pattern.pattern_type == "time_preferences":
                preferred_times = pattern.pattern_data.get("mentioned_times", [])
                if preferred_times:
                    personalized.append(f"Schedule during your preferred time: {preferred_times[0]}")
            
            elif pattern.pattern_type == "communication_style":
                style = pattern.pattern_data.get("preference", "")
                if style == "concise":
                    personalized.append("Quick scheduling options")
                elif style == "detailed":
                    personalized.append("Detailed calendar analysis")
        
        return personalized[:5]  # Limit to 5 suggestions
    
    def _generate_proactive_insights(self, context: Dict, knowledge: List) -> List[str]:
        """
        Generate proactive insights and suggestions
        """
        insights = []
        
        # Check for scheduling conflicts
        upcoming_bookings = context.get("data", {}).get("upcoming_bookings", [])
        if len(upcoming_bookings) > 5:
            insights.append("You have many meetings this week. Consider blocking time for deep work.")
        
        # Check for availability patterns
        available_slots = context.get("data", {}).get("available_slots", [])
        if not available_slots:
            insights.append("You're fully booked! Consider adding more availability slots.")
        
        # Add knowledge-based insights
        for entry in knowledge:
            if "calendar_management" in entry.tags:
                insights.append(entry.content.get("break_patterns", ""))
        
        return insights[:3]  # Limit to 3 insights
    
    def _calculate_personalization_level(self, patterns: List) -> str:
        """
        Calculate personalization level based on learned patterns
        """
        if len(patterns) >= 5:
            return "high"
        elif len(patterns) >= 2:
            return "medium"
        else:
            return "basic"
    
    def _generate_learning_insights(self, conversation_data: Dict) -> List[str]:
        """
        Generate insights about what the agent learned
        """
        insights = []
        
        extracted_info = conversation_data.get("extracted_info")
        if extracted_info:
            if extracted_info.confidence > 0.8:
                insights.append("High confidence in understanding your request")
            elif extracted_info.confidence < 0.5:
                insights.append("Learning to better understand similar requests")
        
        # Add pattern learning insights
        if conversation_data.get("conversation_history"):
            insights.append("Updated your communication preferences")
        
        return insights
    
    def _get_user_preferences(self, user_id: int) -> Dict[str, Any]:
        """
        Get user preferences from knowledge base
        """
        user_patterns = self.knowledge_base.get_user_patterns(user_id)
        preferences = {
            "preferred_meeting_duration": 30,
            "preferred_times": [],
            "communication_style": "balanced"
        }
        
        for pattern in user_patterns:
            if pattern.pattern_type == "time_preferences":
                preferences["preferred_times"] = pattern.pattern_data.get("mentioned_times", [])
            elif pattern.pattern_type == "communication_style":
                preferences["communication_style"] = pattern.pattern_data.get("preference", "balanced")
        
        return preferences
    
    def get_agent_capabilities(self) -> Dict[str, Any]:
        """
        Get agent capabilities and status
        """
        return {
            "capabilities": self.agent_capabilities,
            "knowledge_summary": self.knowledge_base.get_knowledge_summary(),
            "total_conversations": len(self.conversation_contexts),
            "learning_enabled": True,
            "personalization_enabled": True
        }
    
    def get_user_insights(self, user_id: int) -> Dict[str, Any]:
        """
        Get personalized insights for a user
        """
        patterns = self.knowledge_base.get_user_patterns(user_id)
        preferences = self._get_user_preferences(user_id)
        
        return {
            "learned_patterns": len(patterns),
            "preferences": preferences,
            "personalization_level": self._calculate_personalization_level(patterns),
            "communication_style": preferences.get("communication_style", "balanced"),
            "preferred_times": preferences.get("preferred_times", []),
            "scheduling_habits": self._analyze_scheduling_habits(user_id)
        }
    
    def _analyze_scheduling_habits(self, user_id: int) -> Dict[str, Any]:
        """
        Analyze user's scheduling habits
        """
        # Get user's bookings and availability
        bookings = booking_service.get_upcoming_bookings(self.db, user_id)
        available_slots = availability_service.get_available_slots_for_booking(self.db, user_id)
        
        habits = {
            "total_meetings": len(bookings),
            "available_slots": len(available_slots),
            "booking_frequency": "moderate",
            "preferred_duration": 30
        }
        
        if bookings:
            # Analyze meeting durations
            durations = [b.get("duration", 30) for b in bookings]
            habits["preferred_duration"] = max(set(durations), key=durations.count)
            
            # Analyze booking frequency
            if len(bookings) > 10:
                habits["booking_frequency"] = "high"
            elif len(bookings) < 3:
                habits["booking_frequency"] = "low"
        
        return habits 
    
    def _merge_intent_analysis(self, rule_based: ExtractedInfo, llm_analysis: Dict) -> ExtractedInfo:
        """
        Merge rule-based and LLM intent analysis
        """
        # Convert LLM intent string to IntentType enum if needed
        llm_intent = llm_analysis.get("intent", rule_based.intent)
        if isinstance(llm_intent, str):
            try:
                # Map common LLM intent strings to IntentType enum values
                intent_mapping = {
                    "schedule": IntentType.SCHEDULE_MEETING,
                    "schedule_meeting": IntentType.SCHEDULE_MEETING,
                    "book": IntentType.SCHEDULE_MEETING,
                    "reschedule": IntentType.RESCHEDULE,
                    "move": IntentType.RESCHEDULE,
                    "change": IntentType.RESCHEDULE,
                    "cancel": IntentType.CANCEL,
                    "delete": IntentType.CANCEL,
                    "availability": IntentType.CHECK_AVAILABILITY,
                    "check_availability": IntentType.CHECK_AVAILABILITY,
                    "free": IntentType.CHECK_AVAILABILITY,
                    "general": IntentType.GENERAL_QUERY,
                    "general_query": IntentType.GENERAL_QUERY,
                    "help": IntentType.GENERAL_QUERY,
                    "info": IntentType.MEETING_INFO,
                    "meeting_info": IntentType.MEETING_INFO
                }
                llm_intent = intent_mapping.get(llm_intent.lower(), rule_based.intent)
            except Exception as e:
                logger.warning(f"Failed to convert LLM intent '{llm_intent}' to enum: {e}")
                llm_intent = rule_based.intent
        
        # If LLM confidence is higher, use LLM analysis
        if llm_analysis.get("confidence", 0) > rule_based.confidence:
            return ExtractedInfo(
                intent=llm_intent,
                confidence=llm_analysis.get("confidence", rule_based.confidence),
                entities={**rule_based.entities, **llm_analysis.get("entities", {})},
                context=rule_based.context,
                sentiment=rule_based.sentiment,
                urgency=llm_analysis.get("urgency", rule_based.urgency)
            )
        
        # Otherwise, enhance rule-based with LLM entities
        enhanced_entities = {**rule_based.entities, **llm_analysis.get("entities", {})}
        return ExtractedInfo(
            intent=rule_based.intent,
            confidence=rule_based.confidence,
            entities=enhanced_entities,
            context=rule_based.context,
            sentiment=rule_based.sentiment,
            urgency=llm_analysis.get("urgency", rule_based.urgency)
        )
    
    def _has_scheduling_info(self, message: str) -> bool:
        """Check if message contains scheduling information"""
        scheduling_keywords = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
                              "9am", "10am", "11am", "12pm", "1pm", "2pm", "3pm", "4pm", "5pm",
                              "with", "about", "discuss", "meeting", "call"]
        message_lower = message.lower()
        return any(keyword in message_lower for keyword in scheduling_keywords)
    
    def _has_confirmation(self, message: str) -> bool:
        """Check if message contains confirmation"""
        confirm_keywords = ["yes", "confirm", "cancel", "delete", "remove", "ok", "sure"]
        message_lower = message.lower()
        return any(keyword in message_lower for keyword in confirm_keywords)
    
    def _has_new_time(self, message: str) -> bool:
        """Check if message contains new time information"""
        time_keywords = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
                        "9am", "10am", "11am", "12pm", "1pm", "2pm", "3pm", "4pm", "5pm",
                        "tomorrow", "next", "later", "earlier"]
        message_lower = message.lower()
        return any(keyword in message_lower for keyword in time_keywords)
    
    def _generate_conversation_summary(self, context: Dict) -> str:
        """Generate a summary of the current conversation"""
        recent_messages = context.get("recent_messages", [])
        if not recent_messages:
            return "New conversation started"
        
        summary_parts = []
        for msg in recent_messages[-3:]:  # Last 3 messages
            user_msg = msg.get("user_message", "")
            agent_msg = msg.get("agent_response", "")
            intent = msg.get("extracted_info", {}).get("intent", "unknown")
            
            if user_msg:
                summary_parts.append(f"User: {user_msg[:50]}... (Intent: {intent})")
            if agent_msg:
                summary_parts.append(f"Agent: {agent_msg[:50]}...")
        
        return " | ".join(summary_parts)
    
    def _is_question_already_asked(self, new_question: str, context: Dict) -> bool:
        """Check if a similar question was already asked"""
        asked_questions = context.get("asked_questions", [])
        new_question_lower = new_question.lower()
        
        for q in asked_questions:
            if any(word in new_question_lower for word in q["question"].lower().split()[:3]):
                return True
        return False
    
    def _update_user_patterns(self, user_id: int, extracted_info: ExtractedInfo, context: Dict):
        """Update user patterns based on current interaction"""
        try:
            # Extract time preferences
            if extracted_info.entities.get("time"):
                self.knowledge_base.add_user_pattern(
                    user_id, 
                    "time_preferences", 
                    {"mentioned_times": [extracted_info.entities["time"]]}
                )
            
            # Extract communication style
            if extracted_info.sentiment:
                self.knowledge_base.add_user_pattern(
                    user_id,
                    "communication_style",
                    {"preference": extracted_info.sentiment}
                )
            
            # Extract urgency patterns
            if extracted_info.urgency:
                self.knowledge_base.add_user_pattern(
                    user_id,
                    "urgency_patterns",
                    {"urgency_level": extracted_info.urgency}
                )
            
            # Extract scheduling preferences
            if extracted_info.entities.get("duration"):
                self.knowledge_base.add_user_pattern(
                    user_id,
                    "scheduling_preferences",
                    {"preferred_duration": extracted_info.entities["duration"]}
                )
                
        except Exception as e:
            logger.warning(f"Failed to update user patterns: {e}")