"""
Calendar Schemas - Pydantic models for calendar operations.
Following FastAPI best practices with proper validation and documentation.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, field_validator


class SyncStatusEnum(str, Enum):
    """Sync status enumeration for API responses."""
    PENDING = "pending"
    SYNCED = "synced"
    FAILED = "failed"
    CONFLICT = "conflict"


class CalendarProviderEnum(str, Enum):
    """Supported calendar provider types."""
    GOOGLE = "google"
    MICROSOFT = "microsoft"


class EventBase(BaseModel):
    """Base event model with common fields."""
    
    title: str = Field(..., description="Event title", min_length=1, max_length=200)
    start_time: datetime = Field(..., description="Event start time")
    end_time: datetime = Field(..., description="Event end time")
    description: Optional[str] = Field(None, description="Event description", max_length=1000)
    location: Optional[str] = Field(None, description="Event location", max_length=200)
    
    @field_validator('end_time')
    @classmethod
    def end_time_must_be_after_start_time(cls, v, info):
        """Validate that end time is after start time."""
        if 'start_time' in info.data and v <= info.data['start_time']:
            raise ValueError('end_time must be after start_time')
        return v


class CreateEventRequest(EventBase):
    """Request model for creating a new event."""
    
    provider_type: CalendarProviderEnum = Field(
        default=CalendarProviderEnum.GOOGLE,
        description="Calendar provider to sync with"
    )
    sync_immediately: bool = Field(
        default=True,
        description="Whether to sync immediately to external calendar"
    )


class UpdateEventRequest(BaseModel):
    """Request model for updating an existing event."""
    
    title: Optional[str] = Field(None, description="Event title", min_length=1, max_length=200)
    start_time: Optional[datetime] = Field(None, description="Event start time")
    end_time: Optional[datetime] = Field(None, description="Event end time")
    description: Optional[str] = Field(None, description="Event description", max_length=1000)
    location: Optional[str] = Field(None, description="Event location", max_length=200)
    sync_immediately: bool = Field(
        default=True,
        description="Whether to sync immediately to external calendar"
    )


class SyncMetadataResponse(BaseModel):
    """Response model for sync metadata."""
    
    event_id: str = Field(..., description="Internal event ID")
    provider_type: CalendarProviderEnum = Field(..., description="Calendar provider type")
    provider_event_id: Optional[str] = Field(None, description="External provider event ID")
    sync_status: SyncStatusEnum = Field(..., description="Current sync status")
    last_synced: Optional[datetime] = Field(None, description="Last sync timestamp")
    error_message: Optional[str] = Field(None, description="Error message if sync failed")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "event_id": "123",
                "provider_type": "google",
                "provider_event_id": "google_event_456",
                "sync_status": "synced",
                "last_synced": "2024-01-15T10:30:00Z",
                "error_message": None
            }
        }
    }


class EventResponse(EventBase):
    """Response model for event data."""
    
    id: int = Field(..., description="Internal event ID")
    created_at: datetime = Field(..., description="Event creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Event last update timestamp")
    sync_metadata: Optional[SyncMetadataResponse] = Field(None, description="Sync metadata")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "id": 123,
                "title": "Team Meeting",
                "start_time": "2024-01-15T10:00:00Z",
                "end_time": "2024-01-15T11:00:00Z",
                "description": "Weekly team sync",
                "location": "Conference Room A",
                "created_at": "2024-01-15T09:00:00Z",
                "updated_at": "2024-01-15T09:30:00Z",
                "sync_metadata": {
                    "event_id": "123",
                    "provider_type": "google",
                    "provider_event_id": "google_event_456",
                    "sync_status": "synced",
                    "last_synced": "2024-01-15T09:30:00Z",
                    "error_message": None
                }
            }
        }
    }


class SyncResultResponse(BaseModel):
    """Response model for sync operation results."""
    
    success: bool = Field(..., description="Whether sync operation was successful")
    operation: str = Field(..., description="Type of sync operation (create, update, delete)")
    event_id: str = Field(..., description="Internal event ID")
    provider_results: Dict[str, Dict[str, Any]] = Field(
        ..., 
        description="Results for each calendar provider"
    )
    timestamp: datetime = Field(..., description="Sync operation timestamp")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "success": True,
                "operation": "create",
                "event_id": "123",
                "provider_results": {
                    "google": {
                        "success": True,
                        "provider_event_id": "google_event_456",
                        "sync_status": "synced"
                    }
                },
                "timestamp": "2024-01-15T09:30:00Z"
            }
        }
    }


class ErrorResponse(BaseModel):
    """Standard error response model."""
    
    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Detailed error information")
    timestamp: datetime = Field(..., description="Error timestamp")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "error": "Failed to sync event",
                "detail": "Google Calendar API returned 401 Unauthorized",
                "timestamp": "2024-01-15T09:30:00Z"
            }
        }
    } 