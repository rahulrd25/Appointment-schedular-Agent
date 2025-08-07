"""
Sync Configuration - Settings for calendar synchronization.
This module manages configuration for the new calendar architecture
while maintaining compatibility with existing functionality.
"""

from typing import Dict, Any
from datetime import timedelta
from enum import Enum


class SyncMode(Enum):
    """Sync operation modes."""
    IMMEDIATE = "immediate"  # Sync immediately after database changes
    BATCH = "batch"          # Sync in batches
    SCHEDULED = "scheduled"  # Sync on schedule


class SyncConfig:
    """
    Configuration for calendar synchronization.
    Maintains existing functionality while adding sync tracking.
    """
    
    def __init__(self):
        # Sync behavior settings
        self.sync_mode = SyncMode.IMMEDIATE
        self.retry_attempts = 3
        self.retry_delay = 5  # seconds
        self.batch_size = 50
        self.sync_interval = timedelta(minutes=15)
        self.background_sync_interval = 60  # 1 minute in seconds (for testing)
        
        # Conflict resolution settings
        self.conflict_resolution = "database_wins"  # or "provider_wins", "manual"
        self.allow_manual_resolution = True
        
        # Logging settings
        self.enable_detailed_logging = True
        self.log_sync_operations = True
        self.log_conflicts = True
        
        # Provider-specific settings
        self.providers = {
            "google": {
                "enabled": True,
                "sync_availability": True,
                "sync_bookings": True,
                "webhook_enabled": True
            },
            "microsoft": {
                "enabled": False,  # Future implementation
                "sync_availability": True,
                "sync_bookings": True,
                "webhook_enabled": False
            }
        }
    
    def get_provider_config(self, provider_name: str) -> Dict[str, Any]:
        """Get configuration for a specific provider."""
        return self.providers.get(provider_name, {})
    
    def is_provider_enabled(self, provider_name: str) -> bool:
        """Check if a provider is enabled."""
        config = self.get_provider_config(provider_name)
        return config.get("enabled", False)
    
    def should_sync_availability(self, provider_name: str) -> bool:
        """Check if availability slots should be synced for a provider."""
        config = self.get_provider_config(provider_name)
        return config.get("sync_availability", True)
    
    def should_sync_bookings(self, provider_name: str) -> bool:
        """Check if bookings should be synced for a provider."""
        config = self.get_provider_config(provider_name)
        return config.get("sync_bookings", True)


# Global sync configuration instance
sync_config = SyncConfig()


def get_sync_config() -> SyncConfig:
    """Get the global sync configuration."""
    return sync_config


def update_sync_config(**kwargs):
    """Update sync configuration settings."""
    global sync_config
    for key, value in kwargs.items():
        if hasattr(sync_config, key):
            setattr(sync_config, key, value)
        elif key in sync_config.providers:
            sync_config.providers[key].update(value) 