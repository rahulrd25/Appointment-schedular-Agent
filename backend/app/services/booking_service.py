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
    """Create a new booking for a specific availability slot."""
    
    # Check if slot is available
    if not check_slot_availability(db, slot_id):
        return None
    
    slot = get_availability_slot(db, slot_id)
    if not slot:
        return None
    
    # Create the booking
    db_booking = Booking(
        host_user_id=host_user.id,
        availability_slot_id=slot_id,
        guest_name=booking_data.guest_name,
        guest_email=booking_data.guest_email,
        guest_message=booking_data.guest_message,
        start_time=slot.start_time,
        end_time=slot.end_time,
        status="confirmed"
    )
    
    # Try to create Google Calendar event if host has credentials
    google_event_id = None
    if host_user.google_access_token and host_user.google_refresh_token:
        try:
            calendar_service = GoogleCalendarService(
                access_token=host_user.google_access_token,
                refresh_token=host_user.google_refresh_token,
                db=db,
                user_id=host_user.id
            )
            
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
            
            # Verify that the event was actually created
            if not google_event_id:
                raise Exception("Failed to create Google Calendar event - no event ID returned")
            
            print(f"✅ Google Calendar booking event created successfully: {google_event_id}")
            
        except Exception as e:
            print(f"Failed to create Google Calendar event: {e}")
            # Continue with booking even if calendar event creation fails
    
    db_booking.google_event_id = google_event_id
    
    # Mark the availability slot as unavailable (booked)
    slot.is_available = False
    
    db.add(db_booking)
    db.commit()
    db.refresh(db_booking)
    
    # Log success if both database and calendar were created
    if google_event_id:
        print(f"✅ Booking successfully created in DB and calendar for user {host_user.id}")
    else:
        print(f"⚠️ Booking created in DB only (no calendar connection) for user {host_user.id}")
    
    # Send confirmation emails with proper success/failure tracking
    emails_sent = False
    if host_user.google_access_token and host_user.google_refresh_token:
        try:
            from app.services.notification_service import NotificationService
            
            notification_service = NotificationService()
            
            notification_results = notification_service.send_booking_confirmation_notifications(
                guest_email=booking_data.guest_email,
                guest_name=booking_data.guest_name,
                host_email=host_user.email,
                host_name=host_user.full_name,
                booking=db_booking,
                host_access_token=host_user.google_access_token,
                host_refresh_token=host_user.google_refresh_token
            )
            
            emails_sent = notification_results["success"]
        except Exception as e:
            print(f"Failed to send booking confirmation notifications: {e}")
            emails_sent = False
    
    # Return booking with email status (for consistency with other functions)
    # Note: We don't return a dict like other functions since this is the main create_booking function
    # that returns the booking object directly
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
                    refresh_token=host.google_refresh_token
                )
                calendar_service.delete_event(booking.google_event_id)
        except Exception as e:
            print(f"Failed to delete Google Calendar event: {e}")
    
    db.commit()
    return True


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
        if not success:
            return {
                "success": False,
                "message": "Failed to cancel booking",
                "source": "database",
                "calendar_deleted": False,
                "emails_sent": False
            }
        
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
    """Reschedule a booking with full calendar and notification handling."""
    # Get the current booking
    booking = get_booking(db, booking_id, user.id)
    if not booking:
        return {
            "success": False,
            "message": "Booking not found",
            "calendar_updated": False,
            "emails_sent": False
        }
    
    # Store original times for rollback
    original_start_time = booking.start_time
    original_end_time = booking.end_time
    original_event_id = booking.google_event_id
    
    # Create booking update
    from app.schemas.schemas import BookingUpdate
    booking_update = BookingUpdate(
        start_time=new_start_time,
        end_time=new_end_time,
        status="rescheduled"
    )
    
    # Update booking in database (but don't let it update calendar - we'll do that separately)
    updated_booking = update_booking(db, booking_id, booking_update, user.id, update_calendar=False)
    if not updated_booking:
        return {
            "success": False,
            "message": "Failed to update booking in database",
            "calendar_updated": False,
            "emails_sent": False
        }
    
    # Handle calendar event update/creation
    calendar_updated = False
    calendar_event_id = None
    
    if user.google_access_token and user.google_refresh_token:
        try:
            calendar_service = GoogleCalendarService(
                access_token=user.google_access_token,
                refresh_token=user.google_refresh_token,
                db=db,
                user_id=user.id
            )
            
            if booking.google_event_id:
                # Check if event exists and update it
                existing_event = calendar_service.get_event(booking.google_event_id)
                if existing_event:
                    calendar_service.update_event(
                        event_id=booking.google_event_id,
                        start_time=new_start_time,
                        end_time=new_end_time
                    )
                    calendar_event_id = booking.google_event_id
                else:
                    # Event not found, create new one
                    created_event = calendar_service.create_booking_event(
                        title=f"Meeting with {booking.guest_name}",
                        start_time=new_start_time,
                        end_time=new_end_time,
                        guest_email=booking.guest_email,
                        host_email=user.email,
                        description=f"Rescheduled meeting with {booking.guest_name}\n\nGuest: {booking.guest_name}\nEmail: {booking.guest_email}"
                    )
                    calendar_event_id = created_event.get('id')
                    booking.google_event_id = calendar_event_id
                    db.commit()
            else:
                # No existing event, create new one
                created_event = calendar_service.create_booking_event(
                    title=f"Meeting with {booking.guest_name}",
                    start_time=new_start_time,
                    end_time=new_end_time,
                    guest_email=booking.guest_email,
                    host_email=user.email,
                    description=f"Rescheduled meeting with {booking.guest_name}\n\nGuest: {booking.guest_name}\nEmail: {booking.guest_email}"
                )
                calendar_event_id = created_event.get('id')
                booking.google_event_id = calendar_event_id
                db.commit()
            
            calendar_updated = True
            
        except Exception as e:
            # Rollback database changes if calendar failed
            if booking.google_event_id != original_event_id:
                booking.google_event_id = original_event_id
                db.commit()
            
            return {
                "success": False,
                "message": f"Failed to update Google Calendar: {str(e)}",
                "calendar_updated": False,
                "emails_sent": False
            }
    
    # Send email notifications
    emails_sent = False
    if user.google_access_token and user.google_refresh_token:
        try:
            from app.services.notification_service import NotificationService
            
            notification_service = NotificationService()
            
            notification_results = notification_service.send_reschedule_notifications(
                guest_email=booking.guest_email,
                guest_name=booking.guest_name,
                host_email=user.email,
                host_name=user.full_name,
                booking=updated_booking,
                old_start_time=original_start_time,
                reason=reason,
                host_access_token=user.google_access_token,
                host_refresh_token=user.google_refresh_token
            )
            
            emails_sent = notification_results["success"]
        except Exception as e:
            print(f"Failed to send reschedule notifications: {e}")
            emails_sent = False
    
    return {
        "success": True,
        "message": "Booking rescheduled successfully",
        "calendar_updated": calendar_updated,
        "emails_sent": emails_sent,
        "booking": updated_booking
    } 


def format_bookings_for_template(db: Session, user_id: int, user: User) -> List[Dict[str, Any]]:
    """Format bookings data for template display with proper field names."""
    from datetime import datetime, timedelta, timezone
    
    # Get database bookings
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
            "datetime": booking.start_time
        })
    
    # Get calendar events if connected
    if user.google_calendar_connected and user.google_access_token:
        try:
            calendar_service = GoogleCalendarService(
                access_token=user.google_access_token,
                refresh_token=user.google_refresh_token,
                db=db,
                user_id=user.id
            )
            
            # Get events from past 30 days to next 30 days
            start_date = datetime.now(timezone.utc) - timedelta(days=30)
            end_date = datetime.now(timezone.utc) + timedelta(days=30)
            calendar_events = calendar_service.get_events(start_date, end_date)
            
            # Process calendar events
            for event in calendar_events:
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
                    
                    # Add to all bookings
                    all_bookings.append({
                        "id": f"calendar_{event.get('id')}",
                        "guest_name": event.get('summary', 'Untitled Event'),
                        "guest_email": event.get('organizer', {}).get('email', ''),
                        "start_time": event_start_dt.strftime("%B %d, %Y at %I:%M %p"),
                        "end_time": event_end_dt.strftime("%I:%M %p"),
                        "status": "confirmed",
                        "source": "calendar",
                        "calendar_id": event.get('id'),
                        "description": event.get('description', ''),
                        "location": event.get('location', ''),
                        "guest_message": event.get('description', ''),
                        "datetime": event_start_dt
                    })
            
        except Exception as e:
            print(f"Error accessing Google Calendar: {e}")
    
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