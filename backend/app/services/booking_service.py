from typing import List, Optional
from datetime import datetime, timezone
import logging

from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.models import Booking, AvailabilitySlot, User
from app.schemas.schemas import BookingCreate, BookingUpdate, PublicBookingCreate
from app.services.availability_service import get_availability_slot, check_slot_availability
from app.services.google_calendar_service import GoogleCalendarService
from app.services.email_service import send_booking_confirmation_email

logger = logging.getLogger(__name__)


def create_booking(
    db: Session, 
    booking_data: PublicBookingCreate, 
    slot_id: int, 
    host_user: User
) -> Optional[Booking]:
    """Create a new booking for a specific availability slot."""
    
    # Check if slot is available
    if not check_slot_availability(db, slot_id):
        return None
    
    slot = get_availability_slot(db, slot_id)
    if not slot:
        return None
    
    # Create the booking
    try:
        # Ensure timezone-aware datetimes for database storage
        start_time = slot.start_time
        end_time = slot.end_time
        
        # If datetimes are naive, assume they're in UTC
        if start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=timezone.utc)
        if end_time.tzinfo is None:
            end_time = end_time.replace(tzinfo=timezone.utc)
        
        db_booking = Booking(
            host_user_id=host_user.id,
            availability_slot_id=slot_id,
            guest_name=booking_data.guest_name,
            guest_email=booking_data.guest_email,
            guest_message=booking_data.guest_message,
            start_time=start_time,
            end_time=end_time,
            status="confirmed"
        )
        
        # Create the booking in database FIRST (single source of truth)
        db_booking.google_event_id = None  # Will be updated after calendar sync
        
        # Mark the availability slot as unavailable (booked)
        slot.is_available = False
        
        # Save to database first
        db.add(db_booking)
        db.commit()
        db.refresh(db_booking)
        logger.info(f"✅ Booking created successfully: {db_booking.id}")
        
    except Exception as e:
        logger.error(f"Error creating booking: {e}")
        import traceback
        traceback.print_exc()
        return None
    
    # Now sync to Google Calendar (derived from database)
    google_event_id = None
    if host_user.google_access_token and host_user.google_refresh_token:
        try:
            calendar_service = GoogleCalendarService(
                access_token=host_user.google_access_token,
                refresh_token=host_user.google_refresh_token,
                db=db,
                user_id=host_user.id
            )
            
            # Delete the availability slot's calendar event if it exists
            if slot.google_event_id:
                try:
                    calendar_service.delete_event(slot.google_event_id)
                    logger.info(f"Deleted availability slot calendar event: {slot.google_event_id}")
                    slot.google_event_id = None  # Clear the slot's calendar event ID
                except Exception as e:
                    logger.error(f"Failed to delete availability slot calendar event: {e}")
            
            event_title = f"Meeting with {booking_data.guest_name}"
            event_description = f"Meeting scheduled via booking system.\n\nGuest: {booking_data.guest_name}\nEmail: {booking_data.guest_email}"
            if booking_data.guest_message:
                event_description += f"\nMessage: {booking_data.guest_message}"
            
            created_event = calendar_service.create_booking_event(
                title=event_title,
                start_time=slot.start_time,
                end_time=slot.end_time,
                guest_email=booking_data.guest_email,
                host_email=host_user.email,
                description=event_description
            )
            
            google_event_id = created_event.get('id')
            
            # Update database with calendar event ID
            db_booking.google_event_id = google_event_id
            db.commit()
            logger.info(f"✅ Successfully synced booking {db_booking.id} to Google Calendar")
            
        except Exception as e:
            logger.error(f"Failed to create Google Calendar event: {e}")
            # Booking exists in database, calendar sync failed
            # This is acceptable - database is source of truth
    
    # Only send confirmation emails if both database booking and calendar event are created successfully
    email_sent = False
    if db_booking.id and (google_event_id or not host_user.google_calendar_connected):
        try:
            email_sent = send_booking_confirmation_email(
                guest_email=booking_data.guest_email,
                guest_name=booking_data.guest_name,
                host_email=host_user.email,
                host_name=host_user.full_name,
                booking=db_booking,
                host_access_token=host_user.google_access_token,
                host_refresh_token=host_user.google_refresh_token,
                db=db
            )
            if email_sent:
                logger.info(f"✅ Booking confirmation emails sent successfully for booking {db_booking.id}")
            else:
                logger.warning(f"⚠️  Failed to send booking confirmation emails for booking {db_booking.id}")
        except Exception as e:
            logger.error(f"Failed to send confirmation email: {e}")
    else:
        logger.warning(f"⚠️  Skipping email confirmation - booking ID: {db_booking.id}, calendar event ID: {google_event_id}")
    
    return db_booking


def get_bookings_for_user(db: Session, user_id: int, status: str = None) -> List[Booking]:
    """Get all bookings for a user (as host)."""
    query = db.query(Booking).filter(Booking.host_user_id == user_id)
    
    if status:
        query = query.filter(Booking.status == status)
    
    return query.order_by(Booking.start_time.desc()).all()


def get_booking(db: Session, booking_id: int, user_id: int = None) -> Optional[Booking]:
    """Get a specific booking."""
    query = db.query(Booking).filter(Booking.id == booking_id)
    
    if user_id:
        query = query.filter(Booking.host_user_id == user_id)
    
    return query.first()


def update_booking(
    db: Session, 
    booking_id: int, 
    booking_update: BookingUpdate, 
    user_id: int,
    update_calendar: bool = True) -> Optional[Booking]:
    """Update a booking."""
    booking = get_booking(db, booking_id, user_id)
    if not booking:
        return None
    
    # Handle Google Calendar updates only if requested
    if update_calendar and booking.google_event_id:
        try:
            host = db.query(User).filter(User.id == booking.host_user_id).first()
            if host and host.google_access_token and host.google_refresh_token:
                calendar_service = GoogleCalendarService(
                    access_token=host.google_access_token,
                    refresh_token=host.google_refresh_token,
                    db=db,
                    user_id=host.id
                )
                
                # If status is being changed to cancelled, delete the event
                if booking_update.status == 'cancelled':
                    calendar_service.delete_event(booking.google_event_id)
                    logger.info(f"Deleted Google Calendar event: {booking.google_event_id}")
                
                # If times are being updated, update the event
                elif (booking_update.start_time and booking_update.end_time and 
                      (booking.start_time != booking_update.start_time or booking.end_time != booking_update.end_time)):
                    calendar_service.update_event(
                        event_id=booking.google_event_id,
                        start_time=booking.start_time,
                        end_time=booking.end_time
                    )
                    logger.info(f"Updated Google Calendar event: {booking.google_event_id}")
                    
        except Exception as e:
            logger.error(f"Failed to update Google Calendar event: {e}")
            # Continue with booking update even if calendar update fails    
    db.commit()
    db.refresh(booking)
    return booking


def cancel_booking(db: Session, booking_id: int, user_id: int = None) -> bool:
    """Cancel a booking."""
    booking = get_booking(db, booking_id, user_id)
    if not booking:
        return False
    
    booking.status = "cancelled"
    
    # Try to delete the Google Calendar event
    if booking.google_event_id:
        try:
            host = db.query(User).filter(User.id == booking.host_user_id).first()
            if host and host.google_access_token and host.google_refresh_token:
                calendar_service = GoogleCalendarService(
                    access_token=host.google_access_token,
                    refresh_token=host.google_refresh_token,
                    db=db,
                    user_id=host.id
                )
                calendar_service.delete_event(booking.google_event_id)
        except Exception as e:
            logger.error(f"Failed to delete Google Calendar event: {e}")
    
    db.commit()
    return True


def get_upcoming_bookings(db: Session, user_id: int, limit: int = 10) -> List[Booking]:
    """Get upcoming bookings for a user."""
    now = datetime.now(timezone.utc)
    return (
        db.query(Booking)
        .filter(
            and_(
                Booking.host_user_id == user_id,
                Booking.start_time > now,
                Booking.status == "confirmed"
            )
        )
        .order_by(Booking.start_time)
        .limit(limit)
        .all()
    )


def get_booking_by_guest_email(db: Session, guest_email: str, booking_id: int = None) -> List[Booking]:
    """Get bookings by guest email (for guest access to their bookings)."""
    query = db.query(Booking).filter(Booking.guest_email == guest_email)
    
    if booking_id:
        query = query.filter(Booking.id == booking_id)
    
    return query.order_by(Booking.start_time.desc()).all() 