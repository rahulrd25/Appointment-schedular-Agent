from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session
import json
import pickle
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
import logging
import re

logger = logging.getLogger(__name__)

@dataclass
class KnowledgeEntry:
    """Knowledge base entry"""
    id: str
    category: str
    content: Dict[str, Any]
    confidence: float
    created_at: datetime
    last_accessed: datetime
    access_count: int
    source: str
    tags: List[str]

@dataclass
class UserPattern:
    """User behavior pattern"""
    user_id: int
    pattern_type: str
    pattern_data: Dict[str, Any]
    frequency: int
    last_observed: datetime
    confidence: float

class KnowledgeBaseService:
    """
    Advanced knowledge base service for AI agent learning and context
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.knowledge_store: Dict[str, KnowledgeEntry] = {}
        self.user_patterns: Dict[int, List[UserPattern]] = {}
        self.conversation_memory: Dict[str, List[Dict]] = {}
        
        # Initialize with domain knowledge
        self._initialize_domain_knowledge()
    
    def _initialize_domain_knowledge(self):
        """Initialize with domain-specific knowledge"""
        domain_knowledge = {
            "scheduling_best_practices": {
                "content": {
                    "business_hours": "9:00 AM - 5:00 PM",
                    "buffer_time": "15 minutes between meetings",
                    "timezone_consideration": "Always check participant timezones",
                    "meeting_duration": "30 minutes is standard",
                    "follow_up": "Send calendar invites with agenda"
                },
                "confidence": 0.95,
                "tags": ["scheduling", "best_practices", "productivity"]
            },
            "calendar_management": {
                "content": {
                    "deep_work_blocks": "Schedule 2-3 hour blocks for focused work",
                    "break_patterns": "Take 5-10 minute breaks between meetings",
                    "recurring_meetings": "Use recurring slots for regular meetings",
                    "priority_scheduling": "Schedule important tasks during peak hours"
                },
                "confidence": 0.90,
                "tags": ["calendar", "productivity", "time_management"]
            },
            "communication_patterns": {
                "content": {
                    "urgent_requests": "High urgency often indicates last-minute requests",
                    "vague_requests": "Ask clarifying questions for better scheduling",
                    "preference_indicators": "Listen for time/day preferences",
                    "conflict_resolution": "Offer alternatives when conflicts arise"
                },
                "confidence": 0.85,
                "tags": ["communication", "user_experience", "conflict_resolution"]
            }
        }
        
        for key, data in domain_knowledge.items():
            entry = KnowledgeEntry(
                id=key,
                category="domain_knowledge",
                content=data["content"],
                confidence=data["confidence"],
                created_at=datetime.now(),
                last_accessed=datetime.now(),
                access_count=0,
                source="system",
                tags=data["tags"]
            )
            self.knowledge_store[key] = entry
    
    def learn_from_conversation(self, user_id: int, conversation_data: Dict[str, Any]):
        """
        Learn from conversation interactions
        """
        try:
            # Extract patterns from conversation
            patterns = self._extract_conversation_patterns(conversation_data)
            
            # Update user patterns
            for pattern in patterns:
                self._update_user_pattern(user_id, pattern)
            
            # Store conversation for future reference
            context_id = conversation_data.get("context_id")
            if context_id:
                if context_id not in self.conversation_memory:
                    self.conversation_memory[context_id] = []
                self.conversation_memory[context_id].append(conversation_data)
            
            # Learn scheduling preferences
            self._learn_scheduling_preferences(user_id, conversation_data)
            
            # Learn from entities and sentiment
            self._learn_from_entities(user_id, conversation_data)
            
            # Learn from action taken
            self._learn_from_actions(user_id, conversation_data)
            
            logger.info(f"Learned from conversation for user {user_id}")
            
        except Exception as e:
            logger.error(f"Error learning from conversation: {e}")
    
    def _extract_conversation_patterns(self, conversation_data: Dict[str, Any]) -> List[UserPattern]:
        """
        Extract patterns from conversation data
        """
        patterns = []
        
        # Extract time preferences
        time_preferences = self._extract_time_preferences(conversation_data)
        if time_preferences:
            patterns.append(UserPattern(
                user_id=conversation_data.get("user_id"),
                pattern_type="time_preferences",
                pattern_data=time_preferences,
                frequency=1,
                last_observed=datetime.now(),
                confidence=0.7
            ))
        
        # Extract communication style
        communication_style = self._extract_communication_style(conversation_data)
        if communication_style:
            patterns.append(UserPattern(
                user_id=conversation_data.get("user_id"),
                pattern_type="communication_style",
                pattern_data=communication_style,
                frequency=1,
                last_observed=datetime.now(),
                confidence=0.6
            ))
        
        return patterns
    
    def _extract_time_preferences(self, conversation_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract time preferences from conversation
        """
        preferences = {}
        
        # Look for time mentions in conversation history
        history = conversation_data.get("conversation_history", [])
        for entry in history:
            message = entry.get("user_message", "").lower()
            
            # Extract preferred times
            if "morning" in message:
                preferences["preferred_period"] = "morning"
            elif "afternoon" in message:
                preferences["preferred_period"] = "afternoon"
            elif "evening" in message:
                preferences["preferred_period"] = "evening"
            
            # Extract specific times
            time_matches = re.findall(r'(\d{1,2}:\d{2})', message)
            if time_matches:
                preferences["mentioned_times"] = time_matches
        
        return preferences
    
    def _extract_communication_style(self, conversation_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract communication style preferences
        """
        style = {}
        
        history = conversation_data.get("conversation_history", [])
        for entry in history:
            message = entry.get("user_message", "")
            
            # Analyze message length
            if len(message) < 20:
                style["preference"] = "concise"
            elif len(message) > 100:
                style["preference"] = "detailed"
            
            # Analyze formality
            if any(word in message.lower() for word in ["please", "thank you", "would you"]):
                style["formality"] = "formal"
            else:
                style["formality"] = "casual"
        
        return style
    
    def _update_user_pattern(self, user_id: int, pattern: UserPattern):
        """
        Update user patterns with new information
        """
        if user_id not in self.user_patterns:
            self.user_patterns[user_id] = []
        
        # Check if pattern already exists
        existing_pattern = None
        for existing in self.user_patterns[user_id]:
            if existing.pattern_type == pattern.pattern_type:
                existing_pattern = existing
                break
        
        if existing_pattern:
            # Update existing pattern
            existing_pattern.frequency += 1
            existing_pattern.last_observed = datetime.now()
            existing_pattern.confidence = min(existing_pattern.confidence + 0.1, 1.0)
            
            # Merge pattern data
            for key, value in pattern.pattern_data.items():
                if key not in existing_pattern.pattern_data:
                    existing_pattern.pattern_data[key] = value
        else:
            # Add new pattern
            self.user_patterns[user_id].append(pattern)
    
    def _learn_scheduling_preferences(self, user_id: int, conversation_data: Dict[str, Any]):
        """
        Learn user's scheduling preferences
        """
        preferences = {
            "preferred_duration": 30,
            "preferred_times": [],
            "avoided_times": [],
            "meeting_frequency": "moderate"
        }
        
        # Analyze conversation for preferences
        history = conversation_data.get("conversation_history", [])
        for entry in history:
            message = entry.get("user_message", "").lower()
            
            # Extract duration preferences
            if "hour" in message or "60 min" in message:
                preferences["preferred_duration"] = 60
            elif "15 min" in message:
                preferences["preferred_duration"] = 15
            
            # Extract time preferences
            if "morning" in message:
                preferences["preferred_times"].append("morning")
            elif "afternoon" in message:
                preferences["preferred_times"].append("afternoon")
        
        # Store learned preferences
        entry = KnowledgeEntry(
            id=f"user_preferences_{user_id}",
            category="user_preferences",
            content=preferences,
            confidence=0.8,
            created_at=datetime.now(),
            last_accessed=datetime.now(),
            access_count=1,
            source="learned",
            tags=["user_preferences", f"user_{user_id}"]
        )
        self.knowledge_store[entry.id] = entry
    
    def get_relevant_knowledge(self, query: str, user_id: int = None, context: Dict = None) -> List[KnowledgeEntry]:
        """
        Retrieve relevant knowledge for a given query
        """
        relevant_entries = []
        
        # Search through knowledge store
        for entry in self.knowledge_store.values():
            relevance_score = self._calculate_relevance(entry, query, user_id, context)
            if relevance_score > 0.3:  # Threshold for relevance
                entry.last_accessed = datetime.now()
                entry.access_count += 1
                relevant_entries.append((entry, relevance_score))
        
        # Sort by relevance score
        relevant_entries.sort(key=lambda x: x[1], reverse=True)
        
        return [entry for entry, score in relevant_entries[:5]]
    
    def _calculate_relevance(self, entry: KnowledgeEntry, query: str, user_id: int = None, context: Dict = None) -> float:
        """
        Calculate relevance score for knowledge entry
        """
        score = 0.0
        query_lower = query.lower()
        
        # Tag matching
        for tag in entry.tags:
            if tag.lower() in query_lower:
                score += 0.3
        
        # Content matching
        content_str = json.dumps(entry.content).lower()
        if any(word in content_str for word in query_lower.split()):
            score += 0.2
        
        # User-specific relevance
        if user_id and f"user_{user_id}" in entry.tags:
            score += 0.4
        
        # Recency bonus
        days_since_access = (datetime.now() - entry.last_accessed).days
        if days_since_access < 7:
            score += 0.1
        
        # Confidence bonus
        score += entry.confidence * 0.2
        
        return min(score, 1.0)
    
    def get_user_patterns(self, user_id: int) -> List[UserPattern]:
        """
        Get learned patterns for a specific user
        """
        return self.user_patterns.get(user_id, [])
    
    def get_conversation_context(self, context_id: str) -> List[Dict]:
        """
        Get conversation context for a specific session
        """
        return self.conversation_memory.get(context_id, [])
    
    def add_knowledge(self, category: str, content: Dict[str, Any], source: str = "user", tags: List[str] = None):
        """
        Add new knowledge to the knowledge base
        """
        entry = KnowledgeEntry(
            id=f"{category}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            category=category,
            content=content,
            confidence=0.7,
            created_at=datetime.now(),
            last_accessed=datetime.now(),
            access_count=0,
            source=source,
            tags=tags or []
        )
        
        self.knowledge_store[entry.id] = entry
        logger.info(f"Added new knowledge entry: {entry.id}")
    
    def update_knowledge_confidence(self, entry_id: str, new_confidence: float):
        """
        Update confidence level of a knowledge entry
        """
        if entry_id in self.knowledge_store:
            self.knowledge_store[entry_id].confidence = new_confidence
            self.knowledge_store[entry_id].last_accessed = datetime.now()
    
    def get_knowledge_summary(self) -> Dict[str, Any]:
        """
        Get summary of knowledge base
        """
        return {
            "total_entries": len(self.knowledge_store),
            "categories": list(set(entry.category for entry in self.knowledge_store.values())),
            "total_users_with_patterns": len(self.user_patterns),
            "total_conversations": len(self.conversation_memory),
            "most_accessed": sorted(
                self.knowledge_store.values(),
                key=lambda x: x.access_count,
                reverse=True
            )[:5]
        }
    
    def _learn_from_entities(self, user_id: int, conversation_data: Dict[str, Any]):
        """
        Learn from extracted entities
        """
        try:
            entities = conversation_data.get("entities", {})
            
            # Learn person preferences
            if entities.get("person"):
                self.add_user_pattern(
                    user_id,
                    "person_preferences",
                    {"frequent_contacts": [entities["person"]]}
                )
            
            # Learn time patterns
            if entities.get("time"):
                self.add_user_pattern(
                    user_id,
                    "time_patterns",
                    {"mentioned_times": [entities["time"]]}
                )
            
            # Learn date patterns
            if entities.get("date"):
                self.add_user_pattern(
                    user_id,
                    "date_patterns",
                    {"mentioned_dates": [entities["date"]]}
                )
                
        except Exception as e:
            logger.error(f"Error learning from entities: {e}")
    
    def _learn_from_actions(self, user_id: int, conversation_data: Dict[str, Any]):
        """
        Learn from actions taken
        """
        try:
            action_taken = conversation_data.get("action_taken")
            if action_taken:
                self.add_user_pattern(
                    user_id,
                    "action_patterns",
                    {"common_actions": [action_taken]}
                )
            
            # Learn from urgency
            urgency = conversation_data.get("urgency")
            if urgency:
                self.add_user_pattern(
                    user_id,
                    "urgency_patterns",
                    {"urgency_level": urgency}
                )
                
        except Exception as e:
            logger.error(f"Error learning from actions: {e}")
    
    def add_user_pattern(self, user_id: int, pattern_type: str, pattern_data: Dict[str, Any]):
        """
        Add a new user pattern to the knowledge base
        """
        try:
            pattern = UserPattern(
                user_id=user_id,
                pattern_type=pattern_type,
                pattern_data=pattern_data,
                frequency=1,
                last_observed=datetime.now(),
                confidence=0.8
            )
            
            if user_id not in self.user_patterns:
                self.user_patterns[user_id] = []
            
            # Check if pattern already exists
            existing_pattern = None
            for p in self.user_patterns[user_id]:
                if p.pattern_type == pattern_type:
                    existing_pattern = p
                    break
            
            if existing_pattern:
                # Update existing pattern
                existing_pattern.frequency += 1
                existing_pattern.last_observed = datetime.now()
                existing_pattern.confidence = min(existing_pattern.confidence + 0.1, 1.0)
                # Merge pattern data
                for key, value in pattern_data.items():
                    if key in existing_pattern.pattern_data:
                        if isinstance(existing_pattern.pattern_data[key], list):
                            existing_pattern.pattern_data[key].extend(value if isinstance(value, list) else [value])
                        else:
                            existing_pattern.pattern_data[key] = value
                    else:
                        existing_pattern.pattern_data[key] = value
            else:
                # Add new pattern
                self.user_patterns[user_id].append(pattern)
                
            logger.info(f"Added/updated user pattern for user {user_id}: {pattern_type}")
            
        except Exception as e:
            logger.error(f"Error adding user pattern: {e}") 