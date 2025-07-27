from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import os
import logging
import json

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

logger = logging.getLogger(__name__)

class LLMProvider(ABC):
    """Abstract base class for LLM providers"""
    
    @abstractmethod
    async def generate_response(self, prompt: str, context: Dict[str, Any] = None) -> str:
        """Generate response from LLM"""
        pass
    
    @abstractmethod
    async def analyze_intent(self, message: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Analyze user intent and extract information"""
        pass

class OpenAIProvider(LLMProvider):
    """OpenAI GPT-4o provider using LangChain"""
    
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")
        
        # Initialize LangChain ChatOpenAI with standard OpenAI (override global settings)
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",  # Use GPT-4o-mini (most commonly available)
            temperature=0.3,      # More focused responses
            max_tokens=150,       # Shorter responses
            api_key=self.api_key,
            base_url="https://api.openai.com/v1"  # Explicitly override global base URL
        )
        
        # Create prompt template for scheduling assistant
        self.scheduling_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a reliable, context-aware appointment scheduling assistant. Your job is to understand user intent, keep track of context throughout the conversation, and handle the following tasks smoothly:

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

RESPONSE FORMAT:
- For scheduling with complete info: "✅ Meeting scheduled! [details with confirmation]"
- For missing info: "❓ [specific question about missing info only]"
- For confirmation: "Just confirming, you mean [exact details]?"
- For general help: "[helpful response with suggestions]"
- For errors: "❌ [specific error explanation]"

Remember: Only ask for what's actually missing, never repeat questions, and always confirm actions before claiming they're done.

Available context: {context}"""),
            ("user", "{prompt}")
        ])
        
        # Create prompt template for intent analysis
        self.intent_prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a JSON-only response assistant. Analyze the user message for scheduling intent and return only valid JSON."),
            ("user", "Analyze this message for scheduling intent: {message}\n\nReturn a JSON object with:\n- intent: \"schedule_meeting\", \"check_availability\", \"reschedule\", \"cancel\", \"general_query\"\n- confidence: 0.0 to 1.0\n- entities: {{\"date\": \"...\", \"time\": \"...\", \"person\": \"...\", \"duration\": \"...\"}}\n- urgency: \"low\", \"medium\", \"high\"")
        ])
        
        # JSON output parser for intent analysis
        self.json_parser = JsonOutputParser()
    
    async def generate_response(self, prompt: str, context: Dict[str, Any] = None) -> str:
        """Generate response using LangChain ChatOpenAI"""
        try:
            # Format context for prompt
            context_str = ""
            if context:
                if context.get('available_slots'):
                    context_str += f"Available time slots: {context['available_slots']}\n"
                if context.get('user_preferences'):
                    context_str += f"User preferences: {context['user_preferences']}\n"
            
            # Create chain
            chain = self.scheduling_prompt | self.llm
            
            # Generate response
            response = await chain.ainvoke({
                "prompt": prompt,
                "context": context_str
            })
            
            return response.content
        except Exception as e:
            logger.error(f"LangChain OpenAI API error: {e}")
            return "I apologize, but I'm having trouble processing your request right now."
    
    async def analyze_intent(self, message: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Analyze user intent using LangChain ChatOpenAI"""
        try:
            # Create chain with JSON parser
            chain = self.intent_prompt | self.llm | self.json_parser
            
            # Analyze intent
            result = await chain.ainvoke({"message": message})
            
            return result
        except Exception as e:
            logger.error(f"LangChain intent analysis error: {e}")
            return {
                "intent": "general_query",
                "confidence": 0.0,
                "entities": {},
                "urgency": "low"
            }

class ClaudeProvider(LLMProvider):
    """Anthropic Claude 3 Haiku provider"""
    
    def __init__(self):
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is required")
        
        # Import here to avoid dependency issues
        try:
            import anthropic
            self.client = anthropic.Anthropic(api_key=self.api_key)
        except ImportError:
            raise ImportError("anthropic package is required. Install with: pip install anthropic")
    
    async def generate_response(self, prompt: str, context: Dict[str, Any] = None) -> str:
        """Generate response using Claude 3 Haiku"""
        try:
            system_prompt = self._get_system_prompt(context)
            
            response = self.client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=150,  # Shorter responses
                messages=[
                    {"role": "user", "content": f"{system_prompt}\n\nUser: {prompt}"}
                ]
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"Claude API error: {e}")
            return "I apologize, but I'm having trouble processing your request right now."
    
    async def analyze_intent(self, message: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Analyze user intent using Claude"""
        try:
            analysis_prompt = f"""
            Analyze this message for scheduling intent: "{message}"
            
            Return a JSON object with:
            - intent: "schedule_meeting", "check_availability", "reschedule", "cancel", "general_query"
            - confidence: 0.0 to 1.0
            - entities: {{"date": "...", "time": "...", "person": "...", "duration": "..."}}
            - urgency: "low", "medium", "high"
            """
            
            response = self.client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=300,
                messages=[
                    {"role": "user", "content": analysis_prompt}
                ]
            )
            
            import json
            return json.loads(response.content[0].text)
        except Exception as e:
            logger.error(f"Claude intent analysis error: {e}")
            return {
                "intent": "general_query",
                "confidence": 0.0,
                "entities": {},
                "urgency": "low"
            }
    
    def _get_system_prompt(self, context: Dict[str, Any] = None) -> str:
        """Get system prompt for scheduling assistant"""
        base_prompt = """You are a focused, action-oriented scheduling assistant. Your responses must be:

1. **CONCISE** - Keep responses under 2-3 sentences
2. **ACTION-ORIENTED** - Take action when possible, don't just talk about it
3. **CONTEXT-AWARE** - Remember previous conversation and don't repeat questions
4. **STRUCTURED** - Use bullet points for multiple items
5. **DIRECT** - Get to the point quickly

**Core Rules:**
- If user wants to schedule: Ask for date, time, person, and topic (ONCE)
- If user wants to check availability: Show available slots immediately
- If user wants to cancel: Confirm and cancel immediately
- If user wants to reschedule: Ask for new time and update immediately
- If you need info: Ask specific questions, not general ones
- NEVER repeat the same question twice in a conversation

**Available Actions:**
- Check calendar availability
- Schedule meetings
- Cancel appointments  
- Reschedule meetings
- Show upcoming events

**Response Format:**
- ✅ **Action taken** (if applicable)
- 📅 **Available slots** (if checking availability)
- ❓ **Next step** (if action needed)

Be efficient and get things done!"""
        
        if context and context.get('available_slots'):
            base_prompt += f"\n\n📅 Available time slots: {context['available_slots']}"
        
        if context and context.get('user_preferences'):
            base_prompt += f"\n\n⚙️ User preferences: {context['user_preferences']}"
        
        if context and context.get('calendar_status'):
            calendar_status = context['calendar_status']
            if calendar_status.get('connected'):
                base_prompt += f"\n\n✅ Calendar connected: {calendar_status.get('calendar_email', 'Unknown')}"
            else:
                base_prompt += f"\n\n❌ Calendar not connected: {calendar_status.get('message', 'Unknown error')}"
        
        return base_prompt

class LLMService:
    """Service for managing LLM providers"""
    
    def __init__(self, provider_name: str = None):
        self.provider_name = provider_name or os.getenv("LLM_PROVIDER", "openai")
        logger.info(f"Initializing LLM Service with provider: {self.provider_name}")
        try:
            self.provider = self._get_provider()
            logger.info(f"LLM Provider initialized successfully: {self.provider_name}")
        except Exception as e:
            logger.error(f"Failed to initialize LLM provider {self.provider_name}: {e}")
            raise
    
    def _get_provider(self) -> LLMProvider:
        """Get the appropriate LLM provider"""
        if self.provider_name.lower() == "openai":
            return OpenAIProvider()
        elif self.provider_name.lower() == "claude":
            return ClaudeProvider()
        else:
            # Default to OpenAI
            return OpenAIProvider()
    
    async def generate_response(self, prompt: str, context: Dict[str, Any] = None) -> str:
        """Generate response using current provider"""
        return await self.provider.generate_response(prompt, context)
    
    async def analyze_intent(self, message: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Analyze intent using current provider"""
        return await self.provider.analyze_intent(message, context)
    
    def switch_provider(self, provider_name: str):
        """Switch to a different LLM provider"""
        self.provider_name = provider_name
        self.provider = self._get_provider()
        logger.info(f"Switched to {provider_name} provider") 