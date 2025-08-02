import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from app.core.calendar_architecture import BaseCalendarProvider, CalendarProviderType


class GoogleCalendarService(BaseCalendarProvider):
    def __init__(self, access_token: str = None, refresh_token: str = None, db: Optional[Any] = None, user_id: Optional[int] = None):
        super().__init__(access_token, refresh_token, db, user_id)
        self.credentials = None
        self.db = db
        self.user_id = user_id
        if access_token:
            # Create credentials with available tokens
            # Note: refresh_token can be None for some OAuth flows
            self.credentials = Credentials(
                token=access_token,
                refresh_token=refresh_token,  # Can be None
                token_uri="https://oauth2.googleapis.com/token",
                client_id=os.getenv("GOOGLE_CLIENT_ID"),
                client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
                scopes=[
                    "https://www.googleapis.com/auth/calendar",
                    "https://www.googleapis.com/auth/calendar.events",
                    "https://www.googleapis.com/auth/calendar.readonly"
                ],
            )

    def _get_provider_type(self) -> CalendarProviderType:
        """Return the provider type."""
        return CalendarProviderType.GOOGLE

    def get_authorization_url(self):
        flow = InstalledAppFlow.from_client_secrets_file(
            'client_secret.json', [
                "https://www.googleapis.com/auth/calendar",
                "https://www.googleapis.com/auth/calendar.events",
                "https://www.googleapis.com/auth/calendar.readonly"
            ]
        )
        flow.redirect_uri = os.getenv("GOOGLE_REDIRECT_URI")
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent'  # Force consent screen to ensure refresh token
        )
        return authorization_url, state

    def get_tokens_from_auth_code(self, auth_code: str):
        flow = InstalledAppFlow.from_client_secrets_file(
            'client_secret.json', [
                "https://www.googleapis.com/auth/calendar",
                "https://www.googleapis.com/auth/calendar.events",
                "https://www.googleapis.com/auth/calendar.readonly"
            ]
        )
        flow.redirect_uri = os.getenv("GOOGLE_REDIRECT_URI")
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
                client_id=os.getenv("GOOGLE_CLIENT_ID"),
                client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
                scopes=[
                    "https://www.googleapis.com/auth/calendar",
                    "https://www.googleapis.com/auth/calendar.events",
                    "https://www.googleapis.com/auth/calendar.readonly"
                ],
            )
        else:
            raise Exception("Token refresh failed: " + result["message"])

    def _handle_google_api_error(self, error):
        """Handle Google API errors."""
        error_message = f"Calendar access failed: {str(error)}"
        print(f"Google Calendar API Error: {error}")
        raise Exception(error_message)


    def get_events(self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Get events from the calendar provider."""
        try:
            self._ensure_valid_credentials()
            service = build('calendar', 'v3', credentials=self.credentials)
            
            # Set default time range if not provided
            if not start_date:
                start_date = datetime.now(timezone.utc) - timedelta(days=7)
            if not end_date:
                end_date = datetime.now(timezone.utc) + timedelta(days=30)
            
            # Format dates for Google Calendar API (RFC 3339 format)
            time_min = start_date.replace(microsecond=0).strftime('%Y-%m-%dT%H:%M:%SZ')
            time_max = end_date.replace(microsecond=0).strftime('%Y-%m-%dT%H:%M:%SZ')
            
            events_result = service.events().list(
                calendarId='primary',
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            return events
            
        except Exception as e:
            self._handle_google_api_error(e)
            return []

    def check_availability(self, start_time: datetime, end_time: datetime) -> bool:
        """Check if a time slot is available."""
        try:
            # Get events in the time range
            events = self.get_events(start_time, end_time)
            
            # Check for conflicts
            for event in events:
                event_start = event.get('start', {}).get('dateTime')
                event_end = event.get('end', {}).get('dateTime')
                
                if event_start and event_end:
                    from datetime import datetime
                    event_start_dt = datetime.fromisoformat(event_start.replace('Z', '+00:00'))
                    event_end_dt = datetime.fromisoformat(event_end.replace('Z', '+00:00'))
                    
                    # Check for overlap
                    if (start_time < event_end_dt and end_time > event_start_dt):
                        return False  # Conflict found
            
            return True  # No conflicts
            
        except Exception as e:
            self._handle_google_api_error(e)
            return False

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
        """Create an event in the calendar provider."""
        try:
            self._ensure_valid_credentials()
            service = build('calendar', 'v3', credentials=self.credentials)
            
            # Extract event data
            summary = event_data.get('summary', 'Appointment')
            start_time = event_data.get('start', {}).get('dateTime')
            end_time = event_data.get('end', {}).get('dateTime')
            description = event_data.get('description', '')
            location = event_data.get('location', '')
            
            event = {
                'summary': summary,
                'description': description,
                'location': location,
                'start': {
                    'dateTime': start_time,
                    'timeZone': 'UTC',
                },
                'end': {
                    'dateTime': end_time,
                    'timeZone': 'UTC',
                },
            }
            
            event = service.events().insert(calendarId='primary', body=event).execute()
            return event
            
        except Exception as e:
            self._handle_google_api_error(e)
            raise

    def create_booking_event(
        self,
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

    def update_event(self, event_id: str, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an event in the calendar provider."""
        try:
            self._ensure_valid_credentials()
            service = build('calendar', 'v3', credentials=self.credentials)
            
            # Get existing event first
            existing_event = service.events().get(calendarId='primary', eventId=event_id).execute()
            
            # Update with new data
            if 'summary' in event_data:
                existing_event['summary'] = event_data['summary']
            if 'description' in event_data:
                existing_event['description'] = event_data['description']
            if 'location' in event_data:
                existing_event['location'] = event_data['location']
            if 'start' in event_data:
                existing_event['start'] = event_data['start']
            if 'end' in event_data:
                existing_event['end'] = event_data['end']
            
            updated_event = service.events().update(
                calendarId='primary', 
                eventId=event_id, 
                body=existing_event
            ).execute()
            
            return updated_event
            
        except Exception as e:
            self._handle_google_api_error(e)
            raise

    def delete_event(self, event_id: str) -> bool:
        """Delete an event from the calendar provider."""
        try:
            self._ensure_valid_credentials()
            service = build('calendar', 'v3', credentials=self.credentials)
            service.events().delete(calendarId='primary', eventId=event_id).execute()
            return True
        except Exception as e:
            self._handle_google_api_error(e)
            return False

    def get_event(self, event_id: str) -> Optional[Dict[str, Any]]:
        """Get an event from the calendar provider."""
        try:
            self._ensure_valid_credentials()
            service = build('calendar', 'v3', credentials=self.credentials)
            event = service.events().get(calendarId='primary', eventId=event_id).execute()
            return event
        except Exception as e:
            self._handle_google_api_error(e)
            return None


