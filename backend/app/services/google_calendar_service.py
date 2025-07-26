import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


class GoogleCalendarService:
    def __init__(self, access_token: str = None, refresh_token: str = None):
        self.credentials = None
        if access_token and refresh_token:
            self.credentials = Credentials(
                token=access_token,
                refresh_token=refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=os.getenv("GOOGLE_CLIENT_ID"),
                client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
                scopes=["https://www.googleapis.com/auth/calendar.events"],
            )

    def get_authorization_url(self):
        flow = InstalledAppFlow.from_client_secrets_file(
            'client_secret.json', ["https://www.googleapis.com/auth/calendar.events"]
        )
        flow.redirect_uri = os.getenv("GOOGLE_REDIRECT_URI")
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true'
        )
        return authorization_url, state

    def get_tokens_from_auth_code(self, auth_code: str):
        flow = InstalledAppFlow.from_client_secrets_file(
            'client_secret.json', ["https://www.googleapis.com/auth/calendar.events"]
        )
        flow.redirect_uri = os.getenv("GOOGLE_REDIRECT_URI")
        flow.fetch_token(code=auth_code)
        self.credentials = flow.credentials
        return {
            "access_token": self.credentials.token,
            "refresh_token": self.credentials.refresh_token,
        }

    def get_events(self):
        if not self.credentials:
            raise Exception("Google credentials not set.")

        if not self.credentials.valid:
            if self.credentials.expired and self.credentials.refresh_token:
                self.credentials.refresh(Request())
            else:
                raise Exception("Google credentials expired and no refresh token available.")

        service = build('calendar', 'v3', credentials=self.credentials)
        events_result = service.events().list(calendarId='primary', maxResults=10).execute()
        events = events_result.get('items', [])
        return events
