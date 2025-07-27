from app.core.database import SessionLocal
from app.models.models import User

def reset_google_auth():
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.scheduling_slug == 'rahuldhanawade').first()
        if not user:
            print("User not found")
            return
            
        print(f"User found: {user.email}")
        print("Current tokens have insufficient scopes for reading calendar events.")
        print("Clearing old tokens...")
        
        # Clear the old tokens
        user.google_access_token = None
        user.google_refresh_token = None
        db.commit()
        
        print("\n" + "="*60)
        print("GOOGLE CALENDAR RE-AUTHENTICATION REQUIRED")
        print("="*60)
        print("Please visit this URL to re-authenticate with proper calendar permissions:")
        print(f"\nhttp://localhost:8000/auth/google/calendar")
        print(f"\nAfter authorization, you'll be redirected back to the dashboard.")
        print("Then try the public booking page again.")
        print("\n" + "="*60)
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    reset_google_auth() 