"""
Calendar Sync API Endpoints - FastAPI implementation following best practices.
This module provides REST API endpoints for calendar synchronization operations.
"""

from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import get_current_user_from_cookie
from app.schemas.calendar_schemas import (
    CreateEventRequest,
    UpdateEventRequest,
    EventResponse,
    SyncResultResponse,
    ErrorResponse,
    SyncMetadataResponse
)
from app.services.repositories.event_repository import EventRepository
from app.core.calendar_architecture import CalendarSyncService, create_calendar_provider, CalendarProviderType
from app.models.models import User
from app.models.models import Booking

# Initialize router with proper tags and prefix
router = APIRouter(
    prefix="/calendar",
    tags=["Calendar Sync"],
    responses={
        404: {"model": ErrorResponse, "description": "Event not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)


@router.post("/events", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
async def create_event(
    event_data: CreateEventRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_cookie)
) -> EventResponse:
    """
    Create a new calendar event with automatic sync to external providers.
    
    This endpoint follows database-first architecture:
    1. Creates event in local database
    2. Syncs to all registered calendar providers
    3. Returns event with sync metadata
    
    Args:
        event_data: Event creation data with validation
        db: Database session (dependency injection)
        current_user: Authenticated user (dependency injection)
        
    Returns:
        EventResponse: Created event with sync metadata
        
    Raises:
        HTTPException: If event creation or sync fails
    """
    try:
        # Initialize repository and sync service
        event_repo = EventRepository(db)
        sync_service = CalendarSyncService(db, current_user.id)
        
        # Register Google Calendar provider if user has tokens
        if current_user.google_access_token and current_user.google_refresh_token:
            google_provider = create_calendar_provider(
                CalendarProviderType.GOOGLE,
                access_token=current_user.google_access_token,
                refresh_token=current_user.google_refresh_token,
                db=db,
                user_id=current_user.id
            )
            sync_service.register_provider(google_provider)
        
        # Create event in database first (source of truth)
        booking_data = {
            'slot_id': None,  # Will be set based on availability
            'guest_name': event_data.title,
            'guest_email': current_user.email,
            'guest_message': event_data.description,
            'start_time': event_data.start_time,
            'end_time': event_data.end_time
        }
        
        booking = event_repo.create_booking(booking_data, current_user.id)
        
        # Sync to external providers if requested
        sync_results = {}
        if event_data.sync_immediately and sync_service.providers:
            event_sync_data = {
                'summary': event_data.title,
                'description': event_data.description,
                'start': {
                    'dateTime': event_data.start_time.isoformat(),
                    'timeZone': 'UTC'
                },
                'end': {
                    'dateTime': event_data.end_time.isoformat(),
                    'timeZone': 'UTC'
                }
            }
            
            sync_results = sync_service.sync_event_to_providers(
                str(booking.id), 
                event_sync_data, 
                "create"
            )
        
        # Build response with sync metadata
        sync_metadata = None
        if sync_results:
            provider_result = next(iter(sync_results.values()))
            sync_metadata = SyncMetadataResponse(
                event_id=str(booking.id),
                provider_type=event_data.provider_type,
                provider_event_id=provider_result.get('result', {}).get('id'),
                sync_status=provider_result['sync_status'],
                last_synced=datetime.utcnow(),
                error_message=provider_result.get('error')
            )
        
        return EventResponse(
            id=booking.id,
            title=event_data.title,
            start_time=event_data.start_time,
            end_time=event_data.end_time,
            description=event_data.description,
            location=event_data.location,
            created_at=booking.created_at,
            updated_at=booking.updated_at if hasattr(booking, 'updated_at') else None,
            sync_metadata=sync_metadata
        )
        
    except ValueError as e:
        """Handle validation errors."""
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Validation error: {str(e)}"
        )
    except Exception as e:
        """Handle unexpected errors."""
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create event: {str(e)}"
        )


@router.get("/events/{event_id}/sync-status", response_model=SyncMetadataResponse)
async def get_event_sync_status(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_cookie)
) -> SyncMetadataResponse:
    """
    Get sync status for a specific event.
    
    Args:
        event_id: Internal event ID
        db: Database session
        current_user: Authenticated user
        
    Returns:
        SyncMetadataResponse: Current sync status and metadata
        
    Raises:
        HTTPException: If event not found or access denied
    """
    try:
        event_repo = EventRepository(db)
        
        # Get booking and verify ownership
        booking = event_repo.get_booking(event_id)
        if not booking:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Event not found"
            )
        
        if booking.host_user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        # Get sync status
        sync_status = event_repo.get_sync_status(event_id, "booking")
        
        return SyncMetadataResponse(
            event_id=str(event_id),
            provider_type="google",  # Currently only Google
            provider_event_id=sync_status.get("provider_event_id"),
            sync_status="synced" if sync_status.get("synced") else "pending",
            last_synced=sync_status.get("last_updated"),
            error_message=None
        )
        
    except HTTPException:
        """Re-raise HTTP exceptions."""
        raise
    except Exception as e:
        """Handle unexpected errors."""
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get sync status: {str(e)}"
        )


@router.post("/sync/retry/{event_id}", response_model=SyncResultResponse)
async def retry_event_sync(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_cookie)
) -> SyncResultResponse:
    """
    Retry synchronization for a failed event.
    
    Args:
        event_id: Internal event ID
        db: Database session
        current_user: Authenticated user
        
    Returns:
        SyncResultResponse: Sync operation results
        
    Raises:
        HTTPException: If event not found or sync fails
    """
    try:
        event_repo = EventRepository(db)
        sync_service = CalendarSyncService(db, current_user.id)
        
        # Get booking and verify ownership
        booking = event_repo.get_booking(event_id)
        if not booking:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Event not found"
            )
        
        if booking.host_user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        # Register Google Calendar provider
        if current_user.google_access_token and current_user.google_refresh_token:
            google_provider = create_calendar_provider(
                CalendarProviderType.GOOGLE,
                access_token=current_user.google_access_token,
                refresh_token=current_user.google_refresh_token,
                db=db,
                user_id=current_user.id
            )
            sync_service.register_provider(google_provider)
        
        # Prepare event data for sync
        event_sync_data = {
            'summary': f"Meeting with {booking.guest_name}",
            'description': booking.guest_message,
            'start': {
                'dateTime': booking.start_time.isoformat(),
                'timeZone': 'UTC'
            },
            'end': {
                'dateTime': booking.end_time.isoformat(),
                'timeZone': 'UTC'
            }
        }
        
        # Retry sync
        sync_results = sync_service.sync_event_to_providers(
            str(event_id), 
            event_sync_data, 
            "create"
        )
        
        return SyncResultResponse(
            success=any(result.get('success') for result in sync_results.values()),
            operation="create",
            event_id=str(event_id),
            provider_results=sync_results,
            timestamp=datetime.utcnow()
        )
        
    except HTTPException:
        """Re-raise HTTP exceptions."""
        raise
    except Exception as e:
        """Handle unexpected errors."""
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retry sync: {str(e)}"
        ) 


@router.post("/sync/retry/{booking_id}")
async def retry_sync_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_cookie)
):
    """Retry sync for a specific booking."""
    try:
        # Get the booking
        booking = db.query(Booking).filter(
            Booking.id == booking_id,
            Booking.host_user_id == current_user.id
        ).first()
        
        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")
        
        # Initialize sync service
        from app.services.sync.background_sync import BackgroundSyncService
        sync_service = BackgroundSyncService()
        
        # Retry sync for this booking
        result = await sync_service._sync_single_booking(db, booking)
        
        return {
            "success": True,
            "booking_id": booking_id,
            "sync_status": booking.sync_status,
            "message": "Sync retry completed"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retry sync: {str(e)}")


@router.post("/sync/retry-failed")
async def retry_failed_syncs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_cookie)
):
    """Retry all failed syncs for the current user."""
    try:
        # Initialize sync service
        from app.services.sync.background_sync import BackgroundSyncService
        sync_service = BackgroundSyncService()
        
        # Retry failed syncs
        result = await sync_service.sync_failed_bookings()
        
        return {
            "success": True,
            "retried_count": result.get("retried_count", 0),
            "successful_count": result.get("successful_count", 0),
            "failed_count": result.get("failed_count", 0),
            "message": "Failed sync retry completed"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retry syncs: {str(e)}")


@router.get("/sync/status")
async def get_sync_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_cookie)
):
    """Get sync status summary for the current user."""
    try:
        # Get all bookings for the user
        bookings = db.query(Booking).filter(
            Booking.host_user_id == current_user.id
        ).all()
        
        # Count by sync status
        status_counts = {}
        for booking in bookings:
            status = booking.sync_status
            if status not in status_counts:
                status_counts[status] = 0
            status_counts[status] += 1
        
        # Get failed syncs with errors
        failed_bookings = db.query(Booking).filter(
            Booking.host_user_id == current_user.id,
            Booking.sync_status == "failed"
        ).all()
        
        failed_details = []
        for booking in failed_bookings:
            failed_details.append({
                "booking_id": booking.id,
                "guest_name": booking.guest_name,
                "start_time": booking.start_time.isoformat(),
                "sync_error": booking.sync_error,
                "sync_attempts": booking.sync_attempts
            })
        
        return {
            "total_bookings": len(bookings),
            "status_counts": status_counts,
            "failed_bookings": failed_details,
            "calendar_connected": bool(current_user.google_access_token and current_user.google_refresh_token)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get sync status: {str(e)}")


@router.post("/sync/force-sync")
async def force_sync_all(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_cookie)
):
    """Force sync all bookings for the current user."""
    try:
        # Get all pending bookings
        pending_bookings = db.query(Booking).filter(
            Booking.host_user_id == current_user.id,
            Booking.sync_status.in_(["pending", "failed"])
        ).all()
        
        # Initialize sync service
        from app.services.sync.background_sync import BackgroundSyncService
        sync_service = BackgroundSyncService()
        
        # Sync each booking
        synced_count = 0
        failed_count = 0
        
        for booking in pending_bookings:
            try:
                await sync_service._sync_single_booking(db, booking)
                synced_count += 1
            except Exception as e:
                failed_count += 1
                print(f"Failed to sync booking {booking.id}: {e}")
        
        return {
            "success": True,
            "total_bookings": len(pending_bookings),
            "synced_count": synced_count,
            "failed_count": failed_count,
            "message": f"Force sync completed: {synced_count} synced, {failed_count} failed"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to force sync: {str(e)}")


@router.post("/sync/pull-from-calendar")
async def pull_calendar_events_to_database(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_cookie)
):
    """
    Pull calendar events from Google Calendar and sync them to database.
    This implements Calendar → Database sync following the architecture.
    
    This endpoint:
    1. Fetches events from Google Calendar
    2. Creates database bookings for new events
    3. Updates existing bookings for changed events
    4. Returns sync results
    """
    try:
        # Check if user has calendar connected
        if not current_user.google_access_token or not current_user.google_refresh_token:
            raise HTTPException(
                status_code=400, 
                detail="Google Calendar not connected. Please connect your calendar first."
            )
        
        # Initialize background sync service
        from app.services.sync.background_sync import BackgroundSyncService
        sync_service = BackgroundSyncService()
        
        # Perform calendar to database sync
        sync_result = await sync_service.sync_calendar_to_database(db, current_user.id)
        
        if not sync_result.get("success"):
            raise HTTPException(
                status_code=500,
                detail=f"Failed to sync calendar events: {sync_result.get('error', 'Unknown error')}"
            )
        
        return {
            "success": True,
            "message": f"Successfully synced calendar events to database",
            "events_created": sync_result.get("events_created", 0),
            "events_updated": sync_result.get("events_updated", 0),
            "total_events_processed": sync_result.get("total_events_processed", 0)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to pull calendar events: {str(e)}") 