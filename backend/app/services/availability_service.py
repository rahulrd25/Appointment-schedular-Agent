from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta, timezone
import pytz

from sqlalchemy.orm import Session
from sqlalchemy import and_, func, or_

from app.models.models import AvailabilitySlot, User, Booking
from app.schemas.schemas import AvailabilitySlotCreate, AvailabilitySlotUpdate


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
        
        # Check for overlapping slots on the same date with proper error handling
        try:
            # Get user's timezone once
            user_timezone = pytz.timezone(user.timezone or 'UTC')
            
            # Ensure both times are timezone-aware for proper comparison
            if not slot.start_time.tzinfo:
                slot_start = user_timezone.localize(slot.start_time)
                slot_end = user_timezone.localize(slot.end_time)
            else:
                slot_start = slot.start_time
                slot_end = slot.end_time
            
            # Get the date part for comparison (in user's timezone)
            slot_date_local = slot_start.astimezone(user_timezone).date()
            
            # Get all slots for this user
            all_user_slots = db.query(AvailabilitySlot).filter(
                AvailabilitySlot.user_id == user_id
            ).all()
            
            # Check for overlaps in Python (easier to handle timezones)
            existing_overlapping_slot = None
            for existing_slot in all_user_slots:
                # Convert existing slot times to user's timezone for comparison
                existing_start_local = existing_slot.start_time.astimezone(user_timezone)
                existing_end_local = existing_slot.end_time.astimezone(user_timezone)
                
                # Check if dates match (in user's timezone)
                if existing_start_local.date() == slot_date_local:
                    # Check for overlap
                    if (slot_start < existing_end_local and slot_end > existing_start_local):
                        existing_overlapping_slot = existing_slot
                        break
            
            if existing_overlapping_slot:
                # Convert UTC times to user's timezone for display
                existing_start_local = existing_overlapping_slot.start_time.astimezone(user_timezone)
                existing_end_local = existing_overlapping_slot.end_time.astimezone(user_timezone)
                
                existing_time = existing_start_local.strftime("%I:%M %p")
                existing_date = existing_start_local.strftime("%B %d, %Y")
                existing_end_time = existing_end_local.strftime("%I:%M %p")
                
                return {
                    "success": False,
                    "message": f"You already have a slot from {existing_time} to {existing_end_time} on {existing_date}. Please choose a different time.",
                    "slot": existing_overlapping_slot,
                    "calendar_created": False,
                    "calendar_error": None,
                    "google_event_id": None
                }
        except Exception as e:
            return {
                "success": False,
                "message": f"Error checking for duplicate slots: {str(e)}",
                "slot": None,
                "calendar_created": False,
                "calendar_error": str(e),
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
                
            except Exception as e:
                return {
                    "success": False,
                    "message": "Couldn't add slot. Please reconnect your calendar in Settings.",
                    "slot": None,
                    "calendar_created": False,
                    "calendar_error": str(e),
                    "google_event_id": None
                }
        
        # Create slot in database with error handling
        try:
            db_slot = AvailabilitySlot(
                user_id=user_id,
                start_time=slot.start_time,
                end_time=slot.end_time,
                is_available=slot.is_available
            )
            db.add(db_slot)
            db.commit()
            db.refresh(db_slot)
        except Exception as e:
            db.rollback()
            return {
                "success": False,
                "message": f"Failed to create slot in database: {str(e)}",
                "slot": None,
                "calendar_created": False,
                "calendar_error": str(e),
                "google_event_id": None
            }
        
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
                try:
                    db_slot.google_event_id = google_event_id
                    db.commit()
                    calendar_created = True
                except Exception as e:
                    db.rollback()
                    return {
                        "success": False,
                        "message": f"Slot created but failed to update with calendar event ID: {str(e)}",
                        "slot": None,
                        "calendar_created": False,
                        "calendar_error": str(e),
                        "google_event_id": None
                    }
                
            except Exception as e:
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


def get_availability_slots_for_user(db: Session, user_id: int, include_unavailable: bool = False) -> List[AvailabilitySlot]:
    """Get all availability slots for a user."""
    query = db.query(AvailabilitySlot).filter(AvailabilitySlot.user_id == user_id)
    
    if not include_unavailable:
        query = query.filter(AvailabilitySlot.is_available == True)
    
    return query.order_by(AvailabilitySlot.start_time).all()


def get_available_slots_for_booking(db: Session, user_id: int, from_date: datetime = None) -> List[AvailabilitySlot]:
    """Get available slots that can be booked (not already booked and in the future)."""
    from datetime import timezone
    now = datetime.now(timezone.utc)
    
    # If from_date is provided, use it; otherwise use current time
    if from_date:
        # If from_date is naive, assume it's in UTC
        if from_date.tzinfo is None:
            from_date = from_date.replace(tzinfo=timezone.utc)
        start_filter = from_date
    else:
        start_filter = now
    
    # Get availability slots that are:
    # 1. Available
    # 2. For the specific date (if provided) or in the future
    # 3. Not fully booked
    if from_date:
        # For specific date, get slots for that date only
        query = db.query(AvailabilitySlot).filter(
            and_(
                AvailabilitySlot.user_id == user_id,
                AvailabilitySlot.is_available == True,
                func.date(AvailabilitySlot.start_time) == func.date(from_date)
            )
        )
    else:
        # For future slots, get all future slots
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


def delete_availability_slot(db: Session, slot_id: int, user_id: int) -> dict:
    """Delete an availability slot and its Google Calendar event if linked."""
    slot = get_availability_slot(db, slot_id, user_id)
    if not slot:
        return {"success": False, "message": "Slot not found"}
    
    # Check if there are any bookings for this slot (any status)
    existing_booking = db.query(Booking).filter(
        Booking.availability_slot_id == slot.id
    ).first()
    
    if existing_booking:
        return {"success": False, "message": f"Cannot delete slot with existing booking (ID: {existing_booking.id}, Status: {existing_booking.status})"}
    
    # Delete from database first
    try:
        db.delete(slot)
        db.commit()
        db_deleted = True
    except Exception as e:
        db.rollback()
        return {
            "success": False,
            "message": f"Failed to delete slot from database: {str(e)}",
            "calendar_deleted": None,
            "calendar_error": None
        }
    
    # Try to delete from Google Calendar if database deletion succeeded
    calendar_deleted = None
    calendar_error = None
    
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
                calendar_deleted = False
                calendar_error = str(e)
        else:
            calendar_deleted = False
            calendar_error = "Google Calendar not connected"
    
    # Return result with appropriate message
    if calendar_deleted is True:
        message = "Slot deleted successfully from app and calendar!"
    elif calendar_deleted is False:
        message = f"Slot deleted from app but failed to delete from calendar: {calendar_error}"
    else:
        message = "Slot deleted successfully from app."
    
    return {
        "success": True,
        "message": message,
        "calendar_deleted": calendar_deleted,
        "calendar_error": calendar_error
    }


def check_slot_availability(db: Session, slot_id: int) -> bool:
    """Check if a slot is available for booking."""
    slot = get_availability_slot(db, slot_id)
    if not slot or not slot.is_available:
        return False
    
    # Check if slot is in the future - ensure timezone-aware comparison
    if slot.start_time <= datetime.now(timezone.utc):
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
        refresh_token=user.google_refresh_token,
        db=db,
        user_id=user.id
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
            google_event_id = slot_data.get('event_id')  # Save event ID if present
            
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
                    is_available=True,
                    google_event_id=google_event_id
                )
                db.add(db_slot)
                created_slots.append(db_slot)
        
        current_date += timedelta(days=1)
    
    db.commit()
    return created_slots


def check_calendar_connection(db: Session, user: User) -> dict:
    """Check if user's Google Calendar connection is working."""
    try:
        if not user.google_calendar_connected or not user.google_access_token:
            return {
                "connected": False,
                "message": "Calendar not connected"
            }
        
        from app.services.google_calendar_service import GoogleCalendarService
        calendar_service = GoogleCalendarService(
            access_token=user.google_access_token,
            refresh_token=user.google_refresh_token,
            db=db,
            user_id=user.id
        )
        
        # Test connection by getting events
        events = calendar_service.get_events()
        
        return {
            "connected": True,
            "message": "Calendar connected and working",
            "event_count": len(events) if events else 0
        }
        
    except Exception as e:
        return {
            "connected": False,
            "message": f"Calendar connection failed: {str(e)}"
        }


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