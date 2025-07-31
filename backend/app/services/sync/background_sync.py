"""
Background Sync Service - Periodic synchronization with calendar providers.
This module handles background sync jobs to keep database and external calendars in sync.
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.models import Booking, User
from app.services.repositories.event_repository import EventRepository
from app.core.calendar_architecture import CalendarSyncService, create_calendar_provider, CalendarProviderType
from app.core.sync_config import get_sync_config

# Configure logging
logger = logging.getLogger(__name__)


class BackgroundSyncService:
    """
    Background synchronization service for periodic sync operations.
    Maintains existing functionality while adding automated sync capabilities.
    """
    
    def __init__(self):
        """Initialize the background sync service."""
        self.sync_config = get_sync_config()
        self.is_running = False
    
    async def start_periodic_sync(self) -> None:
        """
        Start periodic synchronization with calendar providers.
        
        This runs in the background and syncs:
        1. Failed syncs that need retry
        2. New bookings that haven't been synced
        3. Updated bookings that need re-sync
        """
        if self.is_running:
            logger.warning("Background sync service is already running")
            return
        
        self.is_running = True
        logger.info("Starting background sync service")
        
        try:
            while self.is_running:
                await self._perform_sync_cycle()
                await asyncio.sleep(self.sync_config.background_sync_interval)
                
        except Exception as e:
            logger.error(f"Background sync service failed: {str(e)}")
            self.is_running = False
    
    async def stop_periodic_sync(self) -> None:
        """Stop the periodic sync service."""
        self.is_running = False
        logger.info("Stopping background sync service")
    
    async def _perform_sync_cycle(self) -> None:
        """
        Perform one sync cycle.
        
        This method:
        1. Finds bookings that need sync
        2. Attempts to sync them to calendar providers
        3. Updates sync status and metadata
        """
        try:
            logger.debug("Starting sync cycle")
            
            # Get database session
            db = next(get_db())
            
            # Find bookings that need sync
            bookings_to_sync = self._find_bookings_needing_sync(db)
            
            if not bookings_to_sync:
                logger.debug("No bookings need sync in this cycle")
                return
            
            logger.info(f"Found {len(bookings_to_sync)} bookings that need sync")
            
            # Process each booking
            for booking in bookings_to_sync:
                await self._sync_single_booking(db, booking)
            
            logger.debug("Completed sync cycle")
            
        except Exception as e:
            logger.error(f"Failed to perform sync cycle: {str(e)}")
    
    def _find_bookings_needing_sync(self, db: Session) -> List[Booking]:
        """
        Find bookings that need synchronization.
        
        Args:
            db: Database session
            
        Returns:
            List of bookings that need sync
        """
        try:
            # Check if sync_status column exists
            try:
                # Try to query sync_status to see if column exists
                test_query = db.query(Booking.sync_status).limit(1).first()
                sync_columns_exist = True
            except Exception:
                # Column doesn't exist yet, use fallback logic
                sync_columns_exist = False
                logger.warning("Sync status columns not found in database. Using fallback logic.")
            
            if sync_columns_exist:
                # Use sync status logic
                recent_cutoff = datetime.utcnow() - timedelta(hours=1)
                
                bookings = db.query(Booking).filter(
                    (Booking.sync_status.in_(['pending', 'failed'])) |
                    ((Booking.updated_at > recent_cutoff) & (Booking.sync_status == 'synced'))
                ).all()
            else:
                # Fallback: find bookings without google_event_id
                bookings = db.query(Booking).filter(
                    Booking.google_event_id.is_(None)
                ).all()
            
            return bookings
            
        except Exception as e:
            logger.error(f"Failed to find bookings needing sync: {str(e)}")
            return []
    
    async def _sync_single_booking(self, db: Session, booking: Booking) -> None:
        """
        Sync a single booking to calendar providers.
        
        Args:
            db: Database session
            booking: Booking to sync
        """
        try:
            # Get user for this booking
            user = db.query(User).filter(User.id == booking.host_user_id).first()
            if not user:
                logger.warning(f"No user found for booking {booking.id}")
                return
            
            # Initialize sync service for this user
            sync_service = CalendarSyncService(db, user.id)
            
            # Register calendar providers
            if (user.google_access_token and 
                user.google_refresh_token and 
                self.sync_config.is_provider_enabled("google")):
                
                google_provider = create_calendar_provider(
                    CalendarProviderType.GOOGLE,
                    access_token=user.google_access_token,
                    refresh_token=user.google_refresh_token,
                    db=db,
                    user_id=user.id
                )
                sync_service.register_provider(google_provider)
            
            # Prepare event data for sync
            event_sync_data = {
                'summary': f"Meeting with {booking.guest_name}",
                'description': self._build_event_description(booking),
                'start': {
                    'dateTime': booking.start_time.isoformat(),
                    'timeZone': 'UTC'
                },
                'end': {
                    'dateTime': booking.end_time.isoformat(),
                    'timeZone': 'UTC'
                }
            }
            
            # Sync to providers
            sync_results = sync_service.sync_event_to_providers(
                str(booking.id),
                event_sync_data,
                "create" if not booking.google_event_id else "update"
            )
            
            # Update booking with sync results
            self._update_booking_with_sync_results(booking, sync_results)
            
            logger.info(f"Successfully synced booking {booking.id} in background")
            
        except Exception as e:
            logger.error(f"Failed to sync booking {booking.id} in background: {str(e)}")
    
    def _build_event_description(self, booking: Booking) -> str:
        """Build event description from booking."""
        description = f"Meeting scheduled via booking system.\n\nGuest: {booking.guest_name}\nEmail: {booking.guest_email}"
        if booking.guest_message:
            description += f"\nMessage: {booking.guest_message}"
        return description
    
    def _update_booking_with_sync_results(self, booking: Booking, sync_results: Dict[str, Any]) -> None:
        """Update booking with sync results from providers."""
        try:
            # Check if sync columns exist
            has_sync_columns = hasattr(booking, 'sync_status')
            
            for provider_name, result in sync_results.items():
                # Handle None results from providers (e.g., when event_id is None)
                if result is None:
                    continue
                    
                if result.get('success') and result.get('result', {}).get('id'):
                    if provider_name == 'google':
                        booking.google_event_id = result['result']['id']
                    # Future: Handle other providers
                    break
            
            # Update sync status if columns exist
            if has_sync_columns:
                if any(result.get('success') for result in sync_results.values() if result is not None):
                    booking.sync_status = 'synced'
                    booking.last_synced = datetime.utcnow()
                    booking.sync_error = None
                else:
                    booking.sync_status = 'failed'
                    booking.sync_attempts = getattr(booking, 'sync_attempts', 0) + 1
                    booking.sync_error = 'All providers failed'
            
            booking.updated_at = datetime.utcnow()
            
        except Exception as e:
            logger.error(f"Failed to update booking {booking.id} with sync results: {str(e)}")
            # Still update the basic fields even if sync status update fails
            booking.updated_at = datetime.utcnow()
    
    async def sync_failed_bookings(self) -> Dict[str, Any]:
        """
        Manually sync all failed bookings.
        
        Returns:
            Sync results summary
        """
        try:
            db = next(get_db())
            
            # Find bookings with failed sync status
            failed_bookings = db.query(Booking).filter(
                Booking.google_event_id.is_(None)
            ).all()
            
            if not failed_bookings:
                return {"success": True, "message": "No failed bookings found", "synced_count": 0}
            
            synced_count = 0
            for booking in failed_bookings:
                try:
                    await self._sync_single_booking(db, booking)
                    synced_count += 1
                except Exception as e:
                    logger.error(f"Failed to sync booking {booking.id}: {str(e)}")
            
            return {
                "success": True,
                "message": f"Synced {synced_count} out of {len(failed_bookings)} failed bookings",
                "synced_count": synced_count,
                "total_failed": len(failed_bookings)
            }
            
        except Exception as e:
            logger.error(f"Failed to sync failed bookings: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def get_sync_status_summary(self) -> Dict[str, Any]:
        """
        Get summary of sync status across all bookings.
        
        Returns:
            Sync status summary
        """
        try:
            db = next(get_db())
            
            total_bookings = db.query(Booking).count()
            synced_bookings = db.query(Booking).filter(Booking.google_event_id.isnot(None)).count()
            failed_bookings = total_bookings - synced_bookings
            
            return {
                "total_bookings": total_bookings,
                "synced_bookings": synced_bookings,
                "failed_bookings": failed_bookings,
                "sync_percentage": (synced_bookings / total_bookings * 100) if total_bookings > 0 else 0,
                "last_sync_check": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get sync status summary: {str(e)}")
            return {"error": str(e)}


# Global instance for background sync service
background_sync_service = BackgroundSyncService() 