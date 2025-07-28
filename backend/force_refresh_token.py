from app.core.database import SessionLocal
from app.models.models import User

def force_refresh_token():
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.scheduling_slug == 'rahuldhanawade').first()
        if not user:
            print("User not found")
            return
            
        print(f"User: {user.email}")
        print(f"Calendar email: {getattr(user, 'google_calendar_email', 'Not set')}")
        print("Current tokens don't have refresh token - clearing and re-authenticating...")
        
        # Clear the current tokens
        user.google_access_token = None
        user.google_refresh_token = None
        user.google_calendar_connected = False
        user.google_calendar_email = None
        db.commit()
        
        print("\n" + "="*60)
        print("CALENDAR RE-AUTHENTICATION REQUIRED")
        print("="*60)
        print("Please visit this URL to re-authenticate with refresh token:")
        print(f"\nhttp://localhost:8000/auth/google/calendar")
        print(f"\nThis will force Google to provide a refresh token.")
        print("After authorization, complete the connection in the dashboard.")
        print("\n" + "="*60)
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    force_refresh_token() 