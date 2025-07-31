from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.models.models import User
from app.services.booking_service import get_booking, update_booking
from app.services.google_calendar_service import GoogleCalendarService
from app.services.notification_service import NotificationService
from app.schemas.schemas import BookingUpdate


class RescheduleService:
    """Service to handle booking reschedule operations with proper error handling."""
    
    def __init__(self, db: Session, user: User):
        self.db = db
        self.user = user
        self.calendar_service = None
        
        # Initialize calendar service if user has Google tokens
        if user.google_access_token and user.google_refresh_token:
            try:
                self.calendar_service = GoogleCalendarService(
                    access_token=user.google_access_token,
                    refresh_token=user.google_refresh_token,
                    db=db,
                    user_id=user.id
                )
            except Exception as e:
                print(f"Failed to initialize calendar service: {e}")
                self.calendar_service = None
    
    def reschedule_booking(
        self, 
        booking_id: int, 
        new_start_time: datetime, 
        new_end_time: datetime, 
        reason: str = ""
    ) -> Dict[str, Any]:
        """
        Reschedule a booking with comprehensive error handling.
        
        Returns:
            Dict with success status, message, and details
        """
        try:
            # Step 1: Validate booking exists and can be rescheduled
            booking = get_booking(self.db, booking_id, self.user.id)
            if not booking:
                return {
                    "success": False,
                    "message": "Booking not found",
                    "error_type": "not_found"
                }
            
            if booking.status != "confirmed":
                return {
                    "success": False,
                    "message": "Only confirmed bookings can be rescheduled",
                    "error_type": "invalid_status"
                }
            
            # Store original data for rollback
            original_start_time = booking.start_time
            original_end_time = booking.end_time
            original_event_id = booking.google_event_id
            
            # Step 2: Update database booking
            booking_update = BookingUpdate(
                start_time=new_start_time,
                end_time=new_end_time,
                status="rescheduled"
            )
            
            updated_booking = update_booking(
                self.db, 
                booking_id, 
                booking_update, 
                self.user.id, 
                update_calendar=False
            )
            
            if not updated_booking:
                return {
                    "success": False,
                    "message": "Failed to update booking in database",
                    "error_type": "database_error"
                }
            
            # Step 3: Handle calendar event update/creation
            calendar_updated = False
            calendar_event_id = None
            
            if self.calendar_service:
                try:
                    if booking.google_event_id:
                        # Try to update existing event
                        existing_event = self.calendar_service.get_event(booking.google_event_id)
                        if existing_event:
                            self.calendar_service.update_event(
                                event_id=booking.google_event_id,
                                start_time=new_start_time,
                                end_time=new_end_time
                            )
                            calendar_event_id = booking.google_event_id
                        else:
                            # Event not found, create new one
                            created_event = self.calendar_service.create_booking_event(
                                title=f"Meeting with {booking.guest_name}",
                                start_time=new_start_time,
                                end_time=new_end_time,
                                guest_email=booking.guest_email,
                                host_email=self.user.email,
                                description=f"Rescheduled meeting with {booking.guest_name}\n\nGuest: {booking.guest_name}\nEmail: {booking.guest_email}"
                            )
                            calendar_event_id = created_event.get('id')
                            booking.google_event_id = calendar_event_id
                            self.db.commit()
                    else:
                        # No existing event, create new one
                        created_event = self.calendar_service.create_booking_event(
                            title=f"Meeting with {booking.guest_name}",
                            start_time=new_start_time,
                            end_time=new_end_time,
                            guest_email=booking.guest_email,
                            host_email=self.user.email,
                            description=f"Rescheduled meeting with {booking.guest_name}\n\nGuest: {booking.guest_name}\nEmail: {booking.guest_email}"
                        )
                        calendar_event_id = created_event.get('id')
                        booking.google_event_id = calendar_event_id
                        self.db.commit()
                    
                    calendar_updated = True
                    
                except Exception as calendar_error:
                    # Rollback database changes if calendar failed
                    if booking.google_event_id != original_event_id:
                        booking.google_event_id = original_event_id
                        self.db.commit()
                    
                    return {
                        "success": False,
                        "message": f"Failed to update Google Calendar: {str(calendar_error)}",
                        "error_type": "calendar_error",
                        "calendar_error": str(calendar_error)
                    }
            
            # Step 4: Send email notifications
            emails_sent = False
            if self.calendar_service:
                try:
                    notification_service = NotificationService()
                    
                    notification_results = notification_service.send_reschedule_notifications(
                        guest_email=booking.guest_email,
                        guest_name=booking.guest_name,
                        host_email=self.user.email,
                        host_name=self.user.full_name,
                        booking=updated_booking,
                        old_start_time=original_start_time,
                        reason=reason,
                        host_access_token=self.user.google_access_token,
                        host_refresh_token=self.user.google_refresh_token
                    )
                    
                    emails_sent = notification_results["success"]
                    
                except Exception as email_error:
                    print(f"Failed to send reschedule notifications: {email_error}")
                    emails_sent = False
            
            # Step 5: Determine final status and return result
            if calendar_updated and emails_sent:
                return {
                    "success": True,
                    "message": "Booking rescheduled successfully! Google Calendar updated and notifications sent to both parties.",
                    "calendar_updated": True,
                    "emails_sent": True,
                    "booking": updated_booking
                }
            elif calendar_updated and not emails_sent:
                return {
                    "success": True,
                    "message": "Booking rescheduled and Google Calendar updated, but email notifications failed.",
                    "calendar_updated": True,
                    "emails_sent": False,
                    "booking": updated_booking
                }
            else:
                return {
                    "success": True,
                    "message": "Booking rescheduled successfully (Google Calendar not connected).",
                    "calendar_updated": False,
                    "emails_sent": False,
                    "booking": updated_booking
                }
                
        except Exception as e:
            return {
                "success": False,
                "message": f"Unexpected error during reschedule: {str(e)}",
                "error_type": "unexpected_error",
                "error": str(e)
            }
    
    def can_reschedule_booking(self, booking_id: int) -> Dict[str, Any]:
        """Check if a booking can be rescheduled."""
        try:
            booking = get_booking(self.db, booking_id, self.user.id)
            if not booking:
                return {
                    "can_reschedule": False,
                    "message": "Booking not found",
                    "error_type": "not_found"
                }
            
            if booking.status != "confirmed":
                return {
                    "can_reschedule": False,
                    "message": "Only confirmed bookings can be rescheduled",
                    "error_type": "invalid_status"
                }
            
            return {
                "can_reschedule": True,
                "message": "Booking can be rescheduled",
                "booking": booking
            }
            
        except Exception as e:
            return {
                "can_reschedule": False,
                "message": f"Error checking reschedule eligibility: {str(e)}",
                "error_type": "check_error"
            } 