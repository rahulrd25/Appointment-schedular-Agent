from app.core.database import SessionLocal
from app.models.models import User
from app.services.google_calendar_service import GoogleCalendarService

def test_calendar_access():
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.scheduling_slug == 'rahuldhanawade').first()
        if not user:
            print("User not found")
            return
            
        print(f"User found: {user.email}")
        print(f"Has access token: {user.google_access_token is not None}")
        print(f"Has refresh token: {user.google_refresh_token is not None}")
        
        service = GoogleCalendarService(user.google_access_token, user.google_refresh_token)
        print("Testing calendar access...")
        
        try:
            events = service.get_events()
            print(f"Success! Can read calendar events. Found {len(events)} events")
        except Exception as e:
            print(f"Error reading calendar: {e}")
            
    finally:
        db.close()

if __name__ == "__main__":
    test_calendar_access() 