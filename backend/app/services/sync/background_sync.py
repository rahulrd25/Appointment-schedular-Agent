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
            print("[SYNC] Background sync service is already running")
            logger.warning("Background sync service is already running")
            return
        
        self.is_running = True
        print("[SYNC] Starting background sync service...")
        logger.info("Starting background sync service")
        
        try:
            while self.is_running:
                print(f"[SYNC] Starting sync cycle at {datetime.now()}")
                await self._perform_sync_cycle()
                print(f"[SYNC] Waiting {self.sync_config.background_sync_interval} seconds before next cycle...")
                await asyncio.sleep(self.sync_config.background_sync_interval)
                
        except Exception as e:
            print(f"[SYNC ERROR] Background sync service failed: {str(e)}")
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
        1. Syncs calendar events to database (Calendar → DB)
        2. Finds bookings that need sync to calendar (DB → Calendar)
        3. Attempts to sync them to calendar providers
        4. Updates sync status and metadata
        """
        try:
            print("[SYNC CYCLE] Starting sync cycle...")
            logger.debug("Starting sync cycle")
            
            # Get database session
            db = next(get_db())
            print("[SYNC CYCLE] Database session acquired")
            
            # Step 1: Calendar → Database sync
            print("[SYNC CYCLE] Step 1 - Calendar to DB...")
            await self._perform_calendar_to_database_sync(db)
            
            # Step 2: Find bookings to sync to calendar
            print("[SYNC CYCLE] Step 2 - Find bookings to sync...")
            bookings_to_sync = self._find_bookings_needing_sync(db)
            
            if not bookings_to_sync:
                print("[SYNC CYCLE] No bookings to sync")
                logger.debug("No bookings need sync to calendar in this cycle")
            else:
                print(f"[SYNC CYCLE] Found {len(bookings_to_sync)} bookings to sync")
                logger.info(f"Found {len(bookings_to_sync)} bookings that need sync to calendar")
                
                # Process each booking
                for i, booking in enumerate(bookings_to_sync):
                    print(f"[SYNC CYCLE] Syncing booking {i+1}/{len(bookings_to_sync)} - ID: {booking.id}")
                    await self._sync_single_booking(db, booking)
            
            print("[SYNC CYCLE] Completed sync cycle")
            logger.debug("Completed sync cycle")
            
        except Exception as e:
            print(f"[SYNC CYCLE ERROR] Failed to perform sync cycle: {str(e)}")
            logger.error(f"Failed to perform sync cycle: {str(e)}")
    
    async def _perform_calendar_to_database_sync(self, db: Session) -> None:
        """
        Calendar to database sync for all connected users.
        What does it do? Finds users with calendars and syncs events to DB.
        """
        try:
            logger.debug("Starting calendar to database sync cycle")
            
            # Find users with connected calendars
            users_with_calendar = db.query(User).filter(
                User.google_calendar_connected == True,
                User.google_access_token.isnot(None),
                User.google_refresh_token.isnot(None)
            ).all()
            
            if not users_with_calendar:
                logger.debug("No users with connected calendars found")
                return
            
            logger.info(f"Found {len(users_with_calendar)} users with calendars")
            
            # Sync calendar events for each user
            for user in users_with_calendar:
                try:
                    logger.debug(f"Syncing calendar for user {user.id} ({user.email})")
                    await self.sync_calendar_to_database(db, user.id)
                except Exception as e:
                    logger.error(f"Failed to sync calendar for user {user.id}: {str(e)}")
                    continue
            
            logger.debug("Completed calendar to database sync cycle")
            
        except Exception as e:
            logger.error(f"Failed to perform calendar to database sync cycle: {str(e)}")
    
    def _find_bookings_needing_sync(self, db: Session) -> List[Booking]:
        """
        Find bookings that need synchronization.
        
        Args:
            db: Database session
            
        Returns:
            List of bookings that need sync
        """
        try:
            # Use existing schema: find bookings without google_event_id or recently updated
            recent_cutoff = datetime.utcnow() - timedelta(hours=1)
            
            bookings = db.query(Booking).filter(
                (Booking.google_event_id.is_(None)) |
                ((Booking.updated_at > recent_cutoff) & (Booking.google_event_id.isnot(None)))
            ).all()
            
            print(f"[SYNC] Found {len(bookings)} bookings that need sync")
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
            for provider_name, result in sync_results.items():
                # Handle None results from providers (e.g., when event_id is None)
                if result is None:
                    continue
                    
                if result.get('success') and result.get('result', {}).get('id'):
                    if provider_name == 'google':
                        booking.google_event_id = result['result']['id']
                        print(f"[SYNC] Updated booking {booking.id} with Google event ID: {result['result']['id']}")
                    # Future: Handle other providers
                    break
            
            # Update the booking timestamp
            booking.updated_at = datetime.utcnow()
            print(f"[SYNC] Updated booking {booking.id} timestamp")
            
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
            
            # Find bookings without google_event_id (not synced to Google Calendar)
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
        Get a summary of sync status for all users.
        
        Returns:
            Dict containing sync status summary
        """
        try:
            db = next(get_db())
            
            # Get all users with calendar connections
            users_with_calendar = db.query(User).filter(
                User.google_access_token.isnot(None),
                User.google_refresh_token.isnot(None)
            ).all()
            
            summary = {
                "total_users_with_calendar": len(users_with_calendar),
                "users_sync_status": []
            }
            
            for user in users_with_calendar:
                user_bookings = db.query(Booking).filter(
                    Booking.host_user_id == user.id
                ).all()
                
                # Count bookings by sync status using google_event_id
                synced_count = len([b for b in user_bookings if b.google_event_id is not None])
                unsynced_count = len([b for b in user_bookings if b.google_event_id is None])
                
                summary["users_sync_status"].append({
                    "user_id": user.id,
                    "email": user.email,
                    "total_bookings": len(user_bookings),
                    "synced_bookings": synced_count,
                    "unsynced_bookings": unsynced_count
                })
            
            return summary
            
        except Exception as e:
            logger.error(f"Failed to get sync status summary: {str(e)}")
            return {"error": str(e)}

    async def sync_calendar_to_database(self, db: Session, user_id: int) -> Dict[str, Any]:
        """
        Pull calendar events and sync to database.
        What does it do? Calendar → Database sync.
        """
        try:
            print(f"[SYNC SERVICE] Starting calendar sync for user {user_id}")
            logger.info(f"Starting calendar to database sync for user {user_id}")
            
            # Get user
            print(f"[SYNC SERVICE] Getting user...")
            user = db.query(User).filter(User.id == user_id).first()
            if not user or not user.google_access_token:
                print(f"[SYNC SERVICE ERROR] User not found or calendar not connected")
                return {
                    "success": False,
                    "error": "User not found or calendar not connected",
                    "events_created": 0,
                    "events_updated": 0
                }
            
            print(f"[SYNC SERVICE] User found - {user.email}")
            
            # Initialize Google Calendar service
            print(f"[SYNC SERVICE] Initializing Google Calendar...")
            from app.services.google_calendar_service import GoogleCalendarService
            calendar_service = GoogleCalendarService(
                access_token=user.google_access_token,
                refresh_token=user.google_refresh_token,
                db=db,
                user_id=user_id
            )
            
            # Get events from Google Calendar
            from datetime import datetime, timedelta, timezone
            start_date = datetime.now(timezone.utc) - timedelta(days=7)
            end_date = datetime.now(timezone.utc) + timedelta(days=7)
            
            print(f"[SYNC SERVICE] Fetching events...")
            try:
                calendar_events = calendar_service.get_events(start_date, end_date)
                print(f"[SYNC SERVICE] Found {len(calendar_events)} events")
            except Exception as e:
                print(f"[SYNC SERVICE] Failed to fetch events: {str(e)}")
                print(f"[SYNC SERVICE] Skipping calendar sync due to error")
                return {
                    "success": False,
                    "error": str(e),
                    "events_created": 0,
                    "events_updated": 0
                }
            
            events_created = 0
            events_updated = 0
            
            print(f"[SYNC SERVICE] Processing {len(calendar_events)} events...")
            for i, event in enumerate(calendar_events):
                try:
                    print(f"[SYNC SERVICE] Processing event {i+1}/{len(calendar_events)} - {event.get('summary', 'No title')}")
                    
                    # Check if booking exists for this event
                    existing_booking = db.query(Booking).filter(
                        Booking.google_event_id == event.get('id'),
                        Booking.host_user_id == user_id
                    ).first()
                    
                    if existing_booking:
                        print(f"[SYNC SERVICE] Found booking {existing_booking.id} for event {event.get('id')}")
                        # Update if event changed
                        if self._has_event_changed(existing_booking, event):
                            self._update_booking_from_calendar_event(existing_booking, event)
                            events_updated += 1
                            print(f"[SYNC SERVICE] Updated booking {existing_booking.id}")
                            logger.info(f"Updated booking {existing_booking.id} from calendar event")
                        else:
                            print(f"[SYNC SERVICE] Event unchanged")
                    else:
                        print(f"[SYNC SERVICE] Skipping event {event.get('id')} - Database-First")
                
                except Exception as e:
                    print(f"[SYNC SERVICE ERROR] Failed to process event {event.get('id')}: {str(e)}")
                    logger.error(f"Failed to process calendar event {event.get('id')}: {str(e)}")
                    continue
            
            print(f"[SYNC SERVICE] Committing changes...")
            db.commit()
            
            print(f"[SYNC SERVICE] Sync completed: {events_updated} updated")
            logger.info(f"Calendar to database sync completed: {events_updated} updated (Database-First approach)")
            
            return {
                "success": True,
                "events_created": 0,  # No longer creating from calendar events
                "events_updated": events_updated,
                "total_events_processed": len(calendar_events)
            }
            
        except Exception as e:
            print(f"[SYNC SERVICE ERROR] Failed to sync calendar to database: {str(e)}")
            logger.error(f"Failed to sync calendar to database: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "events_created": 0,
                "events_updated": 0
            }
    
    def _has_event_changed(self, booking: Booking, event: Dict[str, Any]) -> bool:
        """Check if calendar event has changed compared to database booking."""
        try:
            start_data = event.get('start', {})
            end_data = event.get('end', {})
            
            # Handle both dateTime and date formats
            event_start = start_data.get('dateTime') or start_data.get('date')
            event_end = end_data.get('dateTime') or end_data.get('date')
            event_summary = event.get('summary', '')
            event_description = event.get('description', '')
            
            if not event_start or not event_end:
                return False
            
            from datetime import datetime
            
            # Determine event type and parse accordingly
            is_all_day = 'date' in start_data
            
            if is_all_day:
                # All-day event
                event_start_dt = datetime.fromisoformat(event_start + 'T00:00:00+00:00')
                event_end_dt = datetime.fromisoformat(event_end + 'T23:59:59+00:00')
            else:
                # Time-specific event
                event_start_dt = datetime.fromisoformat(event_start.replace('Z', '+00:00'))
                event_end_dt = datetime.fromisoformat(event_end.replace('Z', '+00:00'))
            
            # Compare times (with small tolerance for timezone differences)
            time_diff = abs((event_start_dt - booking.start_time).total_seconds())
            if time_diff > 60:  # 1 minute tolerance
                return True
            
            time_diff = abs((event_end_dt - booking.end_time).total_seconds())
            if time_diff > 60:  # 1 minute tolerance
                return True
            
            # Compare other fields
            if event_summary and booking.guest_name != event_summary:
                return True
            
            if event_description != (booking.guest_message or ''):
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking if event changed: {str(e)}")
            return False
    
    def _update_booking_from_calendar_event(self, booking: Booking, event: Dict[str, Any]) -> None:
        """Update existing booking from calendar event data."""
        try:
            start_data = event.get('start', {})
            end_data = event.get('end', {})
            
            # Handle both dateTime and date formats
            event_start = start_data.get('dateTime') or start_data.get('date')
            event_end = end_data.get('dateTime') or end_data.get('date')
            event_summary = event.get('summary', '')
            event_description = event.get('description', '')
            
            from datetime import datetime
            
            if event_start:
                # Determine if it's all-day or time-specific
                is_all_day = 'date' in start_data
                
                if is_all_day:
                    # All-day event
                    booking.start_time = datetime.fromisoformat(event_start + 'T00:00:00+00:00')
                else:
                    # Time-specific event
                    booking.start_time = datetime.fromisoformat(event_start.replace('Z', '+00:00'))
            
            if event_end:
                # Determine if it's all-day or time-specific
                is_all_day = 'date' in end_data
                
                if is_all_day:
                    # All-day event (end date is exclusive)
                    booking.end_time = datetime.fromisoformat(event_end + 'T23:59:59+00:00')
                else:
                    # Time-specific event
                    booking.end_time = datetime.fromisoformat(event_end.replace('Z', '+00:00'))
            
            if event_summary:
                booking.guest_name = event_summary
            
            if event_description:
                booking.guest_message = event_description
            
            booking.sync_status = "synced"
            booking.last_synced = datetime.utcnow()
            
        except Exception as e:
            logger.error(f"Error updating booking from calendar event: {str(e)}")


# Global instance for background sync service
background_sync_service = BackgroundSyncService() 