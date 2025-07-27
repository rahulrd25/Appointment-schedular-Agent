#!/usr/bin/env python3
"""
Debug script to check calendar connection status
"""

import os
import sys
from pathlib import Path

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent))

from app.core.database import get_db
from app.models.models import User
from app.services.llm_calendar_service import LLMCalendarService

def debug_calendar_connection():
    """Debug the calendar connection issue"""
    print("🔍 Debugging Calendar Connection...")
    print("=" * 50)
    
    try:
        # Get a database session
        db = next(get_db())
        
        # Check all users and their calendar status
        users = db.query(User).all()
        
        print(f"📊 Found {len(users)} users in database:")
        print()
        
        for user in users:
            print(f"👤 User ID: {user.id}")
            print(f"   Email: {user.email}")
            print(f"   Calendar Connected: {user.google_calendar_connected}")
            print(f"   Calendar Email: {user.google_calendar_email}")
            print(f"   Google ID: {user.google_id}")
            print(f"   Has Access Token: {bool(user.google_access_token)}")
            print(f"   Has Refresh Token: {bool(user.google_refresh_token)}")
            
            # Test calendar service for this user
            try:
                calendar_service = LLMCalendarService(db, user.id)
                status = calendar_service.get_calendar_status()
                print(f"   Calendar Service Status: {status}")
            except Exception as e:
                print(f"   Calendar Service Error: {e}")
            
            print("-" * 40)
        
        # Check specifically for the logged-in user
        current_user_email = "rdhanawade56@gmail.com"
        current_user = db.query(User).filter(User.email == current_user_email).first()
        
        if current_user:
            print(f"\n🎯 Current User Analysis ({current_user_email}):")
            print(f"   User ID: {current_user.id}")
            print(f"   Calendar Connected: {current_user.google_calendar_connected}")
            print(f"   Calendar Email: {current_user.google_calendar_email}")
            
            if current_user.google_calendar_connected and current_user.google_calendar_email != current_user_email:
                print(f"   ⚠️  EMAIL MISMATCH DETECTED!")
                print(f"      Logged in as: {current_user_email}")
                print(f"      Calendar connected to: {current_user.google_calendar_email}")
                print(f"      This is why calendar access is failing.")
                
                # Check if the calendar email user exists
                calendar_user = db.query(User).filter(User.email == current_user.google_calendar_email).first()
                if calendar_user:
                    print(f"   ✅ Calendar email user exists in database")
                    print(f"      Calendar user ID: {calendar_user.id}")
                    print(f"      Calendar user has tokens: {bool(calendar_user.google_access_token)}")
                else:
                    print(f"   ❌ Calendar email user NOT found in database")
            
            # Test calendar service
            calendar_service = LLMCalendarService(db, current_user.id)
            status = calendar_service.get_calendar_status()
            print(f"   Calendar Service Status: {status}")
            
            if status.get("action_required") == "refresh_credentials":
                print(f"   🔄 CREDENTIALS NEED REFRESH")
                print(f"      The Google OAuth tokens may have expired.")
                print(f"      Solution: Re-authenticate with Google")
        
        db.close()
        
    except Exception as e:
        print(f"❌ Debug failed: {e}")

def suggest_solutions():
    """Suggest solutions for the calendar connection issue"""
    print("\n💡 Suggested Solutions:")
    print("=" * 50)
    
    print("1. 🔄 Re-authenticate with Google Calendar:")
    print("   - Go to your dashboard")
    print("   - Click 'Connect Calendar' or 'Reconnect Calendar'")
    print("   - This will refresh your Google OAuth tokens")
    
    print("\n2. 🔗 Use the same Google account:")
    print("   - Make sure you're logged in with the same Google account")
    print("   - That has the calendar you want to connect")
    
    print("\n3. 🧹 Clear and reconnect:")
    print("   - Disconnect the current calendar connection")
    print("   - Reconnect with the correct Google account")
    
    print("\n4. 🔍 Check Google Calendar permissions:")
    print("   - Ensure the Google account has calendar access")
    print("   - Check if calendar sharing is enabled")

if __name__ == "__main__":
    debug_calendar_connection()
    suggest_solutions() 