"""
Comprehensive Appointment Assistant Examples and Patterns
This file contains real conversation flows and examples for the AI agent to learn from.
"""

from typing import Dict, List, Any
from datetime import datetime, timedelta

class AppointmentExamples:
    """
    Comprehensive examples and patterns for appointment assistant
    """
    
    @staticmethod
    def get_conversation_examples() -> List[Dict[str, Any]]:
        """
        Get comprehensive conversation examples for training
        """
        return [
            # Example 1: Simple scheduling flow
            {
                "scenario": "Simple meeting scheduling",
                "conversation": [
                    {
                        "user": "schedule meeting with John tomorrow 2pm",
                        "agent": "✅ **Meeting scheduled!**\n📅 Tomorrow at 2pm\n👤 John\n📝 General discussion\n🔗 Booking ID: 12345",
                        "action_taken": "meeting_scheduled",
                        "entities": {"person": "John", "date": "tomorrow", "time": "2pm", "topic": "general discussion"},
                        "context_used": "Complete information provided in single message"
                    }
                ],
                "learning_points": [
                    "When all required info is provided, schedule immediately",
                    "Don't ask for confirmation if info is complete",
                    "Provide booking ID for reference"
                ]
            },
            
            # Example 2: Multi-turn scheduling
            {
                "scenario": "Multi-turn scheduling with context",
                "conversation": [
                    {
                        "user": "schedule meeting with Sarah on Monday",
                        "agent": "❓ What time would you like to meet with Sarah on Monday?",
                        "action_taken": "asking_for_info",
                        "entities": {"person": "Sarah", "date": "Monday", "time": None, "topic": None},
                        "context_used": "Missing time and topic"
                    },
                    {
                        "user": "3pm for project review",
                        "agent": "✅ **Meeting scheduled!**\n📅 Monday at 3pm\n👤 Sarah\n📝 project review\n🔗 Booking ID: 12346",
                        "action_taken": "meeting_scheduled",
                        "entities": {"person": "Sarah", "date": "Monday", "time": "3pm", "topic": "project review"},
                        "context_used": "Combined previous context (Sarah, Monday) with new info (3pm, project review)"
                    }
                ],
                "learning_points": [
                    "Remember context from previous messages",
                    "Combine entities from multiple turns",
                    "Schedule when all info is complete"
                ]
            },
            
            # Example 3: Availability checking
            {
                "scenario": "Check availability with real data",
                "conversation": [
                    {
                        "user": "check my availability",
                        "agent": "📅 **Available time slots:** 5 slots\n⏰ **Best time:** 14:00\n📊 **Busy:** 60% booked this week\n\n**Next available slots:**\n• 2025-01-27 09:00 - 10:00\n• 2025-01-27 14:00 - 15:00\n• 2025-01-28 10:00 - 11:00\n\n**📅 Calendar events today:**\n• Team Standup - 09:00\n• Client Meeting - 15:00",
                        "action_taken": "availability_checked",
                        "entities": {},
                        "context_used": "Fetched real calendar data and availability slots"
                    }
                ],
                "learning_points": [
                    "Show actual available slots",
                    "Display real calendar events",
                    "Provide insights about busy percentage"
                ]
            },
            
            # Example 4: Meeting cancellation
            {
                "scenario": "Meeting cancellation with confirmation",
                "conversation": [
                    {
                        "user": "cancel my meeting with John",
                        "agent": "❓ **Confirm cancellation:**\n👤 John\n📅 Monday at 2pm\n\nReply 'yes' to confirm cancellation.",
                        "action_taken": "cancellation_confirmation",
                        "entities": {"person": "John"},
                        "context_used": "Found matching meeting in upcoming bookings"
                    },
                    {
                        "user": "yes",
                        "agent": "✅ **Meeting ACTUALLY cancelled!**\n👤 John\n📅 Monday at 2pm\n🗑️ Removed from calendar",
                        "action_taken": "meeting_cancelled",
                        "entities": {},
                        "context_used": "Confirmed cancellation, actually deleted from database and calendar"
                    }
                ],
                "learning_points": [
                    "Ask for confirmation before cancelling",
                    "Actually delete from database and calendar",
                    "Confirm the action was completed"
                ]
            },
            
            # Example 5: Context awareness
            {
                "scenario": "Context awareness in conversation",
                "conversation": [
                    {
                        "user": "schedule with Ajay on Monday 5pm",
                        "agent": "❓ What would you like to discuss with Ajay on Monday at 5pm?",
                        "action_taken": "asking_for_info",
                        "entities": {"person": "Ajay", "date": "Monday", "time": "5pm", "topic": None},
                        "context_used": "Missing topic"
                    },
                    {
                        "user": "logo design",
                        "agent": "✅ **Meeting scheduled!**\n📅 Monday at 5pm\n👤 Ajay\n📝 logo design\n🔗 Booking ID: 12347",
                        "action_taken": "meeting_scheduled",
                        "entities": {"person": "Ajay", "date": "Monday", "time": "5pm", "topic": "logo design"},
                        "context_used": "Remembered Ajay, Monday, 5pm from previous message"
                    }
                ],
                "learning_points": [
                    "Remember all context from previous messages",
                    "Don't ask for info already provided",
                    "Combine entities intelligently"
                ]
            },
            
            # Example 6: Rescheduling
            {
                "scenario": "Meeting rescheduling",
                "conversation": [
                    {
                        "user": "reschedule my meeting with Sarah",
                        "agent": "**Upcoming meetings:**\n• Sarah - Monday at 3pm (project review)\n• John - Tuesday at 2pm (general discussion)\n\nWhich meeting would you like to reschedule?",
                        "action_taken": "reschedule_requested",
                        "entities": {"person": "Sarah"},
                        "context_used": "Found matching meeting"
                    },
                    {
                        "user": "the project review one",
                        "agent": "❓ What new time would you like for the project review with Sarah?",
                        "action_taken": "asking_for_new_time",
                        "entities": {"person": "Sarah", "topic": "project review"},
                        "context_used": "Identified specific meeting to reschedule"
                    },
                    {
                        "user": "Wednesday 4pm",
                        "agent": "✅ **Meeting rescheduled!**\n👤 Sarah\n📅 Wednesday at 4pm\n📝 project review\n🔄 Moved from Monday 3pm",
                        "action_taken": "meeting_rescheduled",
                        "entities": {"person": "Sarah", "date": "Wednesday", "time": "4pm", "topic": "project review"},
                        "context_used": "Updated existing meeting with new time"
                    }
                ],
                "learning_points": [
                    "Show available meetings when rescheduling",
                    "Ask for new time after identifying meeting",
                    "Actually update the meeting in database"
                ]
            },
            
            # Example 7: Urgent requests
            {
                "scenario": "Urgent meeting request",
                "conversation": [
                    {
                        "user": "urgent meeting with CEO now",
                        "agent": "🚨 **Urgent meeting detected!**\n\n**Available slots today:**\n• 11:00 - 12:00\n• 16:00 - 17:00\n\n✅ **Meeting scheduled!**\n📅 Today at 11:00\n👤 CEO\n📝 urgent discussion\n🔗 Booking ID: 12348",
                        "action_taken": "urgent_meeting_scheduled",
                        "entities": {"person": "CEO", "date": "today", "time": "now", "urgency": "high"},
                        "context_used": "Detected urgency, found next available slot"
                    }
                ],
                "learning_points": [
                    "Detect urgency in requests",
                    "Prioritize urgent meetings",
                    "Find immediate availability"
                ]
            },
            
            # Example 8: Recurring meetings
            {
                "scenario": "Recurring meeting setup",
                "conversation": [
                    {
                        "user": "set up weekly team meeting every Monday 10am",
                        "agent": "✅ **Recurring meeting created!**\n📅 Every Monday at 10am\n👥 Team Meeting\n📝 Weekly team sync\n🔄 Recurring: Weekly\n🔗 Series ID: 12349",
                        "action_taken": "recurring_meeting_created",
                        "entities": {"person": "team", "date": "Monday", "time": "10am", "frequency": "weekly", "topic": "team meeting"},
                        "context_used": "Detected recurring pattern"
                    }
                ],
                "learning_points": [
                    "Recognize recurring meeting patterns",
                    "Create series of meetings",
                    "Provide series ID for management"
                ]
            },
            
            # Example 9: Calendar sync issues
            {
                "scenario": "Calendar connection issues",
                "conversation": [
                    {
                        "user": "check my calendar",
                        "agent": "❌ **Calendar not connected**\n\nI can't access your calendar. Please connect your Google Calendar to see your events.\n\n**Available actions:**\n• Connect Google Calendar\n• Check availability slots\n• Schedule new meetings",
                        "action_taken": "calendar_not_connected",
                        "entities": {},
                        "context_used": "Detected missing calendar connection"
                    }
                ],
                "learning_points": [
                    "Handle missing calendar connections gracefully",
                    "Provide alternative actions",
                    "Guide user to connect calendar"
                ]
            },
            
            # Example 10: Complex scheduling with preferences
            {
                "scenario": "Scheduling with user preferences",
                "conversation": [
                    {
                        "user": "schedule meeting with client",
                        "agent": "❓ What client would you like to meet with?",
                        "action_taken": "asking_for_info",
                        "entities": {"person": "client", "date": None, "time": None, "topic": None},
                        "context_used": "Missing specific client name"
                    },
                    {
                        "user": "ABC Corp",
                        "agent": "❓ When would you like to meet with ABC Corp?",
                        "action_taken": "asking_for_info",
                        "entities": {"person": "ABC Corp", "date": None, "time": None, "topic": None},
                        "context_used": "Remembered client name"
                    },
                    {
                        "user": "this week",
                        "agent": "**Available slots this week:**\n• Tuesday 2pm - 3pm\n• Wednesday 10am - 11am\n• Thursday 3pm - 4pm\n\nWhich time works best for ABC Corp?",
                        "action_taken": "showing_availability",
                        "entities": {"person": "ABC Corp", "date": "this week"},
                        "context_used": "Found available slots for the week"
                    },
                    {
                        "user": "Tuesday 2pm",
                        "agent": "❓ What would you like to discuss with ABC Corp on Tuesday at 2pm?",
                        "action_taken": "asking_for_info",
                        "entities": {"person": "ABC Corp", "date": "Tuesday", "time": "2pm", "topic": None},
                        "context_used": "Missing topic"
                    },
                    {
                        "user": "project proposal",
                        "agent": "✅ **Meeting scheduled!**\n📅 Tuesday at 2pm\n👤 ABC Corp\n📝 project proposal\n🔗 Booking ID: 12350",
                        "action_taken": "meeting_scheduled",
                        "entities": {"person": "ABC Corp", "date": "Tuesday", "time": "2pm", "topic": "project proposal"},
                        "context_used": "Complete information gathered through conversation"
                    }
                ],
                "learning_points": [
                    "Ask for missing information step by step",
                    "Show available slots when needed",
                    "Remember all context throughout conversation",
                    "Schedule when all info is complete"
                ]
            }
        ]
    
    @staticmethod
    def get_entity_patterns() -> Dict[str, List[str]]:
        """
        Get patterns for entity extraction
        """
        return {
            "person": [
                "with {name}",
                "meeting {name}",
                "call {name}",
                "discussion with {name}",
                "{name} and I",
                "team meeting",
                "client meeting",
                "CEO",
                "manager"
            ],
            "date": [
                "today",
                "tomorrow",
                "next {day}",
                "this {day}",
                "upcoming {day}",
                "Monday",
                "Tuesday",
                "Wednesday",
                "Thursday",
                "Friday",
                "Saturday",
                "Sunday",
                "next week",
                "this week",
                "in 2 days",
                "on {date}"
            ],
            "time": [
                "at {time}",
                "{time}",
                "morning",
                "afternoon",
                "evening",
                "9am",
                "10am",
                "11am",
                "12pm",
                "1pm",
                "2pm",
                "3pm",
                "4pm",
                "5pm",
                "6pm",
                "now",
                "asap",
                "urgent"
            ],
            "topic": [
                "about {topic}",
                "discuss {topic}",
                "review {topic}",
                "meeting for {topic}",
                "call about {topic}",
                "project {topic}",
                "client {topic}",
                "team {topic}",
                "weekly sync",
                "daily standup",
                "monthly review"
            ],
            "duration": [
                "for {duration}",
                "{duration} meeting",
                "30 minutes",
                "1 hour",
                "2 hours",
                "half hour",
                "quick call",
                "long meeting"
            ]
        }
    
    @staticmethod
    def get_context_rules() -> List[str]:
        """
        Get rules for context management
        """
        return [
            "ALWAYS remember person, date, time, topic from previous messages",
            "NEVER ask for information already provided",
            "Combine entities from multiple messages intelligently",
            "When all required info is present, take action immediately",
            "If missing info, ask for ONLY the missing pieces",
            "Use 'this' and 'that' to refer to previously mentioned items",
            "Remember user preferences and patterns",
            "Handle urgency appropriately",
            "Provide confirmation for destructive actions",
            "Show real data when available"
        ]
    
    @staticmethod
    def get_action_patterns() -> Dict[str, Dict[str, Any]]:
        """
        Get patterns for different actions
        """
        return {
            "schedule_meeting": {
                "required_entities": ["person", "date", "time", "topic"],
                "optional_entities": ["duration"],
                "action": "create_booking",
                "confirmation_required": False,
                "success_message": "✅ **Meeting scheduled!**\n📅 {date} at {time}\n👤 {person}\n📝 {topic}\n🔗 Booking ID: {booking_id}",
                "missing_info_message": "❓ {missing_info_question}"
            },
            "check_availability": {
                "required_entities": [],
                "optional_entities": ["date", "time"],
                "action": "fetch_availability",
                "confirmation_required": False,
                "success_message": "📅 **Available time slots:** {count} slots\n⏰ **Best time:** {best_time}\n📊 **Busy:** {busy_percentage}% booked\n\n**Next available slots:**\n{slots}\n\n**📅 Calendar events today:**\n{events}",
                "missing_info_message": "📅 **Available time slots:** {count} slots\n⏰ **Best time:** {best_time}\n📊 **Busy:** {busy_percentage}% booked"
            },
            "cancel_meeting": {
                "required_entities": ["person"],
                "optional_entities": ["date", "time"],
                "action": "delete_booking",
                "confirmation_required": True,
                "success_message": "✅ **Meeting ACTUALLY cancelled!**\n👤 {person}\n📅 {date} at {time}\n🗑️ Removed from calendar",
                "missing_info_message": "❓ **Confirm cancellation:**\n👤 {person}\n📅 {date} at {time}\n\nReply 'yes' to confirm cancellation."
            },
            "reschedule_meeting": {
                "required_entities": ["person", "date", "time"],
                "optional_entities": ["topic"],
                "action": "update_booking",
                "confirmation_required": True,
                "success_message": "✅ **Meeting rescheduled!**\n👤 {person}\n📅 {date} at {time}\n📝 {topic}\n🔄 Moved from {old_time}",
                "missing_info_message": "❓ What new time would you like for the {topic} with {person}?"
            }
        } 