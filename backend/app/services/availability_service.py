from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.models import AvailabilitySlot, User, Booking
from app.schemas.schemas import AvailabilitySlotCreate, AvailabilitySlotUpdate


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


def delete_availability_slot(db: Session, slot_id: int, user_id: int) -> bool:
    """Delete an availability slot."""
    slot = get_availability_slot(db, slot_id, user_id)
    if not slot:
        return False
    
    # Check if there are any confirmed bookings for this slot
    existing_booking = db.query(Booking).filter(
        and_(
            Booking.availability_slot_id == slot_id,
            Booking.status == "confirmed"
        )
    ).first()
    
    if existing_booking:
        # Don't delete slots with confirmed bookings, just mark as unavailable
        slot.is_available = False
        db.commit()
        return True
    
    db.delete(slot)
    db.commit()
    return True


def check_slot_availability(db: Session, slot_id: int) -> bool:
    """Check if a slot is available for booking."""
    slot = get_availability_slot(db, slot_id)
    if not slot or not slot.is_available:
        return False
    
    # Check if slot is in the future
    if slot.start_time <= datetime.utcnow():
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
        refresh_token=user.google_refresh_token
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
                    is_available=True
                )
                db.add(db_slot)
                created_slots.append(db_slot)
        
        current_date += timedelta(days=1)
    
    db.commit()
    return created_slots


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


class AvailabilityService:
    """Service class for availability operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_user_availability_slots(self, user_id: int, date: Optional[datetime] = None, duration_minutes: int = 30) -> List[Dict[str, Any]]:
        """Get availability slots for a user, optionally filtered by date"""
        slots = get_availability_slots_for_user(self.db, user_id)
        
        if date:
            # Filter by date
            date_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
            date_end = date.replace(hour=23, minute=59, second=59, microsecond=999999)
            slots = [s for s in slots if date_start <= s.start_time <= date_end]
        
        # Convert to dictionary format
        result = []
        for slot in slots:
            result.append({
                "id": slot.id,
                "start_time": slot.start_time.isoformat(),
                "end_time": slot.end_time.isoformat(),
                "duration_minutes": int((slot.end_time - slot.start_time).total_seconds() / 60),
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