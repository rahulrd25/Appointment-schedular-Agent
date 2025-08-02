import os
import requests
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.models import User


class TokenRefreshService:
    """Service to handle automatic Google OAuth token refresh."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def refresh_user_tokens(self, user: User) -> Dict[str, Any]:
        """Refresh Google OAuth tokens for a user."""
        try:
            if not user.google_refresh_token:
                return {
                    "success": False,
                    "message": "No refresh token available",
                    "requires_reconnection": True
                }
            
            # Prepare token refresh request
            token_url = "https://oauth2.googleapis.com/token"
            token_data = {
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "refresh_token": user.google_refresh_token,
                "grant_type": "refresh_token",
            }
            headers = {"Content-Type": "application/x-www-form-urlencoded"}
            
            # Make the refresh request
            response = requests.post(token_url, data=token_data, headers=headers)
            response.raise_for_status()
            
            tokens = response.json()
            new_access_token = tokens.get("access_token")
            new_refresh_token = tokens.get("refresh_token")  # May not be present
            
            if not new_access_token:
                return {
                    "success": False,
                    "message": "No access token in refresh response",
                    "requires_reconnection": True
                }
            
            # Update user tokens
            user.google_access_token = new_access_token
            if new_refresh_token:
                user.google_refresh_token = new_refresh_token
            
            self.db.commit()
            
            return {
                "success": True,
                "message": "Tokens refreshed successfully",
                "access_token": new_access_token,
                "refresh_token": new_refresh_token
            }
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 400:
                # Invalid refresh token - user needs to reconnect
                return {
                    "success": False,
                    "message": "Invalid refresh token - reconnection required",
                    "requires_reconnection": True
                }
            else:
                return {
                    "success": False,
                    "message": f"Token refresh failed: {str(e)}",
                    "requires_reconnection": False
                }
        except Exception as e:
            return {
                "success": False,
                "message": f"Token refresh error: {str(e)}",
                "requires_reconnection": False
            }
    
    def ensure_valid_tokens(self, user: User) -> Dict[str, Any]:
        """Ensure user has valid tokens, refresh if needed."""
        try:
            # Check if we have the minimum required tokens
            if not user.google_access_token:
                return {
                    "success": False,
                    "message": "No access token available",
                    "requires_reconnection": True
                }
            
            # Test the current access token by making a simple API call
            test_url = "https://www.googleapis.com/oauth2/v2/userinfo"
            headers = {"Authorization": f"Bearer {user.google_access_token}"}
            
            response = requests.get(test_url, headers=headers)
            
            if response.status_code == 200:
                # Token is still valid
                return {
                    "success": True,
                    "message": "Tokens are valid",
                    "access_token": user.google_access_token,
                    "refresh_token": user.google_refresh_token
                }
            elif response.status_code == 401:
                # Token is expired, try to refresh
                if user.google_refresh_token:
                    return self.refresh_user_tokens(user)
                else:
                    return {
                        "success": False,
                        "message": "Token expired and no refresh token available",
                        "requires_reconnection": True
                    }
            else:
                return {
                    "success": False,
                    "message": f"Token validation failed: {response.status_code}",
                    "requires_reconnection": True
                }
                
        except Exception as e:
            return {
                "success": False,
                "message": f"Token validation error: {str(e)}",
                "requires_reconnection": False
            }
    
    def get_user_by_scheduling_slug(self, scheduling_slug: str) -> Optional[User]:
        """Get user by scheduling slug."""
        return self.db.query(User).filter(User.scheduling_slug == scheduling_slug).first()
    
    def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        return self.db.query(User).filter(User.email == email).first()


def get_token_refresh_service(db: Session) -> TokenRefreshService:
    """Get a token refresh service instance."""
    return TokenRefreshService(db) 