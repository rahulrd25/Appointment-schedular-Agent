from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta, timezone
import logging

from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.models import AvailabilitySlot, User, Booking
from app.schemas.schemas import AvailabilitySlotCreate, AvailabilitySlotUpdate
from app.core.timezone_utils import TimezoneManager

logger = logging.getLogger(__name__)


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
        
        # Get user's timezone
        user_timezone = TimezoneManager.get_user_timezone(user.timezone)
        
        # Ensure times are timezone-aware and convert to UTC for storage
        start_time = slot.start_time
        end_time = slot.end_time
        
        # If times are naive, assume they're in user's timezone
        if start_time.tzinfo is None:
            start_time = TimezoneManager.make_timezone_aware(start_time, user_timezone)
        if end_time.tzinfo is None:
            end_time = TimezoneManager.make_timezone_aware(end_time, user_timezone)
        
        # Convert to UTC for storage
        utc_start_time = start_time.astimezone(timezone.utc)
        utc_end_time = end_time.astimezone(timezone.utc)
        
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
                logger.info(f"✅ Calendar connection test successful for {user.email}")
                
            except Exception as e:
                logger.error(f"Calendar connection test failed: {e}")
                return {
                    "success": False,
                    "message": "Couldn't add slot. Please reconnect your calendar in Settings.",
                    "slot": None,
                    "calendar_created": False,
                    "calendar_error": str(e),
                    "google_event_id": None
                }
        
        # Create slot in database FIRST (single source of truth)
        db_slot = AvailabilitySlot(
            user_id=user_id,
            start_time=utc_start_time,
            end_time=utc_end_time,
            is_available=slot.is_available,
            google_event_id=None  # Will be updated after calendar sync
        )
        db.add(db_slot)
        db.commit()
        db.refresh(db_slot)
        
        calendar_created = None
        calendar_error = None
        google_event_id = None
        
        # Create Google Calendar event if user has connected calendar (derived from database)
        if user.google_calendar_connected and user.google_access_token and user.google_refresh_token:
            try:
                # Create event in Google Calendar
                event_data = {
                    'summary': 'Available for Booking',
                    'description': 'Time slot available for appointments',
                    'start': {
                        'dateTime': utc_start_time.isoformat(),
                        'timeZone': 'UTC'
                    },
                    'end': {
                        'dateTime': utc_end_time.isoformat(),
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
                logger.info(f"✅ Successfully synced availability slot {db_slot.id} to Google Calendar")
                
            except Exception as e:
                logger.error(f"Failed to create Google Calendar event: {e}")
                # Slot exists in database, calendar sync failed
                # This is acceptable - database is source of truth
                calendar_created = False
                calendar_error = str(e)
        
        return {
            "success": True,
            "message": "Availability slot created successfully",
            "slot": db_slot,
            "calendar_created": calendar_created,
            "calendar_error": calendar_error,
            "google_event_id": google_event_id
        }
        
    except Exception as e:
        logger.error(f"Error creating availability slot: {e}")
        import traceback
        traceback.print_exc()
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
    now = datetime.now(timezone.utc)
    
    # Ensure from_date is timezone-aware for comparison
    if from_date:
        # Handle both datetime and date objects
        if hasattr(from_date, 'tzinfo'):
            # It's a datetime object
            if from_date.tzinfo is None:
                # Make timezone-naive datetime timezone-aware (assume UTC)
                from_date = from_date.replace(tzinfo=timezone.utc)
            start_filter = from_date if from_date > now else now
        else:
            # It's a date object, convert to datetime at start of day
            from_date = datetime.combine(from_date, datetime.min.time()).replace(tzinfo=timezone.utc)
            start_filter = from_date if from_date > now else now
    else:
        start_filter = now
    
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


def delete_availability_slot(db: Session, slot_id: int, user_id: int) -> dict:
    """Delete an availability slot and its Google Calendar event if linked."""
    slot = get_availability_slot(db, slot_id, user_id)
    if not slot:
        return {"success": False, "message": "Slot not found"}    
    
    # Check if there are any confirmed bookings for this slot
    existing_bookings = db.query(Booking).filter(
        and_(
            Booking.availability_slot_id == slot.id,
            Booking.status == "confirmed"
        )
    ).all()
    
    booking_deleted = False
    if existing_bookings:
        # Delete associated bookings first
        for booking in existing_bookings:
            # Delete Google Calendar event for the booking if it exists
            if booking.google_event_id:
                try:
                    user = db.query(User).filter(User.id == booking.host_user_id).first()
                    if user and user.google_access_token and user.google_refresh_token:
                        from app.services.google_calendar_service import GoogleCalendarService
                        calendar_service = GoogleCalendarService(
                            access_token=user.google_access_token,
                            refresh_token=user.google_refresh_token,
                            db=db,
                            user_id=user.id
                        )
                        calendar_service.delete_event(booking.google_event_id)
                        logger.info(f"Deleted Google Calendar event for booking {booking.id}")
                except Exception as e:
                    logger.error(f"Failed to delete Google Calendar event for booking {booking.id}: {e}")
            
            # Delete the booking
            db.delete(booking)
            booking_deleted = True
        
        logger.info(f"Deleted {len(existing_bookings)} associated booking(s)")
    
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
                logger.error(f"Failed to delete Google Calendar event: {e}")
                calendar_deleted = False
                calendar_error = str(e)
        else:
            calendar_deleted = False
            calendar_error = "Google Calendar not connected"
    else:
        # No Google Calendar event associated
        calendar_deleted = None
    
    # Delete the slot from database
    db.delete(slot)
    db.commit()
    
    # Build success message
    message = "Availability slot deleted successfully"
    if booking_deleted:
        message += f" (and {len(existing_bookings)} associated booking(s))"
    
    return {
        "success": True,
        "message": message,
        "calendar_deleted": calendar_deleted,
        "calendar_error": calendar_error,
        "bookings_deleted": len(existing_bookings) if existing_bookings else 0
    }

def check_slot_availability(db: Session, slot_id: int) -> bool:
    """Check if a slot is available for booking."""
    slot = get_availability_slot(db, slot_id)
    if not slot or not slot.is_available:
        return False
    
    # Check if slot is in the future - ensure timezone-aware comparison
    now = datetime.now(timezone.utc)
    slot_start_time = slot.start_time
    
    # Make slot_start_time timezone-aware if it's not already
    if slot_start_time.tzinfo is None:
        slot_start_time = slot_start_time.replace(tzinfo=timezone.utc)
    
    if slot_start_time <= now:
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
        user_id=user.id    )
    
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
            # Ensure times are timezone-aware (should be from Google Calendar)
            start_time = slot_data['start_time']
            end_time = slot_data['end_time']
            
            # Make timezone-aware if not already
            if start_time.tzinfo is None:
                start_time = start_time.replace(tzinfo=timezone.utc)
            if end_time.tzinfo is None:
                end_time = end_time.replace(tzinfo=timezone.utc)
            
            # Convert to UTC for storage
            utc_start_time = start_time.astimezone(timezone.utc)
            utc_end_time = end_time.astimezone(timezone.utc)
            
            db_slot = AvailabilitySlot(
                user_id=user.id,
                start_time=utc_start_time,
                end_time=utc_end_time,
                is_available=True
            )
            db.add(db_slot)
            created_slots.append(db_slot)
        
        current_date += timedelta(days=1)
    
    db.commit()
    return created_slots


def create_availability_slots_bulk(db: Session, user_id: int, slots_data: List[Dict[str, Any]]) -> dict:
    """Create multiple availability slots for a user."""
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return {
                "success": False,
                "message": "User not found",
                "slots_created": 0,
                "errors": [],
                "existing_slots": []
            }
        
        # Get user's timezone
        user_timezone = TimezoneManager.get_user_timezone(user.timezone)
        
        created_slots = []
        existing_slots = []
        errors = []
        
        for slot_data in slots_data:
            try:
                # Parse date and time
                date_str = slot_data.get('date')
                start_time_str = slot_data.get('start_time')
                period = slot_data.get('period', 30)  # Default 30 minutes
                
                if not date_str or not start_time_str:
                    errors.append(f"Missing date or start_time for slot: {slot_data}")
                    continue
                
                # Combine date and time and parse as naive datetime
                datetime_str = f"{date_str} {start_time_str}"
                naive_start_time = datetime.strptime(datetime_str, '%Y-%m-%d %H:%M')
                
                # Convert naive datetime to timezone-aware datetime in user's timezone, then to UTC
                user_start_time = TimezoneManager.make_timezone_aware(naive_start_time, user_timezone)
                utc_start_time = user_start_time.astimezone(timezone.utc)
                
                # Calculate end time based on period
                utc_end_time = utc_start_time + timedelta(minutes=period)
                
                # Check if slot already exists
                existing_slot = db.query(AvailabilitySlot).filter(
                    and_(
                        AvailabilitySlot.user_id == user_id,
                        AvailabilitySlot.start_time == utc_start_time,
                        AvailabilitySlot.end_time == utc_end_time
                    )
                ).first()
                
                if existing_slot:
                    # Add existing slot to the response instead of just an error
                    existing_slots.append({
                        "id": existing_slot.id,
                        "start_time": existing_slot.start_time.isoformat(),
                        "end_time": existing_slot.end_time.isoformat(),
                        "is_available": existing_slot.is_available,
                        "status": "booked" if not existing_slot.is_available else "available"
                    })
                    continue
                
                # Create the slot with UTC times
                db_slot = AvailabilitySlot(
                    user_id=user_id,
                    start_time=utc_start_time,
                    end_time=utc_end_time,
                    is_available=True
                )
                db.add(db_slot)
                created_slots.append(db_slot)
                
            except Exception as e:
                errors.append(f"Error creating slot {slot_data}: {str(e)}")
                continue
        
        # Commit all slots at once
        if created_slots:
            db.commit()
            
            # Refresh all created slots
            for slot in created_slots:
                db.refresh(slot)
        
        # Build appropriate message
        message_parts = []
        if created_slots:
            message_parts.append(f"Successfully created {len(created_slots)} availability slots")
        if existing_slots:
            message_parts.append(f"{len(existing_slots)} slots already exist")
        
        message = ". ".join(message_parts) if message_parts else "No slots were created"
        
        return {
            "success": True,
            "message": message,
            "slots_created": len(created_slots),
            "existing_slots": existing_slots,
            "errors": errors,
            "created_slots": [
                {
                    "id": slot.id,
                    "start_time": slot.start_time.isoformat(),
                    "end_time": slot.end_time.isoformat(),
                    "is_available": slot.is_available,
                    "status": "available"
                }
                for slot in created_slots
            ]
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": f"Error creating slots: {str(e)}",
            "slots_created": 0,
            "errors": [str(e)],
            "existing_slots": [],
            "created_slots": []
        }

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

class AvailabilityService:
    """Service class for availability operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_user_availability_slots(self, user_id: int, date: Optional[datetime] = None, duration_minutes: int = 30) -> List[Dict[str, Any]]:
        """Get availability slots for a user, optionally filtered by date"""
        # Use get_available_slots_for_booking to ensure slots are actually bookable
        slots = get_available_slots_for_booking(self.db, user_id, from_date=date)
        
        if date:
            # Handle both datetime and date objects
            if hasattr(date, 'tzinfo'):
                # It's a datetime object
                if date.tzinfo is None:
                    # Make timezone-naive datetime timezone-aware (assume UTC)
                    date = date.replace(tzinfo=timezone.utc)
                date_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
                date_end = date.replace(hour=23, minute=59, second=59, microsecond=999999)
            else:
                # It's a date object, convert to datetime
                date_start = datetime.combine(date, datetime.min.time()).replace(tzinfo=timezone.utc)
                date_end = datetime.combine(date, datetime.max.time().replace(microsecond=999999)).replace(tzinfo=timezone.utc)
            
            # Filter slots by date
            filtered_slots = []
            for slot in slots:
                # Ensure slot times are timezone-aware for comparison
                slot_start = slot.start_time
                if slot_start.tzinfo is None:
                    slot_start = slot_start.replace(tzinfo=timezone.utc)
                
                if date_start <= slot_start <= date_end:
                    filtered_slots.append(slot)
            slots = filtered_slots
        
        # Convert to dictionary format
        result = []
        for slot in slots:
            # Ensure timezone-aware datetime for JSON serialization
            start_time = slot.start_time
            end_time = slot.end_time
            
            # Make timezone-aware if not already
            if start_time.tzinfo is None:
                start_time = start_time.replace(tzinfo=timezone.utc)
            if end_time.tzinfo is None:
                end_time = end_time.replace(tzinfo=timezone.utc)
            
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


