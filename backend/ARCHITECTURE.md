# Appointment Agent Architecture

## Overview

The Appointment Agent follows a **Database-as-Source-of-Truth** architecture with **Calendar Sync** mechanism. This ensures data consistency, reliability, and offline functionality while maintaining calendar integration.

## Core Architecture Principles

### 1. Database-First Approach
- **Primary Source**: All booking and availability data is stored in the database
- **Single Source of Truth**: Database is the authoritative source for all application data
- **Offline Capability**: Application works without calendar connection
- **Data Consistency**: No conflicts between multiple data sources

### 2. Calendar Sync Mechanism
- **Bidirectional Sync**: Database ↔ Google Calendar
- **Event Tracking**: Each booking/availability slot tracks its calendar sync status
- **Error Handling**: Failed syncs are tracked and can be retried
- **Token Management**: Secure OAuth token storage and refresh

## Data Models

### User Model
```python
class User(Base):
    # Calendar Integration
    google_calendar_connected = Column(Boolean, default=False)
    google_access_token = Column(String, nullable=True)
    google_refresh_token = Column(String, nullable=True)
    google_calendar_email = Column(String, nullable=True)
```

### Booking Model
```python
class Booking(Base):
    # Calendar Sync Fields
    google_event_id = Column(String, nullable=True)  # Links to calendar event
    sync_status = Column(String, default="pending")  # synced, failed, pending
    sync_error = Column(String, nullable=True)       # Error message if sync failed
    last_synced = Column(DateTime, nullable=True)    # Last successful sync
```

### AvailabilitySlot Model
```python
class AvailabilitySlot(Base):
    # Calendar Integration
    google_event_id = Column(String, nullable=True)  # Links to calendar event
```

## Sync Workflow

### 1. Booking Creation Flow
```
1. User creates booking → Database
2. If calendar connected → Create calendar event
3. Store calendar event ID → Database
4. Update sync status → "synced"
5. Send confirmation email
```

### 2. Calendar Event Creation
```python
# In booking_service.py
if host_user.google_calendar_connected:
    calendar_event = calendar_service.create_booking_event(...)
    if calendar_event:
        booking.google_event_id = calendar_event['id']
        booking.sync_status = "synced"
        booking.last_synced = datetime.utcnow()
```

### 3. Calendar Event Updates
```python
# When booking is updated
if booking.google_event_id and update_calendar:
    calendar_service.update_event(booking.google_event_id, ...)
    booking.last_synced = datetime.utcnow()
```

### 4. Calendar Event Deletion
```python
# When booking is cancelled
if booking.google_event_id:
    calendar_service.delete_event(booking.google_event_id)
    booking.google_event_id = None
    booking.sync_status = "deleted"
```

## Dashboard Data Flow

### Correct Implementation (Database-Only)
```python
# Dashboard should ONLY show database data
def get_dashboard_data():
    # Get all bookings from database (includes synced calendar events)
    all_bookings = get_bookings_for_user(db, user.id)
    
    # Calculate stats from database only
    upcoming_count = len([b for b in all_bookings if is_upcoming(b)])
    total_bookings = len(all_bookings)
    
    return {
        "upcomingCount": upcoming_count,
        "totalBookings": total_bookings,
        "calendarConnected": user.google_calendar_connected
    }
```

### Current Issue (Hybrid Approach - INCORRECT)
```python
# main.py incorrectly fetches live calendar data
calendar_events = calendar_service.get_events()  # ❌ Live fetching
total_bookings = len(db_bookings) + len(calendar_events)  # ❌ Hybrid
```

## API Endpoints

### Dashboard Endpoints
- `/dashboard/api/data` - Should return database-only data
- `/dashboard/api/bookings/upcoming` - Database bookings only
- `/dashboard/api/bookings/all` - Database bookings only

### Calendar Sync Endpoints
- `/api/v1/auth/google/calendar` - Initiate calendar connection
- `/api/v1/auth/calendar/connect` - Complete calendar connection
- `/dashboard/api/calendar/refresh-tokens` - Refresh OAuth tokens

### Booking Endpoints
- `/api/v1/bookings/create` - Creates booking + syncs to calendar
- `/api/v1/bookings/update` - Updates booking + syncs to calendar
- `/api/v1/bookings/cancel` - Cancels booking + removes from calendar

## Error Handling

### Sync Failures
```python
# Track sync errors in database
booking.sync_status = "failed"
booking.sync_error = "Calendar event creation failed"

# Retry mechanism
if booking.sync_status == "failed":
    retry_sync(booking)
```

### Token Expiration
```python
# Automatic token refresh
if token_expired(user.google_access_token):
    new_tokens = refresh_tokens(user.google_refresh_token)
    user.google_access_token = new_tokens['access_token']
    user.google_refresh_token = new_tokens['refresh_token']
```

## Security Considerations

### OAuth Token Storage
- Tokens stored encrypted in database
- Automatic refresh before expiration
- Secure token rotation

### Data Privacy
- User data stays in user's database
- Calendar events only synced to user's own calendar
- No cross-user data sharing

## Performance Benefits

### 1. Fast Dashboard Loading
- No live API calls to Google Calendar
- Database queries are fast and cached
- Consistent response times

### 2. Offline Functionality
- Dashboard works without internet
- Bookings can be created offline
- Sync when connection restored

### 3. Reduced API Quotas
- No constant calendar API calls
- Batch sync operations
- Efficient token usage

## Migration Strategy

### From Hybrid to Database-First
1. **Stop live calendar fetching** in dashboard endpoints
2. **Use only database data** for statistics
3. **Maintain sync mechanism** for calendar integration
4. **Update frontend** to expect database-only responses

### Code Changes Required
```python
# Remove from main.py dashboard endpoints:
calendar_events = calendar_service.get_events()  # ❌ Remove
total_calendar = len(calendar_events)           # ❌ Remove

# Keep only:
db_bookings = get_bookings_for_user(db, user.id)  # ✅ Keep
total_bookings = len(db_bookings)                  # ✅ Keep
```

## Testing Strategy

### Sync Testing
1. Create booking with calendar connected
2. Verify event appears in Google Calendar
3. Verify `google_event_id` stored in database
4. Verify sync status is "synced"

### Offline Testing
1. Disconnect calendar
2. Create booking
3. Verify booking stored in database
4. Verify sync status is "pending"
5. Reconnect calendar and verify sync

### Error Testing
1. Create booking with invalid calendar tokens
2. Verify sync status is "failed"
3. Verify error message stored
4. Test retry mechanism

## Monitoring

### Sync Health Metrics
- Sync success rate
- Failed sync count
- Average sync time
- Token refresh frequency

### Database Metrics
- Total bookings count
- Synced vs unsynced ratio
- Calendar connection rate
- Error rate by sync operation

## Future Enhancements

### 1. Batch Sync Operations
- Sync multiple events at once
- Reduce API call frequency
- Improve performance

### 2. Conflict Resolution
- Handle calendar conflicts
- Merge duplicate events
- Resolve time conflicts

### 3. Multi-Calendar Support
- Support multiple Google accounts
- Microsoft Calendar integration
- Apple Calendar integration

## Conclusion

This architecture ensures:
- **Reliability**: Database as single source of truth
- **Performance**: Fast dashboard loading
- **Offline Capability**: Works without internet
- **Data Consistency**: No conflicts between sources
- **Scalability**: Efficient API usage
- **Maintainability**: Clear data flow and error handling

The key principle is: **Database First, Calendar Sync Second**. 