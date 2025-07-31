"""
Event Repository - Database operations layer for events.
This maintains existing functionality while adding sync metadata tracking.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.models.models import Booking, AvailabilitySlot, User
from app.core.calendar_architecture import SyncMetadata, SyncStatus, CalendarProviderType


class EventRepository:
    """
    Repository for event database operations.
    Maintains existing functionality while adding sync tracking.
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    # Booking operations (maintains existing functionality)
    def create_booking(self, booking_data: Dict[str, Any], user_id: int) -> Booking:
        """Create a booking with sync metadata tracking."""
        # Create the booking (existing functionality)
        booking = Booking(
            host_user_id=user_id,
            availability_slot_id=booking_data.get('slot_id'),
            guest_name=booking_data.get('guest_name'),
            guest_email=booking_data.get('guest_email'),
            guest_message=booking_data.get('guest_message'),
            start_time=booking_data.get('start_time'),
            end_time=booking_data.get('end_time'),
            status="confirmed"
        )
        
        self.db.add(booking)
        self.db.commit()
        self.db.refresh(booking)
        
        # Add sync metadata tracking
        self._add_sync_metadata(booking.id, "booking", CalendarProviderType.GOOGLE)
        
        return booking
    
    def update_booking(self, booking_id: int, update_data: Dict[str, Any]) -> Optional[Booking]:
        """Update a booking with sync metadata tracking."""
        booking = self.db.query(Booking).filter(Booking.id == booking_id).first()
        if not booking:
            return None
        
        # Update booking fields
        for key, value in update_data.items():
            if hasattr(booking, key):
                setattr(booking, key, value)
        
        self.db.commit()
        self.db.refresh(booking)
        
        # Update sync metadata
        self._update_sync_metadata(booking.id, "booking", CalendarProviderType.GOOGLE)
        
        return booking
    
    def delete_booking(self, booking_id: int) -> bool:
        """Delete a booking with sync metadata tracking."""
        booking = self.db.query(Booking).filter(Booking.id == booking_id).first()
        if not booking:
            return False
        
        # Mark sync metadata as deleted
        self._update_sync_metadata(booking.id, "booking", CalendarProviderType.GOOGLE, 
                                 sync_status=SyncStatus.FAILED, 
                                 error_message="Booking deleted")
        
        self.db.delete(booking)
        self.db.commit()
        
        return True
    
    def get_booking(self, booking_id: int) -> Optional[Booking]:
        """Get a booking by ID."""
        return self.db.query(Booking).filter(Booking.id == booking_id).first()
    
    def get_bookings_for_user(self, user_id: int, status: str = None) -> List[Booking]:
        """Get all bookings for a user."""
        query = self.db.query(Booking).filter(Booking.host_user_id == user_id)
        if status:
            query = query.filter(Booking.status == status)
        return query.order_by(Booking.start_time.desc()).all()
    
    # Availability slot operations (maintains existing functionality)
    def create_availability_slot(self, slot_data: Dict[str, Any], user_id: int) -> AvailabilitySlot:
        """Create an availability slot with sync metadata tracking."""
        slot = AvailabilitySlot(
            user_id=user_id,
            start_time=slot_data.get('start_time'),
            end_time=slot_data.get('end_time'),
            is_available=slot_data.get('is_available', True)
        )
        
        self.db.add(slot)
        self.db.commit()
        self.db.refresh(slot)
        
        # Add sync metadata tracking
        self._add_sync_metadata(slot.id, "availability", CalendarProviderType.GOOGLE)
        
        return slot
    
    def update_availability_slot(self, slot_id: int, update_data: Dict[str, Any]) -> Optional[AvailabilitySlot]:
        """Update an availability slot with sync metadata tracking."""
        slot = self.db.query(AvailabilitySlot).filter(AvailabilitySlot.id == slot_id).first()
        if not slot:
            return None
        
        # Update slot fields
        for key, value in update_data.items():
            if hasattr(slot, key):
                setattr(slot, key, value)
        
        self.db.commit()
        self.db.refresh(slot)
        
        # Update sync metadata
        self._update_sync_metadata(slot.id, "availability", CalendarProviderType.GOOGLE)
        
        return slot
    
    def delete_availability_slot(self, slot_id: int) -> bool:
        """Delete an availability slot with sync metadata tracking."""
        slot = self.db.query(AvailabilitySlot).filter(AvailabilitySlot.id == slot_id).first()
        if not slot:
            return False
        
        # Mark sync metadata as deleted
        self._update_sync_metadata(slot.id, "availability", CalendarProviderType.GOOGLE,
                                 sync_status=SyncStatus.FAILED,
                                 error_message="Slot deleted")
        
        self.db.delete(slot)
        self.db.commit()
        
        return True
    
    def get_availability_slot(self, slot_id: int) -> Optional[AvailabilitySlot]:
        """Get an availability slot by ID."""
        return self.db.query(AvailabilitySlot).filter(AvailabilitySlot.id == slot_id).first()
    
    def get_availability_slots_for_user(self, user_id: int) -> List[AvailabilitySlot]:
        """Get all availability slots for a user."""
        return self.db.query(AvailabilitySlot).filter(
            AvailabilitySlot.user_id == user_id
        ).order_by(AvailabilitySlot.start_time).all()
    
    # Sync metadata operations (new functionality)
    def _add_sync_metadata(self, event_id: int, event_type: str, 
                          provider_type: CalendarProviderType, 
                          provider_event_id: str = None,
                          sync_status: SyncStatus = SyncStatus.PENDING,
                          error_message: str = None):
        """Add sync metadata for an event."""
        # For now, we'll store this in the existing models
        # In the future, we can create a separate SyncMetadata table
        metadata = SyncMetadata(
            event_id=str(event_id),
            provider_type=provider_type,
            provider_event_id=provider_event_id,
            sync_status=sync_status,
            error_message=error_message
        )
        
        # Store metadata in the event model (existing functionality)
        if event_type == "booking":
            booking = self.get_booking(event_id)
            if booking:
                booking.google_event_id = provider_event_id
                self.db.commit()
        elif event_type == "availability":
            slot = self.get_availability_slot(event_id)
            if slot:
                slot.google_event_id = provider_event_id
                self.db.commit()
    
    def _update_sync_metadata(self, event_id: int, event_type: str,
                             provider_type: CalendarProviderType,
                             sync_status: SyncStatus = SyncStatus.SYNCED,
                             error_message: str = None):
        """Update sync metadata for an event."""
        # Update the existing sync tracking
        if event_type == "booking":
            booking = self.get_booking(event_id)
            if booking and error_message:
                # We could add a sync_status field to the Booking model in the future
                pass
        elif event_type == "availability":
            slot = self.get_availability_slot(event_id)
            if slot and error_message:
                # We could add a sync_status field to the AvailabilitySlot model in the future
                pass
    
    def get_sync_status(self, event_id: int, event_type: str) -> Dict[str, Any]:
        """Get sync status for an event."""
        if event_type == "booking":
            booking = self.get_booking(event_id)
            if booking:
                return {
                    "synced": booking.google_event_id is not None,
                    "provider_event_id": booking.google_event_id,
                    "last_updated": booking.updated_at if hasattr(booking, 'updated_at') else None
                }
        elif event_type == "availability":
            slot = self.get_availability_slot(event_id)
            if slot:
                return {
                    "synced": slot.google_event_id is not None,
                    "provider_event_id": slot.google_event_id,
                    "last_updated": slot.updated_at if hasattr(slot, 'updated_at') else None
                }
        
        return {"synced": False, "provider_event_id": None, "last_updated": None} 