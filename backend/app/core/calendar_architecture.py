"""
Core Calendar Architecture - Abstract interfaces for calendar providers.
This module provides the foundation for our modular calendar system while
maintaining compatibility with existing functionality.

Following FastAPI best practices:
- Type hints throughout
- Proper error handling
- Comprehensive documentation
- Clean separation of concerns
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Union
from datetime import datetime
from enum import Enum
import logging

# Configure logging for calendar operations
logger = logging.getLogger(__name__)


class SyncStatus(Enum):
    """Sync status enumeration for tracking event synchronization."""
    PENDING = "pending"
    SYNCED = "synced"
    FAILED = "failed"
    CONFLICT = "conflict"


class CalendarProviderType(Enum):
    """Supported calendar provider types."""
    GOOGLE = "google"
    MICROSOFT = "microsoft"
    # Future providers can be added here


class BaseCalendarProvider(ABC):
    """
    Abstract base class for calendar providers.
    This maintains compatibility with existing Google Calendar service.
    """
    
    def __init__(self, access_token: str = None, refresh_token: str = None, 
                 db=None, user_id: int = None):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.db = db
        self.user_id = user_id
        self.provider_type = self._get_provider_type()
    
    @abstractmethod
    def _get_provider_type(self) -> CalendarProviderType:
        """Return the provider type."""
        pass
    
    @abstractmethod
    def create_event(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create an event in the calendar provider."""
        pass
    
    @abstractmethod
    def update_event(self, event_id: str, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an event in the calendar provider."""
        pass
    
    @abstractmethod
    def delete_event(self, event_id: str) -> bool:
        """Delete an event from the calendar provider."""
        pass
    
    @abstractmethod
    def get_event(self, event_id: str) -> Optional[Dict[str, Any]]:
        """Get an event from the calendar provider."""
        pass
    
    @abstractmethod
    def get_events(self, start_date: Optional[datetime] = None, 
                   end_date: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Get events from the calendar provider."""
        pass
    
    @abstractmethod
    def check_availability(self, start_time: datetime, end_time: datetime) -> bool:
        """Check if a time slot is available."""
        pass


class SyncMetadata:
    """
    Metadata for tracking synchronization status.
    This will be added to existing models without breaking changes.
    """
    
    def __init__(self, event_id: str, provider_type: CalendarProviderType, 
                 provider_event_id: str = None, sync_status: SyncStatus = SyncStatus.PENDING,
                 last_synced: datetime = None, error_message: str = None):
        self.event_id = event_id
        self.provider_type = provider_type
        self.provider_event_id = provider_event_id
        self.sync_status = sync_status
        self.last_synced = last_synced or datetime.utcnow()
        self.error_message = error_message
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage."""
        return {
            "event_id": self.event_id,
            "provider_type": self.provider_type.value,
            "provider_event_id": self.provider_event_id,
            "sync_status": self.sync_status.value,
            "last_synced": self.last_synced.isoformat() if self.last_synced else None,
            "error_message": self.error_message
        }


class CalendarSyncService:
    """
    Main synchronization service that orchestrates database-first operations.
    This maintains existing functionality while adding sync tracking.
    
    Following FastAPI best practices:
    - Proper error handling with specific exceptions
    - Comprehensive logging for debugging
    - Type hints for all parameters and return values
    - Clean separation of concerns
    """
    
    def __init__(self, db, user_id: int):
        """
        Initialize the calendar sync service.
        
        Args:
            db: Database session
            user_id: User ID for the sync operations
        """
        self.db = db
        self.user_id = user_id
        self.providers: Dict[CalendarProviderType, BaseCalendarProvider] = {}
        logger.info(f"Initialized CalendarSyncService for user {user_id}")
    
    def register_provider(self, provider: BaseCalendarProvider) -> None:
        """
        Register a calendar provider for synchronization.
        
        Args:
            provider: Calendar provider instance implementing BaseCalendarProvider
            
        Raises:
            ValueError: If provider is invalid
        """
        if not isinstance(provider, BaseCalendarProvider):
            raise ValueError("Provider must implement BaseCalendarProvider")
        
        self.providers[provider.provider_type] = provider
        logger.info(f"Registered {provider.provider_type.value} provider for user {self.user_id}")
    
    def sync_event_to_providers(self, event_id: str, event_data: Dict[str, Any], 
                               operation: str = "create") -> Dict[str, Any]:
        """
        Sync an event to all registered providers.
        This maintains existing functionality while adding sync tracking.
        
        Args:
            event_id: Internal event ID
            event_data: Event data to sync
            operation: Sync operation type (create, update, delete)
            
        Returns:
            Dict containing sync results for each provider
            
        Raises:
            ValueError: If operation is not supported
        """
        if operation not in ["create", "update", "delete"]:
            raise ValueError(f"Unsupported operation: {operation}")
        
        results = {}
        logger.info(f"Starting {operation} sync for event {event_id} to {len(self.providers)} providers")
        
        for provider_type, provider in self.providers.items():
            try:
                logger.debug(f"Syncing to {provider_type.value} provider")
                
                if operation == "create":
                    result = provider.create_event(event_data)
                elif operation == "update":
                    result = provider.update_event(event_data.get("id"), event_data)
                elif operation == "delete":
                    result = provider.delete_event(event_data.get("id"))
                
                results[provider_type.value] = {
                    "success": True,
                    "result": result,
                    "sync_status": SyncStatus.SYNCED
                }
                
                logger.info(f"Successfully synced {operation} to {provider_type.value}")
                
            except Exception as e:
                logger.error(f"Failed to sync {operation} to {provider_type.value}: {str(e)}")
                results[provider_type.value] = {
                    "success": False,
                    "error": str(e),
                    "sync_status": SyncStatus.FAILED
                }
        
        return results


# Factory function for creating providers (maintains existing functionality)
def create_calendar_provider(provider_type: CalendarProviderType, **kwargs) -> BaseCalendarProvider:
    """Create a calendar provider instance."""
    if provider_type == CalendarProviderType.GOOGLE:
        from app.services.google_calendar_service import GoogleCalendarService
        return GoogleCalendarService(**kwargs)
    # Future providers can be added here
    else:
        raise ValueError(f"Unsupported provider type: {provider_type}") 