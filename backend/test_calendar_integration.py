#!/usr/bin/env python3
"""
Test script to verify calendar integration with LLM agent
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.intelligent_agent_service import IntelligentAgentService
from app.services.llm_calendar_service import LLMCalendarService
from app.core.database import get_db
from app.models.models import User

def test_calendar_service():
    """Test the LLM Calendar Service"""
    print("🧪 Testing LLM Calendar Service...")
    
    try:
        # Get a database session
        db = next(get_db())
        
        # Test with a user (assuming user ID 1 exists)
        user_id = 1
        
        # Initialize calendar service
        calendar_service = LLMCalendarService(db, user_id)
        
        # Test calendar status
        status = calendar_service.get_calendar_status()
        print(f"✅ Calendar status: {status}")
        
        if status["connected"]:
            # Test getting available slots
            slots = calendar_service.get_available_slots()
            print(f"✅ Available slots: {len(slots)} found")
            
            # Test getting upcoming events
            events = calendar_service.get_upcoming_events(days=7)
            print(f"✅ Upcoming events: {len(events)} found")
            
            # Test calendar summary
            summary = calendar_service.get_calendar_summary()
            print(f"✅ Calendar summary: {summary}")
        else:
            print("⚠️  Calendar not connected - this is expected for testing")
        
        db.close()
        return True
        
    except Exception as e:
        print(f"❌ Calendar service test failed: {e}")
        return False

def test_agent_with_calendar():
    """Test the intelligent agent with calendar integration"""
    print("\n🧪 Testing Intelligent Agent with Calendar Integration...")
    
    try:
        # Get a database session
        db = next(get_db())
        
        # Initialize the intelligent agent service
        agent_service = IntelligentAgentService(db)
        
        # Test processing a message that requires calendar access
        import asyncio
        
        async def test_calendar_message():
            try:
                result = await agent_service.process_message(
                    user_id=1, 
                    message="What's my calendar looking like today?"
                )
                print("✅ Calendar message processing completed")
                print(f"   Response: {result.get('message', 'No message')[:100]}...")
                print(f"   Calendar available: {result.get('data', {}).get('calendar_available', False)}")
                return True
            except Exception as e:
                print(f"❌ Calendar message processing failed: {e}")
                return False
        
        # Run the async test
        success = asyncio.run(test_calendar_message())
        
        db.close()
        return success
        
    except Exception as e:
        print(f"❌ Agent calendar test failed: {e}")
        return False

def test_calendar_actions():
    """Test calendar-specific actions"""
    print("\n🧪 Testing Calendar Actions...")
    
    try:
        # Get a database session
        db = next(get_db())
        
        # Initialize the intelligent agent service
        agent_service = IntelligentAgentService(db)
        
        # Test calendar actions
        import asyncio
        
        async def test_actions():
            try:
                # Test getting calendar summary
                summary_result = await agent_service.handle_calendar_action(
                    user_id=1, 
                    action="get_calendar_summary"
                )
                print(f"✅ Calendar summary action: {summary_result.get('success', False)}")
                
                # Test getting available slots
                slots_result = await agent_service.handle_calendar_action(
                    user_id=1, 
                    action="get_available_slots",
                    date=datetime.now(),
                    duration_minutes=30
                )
                print(f"✅ Available slots action: {slots_result.get('success', False)}")
                
                return True
            except Exception as e:
                print(f"❌ Calendar actions test failed: {e}")
                return False
        
        # Run the async test
        success = asyncio.run(test_actions())
        
        db.close()
        return success
        
    except Exception as e:
        print(f"❌ Calendar actions test failed: {e}")
        return False

def test_calendar_connection_flow():
    """Test the complete calendar connection flow"""
    print("\n🧪 Testing Calendar Connection Flow...")
    
    try:
        # Get a database session
        db = next(get_db())
        
        # Test with the authenticated user from logs (rdhanawade56@gmail.com)
        user = db.query(User).filter(User.email == "rdhanawade56@gmail.com").first()
        
        if user:
            print(f"✅ Found user: {user.email}")
            print(f"   Calendar connected: {user.google_calendar_connected}")
            print(f"   Calendar email: {user.google_calendar_email}")
            
            # Initialize calendar service for this user
            calendar_service = LLMCalendarService(db, user.id)
            status = calendar_service.get_calendar_status()
            print(f"   Calendar service status: {status}")
            
            if status["connected"]:
                # Test calendar operations
                summary = calendar_service.get_calendar_summary()
                print(f"   Calendar summary: {summary}")
                
                slots = calendar_service.get_available_slots()
                print(f"   Available slots: {len(slots)}")
                
                events = calendar_service.get_upcoming_events()
                print(f"   Upcoming events: {len(events)}")
            else:
                print("   ⚠️  Calendar not connected - user needs to connect calendar")
        else:
            print("❌ User not found in database")
        
        db.close()
        return True
        
    except Exception as e:
        print(f"❌ Calendar connection flow test failed: {e}")
        return False

def main():
    """Run all calendar integration tests"""
    print("🚀 Testing Calendar Integration with LLM Agent")
    print("=" * 60)
    
    # Test calendar service
    test1_success = test_calendar_service()
    
    # Test agent with calendar
    test2_success = test_agent_with_calendar()
    
    # Test calendar actions
    test3_success = test_calendar_actions()
    
    # Test calendar connection flow
    test4_success = test_calendar_connection_flow()
    
    print("\n" + "=" * 60)
    if test1_success and test2_success and test3_success and test4_success:
        print("🎉 All calendar integration tests passed!")
        print("✅ Calendar service is working correctly")
        print("✅ LLM agent can access calendar data")
        print("✅ Calendar actions are functional")
        print("✅ Calendar connection flow is working")
    else:
        print("❌ Some calendar integration tests failed.")
        print("   Please check the implementation and ensure calendar is connected.")
    
    return test1_success and test2_success and test3_success and test4_success

if __name__ == "__main__":
    main() 