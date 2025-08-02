<<<<<<< HEAD
#!/usr/bin/env python3
"""
Script to create test availability slots for testing the booking system.
"""

from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.models import User, AvailabilitySlot
from app.services.user_service import get_user_by_scheduling_slug

async def create_test_slots():
    """Create test availability slots for the user."""
    
    # Get database session
    db = next(get_db())
    
    try:
        # Get the user by scheduling slug
        user = await get_user_by_scheduling_slug(db, "rahuldhanawade")
        if not user:
            print("User 'rahuldhanawade' not found!")
            return
        
        print(f"Found user: {user.full_name} (ID: {user.id})")
        
        # Create slots for next week (Monday to Friday)
        start_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Find next Monday
        while start_date.weekday() != 0:  # Monday is 0
            start_date += timedelta(days=1)
        
        print(f"Creating slots starting from: {start_date.strftime('%Y-%m-%d')}")
        
        # Create slots for each weekday
        for day_offset in range(5):  # Monday to Friday
            current_date = start_date + timedelta(days=day_offset)
            
            # Create slots from 9 AM to 5 PM (30-minute intervals)
            for hour in range(9, 17):  # 9 AM to 5 PM
                for minute in [0, 30]:  # 30-minute intervals
                    start_time = current_date.replace(hour=hour, minute=minute)
                    end_time = start_time + timedelta(minutes=30)
                    
                    # Check if slot already exists
                    existing_slot = db.query(AvailabilitySlot).filter(
                        AvailabilitySlot.user_id == user.id,
                        AvailabilitySlot.start_time == start_time,
                        AvailabilitySlot.end_time == end_time
                    ).first()
                    
                    if not existing_slot:
                        slot = AvailabilitySlot(
                            user_id=user.id,
                            start_time=start_time,
                            end_time=end_time,
                            is_available=True
                        )
                        db.add(slot)
                        print(f"Created slot: {start_time.strftime('%Y-%m-%d %I:%M %p')} - {end_time.strftime('%I:%M %p')}")
        
        db.commit()
        print(f"Successfully created test availability slots!")
        
        # Show created slots
        slots = db.query(AvailabilitySlot).filter(
            AvailabilitySlot.user_id == user.id,
            AvailabilitySlot.start_time >= start_date
        ).order_by(AvailabilitySlot.start_time).all()
        
        print(f"\nTotal slots created: {len(slots)}")
        print("Sample slots:")
        for slot in slots[:5]:
            print(f"  {slot.start_time.strftime('%Y-%m-%d %I:%M %p')} - {slot.end_time.strftime('%I:%M %p')}")
        
    except Exception as e:
        print(f"Error creating slots: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    import asyncio
    asyncio.run(create_test_slots()) 
=======
 
>>>>>>> e3b999cd02f578d5176e7dbc287d1a2a1f5f3840
