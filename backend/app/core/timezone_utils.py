"""
Timezone Utilities - Centralized timezone handling for the booking system.
This module ensures consistent timezone handling across the application.
"""

import pytz
from datetime import datetime, timezone
from typing import Optional, Union
from zoneinfo import ZoneInfo


class TimezoneManager:
    """
    Centralized timezone management for the booking system.
    Ensures all datetime operations are timezone-aware and consistent.
    """
    
    # Default timezone if user hasn't set one
    DEFAULT_TIMEZONE = "UTC"
    
    # Common timezone mappings for user-friendly display
    TIMEZONE_NAMES = {
        "UTC": "UTC",
        "America/New_York": "Eastern Time",
        "America/Chicago": "Central Time", 
        "America/Denver": "Mountain Time",
        "America/Los_Angeles": "Pacific Time",
        "Europe/London": "London",
        "Europe/Paris": "Paris",
        "Asia/Tokyo": "Tokyo",
        "Asia/Shanghai": "Shanghai",
        "Australia/Sydney": "Sydney"
    }
    
    @staticmethod
    def detect_timezone_from_google_calendar(calendar_service) -> str:
        """
        Detect user's timezone from their Google Calendar settings.
        
        Args:
            calendar_service: GoogleCalendarService instance
            
        Returns:
            Detected timezone string or default UTC
        """
        try:
            # Get calendar settings from Google Calendar API
            service = calendar_service._get_calendar_service()
            
            # Get primary calendar settings
            calendar = service.calendars().get(calendarId='primary').execute()
            
            # Extract timezone from calendar settings
            timezone_str = calendar.get('timeZone', 'UTC')
            
            # Validate the timezone
            if timezone_str in pytz.all_timezones:
                return timezone_str
            else:
                print(f"Warning: Invalid timezone '{timezone_str}' from Google Calendar, using UTC")
                return TimezoneManager.DEFAULT_TIMEZONE
                
        except Exception as e:
            print(f"Error detecting timezone from Google Calendar: {e}")
            return TimezoneManager.DEFAULT_TIMEZONE
    
    @staticmethod
    def get_user_timezone(user_timezone: Optional[str] = None) -> str:
        """
        Get user's timezone, falling back to default if not set.
        
        Args:
            user_timezone: User's preferred timezone
            
        Returns:
            Valid timezone string
        """
        if user_timezone and user_timezone in pytz.all_timezones:
            return user_timezone
        return TimezoneManager.DEFAULT_TIMEZONE
    
    @staticmethod
    def make_timezone_aware(dt: datetime, timezone_str: str = "UTC") -> datetime:
        """
        Make a datetime object timezone-aware.
        
        Args:
            dt: Datetime object (naive or aware)
            timezone_str: Timezone string (e.g., 'America/New_York')
            
        Returns:
            Timezone-aware datetime object
        """
        if dt.tzinfo is None:
            # Naive datetime - assume it's in the specified timezone
            tz = ZoneInfo(timezone_str)
            return dt.replace(tzinfo=tz)
        else:
            # Already timezone-aware - convert to specified timezone
            target_tz = ZoneInfo(timezone_str)
            return dt.astimezone(target_tz)
    
    @staticmethod
    def convert_to_utc(dt: datetime, source_timezone: str = "UTC") -> datetime:
        """
        Convert datetime to UTC.
        
        Args:
            dt: Datetime object
            source_timezone: Timezone of the input datetime
            
        Returns:
            UTC datetime object
        """
        if dt.tzinfo is None:
            # Naive datetime - make it timezone-aware first
            aware_dt = TimezoneManager.make_timezone_aware(dt, source_timezone)
        else:
            # Already timezone-aware - use as is
            aware_dt = dt
            
        return aware_dt.astimezone(ZoneInfo("UTC"))
    
    @staticmethod
    def convert_from_utc(dt: datetime, target_timezone: str) -> datetime:
        """
        Convert UTC datetime to target timezone.
        
        Args:
            dt: UTC datetime object
            target_timezone: Target timezone
            
        Returns:
            Datetime in target timezone
        """
        if dt.tzinfo is None:
            # Assume UTC if naive
            dt = dt.replace(tzinfo=ZoneInfo("UTC"))
        
        target_tz = ZoneInfo(target_timezone)
        return dt.astimezone(target_tz)
    
    @staticmethod
    def format_datetime_for_display(dt: datetime, timezone_str: str, format_str: str = "%Y-%m-%d %H:%M") -> str:
        """
        Format datetime for display in user's timezone.
        
        Args:
            dt: Datetime object
            timezone_str: User's timezone
            format_str: Format string
            
        Returns:
            Formatted datetime string
        """
        local_dt = TimezoneManager.convert_from_utc(dt, timezone_str)
        return local_dt.strftime(format_str)
    
    @staticmethod
    def get_timezone_display_name(timezone_str: str) -> str:
        """
        Get user-friendly timezone display name.
        
        Args:
            timezone_str: Timezone string
            
        Returns:
            User-friendly timezone name
        """
        return TimezoneManager.TIMEZONE_NAMES.get(timezone_str, timezone_str)
    
    @staticmethod
    def get_available_timezones() -> list:
        """
        Get list of available timezones for user selection.
        
        Returns:
            List of (timezone_id, display_name) tuples
        """
        common_timezones = [
            "UTC",
            "America/New_York", 
            "America/Chicago",
            "America/Denver", 
            "America/Los_Angeles",
            "Europe/London",
            "Europe/Paris",
            "Asia/Tokyo",
            "Asia/Shanghai",
            "Australia/Sydney"
        ]
        
        return [(tz, TimezoneManager.get_timezone_display_name(tz)) for tz in common_timezones]


def ensure_utc_datetime(dt: datetime) -> datetime:
    """
    Ensure datetime is in UTC for database storage.
    
    Args:
        dt: Datetime object
        
    Returns:
        UTC datetime object
    """
    if dt.tzinfo is None:
        # Assume UTC if naive
        return dt.replace(tzinfo=ZoneInfo("UTC"))
    else:
        # Convert to UTC if in different timezone
        return dt.astimezone(ZoneInfo("UTC"))


def parse_user_datetime(date_str: str, time_str: str, user_timezone: str) -> datetime:
    """
    Parse user input datetime and convert to UTC for storage.
    
    Args:
        date_str: Date string (YYYY-MM-DD)
        time_str: Time string (HH:MM)
        user_timezone: User's timezone
        
    Returns:
        UTC datetime object
    """
    # Create naive datetime in user's timezone
    dt_str = f"{date_str} {time_str}"
    naive_dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
    
    # Make timezone-aware and convert to UTC
    return TimezoneManager.convert_to_utc(naive_dt, user_timezone)


def format_datetime_for_user(dt: datetime, user_timezone: str) -> dict:
    """
    Format datetime for user display with timezone info.
    
    Args:
        dt: UTC datetime object
        user_timezone: User's timezone
        
    Returns:
        Dict with formatted datetime and timezone info
    """
    local_dt = TimezoneManager.convert_from_utc(dt, user_timezone)
    
    return {
        "datetime": local_dt.strftime("%Y-%m-%d %H:%M"),
        "date": local_dt.strftime("%Y-%m-%d"),
        "time": local_dt.strftime("%H:%M"),
        "timezone": TimezoneManager.get_timezone_display_name(user_timezone),
        "timezone_offset": local_dt.strftime("%z")
    } 