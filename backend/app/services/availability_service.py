from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.models import AvailabilitySlot, User, Booking
from app.schemas.schemas import AvailabilitySlotCreate, AvailabilitySlotUpdate


<<<<<<< HEAD
def create_availability_slot(db: Session, slot: AvailabilitySlotCreate, user_id: int) -> AvailabilitySlot:
    """Create a new availability slot for a user."""
    db_slot = AvailabilitySlot(
        user_id=user_id,
        start_time=slot.start_time,
        end_time=slot.end_time,
        is_available=slot.is_available
    )
    db.add(db_slot)
    db.commit()
    db.refresh(db_slot)
    return db_slot
=======
def create_availability_slot(db: Session, slot: AvailabilitySlotCreate, user_id: int) -> dict:
    """Create a new availability slot for a user."""
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return {
                "success": False,
                "message": "User not found",
                "slot": None,
                "calendar_created": False,
                "calendar_error": None,
                "google_event_id": None
            }
        
        # Check if user has Google Calendar connected
        if user.google_calendar_connected and user.google_access_token and user.google_refresh_token:
            try:
                # Test calendar connection first
                from app.services.google_calendar_service import GoogleCalendarService
                calendar_service = GoogleCalendarService(
                    access_token=user.google_access_token,
                    refresh_token=user.google_refresh_token,
                    db=db,
                    user_id=user_id
                )
                
                # Test calendar connection first
                calendar_service.get_events()
                print(f"✅ Calendar connection test successful for {user.email}")
                
            except Exception as e:
                print(f"Calendar connection test failed: {e}")
                return {
                    "success": False,
                    "message": "Couldn't add slot. Please reconnect your calendar in Settings.",
                    "slot": None,
                    "calendar_created": False,
                    "calendar_error": str(e),
                    "google_event_id": None
                }
        
        # Only create slot in database if calendar conditions are met
        db_slot = AvailabilitySlot(
            user_id=user_id,
            start_time=slot.start_time,
            end_time=slot.end_time,
            is_available=slot.is_available
        )
        db.add(db_slot)
        db.commit()
        db.refresh(db_slot)
        
        calendar_created = None
        calendar_error = None
        google_event_id = None
        
        # Create Google Calendar event if user has connected calendar
        if user.google_calendar_connected and user.google_access_token and user.google_refresh_token:
            try:
                # Create event in Google Calendar
                event_data = {
                    'summary': 'Available for Booking',
                    'description': 'Time slot available for appointments',
                    'start': {
                        'dateTime': slot.start_time.isoformat(),
                        'timeZone': 'UTC'
                    },
                    'end': {
                        'dateTime': slot.end_time.isoformat(),
                        'timeZone': 'UTC'
                    },
                    'transparency': 'opaque',  # Mark as busy
                    'reminders': {
                        'useDefault': False,
                        'overrides': []
                    }
                }
                
                created_event = calendar_service.create_event(event_data)
                google_event_id = created_event.get('id')
                
                # Update the slot with Google Calendar event ID
                db_slot.google_event_id = google_event_id
                db.commit()
                
                calendar_created = True
                
            except Exception as e:
                print(f"Failed to create Google Calendar event: {e}")
                # If calendar creation fails, rollback the database slot creation
                db.rollback()
                return {
                    "success": False,
                    "message": "Couldn't add slot. Google Calendar error.",
                    "slot": None,
                    "calendar_created": False,
                    "calendar_error": str(e),
                    "google_event_id": None
                }
        
        return {
            "success": True,
            "message": "Availability slot created successfully",
            "slot": db_slot,
            "calendar_created": calendar_created,
            "calendar_error": calendar_error,
            "google_event_id": google_event_id
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": f"Failed to create availability slot: {str(e)}",
            "slot": None,
            "calendar_created": False,
            "calendar_error": str(e),
            "google_event_id": None
        }
>>>>>>> e3b999cd02f578d5176e7dbc287d1a2a1f5f3840


def get_availability_slots_for_user(db: Session, user_id: int, include_unavailable: bool = False) -> List[AvailabilitySlot]:
    """Get all availability slots for a user."""
    query = db.query(AvailabilitySlot).filter(AvailabilitySlot.user_id == user_id)
    
    if not include_unavailable:
        query = query.filter(AvailabilitySlot.is_available == True)
    
    return query.order_by(AvailabilitySlot.start_time).all()


def get_available_slots_for_booking(db: Session, user_id: int, from_date: datetime = None) -> List[AvailabilitySlot]:
    """Get available slots that can be booked (not already booked and in the future)."""
    now = datetime.utcnow()
    start_filter = from_date if from_date and from_date > now else now
    
    # Get availability slots that are:
    # 1. Available
    # 2. In the future
    # 3. Not fully booked
    query = db.query(AvailabilitySlot).filter(
        and_(
            AvailabilitySlot.user_id == user_id,
            AvailabilitySlot.is_available == True,
            AvailabilitySlot.start_time > start_filter
        )
    )
    
    # Filter out slots that already have confirmed bookings
    available_slots = []
    for slot in query.all():
        existing_booking = db.query(Booking).filter(
            and_(
                Booking.availability_slot_id == slot.id,
                Booking.status == "confirmed"
            )
        ).first()
        
        if not existing_booking:
            available_slots.append(slot)
    
    return sorted(available_slots, key=lambda x: x.start_time)


def get_availability_slot(db: Session, slot_id: int, user_id: int = None) -> Optional[AvailabilitySlot]:
    """Get a specific availability slot."""
    query = db.query(AvailabilitySlot).filter(AvailabilitySlot.id == slot_id)
    
    if user_id:
        query = query.filter(AvailabilitySlot.user_id == user_id)
    
    return query.first()


def update_availability_slot(db: Session, slot_id: int, slot_update: AvailabilitySlotUpdate, user_id: int) -> Optional[AvailabilitySlot]:
    """Update an availability slot."""
    slot = get_availability_slot(db, slot_id, user_id)
    if not slot:
        return None
    
    update_data = slot_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(slot, key, value)
    
    db.commit()
    db.refresh(slot)
    return slot


<<<<<<< HEAD
def delete_availability_slot(db: Session, slot_id: int, user_id: int) -> bool:
    """Delete an availability slot."""
    slot = get_availability_slot(db, slot_id, user_id)
    if not slot:
        return False
=======
def delete_availability_slot(db: Session, slot_id: int, user_id: int) -> dict:
    """Delete an availability slot and its Google Calendar event if linked."""
    slot = get_availability_slot(db, slot_id, user_id)
    if not slot:
        return {"success": False, "message": "Slot not found"}
>>>>>>> e3b999cd02f578d5176e7dbc287d1a2a1f5f3840
    
    # Check if there are any confirmed bookings for this slot
    existing_booking = db.query(Booking).filter(
        and_(
<<<<<<< HEAD
            Booking.availability_slot_id == slot_id,
=======
            Booking.availability_slot_id == slot.id,
>>>>>>> e3b999cd02f578d5176e7dbc287d1a2a1f5f3840
            Booking.status == "confirmed"
        )
    ).first()
    
    if existing_booking:
<<<<<<< HEAD
        # Don't delete slots with confirmed bookings, just mark as unavailable
        slot.is_available = False
        db.commit()
        return True
    
    db.delete(slot)
    db.commit()
    return True
=======
        return {"success": False, "message": "Cannot delete slot with confirmed bookings"}
    
    calendar_deleted = None
    calendar_error = None
    
    # If slot is linked to a Google Calendar event, delete it from Google Calendar
    if slot.google_event_id:
        user = db.query(User).filter(User.id == slot.user_id).first()
        if user and user.google_access_token and user.google_refresh_token:
            from app.services.google_calendar_service import GoogleCalendarService
            calendar_service = GoogleCalendarService(
                access_token=user.google_access_token,
                refresh_token=user.google_refresh_token,
                db=db,
                user_id=user.id
            )
            try:
                calendar_service.delete_event(slot.google_event_id)
                calendar_deleted = True
            except Exception as e:
                print(f"Failed to delete Google Calendar event: {e}")
                calendar_deleted = False
                calendar_error = str(e)
        else:
            calendar_deleted = False
            calendar_error = "Google Calendar not connected"
    else:
        # No Google Calendar event associated
        calendar_deleted = None
    
    # Delete from database
    db.delete(slot)
    db.commit()
    
    return {
        "success": True,
        "message": "Availability slot deleted successfully",
        "calendar_deleted": calendar_deleted,
        "calendar_error": calendar_error
    }
>>>>>>> e3b999cd02f578d5176e7dbc287d1a2a1f5f3840


def check_slot_availability(db: Session, slot_id: int) -> bool:
    """Check if a slot is available for booking."""
    slot = get_availability_slot(db, slot_id)
    if not slot or not slot.is_available:
        return False
    
<<<<<<< HEAD
    # Check if slot is in the future - ensure timezone-naive comparison
    slot_start_naive = slot.start_time.replace(tzinfo=None) if slot.start_time.tzinfo else slot.start_time
    if slot_start_naive <= datetime.utcnow():
=======
    # Check if slot is in the future - ensure timezone-aware comparison
    if slot.start_time <= datetime.now(timezone.utc):
>>>>>>> e3b999cd02f578d5176e7dbc287d1a2a1f5f3840
        return False
    
    # Check if slot is already booked
    existing_booking = db.query(Booking).filter(
        and_(
            Booking.availability_slot_id == slot_id,
            Booking.status == "confirmed"
        )
    ).first()
    
    return existing_booking is None


def create_availability_slots_from_calendar(db: Session, user: User, start_date: datetime, end_date: datetime) -> List[AvailabilitySlot]:
    """Create availability slots based on Google Calendar availability."""
    from app.services.google_calendar_service import GoogleCalendarService
    
    if not user.google_calendar_connected:
        raise Exception("User's Google Calendar is not connected")
    
    # Initialize Google Calendar service
    calendar_service = GoogleCalendarService(
        access_token=user.google_access_token,
<<<<<<< HEAD
        refresh_token=user.google_refresh_token
=======
        refresh_token=user.google_refresh_token,
        db=db,
        user_id=user.id
>>>>>>> e3b999cd02f578d5176e7dbc287d1a2a1f5f3840
    )
    
    created_slots = []
    current_date = start_date.date()
    end_date_obj = end_date.date()
    
    while current_date <= end_date_obj:
        # Get available slots for this date from Google Calendar
        # Create timezone-aware datetime for the date
        date_dt = datetime.combine(current_date, datetime.min.time()).replace(tzinfo=timezone.utc)
        available_slots = calendar_service.get_available_slots(date_dt)
        
        # Create availability slots for each available time
        for slot_data in available_slots:
            # Convert timezone-aware datetimes to naive for database storage
            start_time_naive = slot_data['start_time'].replace(tzinfo=None)
            end_time_naive = slot_data['end_time'].replace(tzinfo=None)
<<<<<<< HEAD
=======
            google_event_id = slot_data.get('event_id')  # Save event ID if present
>>>>>>> e3b999cd02f578d5176e7dbc287d1a2a1f5f3840
            
            # Check if this slot already exists
            existing_slot = db.query(AvailabilitySlot).filter(
                and_(
                    AvailabilitySlot.user_id == user.id,
                    AvailabilitySlot.start_time == start_time_naive,
                    AvailabilitySlot.end_time == end_time_naive
                )
            ).first()
            
            if not existing_slot:
                db_slot = AvailabilitySlot(
                    user_id=user.id,
                    start_time=start_time_naive,
                    end_time=end_time_naive,
<<<<<<< HEAD
                    is_available=True
=======
                    is_available=True,
                    google_event_id=google_event_id
>>>>>>> e3b999cd02f578d5176e7dbc287d1a2a1f5f3840
                )
                db.add(db_slot)
                created_slots.append(db_slot)
        
        current_date += timedelta(days=1)
    
    db.commit()
    return created_slots


<<<<<<< HEAD
def sync_calendar_availability(db: Session, user: User) -> dict:
    """Initialize calendar sync - this now just validates the connection."""
    if not user.google_calendar_connected:
        return {"success": False, "message": "Google Calendar not connected"}
    
    try:
        # Test the calendar connection by getting events
        from app.services.google_calendar_service import GoogleCalendarService
        calendar_service = GoogleCalendarService(
            access_token=user.google_access_token,
            refresh_token=user.google_refresh_token
        )
        
        # Try to get events to verify connection
        events = calendar_service.get_events()
        
        return {
            "success": True,
            "message": f"Calendar connected successfully! Found {len(events)} events in your calendar.",
            "events_found": len(events)
        }
    except Exception as e:
        return {"success": False, "message": f"Failed to connect to calendar: {str(e)}"}
=======
def check_calendar_connection(db: Session, user: User) -> dict:
    """Simple check if calendar is connected - no token refresh."""
    if not user.google_calendar_connected:
        return {"success": False, "message": "Google Calendar not connected"}
    
    if not user.google_access_token:
        return {"success": False, "message": "No access token available"}
    
    return {
        "success": True,
        "message": "Google Calendar connected",
        "connected": True
    }
>>>>>>> e3b999cd02f578d5176e7dbc287d1a2a1f5f3840


class AvailabilityService:
    """Service class for availability operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_user_availability_slots(self, user_id: int, date: Optional[datetime] = None, duration_minutes: int = 30) -> List[Dict[str, Any]]:
        """Get availability slots for a user, optionally filtered by date"""
        slots = get_availability_slots_for_user(self.db, user_id)
        
        if date:
            # Filter by date - ensure timezone-naive comparison
            date_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
            date_end = date.replace(hour=23, minute=59, second=59, microsecond=999999)
            
            # Convert slots to timezone-naive for comparison
            filtered_slots = []
            for slot in slots:
                # Make slot times timezone-naive for comparison
                slot_start = slot.start_time.replace(tzinfo=None) if slot.start_time.tzinfo else slot.start_time
                if date_start <= slot_start <= date_end:
                    filtered_slots.append(slot)
            slots = filtered_slots
        
        # Convert to dictionary format
        result = []
        for slot in slots:
            # Ensure timezone-naive datetime for JSON serialization
            start_time = slot.start_time.replace(tzinfo=None) if slot.start_time.tzinfo else slot.start_time
            end_time = slot.end_time.replace(tzinfo=None) if slot.end_time.tzinfo else slot.end_time
            
            result.append({
                "id": slot.id,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_minutes": int((end_time - start_time).total_seconds() / 60),
                "is_available": slot.is_available
            })
        
        return result
    
    def check_slot_availability(self, user_id: int, start_time: datetime, end_time: datetime) -> bool:
        """Check if a specific time slot is available for a user"""
        # Check if there's an availability slot that covers this time
        overlapping_slots = self.db.query(AvailabilitySlot).filter(
            and_(
                AvailabilitySlot.user_id == user_id,
                AvailabilitySlot.is_available == True,
                AvailabilitySlot.start_time <= start_time,
                AvailabilitySlot.end_time >= end_time
            )
        ).all()
        
        if not overlapping_slots:
            return False
        
        # Check if any of these slots are already booked
        for slot in overlapping_slots:
            existing_booking = self.db.query(Booking).filter(
                and_(
                    Booking.availability_slot_id == slot.id,
                    Booking.status == "confirmed"
                )
            ).first()
            
            if existing_booking:
                return False
        
        return True
    
    def create_booking_from_calendar(self, user_id: int, title: str, start_time: datetime, 
                                   end_time: datetime, guest_email: str, guest_name: str,
                                   description: str = None, google_event_id: str = None) -> Dict[str, Any]:
        """Create a booking from calendar event"""
        try:
            # Create or find an availability slot
            slot = self.db.query(AvailabilitySlot).filter(
                and_(
                    AvailabilitySlot.user_id == user_id,
                    AvailabilitySlot.start_time <= start_time,
                    AvailabilitySlot.end_time >= end_time,
                    AvailabilitySlot.is_available == True
                )
            ).first()
            
            if not slot:
                # Create a new availability slot
                slot = AvailabilitySlot(
                    user_id=user_id,
                    start_time=start_time,
                    end_time=end_time,
                    is_available=True
                )
                self.db.add(slot)
                self.db.flush()  # Get the ID without committing
            
            # Create the booking
            booking = Booking(
                host_user_id=user_id,
                availability_slot_id=slot.id,
                guest_name=guest_name,
                guest_email=guest_email,
                guest_message=description,
                start_time=start_time,
                end_time=end_time,
                status="confirmed",
                google_event_id=google_event_id
            )
            
            self.db.add(booking)
            self.db.commit()
            self.db.refresh(booking)
            
            return {
                "booking_id": booking.id,
                "slot_id": slot.id,
                "status": "success"
            }
            
        except Exception as e:
            self.db.rollback()
            raise e