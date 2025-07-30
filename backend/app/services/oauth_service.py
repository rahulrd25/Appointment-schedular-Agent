import os
import requests
from typing import Dict, Any, Optional
from datetime import datetime

from app.core.config import settings


class GoogleOAuthService:
    """Service to handle Google OAuth flows with proper scopes."""
    
    def __init__(self):
        self.client_id = settings.GOOGLE_CLIENT_ID
        self.client_secret = settings.GOOGLE_CLIENT_SECRET
        self.redirect_uri = settings.GOOGLE_REDIRECT_URI
    
    def get_authorization_url(self, include_calendar_scopes: bool = True, state: str = None) -> str:
        """Get Google OAuth authorization URL with appropriate scopes."""
        
        # Base scopes for user authentication
        scopes = ["openid", "email", "profile"]
        
        # Add calendar scopes if requested
        if include_calendar_scopes:
            scopes.extend([
                "https://www.googleapis.com/auth/calendar",
                "https://www.googleapis.com/auth/calendar.events", 
                "https://www.googleapis.com/auth/calendar.readonly",
                "https://www.googleapis.com/auth/gmail.send"
            ])
        
        # Build authorization URL
        auth_url = (
            "https://accounts.google.com/o/oauth2/v2/auth?"
            f"client_id={self.client_id}&"
            "response_type=code&"
            f"scope={' '.join(scopes)}&"
            f"redirect_uri={self.redirect_uri}&"
            "access_type=offline&"
            "prompt=consent"
        )
        
        # Add state parameter if provided
        if state:
            auth_url += f"&state={state}"
        
        return auth_url
    
    def exchange_code_for_tokens(self, auth_code: str) -> Dict[str, Any]:
        """Exchange authorization code for access and refresh tokens."""
        
        token_url = "https://oauth2.googleapis.com/token"
        token_data = {
            "code": auth_code,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": self.redirect_uri,
            "grant_type": "authorization_code",
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        
        response = requests.post(token_url, data=token_data, headers=headers)
        response.raise_for_status()
        
        tokens = response.json()
        return {
            "access_token": tokens.get("access_token"),
            "refresh_token": tokens.get("refresh_token"),
            "scope": tokens.get("scope", ""),
            "expires_in": tokens.get("expires_in")
        }
    
    def get_user_info(self, access_token: str) -> Dict[str, Any]:
        """Get user information from Google using access token."""
        
        user_info_url = "https://www.googleapis.com/oauth2/v2/userinfo"
        headers = {"Authorization": f"Bearer {access_token}"}
        
        response = requests.get(user_info_url, headers=headers)
        response.raise_for_status()
        
        return response.json()
    
    def validate_calendar_scopes(self, scope: str) -> bool:
        """Check if the received scope includes calendar permissions."""
        required_scopes = [
            "https://www.googleapis.com/auth/calendar",
            "https://www.googleapis.com/auth/calendar.events",
            "https://www.googleapis.com/auth/calendar.readonly"
        ]
        
        scope_list = scope.split()
        return all(required_scope in scope_list for required_scope in required_scopes)


def get_oauth_service() -> GoogleOAuthService:
    """Get OAuth service instance."""
    return GoogleOAuthService() 