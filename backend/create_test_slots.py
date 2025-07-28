#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime, timedelta
from app.core.database import SessionLocal
from app.models.models import AvailabilitySlot, User

def create_test_slots():
    db = SessionLocal()
    
    try:
        # Get the first user (or create one if needed)
        user = db.query(User).first()
        if not user:
            print("No users found in database. Please create a user first.")
            return
        
        print(f"Creating test slots for user: {user.email}")
        
        # Create slots for the next 7 days
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        for i in range(7):
            date = today + timedelta(days=i)
            
            # Create slots from 9 AM to 5 PM, every 30 minutes
            for hour in range(9, 17):
                for minute in [0, 30]:
                    start_time = date.replace(hour=hour, minute=minute)
                    end_time = start_time + timedelta(minutes=30)
                    
                    # Check if slot already exists
                    existing = db.query(AvailabilitySlot).filter(
                        AvailabilitySlot.user_id == user.id,
                        AvailabilitySlot.start_time == start_time
                    ).first()
                    
                    if not existing:
                        slot = AvailabilitySlot(
                            user_id=user.id,
                            start_time=start_time,
                            end_time=end_time,
                            is_available=True
                        )
                        db.add(slot)
                        print(f"Created slot: {start_time.strftime('%Y-%m-%d %H:%M')} - {end_time.strftime('%H:%M')}")
        
        db.commit()
        print("Test slots created successfully!")
        
    except Exception as e:
        print(f"Error creating test slots: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    create_test_slots() 