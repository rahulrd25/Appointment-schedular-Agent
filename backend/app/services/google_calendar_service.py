import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List
import logging

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from app.core.calendar_architecture import BaseCalendarProvider, CalendarProviderType
from app.core.config import settings

logger = logging.getLogger(__name__)

class GoogleCalendarService(BaseCalendarProvider):
    def __init__(self, access_token: str = None, refresh_token: str = None, db: Optional[Any] = None, user_id: Optional[int] = None):
        # Call parent constructor
        super().__init__(access_token=access_token, refresh_token=refresh_token, db=db, user_id=user_id)
        
        self.credentials = None
        
        if access_token and refresh_token:
            self.credentials = Credentials(
                token=access_token,
                refresh_token=refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=settings.GOOGLE_CLIENT_ID,
                client_secret=settings.GOOGLE_CLIENT_SECRET,
                scopes=[
                    "https://www.googleapis.com/auth/calendar",
                    "https://www.googleapis.com/auth/calendar.events",
                    "https://www.googleapis.com/auth/calendar.readonly"
                ],
            )

    def get_authorization_url(self):
        # Use environment variables instead of client_secret.json
        if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
            raise Exception("Google OAuth credentials not configured. Please set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET environment variables.")
        
        # Create flow using environment variables
        flow = InstalledAppFlow.from_client_config(
            {
                "installed": {
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                    "redirect_uris": [settings.GOOGLE_REDIRECT_URI]
                }
            },
            [
                "https://www.googleapis.com/auth/calendar",
                "https://www.googleapis.com/auth/calendar.events",
                "https://www.googleapis.com/auth/calendar.readonly"
            ]
        )
        flow.redirect_uri = settings.GOOGLE_REDIRECT_URI
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent'  # Force consent screen to ensure refresh token
        )
        return authorization_url, state

    def get_tokens_from_auth_code(self, auth_code: str):
        # Use environment variables instead of client_secret.json
        if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
            raise Exception("Google OAuth credentials not configured. Please set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET environment variables.")
        
        # Create flow using environment variables
        flow = InstalledAppFlow.from_client_config(
            {
                "installed": {
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                    "redirect_uris": [settings.GOOGLE_REDIRECT_URI]
                }
            },
            [
                "https://www.googleapis.com/auth/calendar",
                "https://www.googleapis.com/auth/calendar.events",
                "https://www.googleapis.com/auth/calendar.readonly"
            ]
        )
        flow.redirect_uri = settings.GOOGLE_REDIRECT_URI
        flow.fetch_token(code=auth_code)
        self.credentials = flow.credentials
        return {
            "access_token": self.credentials.token,
            "refresh_token": self.credentials.refresh_token,
        }

    def _ensure_valid_credentials(self):
        """Ensure credentials are valid and refresh if needed."""
        if not self.credentials:
            raise Exception("Google credentials not set.")

        # Use our TokenRefreshService for proper token refresh
        if not self.db or not self.user_id:
            raise Exception("Database and user_id required for token refresh")
            
        from app.services.token_refresh_service import TokenRefreshService
        from app.models.models import User
        
        # Get user from database
        user = self.db.query(User).filter(User.id == self.user_id).first()
        if not user:
            raise Exception("User not found")
        
        # Use token refresh service
        token_service = TokenRefreshService(self.db)
        result = token_service.ensure_valid_tokens(user)
        
        if result["success"]:
            # Update credentials with new tokens
            self.credentials = Credentials(
                token=result["access_token"],
                refresh_token=result["refresh_token"],
                token_uri="https://oauth2.googleapis.com/token",
                client_id=settings.GOOGLE_CLIENT_ID,
                client_secret=settings.GOOGLE_CLIENT_SECRET,
                scopes=[
                    "https://www.googleapis.com/auth/calendar",
                    "https://www.googleapis.com/auth/calendar.events",
                    "https://www.googleapis.com/auth/calendar.readonly"
                ],
            )
        else:
            logger.error(f"[GOOGLE CALENDAR] Token refresh failed: {result['message']}")
            # Don't raise exception, just log the error and continue with existing credentials
            # This allows the sync to continue even if token refresh fails
            return

    def check_availability(self, start_time: datetime, end_time: datetime) -> bool:
        """Check if a time slot is available (no conflicting events)."""
        self._ensure_valid_credentials()
        service = build('calendar', 'v3', credentials=self.credentials)
        
        # Ensure datetime objects are timezone-aware
        if start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=timezone.utc)
        if end_time.tzinfo is None:
            end_time = end_time.replace(tzinfo=timezone.utc)
        
        # Get events that overlap with the requested time slot
        events_result = service.events().list(
            calendarId='primary',
            timeMin=start_time.isoformat(),
            timeMax=end_time.isoformat(),
            singleEvents=True
        ).execute()
        
        events = events_result.get('items', [])        
        # Filter out events that are marked as 'transparent' (free time)
        conflicting_events = [
            event for event in events 
            if event.get('transparency', 'opaque') != 'transparent'
        ]
        
        return len(conflicting_events) == 0

    def get_events(self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """
        Get events from Google Calendar for a date range.
        
        Args:
            start_date: Start date for event search (defaults to 7 days ago)
            end_date: End date for event search (defaults to 7 days from now)
            
        Returns:
            List of calendar events
        """
        try:
            self._ensure_valid_credentials()
            
            service = build('calendar', 'v3', credentials=self.credentials)
            
            # Set default date range if not provided
            if start_date is None:
                start_date = datetime.now(timezone.utc) - timedelta(days=7)
            if end_date is None:
                end_date = datetime.now(timezone.utc) + timedelta(days=7)
            
            # Convert datetime to RFC3339 format
            # Ensure timezone-aware datetime and format correctly
            if start_date.tzinfo is None:
                start_date = start_date.replace(tzinfo=timezone.utc)
            if end_date.tzinfo is None:
                end_date = end_date.replace(tzinfo=timezone.utc)
            
            # Format as RFC3339 - don't append 'Z' if already timezone-aware
            start_date_str = start_date.isoformat()
            end_date_str = end_date.isoformat()
            
            logger.info(f"[GOOGLE CALENDAR] Fetching events from {start_date_str} to {end_date_str}")
            
            events_result = service.events().list(
                calendarId='primary',
                timeMin=start_date_str,
                timeMax=end_date_str,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            logger.info(f"[GOOGLE CALENDAR] Found {len(events)} events")
            
            return events
            
        except Exception as e:
            logger.error(f"[GOOGLE CALENDAR ERROR] Failed to get events: {str(e)}")
            # Check if it's a network/SSL error
            if "SSL" in str(e) or "EOF" in str(e) or "Max retries" in str(e):
                logger.warning(f"[GOOGLE CALENDAR] Network error detected, will retry later")
            return []

    def get_available_slots(self, date, duration_minutes: int = 30) -> list:
        """Get available time slots for a given date."""
        self._ensure_valid_credentials()
        service = build('calendar', 'v3', credentials=self.credentials)
        
        # Define business hours (9 AM to 5 PM)
        start_hour = 9
        end_hour = 17
        
        # Ensure date is timezone-aware (UTC)
        # Convert date to datetime if it's a date object
        if hasattr(date, 'date'):  # It's a datetime object
            if date.tzinfo is None:
                date = date.replace(tzinfo=timezone.utc)
        else:  # It's a date object, convert to datetime
            date = datetime.combine(date, datetime.min.time()).replace(tzinfo=timezone.utc)        
        # Create start and end times for the day (timezone-aware)
        day_start = date.replace(hour=start_hour, minute=0, second=0, microsecond=0)
        day_end = date.replace(hour=end_hour, minute=0, second=0, microsecond=0)
        
        # Get all events for the day
        events_result = service.events().list(
            calendarId='primary',
            timeMin=day_start.isoformat(),
            timeMax=day_end.isoformat(),
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        
        # Filter out transparent events (free time)
        busy_events = [
            event for event in events 
            if event.get('transparency', 'opaque') != 'transparent'
        ]
        
        # Generate available slots
        available_slots = []
        current_time = day_start
        
        while current_time + timedelta(minutes=duration_minutes) <= day_end:
            slot_end = current_time + timedelta(minutes=duration_minutes)
            
            # Check if this slot conflicts with any busy events
            is_available = True
            for event in busy_events:
                # Parse event times and ensure they're timezone-aware
                event_start_str = event['start'].get('dateTime', event['start'].get('date'))
                event_end_str = event['end'].get('dateTime', event['end'].get('date'))
                
                # Handle both dateTime and date formats
                if 'T' in event_start_str:  # dateTime format
                    event_start = datetime.fromisoformat(event_start_str.replace('Z', '+00:00'))
                    event_end = datetime.fromisoformat(event_end_str.replace('Z', '+00:00'))
                else:  # date format (all-day events)
                    event_start = datetime.fromisoformat(event_start_str).replace(tzinfo=timezone.utc)
                    event_end = datetime.fromisoformat(event_end_str).replace(tzinfo=timezone.utc)
                
                # Check for overlap
                if (current_time < event_end and slot_end > event_start):
                    is_available = False
                    break
            
            if is_available:
                available_slots.append({
                    'start_time': current_time,
                    'end_time': slot_end
                })
            
            # Move to next slot (30-minute intervals)
            current_time += timedelta(minutes=30)
        
        return available_slots

    def create_event(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a calendar event with the provided event data."""
        self._ensure_valid_credentials()
        
        service = build('calendar', 'v3', credentials=self.credentials)
        
        try:
            created_event = service.events().insert(calendarId='primary', body=event_data, sendUpdates='none').execute()
            return created_event
        except Exception as e:
            self._handle_google_api_error(e)

    def create_booking_event(        self,
        title: str,
        start_time: datetime,
        end_time: datetime,
        guest_email: str,
        host_email: str,
        description: Optional[str] = None,
        location: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a calendar event for a booking."""
        self._ensure_valid_credentials()
        
        service = build('calendar', 'v3', credentials=self.credentials)
        
        # Ensure datetime objects are timezone-aware
        if start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=timezone.utc)
        if end_time.tzinfo is None:
            end_time = end_time.replace(tzinfo=timezone.utc)
        
        event = {
            'summary': title,
            'description': description or f"Meeting with {guest_email}",
            'start': {
                'dateTime': start_time.isoformat(),
                'timeZone': 'UTC',
            },
            'end': {
                'dateTime': end_time.isoformat(),
                'timeZone': 'UTC',
            },
            'attendees': [
                {'email': guest_email},
                {'email': host_email},
            ],
            'reminders': {
                'useDefault': False,
                'overrides': [
                    {'method': 'email', 'minutes': 24 * 60},  # 24 hours before
                    {'method': 'popup', 'minutes': 15},        # 15 minutes before
                ],
            },
            'guestsCanSeeOtherGuests': False,
            'guestsCanModify': False,
        }
        
        if location:
            event['location'] = location
        
        try:
            created_event = service.events().insert(calendarId='primary', body=event, sendUpdates='all').execute()
            return created_event
        except Exception as e:
            self._handle_google_api_error(e)
    def update_event(
        self,
        event_id: str,
        title: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        description: Optional[str] = None,
        location: Optional[str] = None
    ) -> Dict[str, Any]:
        """Update an existing calendar event."""
        try:
            logger.info(f"[GOOGLE CALENDAR] Updating event: {event_id}")
            self._ensure_valid_credentials()
            
            service = build('calendar', 'v3', credentials=self.credentials)
            
            # Get the existing event
            logger.info(f"[GOOGLE CALENDAR] Getting existing event: {event_id}")
            event = service.events().get(calendarId='primary', eventId=event_id).execute()
            logger.info(f"[GOOGLE CALENDAR] Retrieved existing event")
            
            # Update fields if provided
            if title:
                event['summary'] = title
            if description:
                event['description'] = description
            if location:
                event['location'] = location
            if start_time:
                # Ensure datetime object is timezone-aware
                if start_time.tzinfo is None:
                    start_time = start_time.replace(tzinfo=timezone.utc)
                event['start'] = {
                    'dateTime': start_time.isoformat(),
                    'timeZone': 'UTC',
                }
                logger.info(f"[GOOGLE CALENDAR] Updated start time: {start_time.isoformat()}")
            if end_time:
                # Ensure datetime object is timezone-aware
                if end_time.tzinfo is None:
                    end_time = end_time.replace(tzinfo=timezone.utc)
                event['end'] = {
                    'dateTime': end_time.isoformat(),
                    'timeZone': 'UTC',
                }
                logger.info(f"[GOOGLE CALENDAR] Updated end time: {end_time.isoformat()}")
            
            logger.info(f"[GOOGLE CALENDAR] Updating event in calendar...")
            updated_event = service.events().update(
                calendarId='primary', 
                eventId=event_id, 
                body=event,
                sendUpdates='all'
            ).execute()
            logger.info(f"[GOOGLE CALENDAR] Successfully updated event: {event_id}")
            return updated_event
            
        except Exception as e:
            logger.error(f"[GOOGLE CALENDAR ERROR] Error updating event {event_id}: {e}")
            self._handle_google_api_error(e)
            raise
    def delete_event(self, event_id: str) -> bool:
        """Delete an event from Google Calendar."""
        try:
            self._ensure_valid_credentials()
            
            service = build('calendar', 'v3', credentials=self.credentials)
            
            service.events().delete(
                calendarId='primary',
                eventId=event_id
            ).execute()
            
            logger.info(f"[GOOGLE CALENDAR] Deleted event {event_id}")
            return True
            
        except Exception as e:
            logger.error(f"[GOOGLE CALENDAR ERROR] Failed to delete event {event_id}: {str(e)}")
            return False

    def get_event(self, event_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific event from Google Calendar."""
        try:
            self._ensure_valid_credentials()
            
            service = build('calendar', 'v3', credentials=self.credentials)
            
            event = service.events().get(
                calendarId='primary',
                eventId=event_id
            ).execute()
            
            return event
            
        except Exception as e:
            logger.error(f"[GOOGLE CALENDAR ERROR] Failed to get event {event_id}: {str(e)}")
            return None

    def _get_provider_type(self):
        """Return the provider type for the calendar architecture."""
        from app.core.calendar_architecture import CalendarProviderType
        return CalendarProviderType.GOOGLE

    def _handle_google_api_error(self, error):
        """Handle Google API errors."""
        logger.error(f"[GOOGLE CALENDAR ERROR] Google API Error: {error}")
        if hasattr(error, 'resp') and error.resp.status == 401:
            logger.warning("[GOOGLE CALENDAR] Token expired, attempting refresh...")
            try:
                self._ensure_valid_credentials()
            except Exception as refresh_error:
                logger.error(f"[GOOGLE CALENDAR ERROR] Token refresh failed: {refresh_error}")
        raise error

