from typing import List, Optional, Dict, Any
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.models import Booking, AvailabilitySlot, User
from app.schemas.schemas import BookingCreate, BookingUpdate, PublicBookingCreate
from app.services.availability_service import get_availability_slot, check_slot_availability
from app.services.google_calendar_service import GoogleCalendarService



def create_booking(
    db: Session, 
    booking_data: PublicBookingCreate, 
    slot_id: int, 
    host_user: User
) -> Optional[Booking]:
    """Create a new booking."""
    try:
        # Get the availability slot
        slot = db.query(AvailabilitySlot).filter(AvailabilitySlot.id == slot_id).first()
        if not slot:
            return None
        
        # Create the booking
        booking = Booking(
            host_user_id=host_user.id,
            availability_slot_id=slot_id,
            guest_name=booking_data.guest_name,
            guest_email=booking_data.guest_email,
            guest_message=booking_data.guest_message,
            start_time=slot.start_time,
            end_time=slot.end_time,
            status="confirmed",
            sync_status="pending",
            sync_attempts=0
        )
        
        db.add(booking)
        db.flush()  # Get the ID without committing
        
        # Try to create Google Calendar event
        google_event_id = None
        calendar_created = False
        calendar_error = None
        
        if host_user.google_calendar_connected and host_user.google_access_token:
            try:
                from app.services.google_calendar_service import GoogleCalendarService
                calendar_service = GoogleCalendarService(
                    access_token=host_user.google_access_token,
                    refresh_token=host_user.google_refresh_token,
                    db=db,
                    user_id=host_user.id
                )
                
                # Create calendar event
                calendar_event = calendar_service.create_booking_event(
                    title=f"Meeting with {booking_data.guest_name}",
                    start_time=slot.start_time,
                    end_time=slot.end_time,
                    guest_email=booking_data.guest_email,
                    host_email=host_user.email,
                    description=booking_data.guest_message
                )
                
                if calendar_event and calendar_event.get('id'):
                    google_event_id = calendar_event['id']
                    booking.google_event_id = google_event_id
                    booking.sync_status = "synced"
                    booking.last_synced = datetime.utcnow()
                    calendar_created = True
                else:
                    booking.sync_status = "failed"
                    booking.sync_error = "Calendar event creation failed"
                    
            except Exception as e:
                booking.sync_status = "failed"
                booking.sync_error = str(e)
        
        # Commit the booking
        db.commit()
        
        # Send confirmation email
        email_sent = False
        try:
            from app.services.notification_service import NotificationService
            notification_service = NotificationService()
            
            notification_results = notification_service.send_booking_confirmation_notifications(
                guest_email=booking_data.guest_email,
                guest_name=booking_data.guest_name,
                host_email=host_user.email,
                host_name=host_user.full_name,
                booking=booking,
                host_access_token=host_user.google_access_token,
                host_refresh_token=host_user.google_refresh_token
            )
            
            email_sent = notification_results["success"]
        except Exception as e:
            print(f"❌ Email sending failed for booking {booking.id}: {e}")
        
        # Delete the availability slot since it's now booked
        try:
            db.delete(slot)
            slot_deleted = True
            print(f"🗑️ Deleted availability slot {slot_id} after booking {booking.id}")
        except Exception as e:
            slot_deleted = False
            print(f"❌ Failed to delete availability slot {slot_id}: {e}")
        
        # Commit the slot deletion
        db.commit()
        
        if calendar_created and email_sent and slot_deleted:
            print(f"✅ Booking {booking.id} completed: Event in calendar, DB, email sent, and slot deleted")
        elif calendar_created and slot_deleted:
            print(f"✅ Booking {booking.id} completed: Event in calendar and DB, slot deleted, but email failed")
        elif email_sent and slot_deleted:
            print(f"✅ Booking {booking.id} completed: Event in DB, email sent, slot deleted, but calendar failed")
        elif slot_deleted:
            print(f"✅ Booking {booking.id} created in DB and slot deleted: Calendar and email failed")
        else:
            print(f"⚠️ Booking {booking.id} created in DB only: Calendar, email, and slot deletion failed")
        
        return booking
        
    except Exception as e:
        db.rollback()
        print(f"❌ Booking creation failed: {e}")
        return None


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
    update_calendar: bool = True
) -> Optional[Booking]:
    """Update a booking."""
    booking = get_booking(db, booking_id, user_id)
    if not booking:
        return None
    
    # Store original times for calendar update
    original_start_time = booking.start_time
    original_end_time = booking.end_time
    
    update_data = booking_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(booking, key, value)
    
    # Handle Google Calendar updates only if requested
    if update_calendar and booking.google_event_id:
        try:
            host = db.query(User).filter(User.id == booking.host_user_id).first()
            if host and host.google_access_token and host.google_refresh_token:
                calendar_service = GoogleCalendarService(
                    access_token=host.google_access_token,
                    refresh_token=host.google_refresh_token
                )
                
                # If status is being changed to cancelled, delete the event
                if update_data.get('status') == 'cancelled':
                    calendar_service.delete_event(booking.google_event_id)
                    print(f"Deleted Google Calendar event: {booking.google_event_id}")
                
                # If times are being updated, update the event
                elif (update_data.get('start_time') and update_data.get('end_time') and 
                      (booking.start_time != original_start_time or booking.end_time != original_end_time)):
                    calendar_service.update_event(
                        event_id=booking.google_event_id,
                        start_time=booking.start_time,
                        end_time=booking.end_time
                    )
                    print(f"Updated Google Calendar event: {booking.google_event_id}")
                    
        except Exception as e:
            print(f"Failed to update Google Calendar event: {e}")
            # Continue with booking update even if calendar update fails
    
    db.commit()
    db.refresh(booking)
    return booking


def cancel_booking(db: Session, booking_id: int, user_id: int = None) -> bool:
    """Cancel a booking and remove it from Google Calendar."""
    try:
        # Get the booking
        booking = db.query(Booking).filter(Booking.id == booking_id).first()
        if not booking:
            return False
        
        # Check if user has permission to cancel
        if user_id and booking.host_user_id != user_id:
            return False
        
        # Try to delete from Google Calendar first
        calendar_deleted = False
        if booking.google_event_id and booking.host_user.google_calendar_connected:
            try:
                from app.services.google_calendar_service import GoogleCalendarService
                calendar_service = GoogleCalendarService(
                    access_token=booking.host_user.google_access_token,
                    refresh_token=booking.host_user.google_refresh_token,
                    db=db,
                    user_id=booking.host_user_id
                )
                
                calendar_deleted = calendar_service.delete_event(booking.google_event_id)
                if calendar_deleted:
                    print(f"✅ Event cancelled in calendar and deleted in DB for booking {booking.id}")
                else:
                    print(f"⚠️ Event deleted in DB but calendar deletion failed for booking {booking.id}")
                    
            except Exception as e:
                print(f"❌ Calendar deletion failed for booking {booking.id}: {e}")
        
        # Store booking details before deletion for slot recreation
        booking_start_time = booking.start_time
        booking_end_time = booking.end_time
        host_user_id = booking.host_user_id
        
        # Delete from database
        db.delete(booking)
        
        # Recreate the availability slot since the booking was cancelled
        try:
            from app.models.models import AvailabilitySlot
            new_slot = AvailabilitySlot(
                user_id=host_user_id,
                start_time=booking_start_time,
                end_time=booking_end_time,
                is_available=True
            )
            db.add(new_slot)
            slot_recreated = True
            print(f"🔄 Recreated availability slot after booking {booking_id} cancellation")
        except Exception as e:
            slot_recreated = False
            print(f"❌ Failed to recreate availability slot after booking cancellation: {e}")
        
        db.commit()
        
        if calendar_deleted and slot_recreated:
            print(f"✅ Booking {booking_id} cancelled: Event removed from calendar and DB, slot recreated")
        elif calendar_deleted:
            print(f"✅ Booking {booking_id} cancelled: Event removed from calendar and DB, but slot recreation failed")
        elif slot_recreated:
            print(f"✅ Booking {booking_id} cancelled: Event removed from DB and slot recreated, but calendar deletion failed")
        else:
            print(f"✅ Booking {booking_id} cancelled: Event removed from DB only")
        
        return True
        
    except Exception as e:
        db.rollback()
        print(f"❌ Booking cancellation failed: {e}")
        return False


def get_upcoming_bookings(db: Session, user_id: int, limit: int = 10) -> List[Booking]:
    """Get upcoming bookings for a user."""
    now = datetime.utcnow()
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


def get_booking_details(db: Session, booking_id: str, user: User) -> Dict[str, Any]:
    """Get booking details for modal display (handles both database and calendar bookings)."""
    if booking_id.startswith("calendar_"):
        # Handle calendar event
        calendar_event_id = booking_id.replace("calendar_", "")
        
        try:
            # Check if user has Google tokens
            if not user.google_access_token or not user.google_refresh_token:
                return {
                    "id": f"calendar_{calendar_event_id}",
                    "guest_name": "Calendar Event",
                    "guest_email": "",
                    "start_time": "Unknown",
                    "end_time": "Unknown",
                    "status": "confirmed",
                    "guest_message": "Calendar event (Google Calendar not connected)",
                    "created_at": "Unknown",
                    "source": "calendar",
                    "error": "Google Calendar not connected"
                }
            
            calendar_service = GoogleCalendarService(
                access_token=user.google_access_token,
                refresh_token=user.google_refresh_token,
                db=db,
                user_id=user.id
            )
            
            event = calendar_service.get_event(calendar_event_id)
            if not event:
                return {
                    "id": f"calendar_{calendar_event_id}",
                    "guest_name": "Calendar Event",
                    "guest_email": "",
                    "start_time": "Event not found",
                    "end_time": "Event not found",
                    "status": "confirmed",
                    "guest_message": "Calendar event (event not found in Google Calendar)",
                    "created_at": "Unknown",
                    "source": "calendar",
                    "error": "Event not found in Google Calendar"
                }
            
            # Parse event times
            event_start = event.get('start', {}).get('dateTime')
            event_end = event.get('end', {}).get('dateTime')
            
            if event_start and event_end:
                # Handle timezone-aware datetime parsing
                if event_start.endswith('Z'):
                    event_start_dt = datetime.fromisoformat(event_start.replace('Z', '+00:00'))
                else:
                    event_start_dt = datetime.fromisoformat(event_start)
                
                if event_end.endswith('Z'):
                    event_end_dt = datetime.fromisoformat(event_end.replace('Z', '+00:00'))
                else:
                    event_end_dt = datetime.fromisoformat(event_end)
                
                return {
                    "id": f"calendar_{event.get('id')}",
                    "guest_name": event.get('summary', 'Untitled Event'),
                    "guest_email": event.get('organizer', {}).get('email', ''),
                    "start_time": event_start_dt.strftime("%B %d, %Y at %I:%M %p"),
                    "end_time": event_end_dt.strftime("%I:%M %p"),
                    "status": "confirmed",
                    "guest_message": event.get('description', ''),
                    "created_at": event_start_dt.strftime("%B %d, %Y"),
                    "source": "calendar",
                    "raw_start_time": event_start_dt,
                    "raw_end_time": event_end_dt
                }
            else:
                return {
                    "id": f"calendar_{event.get('id')}",
                    "guest_name": event.get('summary', 'Untitled Event'),
                    "guest_email": event.get('organizer', {}).get('email', ''),
                    "start_time": "No time information",
                    "end_time": "No time information",
                    "status": "confirmed",
                    "guest_message": event.get('description', ''),
                    "created_at": "Unknown",
                    "source": "calendar",
                    "error": "No time information in event"
                }
                
        except Exception as e:
            print(f"Error getting calendar event details: {e}")
            return {
                "id": f"calendar_{calendar_event_id}",
                "guest_name": "Calendar Event",
                "guest_email": "",
                "start_time": "Error loading event",
                "end_time": "Error loading event",
                "status": "confirmed",
                "guest_message": f"Calendar event (error: {str(e)})",
                "created_at": "Unknown",
                "source": "calendar",
                "error": f"Error loading event: {str(e)}"
            }
    else:
        # Handle database booking
        try:
            booking_id_int = int(booking_id)
        except ValueError:
            return None
        
        booking = get_booking(db, booking_id_int, user.id)
        if not booking:
            return None

        return {
            "id": booking.id,
            "guest_name": booking.guest_name,
            "guest_email": booking.guest_email,
            "start_time": booking.start_time.strftime("%B %d, %Y at %I:%M %p"),
            "end_time": booking.end_time.strftime("%I:%M %p"),
            "status": booking.status,
            "guest_message": booking.guest_message,
            "created_at": booking.created_at.strftime("%B %d, %Y"),
            "source": "database",
            "raw_start_time": booking.start_time,
            "raw_end_time": booking.end_time
        }


def can_reschedule_booking(db: Session, booking_id: str, user: User) -> bool:
    """Check if a booking can be rescheduled (database and calendar bookings can be rescheduled)."""
    if booking_id.startswith("calendar_"):
        # Calendar events can be rescheduled if user has Google Calendar access
        return user.google_access_token and user.google_refresh_token
    else:
        try:
            booking_id_int = int(booking_id)
        except ValueError:
            return False
        
        booking = get_booking(db, booking_id_int, user.id)
        return booking is not None and booking.status == "confirmed"


def can_cancel_booking(db: Session, booking_id: str, user: User) -> bool:
    """Check if a booking can be cancelled."""
    if booking_id.startswith("calendar_"):
        return True  # Calendar events can be cancelled
    else:
        try:
            booking_id_int = int(booking_id)
        except ValueError:
            return False
        
        booking = get_booking(db, booking_id_int, user.id)
        return booking is not None and booking.status == "confirmed"


def cancel_booking_by_id(db: Session, booking_id: str, user: User) -> Dict[str, Any]:
    """Cancel a booking (database or calendar event) with full notification handling."""
    if booking_id.startswith("calendar_"):
        # Cancel calendar event
        calendar_event_id = booking_id.replace("calendar_", "")
        
        calendar_service = GoogleCalendarService(
            access_token=user.google_access_token,
            refresh_token=user.google_refresh_token,
            db=db,
            user_id=user.id
        )
        
        try:
            calendar_service.delete_event(calendar_event_id)
            
            # Send email notifications if Google tokens are available
            emails_sent = False
            if user.google_access_token and user.google_refresh_token:
                try:
                    from app.services.notification_service import NotificationService
                    
                    notification_service = NotificationService()
                    
                    # Get event details for notification
                    event = calendar_service.get_event(calendar_event_id)
                    if event:
                        guest_email = event.get('attendees', [{}])[0].get('email', '') if event.get('attendees') else ''
                        guest_name = event.get('summary', 'Guest')
                        
                        notification_results = notification_service.send_cancellation_notifications(
                            guest_email=guest_email,
                            guest_name=guest_name,
                            host_email=user.email,
                            host_name=user.full_name,
                            booking=None,  # Calendar events don't have booking object
                            host_access_token=user.google_access_token,
                            host_refresh_token=user.google_refresh_token
                        )
                        
                        emails_sent = notification_results["success"]
                except Exception as e:
                    print(f"Failed to send cancellation notifications: {e}")
                    emails_sent = False
            
            return {
                "success": True,
                "message": "Calendar event cancelled successfully",
                "source": "calendar",
                "calendar_deleted": True,
                "emails_sent": emails_sent
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to cancel calendar event: {str(e)}",
                "source": "calendar",
                "calendar_deleted": False,
                "emails_sent": False
            }
    else:
        # Cancel database booking
        try:
            booking_id_int = int(booking_id)
        except ValueError:
            return {
                "success": False,
                "message": "Invalid booking ID",
                "source": "database",
                "calendar_deleted": False,
                "emails_sent": False
            }
        
        booking = get_booking(db, booking_id_int, user.id)
        if not booking:
            return {
                "success": False,
                "message": "Booking not found",
                "source": "database",
                "calendar_deleted": False,
                "emails_sent": False
            }
        
        # Cancel the booking
        success = cancel_booking(db, booking_id_int, user.id)
        if success:
            print(f"✅ Booking {booking.id} cancelled successfully (database)")
        else:
            print(f"❌ Booking {booking.id} cancellation failed (database)")
        
        # Send email notifications if Google tokens are available
        emails_sent = False
        if user.google_access_token and user.google_refresh_token:
            try:
                from app.services.notification_service import NotificationService
                
                notification_service = NotificationService()
                
                notification_results = notification_service.send_cancellation_notifications(
                    guest_email=booking.guest_email,
                    guest_name=booking.guest_name,
                    host_email=user.email,
                    host_name=user.full_name,
                    booking=booking,
                    host_access_token=user.google_access_token,
                    host_refresh_token=user.google_refresh_token
                )
                
                emails_sent = notification_results["success"]
            except Exception as e:
                print(f"Failed to send cancellation notifications: {e}")
                emails_sent = False
        
        return {
            "success": True,
            "message": "Booking cancelled successfully",
            "source": "database",
            "booking": booking,
            "calendar_deleted": True,
            "emails_sent": emails_sent
        }


def reschedule_booking_by_id(db: Session, booking_id: int, new_start_time: datetime, new_end_time: datetime, user: User, reason: str = "") -> Dict[str, Any]:
    """Reschedule a booking and update Google Calendar event."""
    try:
        # Get the booking
        booking = db.query(Booking).filter(Booking.id == booking_id).first()
        if not booking:
            return {"success": False, "message": "Booking not found"}
        
        # Check if user has permission to reschedule
        if booking.host_user_id != user.id:
            return {"success": False, "message": "Permission denied"}
        
        # Update booking times
        old_start_time = booking.start_time
        old_end_time = booking.end_time
        
        booking.start_time = new_start_time
        booking.end_time = new_end_time
        booking.updated_at = datetime.utcnow()
        
        # Handle availability slot for reschedule
        # Since we delete slots when bookings are created, we need to:
        # 1. Create a new slot for the new time (if it's in the future)
        # 2. The old slot is already deleted when the booking was created
        slot_created = False
        if new_start_time > datetime.utcnow():
            try:
                from app.models.models import AvailabilitySlot
                # Check if there's already a slot for the new time
                existing_slot = db.query(AvailabilitySlot).filter(
                    and_(
                        AvailabilitySlot.user_id == user.id,
                        AvailabilitySlot.start_time == new_start_time,
                        AvailabilitySlot.end_time == new_end_time
                    )
                ).first()
                
                if not existing_slot:
                    # Create new availability slot for the new time
                    new_slot = AvailabilitySlot(
                        user_id=user.id,
                        start_time=new_start_time,
                        end_time=new_end_time,
                        is_available=True
                    )
                    db.add(new_slot)
                    slot_created = True
                    print(f"🔄 Created new availability slot for rescheduled booking {booking.id}")
                else:
                    print(f"⚠️ Availability slot already exists for rescheduled time")
                    
            except Exception as e:
                print(f"❌ Failed to create availability slot for rescheduled booking: {e}")
        
        # Try to update Google Calendar event
        calendar_updated = False
        if booking.google_event_id and user.google_calendar_connected:
            try:
                from app.services.google_calendar_service import GoogleCalendarService
                calendar_service = GoogleCalendarService(
                    access_token=user.google_access_token,
                    refresh_token=user.google_refresh_token,
                    db=db,
                    user_id=user.id
                )
                
                # Update calendar event
                updated_event = calendar_service.update_event(
                    event_id=booking.google_event_id,
                    title=f"Meeting with {booking.guest_name}",
                    start_time=new_start_time,
                    end_time=new_end_time,
                    description=booking.guest_message
                )
                
                if updated_event:
                    calendar_updated = True
                    booking.sync_status = "synced"
                    booking.last_synced = datetime.utcnow()
                    print(f"✅ Event rescheduled in calendar and updated in DB for booking {booking.id}")
                else:
                    booking.sync_status = "failed"
                    booking.sync_error = "Calendar event update failed"
                    print(f"⚠️ Event updated in DB but calendar update failed for booking {booking.id}")
                    
            except Exception as e:
                booking.sync_status = "failed"
                booking.sync_error = str(e)
                print(f"❌ Calendar update failed for booking {booking.id}: {e}")
        
        # Commit changes
        db.commit()
        
        if calendar_updated and slot_created:
            print(f"✅ Booking {booking.id} rescheduled: Event updated in calendar and DB, new slot created")
        elif calendar_updated:
            print(f"✅ Booking {booking.id} rescheduled: Event updated in calendar and DB, but slot creation failed")
        elif slot_created:
            print(f"✅ Booking {booking.id} rescheduled: Event updated in DB and new slot created, but calendar update failed")
        else:
            print(f"✅ Booking {booking.id} rescheduled: Event updated in DB only")
        
        return {
            "success": True,
            "message": "Booking rescheduled successfully",
            "booking_id": booking.id,
            "calendar_updated": calendar_updated,
            "slot_created": slot_created
        }
        
    except Exception as e:
        db.rollback()
        print(f"❌ Booking rescheduling failed: {e}")
        return {"success": False, "message": f"Rescheduling failed: {str(e)}"}


def format_bookings_for_template(db: Session, user_id: int, user: User) -> List[Dict[str, Any]]:
    """Format bookings data for template display with proper field names."""
    from datetime import datetime, timedelta, timezone
    
    # Get database bookings only (database-as-source-of-truth)
    db_bookings = get_bookings_for_user(db, user_id)
    
    # Convert database bookings to template format
    all_bookings = []
    for booking in db_bookings:
        all_bookings.append({
            "id": booking.id,
            "guest_name": booking.guest_name,
            "guest_email": booking.guest_email,
            "start_time": booking.start_time.strftime("%B %d, %Y at %I:%M %p"),
            "end_time": booking.end_time.strftime("%I:%M %p"),
            "status": booking.status,
            "source": "database",
            "guest_message": booking.guest_message,
            "datetime": booking.start_time,
            "google_event_id": booking.google_event_id,
            "sync_status": booking.sync_status
        })
    
    return all_bookings 


def get_filtered_bookings_for_template(
    db: Session, 
    user_id: int, 
    user: User,
    status_filter: str = "",
    time_filter: str = "",
    search_filter: str = ""
) -> List[Dict[str, Any]]:
    """Get filtered and formatted bookings for template display."""
    from datetime import datetime, timedelta, timezone
    
    # Get all bookings (database + calendar)
    all_bookings = format_bookings_for_template(db, user_id, user)
    
    # Apply status filter
    if status_filter:
        all_bookings = [b for b in all_bookings if b['status'] == status_filter]
    
    # Apply time filter
    if time_filter:
        today = datetime.now().date()
        
        # Extract date from start_time for filtering
        for booking in all_bookings:
            try:
                # Parse the formatted start_time to get date
                start_time_str = booking['start_time']
                # Extract date part from "Month DD, YYYY at HH:MM AM/PM"
                date_part = start_time_str.split(' at ')[0]
                booking_date = datetime.strptime(date_part, "%B %d, %Y").date()
                booking['_date'] = booking_date.strftime("%Y-%m-%d")  # For filtering
            except:
                booking['_date'] = "1970-01-01"  # Fallback date
        
        if time_filter == "today":
            all_bookings = [b for b in all_bookings if b['_date'] == today.strftime("%Y-%m-%d")]
        elif time_filter == "week":
            week_start = today - timedelta(days=today.weekday())
            week_end = week_start + timedelta(days=6)
            all_bookings = [b for b in all_bookings if week_start.strftime("%Y-%m-%d") <= b['_date'] <= week_end.strftime("%Y-%m-%d")]
        elif time_filter == "month":
            month_start = today.replace(day=1)
            if today.month == 12:
                month_end = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
            else:
                month_end = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
            all_bookings = [b for b in all_bookings if month_start.strftime("%Y-%m-%d") <= b['_date'] <= month_end.strftime("%Y-%m-%d")]
        elif time_filter == "past":
            all_bookings = [b for b in all_bookings if b['_date'] < today.strftime("%Y-%m-%d")]
    
    # Apply search filter
    if search_filter:
        all_bookings = [b for b in all_bookings if 
                       search_filter in b['guest_name'].lower() or 
                       search_filter in b['guest_email'].lower()]
    
    # Sort by datetime (newest first)
    all_bookings.sort(key=lambda x: x['datetime'], reverse=True)
    
    # Remove temporary _date field used for filtering
    for booking in all_bookings:
        if '_date' in booking:
            del booking['_date']
    
    return all_bookings 