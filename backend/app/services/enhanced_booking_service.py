"""
Enhanced Booking Service - Uses new calendar architecture.
This service maintains all existing functionality while adding proper sync orchestration.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
import logging

from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.models import Booking, AvailabilitySlot, User
from app.schemas.schemas import BookingCreate, BookingUpdate, PublicBookingCreate
from app.services.availability_service import get_availability_slot, check_slot_availability
from app.services.repositories.event_repository import EventRepository
from app.core.calendar_architecture import CalendarSyncService, create_calendar_provider, CalendarProviderType
from app.core.sync_config import get_sync_config

# Configure logging
logger = logging.getLogger(__name__)


class EnhancedBookingService:
    """
    Enhanced booking service that uses the new calendar architecture.
    Maintains all existing functionality while adding proper sync orchestration.
    """
    
    def __init__(self, db: Session, user: User):
        """
        Initialize the enhanced booking service.
        
        Args:
            db: Database session
            user: User for whom operations are performed
        """
        self.db = db
        self.user = user
        self.event_repo = EventRepository(db)
        self.sync_service = CalendarSyncService(db, user.id)
        self.sync_config = get_sync_config()
        
        # Register calendar providers if user has tokens
        self._register_providers()
    
    def _register_providers(self) -> None:
        """Register available calendar providers for the user."""
        try:
            # Register Google Calendar provider
            if (self.user.google_access_token and 
                self.user.google_refresh_token and 
                self.sync_config.is_provider_enabled("google")):
                
                google_provider = create_calendar_provider(
                    CalendarProviderType.GOOGLE,
                    access_token=self.user.google_access_token,
                    refresh_token=self.user.google_refresh_token,
                    db=self.db,
                    user_id=self.user.id
                )
                self.sync_service.register_provider(google_provider)
                logger.info(f"Registered Google Calendar provider for user {self.user.id}")
            
            # Future: Register Microsoft Calendar provider
            # if self.user.microsoft_access_token and self.sync_config.is_provider_enabled("microsoft"):
            #     microsoft_provider = create_calendar_provider(...)
            #     self.sync_service.register_provider(microsoft_provider)
            
        except Exception as e:
            logger.error(f"Failed to register calendar providers for user {self.user.id}: {str(e)}")
    
    def create_booking(self, booking_data: PublicBookingCreate, slot_id: int) -> Optional[Booking]:
        """
        Create a new booking with enhanced sync orchestration.
        
        This follows the database-first architecture:
        1. Create booking in database (source of truth)
        2. Sync to all registered calendar providers
        3. Track sync status and handle failures
        
        Args:
            booking_data: Booking creation data
            slot_id: Availability slot ID
            
        Returns:
            Created booking or None if creation fails
        """
        try:
            # Check if slot is available (existing functionality)
            if not check_slot_availability(self.db, slot_id):
                logger.warning(f"Slot {slot_id} is not available for booking")
                return None
            
            slot = get_availability_slot(self.db, slot_id)
            if not slot:
                logger.error(f"Slot {slot_id} not found")
                return None
            
            # Create booking data for repository
            repo_booking_data = {
                'slot_id': slot_id,
                'guest_name': booking_data.guest_name,
                'guest_email': booking_data.guest_email,
                'guest_message': booking_data.guest_message,
                'start_time': slot.start_time,
                'end_time': slot.end_time
            }
            
            # Create booking in database first (source of truth)
            booking = self.event_repo.create_booking(repo_booking_data, self.user.id)
            logger.info(f"Created booking {booking.id} in database for user {self.user.id}")
            
            # Mark slot as unavailable
            slot.is_available = False
            self.db.commit()
            
            # Sync to calendar providers if enabled
            sync_results = {}
            if self.sync_config.should_sync_bookings("google") and self.sync_service.providers:
                try:
                    # Prepare event data for calendar sync
                    event_sync_data = {
                        'summary': f"Meeting with {booking_data.guest_name}",
                        'description': self._build_event_description(booking_data),
                        'start': {
                            'dateTime': slot.start_time.isoformat(),
                            'timeZone': 'UTC'
                        },
                        'end': {
                            'dateTime': slot.end_time.isoformat(),
                            'timeZone': 'UTC'
                        }
                    }
                    
                    # Sync to all registered providers
                    sync_results = self.sync_service.sync_event_to_providers(
                        str(booking.id),
                        event_sync_data,
                        "create"
                    )
                    
                    # Update booking with provider event IDs
                    self._update_booking_with_sync_results(booking, sync_results)
                    
                    logger.info(f"Successfully synced booking {booking.id} to calendar providers")
                    
                except Exception as e:
                    logger.error(f"Failed to sync booking {booking.id} to calendar providers: {str(e)}")
                    # Continue with booking even if sync fails
            
            # Send confirmation emails (existing functionality)
            self._send_booking_confirmation_emails(booking, booking_data)
            
            return booking
            
        except Exception as e:
            logger.error(f"Failed to create booking: {str(e)}")
            self.db.rollback()
            return None
    
    def update_booking(self, booking_id: int, update_data: Dict[str, Any]) -> Optional[Booking]:
        """
        Update a booking with enhanced sync orchestration.
        
        Args:
            booking_id: Booking ID to update
            update_data: Data to update
            
        Returns:
            Updated booking or None if update fails
        """
        try:
            # Get existing booking
            booking = self.event_repo.get_booking(booking_id)
            if not booking or booking.host_user_id != self.user.id:
                logger.warning(f"Booking {booking_id} not found or access denied for user {self.user.id}")
                return None
            
            # Update booking in database first
            updated_booking = self.event_repo.update_booking(booking_id, update_data)
            if not updated_booking:
                logger.error(f"Failed to update booking {booking_id} in database")
                return None
            
            # Sync to calendar providers if enabled
            if self.sync_config.should_sync_bookings("google") and self.sync_service.providers:
                try:
                    # Prepare updated event data
                    event_sync_data = {
                        'summary': f"Meeting with {updated_booking.guest_name}",
                        'description': self._build_event_description_from_booking(updated_booking),
                        'start': {
                            'dateTime': updated_booking.start_time.isoformat(),
                            'timeZone': 'UTC'
                        },
                        'end': {
                            'dateTime': updated_booking.end_time.isoformat(),
                            'timeZone': 'UTC'
                        }
                    }
                    
                    # Sync to all registered providers
                    sync_results = self.sync_service.sync_event_to_providers(
                        str(booking_id),
                        event_sync_data,
                        "update"
                    )
                    
                    # Update booking with sync results
                    self._update_booking_with_sync_results(updated_booking, sync_results)
                    
                    logger.info(f"Successfully synced booking {booking_id} update to calendar providers")
                    
                except Exception as e:
                    logger.error(f"Failed to sync booking {booking_id} update to calendar providers: {str(e)}")
            
            return updated_booking
            
        except Exception as e:
            logger.error(f"Failed to update booking {booking_id}: {str(e)}")
            self.db.rollback()
            return None
    
    def delete_booking(self, booking_id: int) -> bool:
        """
        Delete a booking with enhanced sync orchestration.
        
        Args:
            booking_id: Booking ID to delete
            
        Returns:
            True if deletion successful, False otherwise
        """
        try:
            # Get existing booking
            booking = self.event_repo.get_booking(booking_id)
            if not booking or booking.host_user_id != self.user.id:
                logger.warning(f"Booking {booking_id} not found or access denied for user {self.user.id}")
                return False
            
            # Sync deletion to calendar providers if enabled
            if self.sync_config.should_sync_bookings("google") and self.sync_service.providers:
                try:
                    # Sync deletion to all registered providers
                    sync_results = self.sync_service.sync_event_to_providers(
                        str(booking_id),
                        {'id': booking.google_event_id},
                        "delete"
                    )
                    
                    logger.info(f"Successfully synced booking {booking_id} deletion to calendar providers")
                    
                except Exception as e:
                    logger.error(f"Failed to sync booking {booking_id} deletion to calendar providers: {str(e)}")
            
            # Delete booking from database
            success = self.event_repo.delete_booking(booking_id)
            if success:
                logger.info(f"Successfully deleted booking {booking_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to delete booking {booking_id}: {str(e)}")
            self.db.rollback()
            return False
    
    def get_bookings_for_user(self, status: str = None) -> List[Booking]:
        """Get all bookings for the current user."""
        return self.event_repo.get_bookings_for_user(self.user.id, status)
    
    def get_booking(self, booking_id: int) -> Optional[Booking]:
        """Get a specific booking for the current user."""
        booking = self.event_repo.get_booking(booking_id)
        if booking and booking.host_user_id == self.user.id:
            return booking
        return None
    
    def get_sync_status(self, booking_id: int) -> Dict[str, Any]:
        """Get sync status for a booking."""
        return self.event_repo.get_sync_status(booking_id, "booking")
    
    # Helper methods
    def _build_event_description(self, booking_data: PublicBookingCreate) -> str:
        """Build event description from booking data."""
        description = f"Meeting scheduled via booking system.\n\nGuest: {booking_data.guest_name}\nEmail: {booking_data.guest_email}"
        if booking_data.guest_message:
            description += f"\nMessage: {booking_data.guest_message}"
        return description
    
    def _build_event_description_from_booking(self, booking: Booking) -> str:
        """Build event description from booking object."""
        description = f"Meeting scheduled via booking system.\n\nGuest: {booking.guest_name}\nEmail: {booking.guest_email}"
        if booking.guest_message:
            description += f"\nMessage: {booking.guest_message}"
        return description
    
    def _update_booking_with_sync_results(self, booking: Booking, sync_results: Dict[str, Any]) -> None:
        """Update booking with sync results from providers."""
        for provider_name, result in sync_results.items():
            if result.get('success') and result.get('result', {}).get('id'):
                if provider_name == 'google':
                    booking.google_event_id = result['result']['id']
                # Future: Handle other providers
                break
        
        self.db.commit()
    
    def _send_booking_confirmation_emails(self, booking: Booking, booking_data: PublicBookingCreate) -> None:
        """Send booking confirmation emails (existing functionality)."""
        try:
            from app.services.notification_service import NotificationService
            
            notification_service = NotificationService()
            
            notification_results = notification_service.send_booking_confirmation_notifications(
                guest_email=booking_data.guest_email,
                guest_name=booking_data.guest_name,
                host_email=self.user.email,
                host_name=self.user.full_name,
                booking=booking,
                host_access_token=self.user.google_access_token,
                host_refresh_token=self.user.google_refresh_token
            )
            
            if notification_results["success"]:
                logger.info(f"Successfully sent booking confirmation emails for booking {booking.id}")
            else:
                logger.warning(f"Failed to send booking confirmation emails for booking {booking.id}")
                
        except Exception as e:
            logger.error(f"Failed to send booking confirmation emails for booking {booking.id}: {str(e)}") 