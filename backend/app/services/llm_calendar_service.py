"""
LLM Calendar Service - Provides calendar access to the AI agent
This service allows the LLM to read and manage calendar events for appointment scheduling
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session

from app.models.models import User
from app.services.google_calendar_service import GoogleCalendarService
from app.services.availability_service import AvailabilityService


class LLMCalendarService:
    """
    Service that provides calendar access to the LLM agent
    Handles calendar operations like checking availability, scheduling, etc.
    """
    
    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.user_id = user_id
        self.user = db.query(User).filter(User.id == user_id).first()
        self.calendar_service = None
        self.availability_service = AvailabilityService(db)
        
        # Initialize calendar service if user has connected calendar
        if self.user and self.user.google_calendar_connected:
            self._initialize_calendar_service()
    
    def _initialize_calendar_service(self):
        """Initialize Google Calendar service with user's credentials"""
        try:
            if self.user.google_access_token:
                # Try to initialize with available tokens
                refresh_token = self.user.google_refresh_token if self.user.google_refresh_token else None
                
                self.calendar_service = GoogleCalendarService(
                    access_token=self.user.google_access_token,
                    refresh_token=refresh_token
                )
                
                # Test the connection by trying to get events
                try:
                    test_events = self.calendar_service.get_events()
                    print(f"Calendar service initialized successfully for {self.user.google_calendar_email}")
                except Exception as test_error:
                    print(f"Calendar service initialized but test failed: {test_error}")
                    # Don't set to None yet, let individual methods handle the error
                    
            else:
                print(f"No access token available for user {self.user_id}")
                self.calendar_service = None
                
        except Exception as e:
            print(f"Failed to initialize calendar service for user {self.user_id}: {e}")
            self.calendar_service = None
    
    def is_calendar_connected(self) -> bool:
        """Check if user has connected their calendar"""
        return self.user and self.user.google_calendar_connected and self.calendar_service is not None
    
    def get_calendar_status(self) -> Dict[str, Any]:
        """Get calendar connection status and basic info"""
        if not self.user:
            return {"connected": False, "message": "User not found"}
        
        if not self.user.google_calendar_connected:
            return {
                "connected": False, 
                "message": "Google Calendar not connected",
                "action_required": "connect_calendar"
            }
        
        # Check if we have the necessary credentials
        if not self.user.google_access_token:
            return {
                "connected": False,
                "message": "No calendar access token available",
                "action_required": "connect_calendar"
            }
        
        # Test the calendar service if available
        if self.calendar_service:
            try:
                # Try a simple operation to test the connection
                test_events = self.calendar_service.get_events()
                return {
                    "connected": True,
                    "calendar_email": self.user.google_calendar_email,
                    "message": "Calendar connected and ready",
                    "test_events_count": len(test_events) if test_events else 0
                }
            except Exception as e:
                return {
                    "connected": False,
                    "message": f"Calendar service error: {str(e)}",
                    "action_required": "refresh_credentials",
                    "calendar_email": self.user.google_calendar_email
                }
        else:
            return {
                "connected": False,
                "message": "Calendar service not initialized",
                "action_required": "refresh_credentials",
                "calendar_email": self.user.google_calendar_email
            }
    
    def get_available_slots(self, date: Optional[datetime] = None, duration_minutes: int = 30) -> List[Dict[str, Any]]:
        """
        Get available time slots for the user
        Returns both manually set availability and calendar-based availability
        """
        if not self.is_calendar_connected():
            return []
        
        try:
            # Get manually set availability slots
            manual_slots = self.availability_service.get_user_availability_slots(
                self.user_id, date, duration_minutes
            )
            
            # Get calendar-based availability
            calendar_slots = []
            if self.calendar_service:
                calendar_slots = self.calendar_service.get_available_slots(
                    date or datetime.now(), duration_minutes
                )
            
            # Combine and deduplicate slots
            all_slots = manual_slots + calendar_slots
            return self._deduplicate_slots(all_slots)
            
        except Exception as e:
            print(f"Error getting available slots: {e}")
            return []
    
    def check_availability(self, start_time: datetime, end_time: datetime) -> Dict[str, Any]:
        """
        Check if a specific time slot is available
        Returns detailed availability information
        """
        if not self.is_calendar_connected():
            return {
                "available": False,
                "reason": "calendar_not_connected",
                "message": "Calendar not connected"
            }
        
        try:
            # Check manual availability slots
            manual_available = self.availability_service.check_slot_availability(
                self.user_id, start_time, end_time
            )
            
            # Check calendar conflicts
            calendar_available = True
            if self.calendar_service:
                calendar_available = self.calendar_service.check_availability(start_time, end_time)
            
            is_available = manual_available and calendar_available
            
            return {
                "available": is_available,
                "manual_available": manual_available,
                "calendar_available": calendar_available,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_minutes": int((end_time - start_time).total_seconds() / 60)
            }
            
        except Exception as e:
            return {
                "available": False,
                "reason": "error",
                "message": f"Error checking availability: {str(e)}"
            }
    
    def get_upcoming_events(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get upcoming calendar events"""
        if not self.is_calendar_connected():
            return []
        
        try:
            start_date = datetime.now()
            end_date = start_date + timedelta(days=days)
            
            events = self.calendar_service.get_events(start_date, end_date)
            
            # Format events for LLM consumption
            formatted_events = []
            for event in events:
                start = event.get('start', {}).get('dateTime')
                end = event.get('end', {}).get('dateTime')
                
                if start and end:
                    formatted_events.append({
                        "id": event.get('id'),
                        "title": event.get('summary', 'Untitled'),
                        "start_time": start,
                        "end_time": end,
                        "description": event.get('description', ''),
                        "location": event.get('location', ''),
                        "attendees": [a.get('email') for a in event.get('attendees', [])]
                    })
            
            return formatted_events
            
        except Exception as e:
            print(f"Error getting upcoming events: {e}")
            return []
    
    def schedule_meeting(self, title: str, start_time: datetime, end_time: datetime, 
                        guest_email: str, description: str = None) -> Dict[str, Any]:
        """
        Schedule a meeting using both availability system and Google Calendar
        """
        if not self.is_calendar_connected():
            return {
                "success": False,
                "reason": "calendar_not_connected",
                "message": "Calendar not connected"
            }
        
        try:
            # First check availability
            availability_check = self.check_availability(start_time, end_time)
            if not availability_check["available"]:
                return {
                    "success": False,
                    "reason": "slot_unavailable",
                    "message": "Requested time slot is not available",
                    "details": availability_check
                }
            
            # Create Google Calendar event
            calendar_event = None
            if self.calendar_service:
                calendar_event = self.calendar_service.create_event(
                    title=title,
                    start_time=start_time,
                    end_time=end_time,
                    guest_email=guest_email,
                    host_email=self.user.email,
                    description=description
                )
            
            # Create availability slot and booking in our system
            booking_data = self.availability_service.create_booking_from_calendar(
                user_id=self.user_id,
                title=title,
                start_time=start_time,
                end_time=end_time,
                guest_email=guest_email,
                guest_name=guest_email.split('@')[0],  # Simple name extraction
                description=description,
                google_event_id=calendar_event.get('id') if calendar_event else None
            )
            
            return {
                "success": True,
                "booking_id": booking_data.get("booking_id"),
                "google_event_id": calendar_event.get('id') if calendar_event else None,
                "message": "Meeting scheduled successfully"
            }
            
        except Exception as e:
            return {
                "success": False,
                "reason": "error",
                "message": f"Error scheduling meeting: {str(e)}"
            }
    
    def get_calendar_summary(self) -> Dict[str, Any]:
        """Get a summary of calendar status and upcoming events"""
        status = self.get_calendar_status()
        
        if not status["connected"]:
            return status
        
        try:
            upcoming_events = self.get_upcoming_events(days=7)
            available_slots = self.get_available_slots(duration_minutes=30)
            
            return {
                **status,
                "upcoming_events_count": len(upcoming_events),
                "available_slots_count": len(available_slots),
                "next_available_slot": available_slots[0] if available_slots else None,
                "next_event": upcoming_events[0] if upcoming_events else None
            }
            
        except Exception as e:
            return {
                **status,
                "error": f"Error getting calendar summary: {str(e)}"
            }
    
    def _deduplicate_slots(self, slots: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate time slots"""
        seen = set()
        unique_slots = []
        
        for slot in slots:
            start_key = slot.get('start_time')
            if start_key not in seen:
                seen.add(start_key)
                unique_slots.append(slot)
        
        return sorted(unique_slots, key=lambda x: x.get('start_time', ''))
    
    def refresh_calendar_credentials(self) -> Dict[str, Any]:
        """Attempt to refresh calendar credentials"""
        if not self.user or not self.user.google_calendar_connected:
            return {
                "success": False,
                "message": "No calendar connection to refresh"
            }
        
        try:
            # Re-initialize the calendar service
            self._initialize_calendar_service()
            
            # Test the connection
            status = self.get_calendar_status()
            
            if status["connected"]:
                return {
                    "success": True,
                    "message": "Calendar credentials refreshed successfully",
                    "calendar_email": self.user.google_calendar_email
                }
            else:
                return {
                    "success": False,
                    "message": "Failed to refresh calendar credentials",
                    "details": status
                }
                
        except Exception as e:
            return {
                "success": False,
                "message": f"Error refreshing credentials: {str(e)}"
            } 