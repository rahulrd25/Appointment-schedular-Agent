#!/usr/bin/env python3
"""
Reset calendar connection and fix email mismatch issues
"""

import os
import sys
from pathlib import Path

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent))

from app.core.database import get_db
from app.models.models import User
from sqlalchemy.orm import Session

def reset_calendar_connection():
    """Reset calendar connection for all users"""
    print("🔄 Resetting Calendar Connections...")
    print("=" * 50)
    
    try:
        # Get a database session
        db = next(get_db())
        
        # Get all users
        users = db.query(User).all()
        
        for user in users:
            print(f"👤 Processing user: {user.email}")
            
            # Reset calendar connection
            user.google_calendar_connected = False
            user.google_calendar_email = None
            
            # Keep the OAuth tokens for re-authentication
            print(f"   ✅ Reset calendar connection for {user.email}")
        
        # Commit changes
        db.commit()
        print("\n✅ All calendar connections have been reset!")
        print("\n📋 Next Steps:")
        print("1. Start your application: uvicorn main:app --reload")
        print("2. Go to your dashboard")
        print("3. Click 'Connect Calendar'")
        print("4. Authenticate with ANY Google account you want to use for calendar")
        print("5. This can be different from your login account")
        print("6. The system will store calendar credentials separately")
        
        db.close()
        
    except Exception as e:
        print(f"❌ Reset failed: {e}")

if __name__ == "__main__":
    reset_calendar_connection() 