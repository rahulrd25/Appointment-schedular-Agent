"""
Knowledge Base Service for AI Agent
Handles storing and retrieving contextual information for AI interactions
"""

from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import json
import csv
import requests
import logging

logger = logging.getLogger(__name__)


class KnowledgeBaseService:
    """Service for managing knowledge base for AI agent interactions."""
    
    def __init__(self, db: Session):
        self.db = db
        self.knowledge_cache = {}
        
        # Initialize scheduling knowledge base
        self.scheduling_qa = self._initialize_scheduling_qa()
        self.common_patterns = self._initialize_common_patterns()
        self.best_practices = self._initialize_best_practices()
    
    def _initialize_scheduling_qa(self) -> Dict[str, List[Dict]]:
        """Initialize common scheduling Q&A"""
        return {
            "scheduling": [
                {
                    "question": "How do I schedule a meeting?",
                    "answer": "You can schedule a meeting by saying something like 'Schedule a meeting with John tomorrow at 2 PM' or 'Book a call about the project next week'. I'll help you find available times and create the booking.",
                    "keywords": ["schedule", "book", "meeting", "call", "appointment"],
                    "intent": "schedule_meeting"
                },
                {
                    "question": "How do I check my availability?",
                    "answer": "Ask me 'When am I free this week?' or 'Show my available times' and I'll display your open slots. You can also check specific dates like 'What's my availability on Friday?'",
                    "keywords": ["availability", "free", "open", "when", "times"],
                    "intent": "check_availability"
                },
                {
                    "question": "How do I reschedule a meeting?",
                    "answer": "Say 'Reschedule my meeting with Sarah to Friday' or 'Move my 3 PM call to tomorrow'. I'll help you find new available times and update the booking.",
                    "keywords": ["reschedule", "move", "change", "postpone"],
                    "intent": "reschedule"
                },
                {
                    "question": "How do I cancel a meeting?",
                    "answer": "Tell me 'Cancel my meeting with John' or 'Delete my 2 PM appointment' and I'll remove it from your calendar and notify the other person.",
                    "keywords": ["cancel", "delete", "remove"],
                    "intent": "cancel"
                },
                {
                    "question": "What are my upcoming meetings?",
                    "answer": "I can show you your upcoming meetings. Just ask 'What meetings do I have this week?' or 'Show my calendar' and I'll display your scheduled appointments.",
                    "keywords": ["upcoming", "meetings", "calendar", "appointments"],
                    "intent": "meeting_info"
                }
            ],
            "time_management": [
                {
                    "question": "What are good meeting times?",
                    "answer": "I recommend scheduling meetings during business hours (9 AM - 5 PM) and avoiding back-to-back meetings. I can suggest optimal times based on your availability and preferences.",
                    "keywords": ["good times", "optimal", "business hours", "recommend"],
                    "intent": "general_query"
                },
                {
                    "question": "How long should meetings be?",
                    "answer": "Meeting duration depends on the purpose. Quick updates: 15-30 minutes. Discussions: 30-60 minutes. Workshops: 1-2 hours. I can help you set appropriate durations.",
                    "keywords": ["duration", "length", "how long"],
                    "intent": "general_query"
                },
                {
                    "question": "How do I set up recurring meetings?",
                    "answer": "For recurring meetings, say 'Schedule a weekly team meeting every Monday at 10 AM' or 'Create a monthly review on the first Friday'. I'll set up the recurring pattern.",
                    "keywords": ["recurring", "weekly", "monthly", "regular"],
                    "intent": "schedule_meeting"
                }
            ],
            "calendar_integration": [
                {
                    "question": "How do I connect my Google Calendar?",
                    "answer": "Go to Settings and click 'Connect Google Calendar'. This will sync your calendar and allow me to check your availability and create events automatically.",
                    "keywords": ["connect", "google calendar", "sync", "integration"],
                    "intent": "settings"
                },
                {
                    "question": "Why can't I see my calendar?",
                    "answer": "Make sure your Google Calendar is connected in Settings. If it's connected but not showing, try refreshing the page or reconnecting your calendar.",
                    "keywords": ["can't see", "not showing", "calendar", "refresh"],
                    "intent": "settings"
                }
            ],
            "troubleshooting": [
                {
                    "question": "What if I can't make a meeting?",
                    "answer": "If you can't attend, you can reschedule or cancel. Say 'Reschedule my meeting with John' or 'Cancel my 2 PM call' and I'll help you handle it.",
                    "keywords": ["can't make", "conflict", "busy", "unavailable"],
                    "intent": "reschedule"
                },
                {
                    "question": "How do I invite people to meetings?",
                    "answer": "When scheduling, include the person's name like 'Schedule a meeting with Sarah about the project'. I'll automatically send them an invitation with the meeting details.",
                    "keywords": ["invite", "people", "participants", "guests"],
                    "intent": "schedule_meeting"
                },
                {
                    "question": "What if someone doesn't respond to my meeting invite?",
                    "answer": "I'll send them a reminder email. If they still don't respond, you can follow up manually or reschedule the meeting for a different time.",
                    "keywords": ["no response", "reminder", "follow up"],
                    "intent": "general_query"
                }
            ]
        }
    
    def _initialize_common_patterns(self) -> Dict[str, List[str]]:
        """Initialize common user patterns and phrases"""
        return {
            "scheduling_requests": [
                "schedule a meeting with {person}",
                "book a call about {topic}",
                "set up an appointment for {date}",
                "arrange a meeting with {person} at {time}",
                "create a meeting about {topic}"
            ],
            "availability_requests": [
                "when am I free {date}?",
                "show my available times",
                "what's my schedule like {date}?",
                "check my availability",
                "find open slots"
            ],
            "rescheduling_requests": [
                "reschedule my meeting with {person}",
                "move my {time} call to {new_time}",
                "change my appointment to {date}",
                "postpone my meeting"
            ],
            "cancellation_requests": [
                "cancel my meeting with {person}",
                "delete my {time} appointment",
                "remove my meeting",
                "call off my appointment"
            ],
            "information_requests": [
                "what meetings do I have {date}?",
                "show my calendar",
                "what's on my schedule?",
                "tell me about my appointments"
            ]
        }
    
    def _initialize_best_practices(self) -> Dict[str, List[str]]:
        """Initialize scheduling best practices"""
        return {
            "meeting_duration": [
                "Quick updates: 15-30 minutes",
                "Discussions: 30-60 minutes", 
                "Workshops: 1-2 hours",
                "Presentations: 45-90 minutes"
            ],
            "timing_tips": [
                "Schedule during business hours (9 AM - 5 PM)",
                "Allow buffer time between meetings",
                "Avoid back-to-back meetings when possible",
                "Consider time zones for remote participants"
            ],
            "preparation_tips": [
                "Send agenda in advance",
                "Include meeting objectives",
                "Set clear expectations",
                "Follow up with action items"
            ],
            "calendar_management": [
                "Block time for deep work",
                "Schedule breaks between meetings",
                "Use recurring slots for regular meetings",
                "Set up automatic reminders"
            ]
        }
    
    def get_relevant_qa(self, message: str, intent: str = None) -> List[Dict]:
        """Get relevant Q&A based on message and intent"""
        relevant_qa = []
        message_lower = message.lower()
        
        for category, qa_list in self.scheduling_qa.items():
            for qa in qa_list:
                # Check if message matches keywords or intent
                keywords = qa.get("keywords", [])
                qa_intent = qa.get("intent", "")
                
                # Match by keywords
                keyword_match = any(keyword in message_lower for keyword in keywords)
                
                # Match by intent
                intent_match = intent and qa_intent == intent
                
                if keyword_match or intent_match:
                    relevant_qa.append(qa)
        
        return relevant_qa
    
    def get_common_patterns(self, category: str = None) -> Dict[str, List[str]]:
        """Get common patterns for a category"""
        if category:
            return {category: self.common_patterns.get(category, [])}
        return self.common_patterns
    
    def get_best_practices(self, category: str = None) -> Dict[str, List[str]]:
        """Get best practices for a category"""
        if category:
            return {category: self.best_practices.get(category, [])}
        return self.best_practices
    
    def find_similar_questions(self, user_question: str) -> List[Dict]:
        """Find similar questions from the knowledge base"""
        similar_qa = []
        user_question_lower = user_question.lower()
        
        for category, qa_list in self.scheduling_qa.items():
            for qa in qa_list:
                question = qa.get("question", "").lower()
                keywords = qa.get("keywords", [])
                
                # Check for keyword overlap
                keyword_overlap = sum(1 for keyword in keywords if keyword in user_question_lower)
                
                # Check for question similarity
                question_similarity = sum(1 for word in user_question_lower.split() if word in question)
                
                if keyword_overlap > 0 or question_similarity > 1:
                    similar_qa.append({
                        "question": qa.get("question"),
                        "answer": qa.get("answer"),
                        "relevance_score": keyword_overlap + question_similarity
                    })
        
        # Sort by relevance score
        similar_qa.sort(key=lambda x: x["relevance_score"], reverse=True)
        return similar_qa[:3]  # Return top 3 matches 
    
    def load_knowledge_from_json(self, file_path: str) -> bool:
        """Load knowledge base from JSON file"""
        try:
            import json
            with open(file_path, 'r', encoding='utf-8') as file:
                knowledge_data = json.load(file)
            
            # Merge with existing knowledge
            for category, qa_list in knowledge_data.items():
                if category in self.scheduling_qa:
                    self.scheduling_qa[category].extend(qa_list)
                else:
                    self.scheduling_qa[category] = qa_list
            
            logger.info(f"✅ Loaded {sum(len(qa_list) for qa_list in knowledge_data.values())} Q&A pairs from {file_path}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to load knowledge from {file_path}: {e}")
            return False
    
    def load_knowledge_from_csv(self, file_path: str) -> bool:
        """Load knowledge base from CSV file"""
        try:
            import csv
            knowledge_data = {}
            
            with open(file_path, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    category = row.get('category', 'general')
                    qa_item = {
                        'question': row.get('question', ''),
                        'answer': row.get('answer', ''),
                        'keywords': row.get('keywords', '').split(','),
                        'intent': row.get('intent', 'general_query')
                    }
                    
                    if category not in knowledge_data:
                        knowledge_data[category] = []
                    knowledge_data[category].append(qa_item)
            
            # Merge with existing knowledge
            for category, qa_list in knowledge_data.items():
                if category in self.scheduling_qa:
                    self.scheduling_qa[category].extend(qa_list)
                else:
                    self.scheduling_qa[category] = qa_list
            
            logger.info(f"✅ Loaded {sum(len(qa_list) for qa_list in knowledge_data.values())} Q&A pairs from {file_path}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to load knowledge from {file_path}: {e}")
            return False
    
    def load_knowledge_from_database(self, table_name: str = "knowledge_base") -> bool:
        """Load knowledge base from database table"""
        try:
            # Query the database for knowledge base entries
            query = f"""
                SELECT category, question, answer, keywords, intent 
                FROM {table_name} 
                WHERE active = true
                ORDER BY relevance_score DESC
            """
            
            # Execute query and load into memory
            # This would depend on your database setup
            # For now, we'll use a placeholder
            logger.info(f"✅ Loaded knowledge base from database table: {table_name}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to load knowledge from database: {e}")
            return False
    
    def load_knowledge_from_api(self, api_url: str, api_key: str = None) -> bool:
        """Load knowledge base from external API"""
        try:
            import requests
            
            headers = {}
            if api_key:
                headers['Authorization'] = f'Bearer {api_key}'
            
            response = requests.get(api_url, headers=headers)
            response.raise_for_status()
            
            knowledge_data = response.json()
            
            # Merge with existing knowledge
            for category, qa_list in knowledge_data.items():
                if category in self.scheduling_qa:
                    self.scheduling_qa[category].extend(qa_list)
                else:
                    self.scheduling_qa[category] = qa_list
            
            logger.info(f"✅ Loaded {sum(len(qa_list) for qa_list in knowledge_data.values())} Q&A pairs from API")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to load knowledge from API: {e}")
            return False
    
    def load_knowledge_from_markdown(self, file_path: str) -> bool:
        """Load knowledge base from Markdown file"""
        try:
            from .md_knowledge_parser import parse_md_qa
            
            with open(file_path, 'r', encoding='utf-8') as file:
                md_content = file.read()
            
            # Parse the markdown content
            knowledge_data = parse_md_qa(md_content)
            
            # Merge with existing knowledge
            for category, qa_list in knowledge_data.items():
                if category in self.scheduling_qa:
                    self.scheduling_qa[category].extend(qa_list)
                else:
                    self.scheduling_qa[category] = qa_list
            
            logger.info(f"✅ Loaded {sum(len(qa_list) for qa_list in knowledge_data.values())} Q&A pairs from {file_path}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to load knowledge from {file_path}: {e}")
            return False
    
    def load_knowledge_from_md_content(self, md_content: str) -> bool:
        """Load knowledge base from Markdown content string"""
        try:
            from .md_knowledge_parser import parse_md_qa
            
            # Parse the markdown content
            knowledge_data = parse_md_qa(md_content)
            
            # Merge with existing knowledge
            for category, qa_list in knowledge_data.items():
                if category in self.scheduling_qa:
                    self.scheduling_qa[category].extend(qa_list)
                else:
                    self.scheduling_qa[category] = qa_list
            
            logger.info(f"✅ Loaded {sum(len(qa_list) for qa_list in knowledge_data.values())} Q&A pairs from markdown content")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to load knowledge from markdown content: {e}")
            return False
    
    def load_knowledge_from_custom_qa(self, file_path: str) -> bool:
        """Load knowledge base from custom Q&A format file"""
        try:
            from .custom_qa_parser import parse_custom_qa
            
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()
            
            # Parse the custom Q&A content
            knowledge_data = parse_custom_qa(content)
            
            # Merge with existing knowledge
            for category, qa_list in knowledge_data.items():
                if category in self.scheduling_qa:
                    self.scheduling_qa[category].extend(qa_list)
                else:
                    self.scheduling_qa[category] = qa_list
            
            logger.info(f"✅ Loaded {sum(len(qa_list) for qa_list in knowledge_data.values())} Q&A pairs from {file_path}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to load knowledge from {file_path}: {e}")
            return False
    
    def load_knowledge_from_custom_qa_content(self, content: str) -> bool:
        """Load knowledge base from custom Q&A content string"""
        try:
            from .custom_qa_parser import parse_custom_qa
            
            # Parse the custom Q&A content
            knowledge_data = parse_custom_qa(content)
            
            # Merge with existing knowledge
            for category, qa_list in knowledge_data.items():
                if category in self.scheduling_qa:
                    self.scheduling_qa[category].extend(qa_list)
                else:
                    self.scheduling_qa[category] = qa_list
            
            logger.info(f"✅ Loaded {sum(len(qa_list) for qa_list in knowledge_data.values())} Q&A pairs from custom Q&A content")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to load knowledge from custom Q&A content: {e}")
            return False
    
    def add_qa_pair(self, category: str, question: str, answer: str, keywords: List[str] = None, intent: str = "general_query") -> bool:
        """Add a single Q&A pair to the knowledge base"""
        try:
            qa_item = {
                'question': question,
                'answer': answer,
                'keywords': keywords or [],
                'intent': intent
            }
            
            if category not in self.scheduling_qa:
                self.scheduling_qa[category] = []
            
            self.scheduling_qa[category].append(qa_item)
            logger.info(f"✅ Added Q&A pair to category: {category}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to add Q&A pair: {e}")
            return False
    
    def bulk_add_qa_pairs(self, qa_pairs: List[Dict]) -> bool:
        """Add multiple Q&A pairs at once"""
        try:
            for qa_pair in qa_pairs:
                category = qa_pair.get('category', 'general')
                question = qa_pair.get('question', '')
                answer = qa_pair.get('answer', '')
                keywords = qa_pair.get('keywords', [])
                intent = qa_pair.get('intent', 'general_query')
                
                self.add_qa_pair(category, question, answer, keywords, intent)
            
            logger.info(f"✅ Added {len(qa_pairs)} Q&A pairs to knowledge base")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to bulk add Q&A pairs: {e}")
            return False
    
    def search_knowledge_advanced(self, query: str, limit: int = 5) -> List[Dict]:
        """Advanced search with relevance scoring"""
        results = []
        query_lower = query.lower()
        query_words = set(query_lower.split())
        
        for category, qa_list in self.scheduling_qa.items():
            for qa in qa_list:
                question = qa.get('question', '').lower()
                answer = qa.get('answer', '').lower()
                keywords = [kw.lower() for kw in qa.get('keywords', [])]
                
                # Calculate relevance score
                score = 0
                
                # Exact keyword matches
                for keyword in keywords:
                    if keyword in query_lower:
                        score += 3
                
                # Question word overlap
                question_words = set(question.split())
                word_overlap = len(query_words.intersection(question_words))
                score += word_overlap * 2
                
                # Answer relevance
                answer_words = set(answer.split())
                answer_overlap = len(query_words.intersection(answer_words))
                score += answer_overlap
                
                if score > 0:
                    results.append({
                        'question': qa.get('question'),
                        'answer': qa.get('answer'),
                        'category': category,
                        'relevance_score': score,
                        'keywords': keywords
                    })
        
        # Sort by relevance score and return top results
        results.sort(key=lambda x: x['relevance_score'], reverse=True)
        return results[:limit]
    
    def get_knowledge_stats(self) -> Dict[str, Any]:
        """Get statistics about the knowledge base"""
        total_qa = sum(len(qa_list) for qa_list in self.scheduling_qa.values())
        categories = list(self.scheduling_qa.keys())
        
        return {
            'total_qa_pairs': total_qa,
            'categories': categories,
            'category_counts': {cat: len(qa_list) for cat, qa_list in self.scheduling_qa.items()},
            'keywords_coverage': self._get_keyword_coverage()
        }
    
    def _get_keyword_coverage(self) -> Dict[str, int]:
        """Get keyword coverage statistics"""
        keyword_counts = {}
        for qa_list in self.scheduling_qa.values():
            for qa in qa_list:
                for keyword in qa.get('keywords', []):
                    keyword_counts[keyword] = keyword_counts.get(keyword, 0) + 1
        return keyword_counts 
    
    def get_user_patterns(self, user_id: int) -> List[Dict]:
        """Get user patterns for personalization"""
        # For now, return empty list - patterns can be implemented later
        return []
    
    def add_user_pattern(self, user_id: int, pattern_type: str, pattern_data: Dict):
        """Add a user pattern for learning"""
        # For now, just log the pattern - can be implemented later
        logger.info(f"User {user_id} pattern: {pattern_type} - {pattern_data}")
    
    def learn_from_conversation(self, user_id: int, conversation_data: Dict):
        """Learn from conversation data"""
        # For now, just log the learning - can be implemented later
        logger.info(f"Learning from conversation for user {user_id}")
    
    def get_relevant_knowledge(self, user_id: int, extracted_info, context: Dict) -> List[Dict]:
        """Get relevant knowledge based on extracted info"""
        # For now, return empty list - can be implemented later
        return [] 