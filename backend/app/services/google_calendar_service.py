import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


class GoogleCalendarService:
    def __init__(self, access_token: str = None, refresh_token: str = None, db: Optional[Any] = None, user_id: Optional[int] = None):
        self.credentials = None
<<<<<<< HEAD
=======
        self.db = db
        self.user_id = user_id
>>>>>>> e3b999cd02f578d5176e7dbc287d1a2a1f5f3840
        if access_token:
            # Create credentials with available tokens
            # Note: refresh_token can be None for some OAuth flows
            self.credentials = Credentials(
                token=access_token,
                refresh_token=refresh_token,  # Can be None
                token_uri="https://oauth2.googleapis.com/token",
                client_id=os.getenv("GOOGLE_CLIENT_ID"),
                client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
<<<<<<< HEAD
                scopes=["https://www.googleapis.com/auth/calendar", "https://www.googleapis.com/auth/calendar.events", "https://www.googleapis.com/auth/calendar.readonly"],
=======
                scopes=[
                    "https://www.googleapis.com/auth/calendar",
                    "https://www.googleapis.com/auth/calendar.events",
                    "https://www.googleapis.com/auth/calendar.readonly"
                ],
>>>>>>> e3b999cd02f578d5176e7dbc287d1a2a1f5f3840
            )

    def get_authorization_url(self):
        flow = InstalledAppFlow.from_client_secrets_file(
<<<<<<< HEAD
            'client_secret.json', ["https://www.googleapis.com/auth/calendar", "https://www.googleapis.com/auth/calendar.events", "https://www.googleapis.com/auth/calendar.readonly"]
=======
            'client_secret.json', [
                "https://www.googleapis.com/auth/calendar",
                "https://www.googleapis.com/auth/calendar.events",
                "https://www.googleapis.com/auth/calendar.readonly"
            ]
>>>>>>> e3b999cd02f578d5176e7dbc287d1a2a1f5f3840
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
<<<<<<< HEAD
            'client_secret.json', ["https://www.googleapis.com/auth/calendar", "https://www.googleapis.com/auth/calendar.events", "https://www.googleapis.com/auth/calendar.readonly"]
=======
            'client_secret.json', [
                "https://www.googleapis.com/auth/calendar",
                "https://www.googleapis.com/auth/calendar.events",
                "https://www.googleapis.com/auth/calendar.readonly"
            ]
>>>>>>> e3b999cd02f578d5176e7dbc287d1a2a1f5f3840
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

<<<<<<< HEAD
=======
    def _handle_google_api_error(self, error):
        """Handle Google API errors."""
        raise Exception("Calendar access failed")


>>>>>>> e3b999cd02f578d5176e7dbc287d1a2a1f5f3840
    def get_events(self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None):
        """Get events from the calendar, optionally filtered by date range."""
        self._ensure_valid_credentials()
        service = build('calendar', 'v3', credentials=self.credentials)
        
        # Set default date range if not provided
        if not start_date:
            start_date = datetime.now(timezone.utc)
        if not end_date:
            end_date = start_date.replace(hour=23, minute=59, second=59)
        
        # Ensure datetime objects are timezone-aware
        if start_date.tzinfo is None:
            start_date = start_date.replace(tzinfo=timezone.utc)
        if end_date.tzinfo is None:
            end_date = end_date.replace(tzinfo=timezone.utc)
        
<<<<<<< HEAD
        events_result = service.events().list(
            calendarId='primary',
            timeMin=start_date.isoformat(),
            timeMax=end_date.isoformat(),
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        return events

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
=======
        try:
            events_result = service.events().list(
                calendarId='primary',
                timeMin=start_date.isoformat(),
                timeMax=end_date.isoformat(),
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            return events_result.get('items', [])
        except Exception as e:
            self._handle_google_api_error(e)

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
>>>>>>> e3b999cd02f578d5176e7dbc287d1a2a1f5f3840
        
        # Filter out events that are marked as 'transparent' (free time)
        conflicting_events = [
            event for event in events 
            if event.get('transparency', 'opaque') != 'transparent'
        ]
        
        return len(conflicting_events) == 0

<<<<<<< HEAD
    def get_available_slots(self, date: datetime, duration_minutes: int = 30) -> list:
=======
    def get_available_slots(self, date, duration_minutes: int = 30) -> list:
>>>>>>> e3b999cd02f578d5176e7dbc287d1a2a1f5f3840
        """Get available time slots for a given date."""
        self._ensure_valid_credentials()
        service = build('calendar', 'v3', credentials=self.credentials)
        
        # Define business hours (9 AM to 5 PM)
        start_hour = 9
        end_hour = 17
        
        # Ensure date is timezone-aware (UTC)
<<<<<<< HEAD
        if date.tzinfo is None:
            date = date.replace(tzinfo=timezone.utc)
=======
        # Convert date to datetime if it's a date object
        if hasattr(date, 'date'):  # It's a datetime object
            if date.tzinfo is None:
                date = date.replace(tzinfo=timezone.utc)
        else:  # It's a date object, convert to datetime
            date = datetime.combine(date, datetime.min.time()).replace(tzinfo=timezone.utc)
>>>>>>> e3b999cd02f578d5176e7dbc287d1a2a1f5f3840
        
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

<<<<<<< HEAD
    def create_event(
=======
    def create_event(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a calendar event with the provided event data."""
        self._ensure_valid_credentials()
        
        service = build('calendar', 'v3', credentials=self.credentials)
        
        try:
            created_event = service.events().insert(calendarId='primary', body=event_data, sendUpdates='none').execute()
            return created_event
        except Exception as e:
            self._handle_google_api_error(e)

    def create_booking_event(
>>>>>>> e3b999cd02f578d5176e7dbc287d1a2a1f5f3840
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
        
<<<<<<< HEAD
        created_event = service.events().insert(calendarId='primary', body=event, sendUpdates='all').execute()
        return created_event
=======
        try:
            created_event = service.events().insert(calendarId='primary', body=event, sendUpdates='all').execute()
            return created_event
        except Exception as e:
            self._handle_google_api_error(e)
>>>>>>> e3b999cd02f578d5176e7dbc287d1a2a1f5f3840

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
<<<<<<< HEAD
        self._ensure_valid_credentials()
        
        service = build('calendar', 'v3', credentials=self.credentials)
        
        # Get the existing event
        event = service.events().get(calendarId='primary', eventId=event_id).execute()
        
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
        if end_time:
            # Ensure datetime object is timezone-aware
            if end_time.tzinfo is None:
                end_time = end_time.replace(tzinfo=timezone.utc)
            event['end'] = {
                'dateTime': end_time.isoformat(),
                'timeZone': 'UTC',
            }
        
        updated_event = service.events().update(
            calendarId='primary', 
            eventId=event_id, 
            body=event,
            sendUpdates='all'
        ).execute()
        return updated_event
=======
        try:
            print(f"Updating event: {event_id}")
            self._ensure_valid_credentials()
            
            service = build('calendar', 'v3', credentials=self.credentials)
            
            # Get the existing event
            print(f"Getting existing event: {event_id}")
            event = service.events().get(calendarId='primary', eventId=event_id).execute()
            print(f"Retrieved existing event")
            
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
                print(f"Updated start time: {start_time.isoformat()}")
            if end_time:
                # Ensure datetime object is timezone-aware
                if end_time.tzinfo is None:
                    end_time = end_time.replace(tzinfo=timezone.utc)
                event['end'] = {
                    'dateTime': end_time.isoformat(),
                    'timeZone': 'UTC',
                }
                print(f"Updated end time: {end_time.isoformat()}")
            
            print(f"Updating event in calendar...")
            updated_event = service.events().update(
                calendarId='primary', 
                eventId=event_id, 
                body=event,
                sendUpdates='all'
            ).execute()
            print(f"Successfully updated event: {event_id}")
            return updated_event
            
        except Exception as e:
            print(f"Error updating event {event_id}: {e}")
            print(f"Error type: {type(e)}")
            import traceback
            print(f"Full traceback: {traceback.format_exc()}")
            raise
>>>>>>> e3b999cd02f578d5176e7dbc287d1a2a1f5f3840

    def delete_event(self, event_id: str) -> bool:
        """Delete a calendar event."""
        try:
            self._ensure_valid_credentials()
            service = build('calendar', 'v3', credentials=self.credentials)
            service.events().delete(calendarId='primary', eventId=event_id, sendUpdates='all').execute()
            return True
        except Exception as e:
            print(f"Error deleting event: {e}")
<<<<<<< HEAD
=======
            self._handle_google_api_error(e)
>>>>>>> e3b999cd02f578d5176e7dbc287d1a2a1f5f3840
            return False

    def get_event(self, event_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific calendar event."""
        try:
<<<<<<< HEAD
            self._ensure_valid_credentials()
            service = build('calendar', 'v3', credentials=self.credentials)
            event = service.events().get(calendarId='primary', eventId=event_id).execute()
            return event
        except Exception as e:
            print(f"Error getting event: {e}")
            return None
=======
            print(f"Getting event: {event_id}")
            self._ensure_valid_credentials()
            service = build('calendar', 'v3', credentials=self.credentials)
            event = service.events().get(calendarId='primary', eventId=event_id).execute()
            print(f"Successfully retrieved event: {event_id}")
            return event
        except Exception as e:
            print(f"Error getting event {event_id}: {e}")
            print(f"Error type: {type(e)}")
            self._handle_google_api_error(e)
            return None


>>>>>>> e3b999cd02f578d5176e7dbc287d1a2a1f5f3840
