# Appointment Agent Backend

A FastAPI-based backend for an intelligent appointment booking system with AI agent capabilities and calendar synchronization.

## 🏗️ Architecture Overview

### Database-as-Source-of-Truth Architecture

This application follows a **Database-as-Source-of-Truth** architecture with bidirectional calendar synchronization:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Database      │◄──►│   Application   │◄──►│  Google Calendar│
│  (Source of     │    │   (FastAPI)     │    │   (External)    │
│   Truth)        │    │                 │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Core Principles

1. **Database is the Single Source of Truth**
   - All booking data is stored in the database first
   - External calendars are synced TO the database
   - Display endpoints show database data only

2. **Bidirectional Sync**
   - **DB → Calendar**: Background sync pushes database bookings to Google Calendar
   - **Calendar → DB**: Manual/automatic sync pulls calendar events into database

3. **Modular Design**
   - Separate routers for different functionalities
   - Service layer for business logic
   - Clean separation of concerns

## 🔄 Sync Flow

### 1. Database → Calendar Sync (Automatic)
```
User creates booking → Database → Background Sync → Google Calendar
```

**Components:**
- `BackgroundSyncService`: Periodic sync of database bookings to calendar
- `CalendarSyncService`: Orchestrates sync to multiple providers
- `EnhancedBookingService`: Integrates sync into booking operations

### 2. Calendar → Database Sync (Manual/Automatic)
```
Google Calendar → Pull Events → Create/Update Database Bookings → Dashboard
```

**Components:**
- `sync_calendar_to_database()`: Pulls calendar events into database
- `/api/v1/calendar-sync/pull-from-calendar`: API endpoint to trigger sync
- Webhook handlers: Real-time updates from calendar changes

### 3. Real-time Updates
```
Calendar Changes → Webhooks → Update Database → Dashboard Updates
```

**Components:**
- `WebhookHandler`: Processes calendar webhooks
- `/api/v1/webhooks/google-calendar`: Webhook endpoint

## 📊 Data Flow

### Dashboard Data Flow
```
Dashboard Request → Database Query → Return Database Data
```

**Endpoints:**
- `/dashboard/api/data`: Shows database bookings only
- `/bookings/api/stats`: Shows database booking statistics
- `/bookings/api/list`: Shows database booking list

### Calendar Integration Flow
```
Calendar Connection → OAuth Flow → Store Tokens → Enable Sync
```

**Endpoints:**
- `/api/v1/auth/google/calendar`: Initiate OAuth
- `/api/v1/auth/calendar/connect`: Complete connection
- `/api/v1/calendar-sync/pull-from-calendar`: Manual sync

## 🗂️ Project Structure

```
backend/
├── app/
│   ├── api/v1/endpoints/          # API endpoints
│   │   ├── calendar_sync.py       # Calendar sync endpoints
│   │   ├── webhooks.py           # Webhook handlers
│   │   └── ...
│   ├── core/                      # Core architecture
│   │   ├── calendar_architecture.py # Calendar provider interfaces
│   │   ├── sync_config.py         # Sync configuration
│   │   └── ...
│   ├── routers/                   # Web page routers
│   │   ├── dashboard.py          # Dashboard pages
│   │   ├── bookings.py           # Booking pages
│   │   └── ...
│   ├── services/                  # Business logic
│   │   ├── sync/                 # Sync services
│   │   │   ├── background_sync.py # Background sync
│   │   │   └── webhook_handler.py # Webhook processing
│   │   ├── booking_service.py    # Booking operations
│   │   └── ...
│   └── models/                    # Database models
├── main.py                        # Application entry point
└── requirements.txt               # Dependencies
```

## 🚀 Getting Started

### Prerequisites
- Python 3.11+
- PostgreSQL database
- Google Calendar API credentials

### Installation

1. **Clone and setup:**
```bash
cd backend
uv sync
```

2. **Environment setup:**
```bash
cp .env.example .env
# Edit .env with your database and Google OAuth credentials
```

3. **Database setup:**
```bash
# Run migrations
alembic upgrade head
```

4. **Start the server:**
```bash
uv run main.py
```

## 🔧 Key Features

### Calendar Synchronization
- **Bidirectional sync** between database and Google Calendar
- **Background sync** for automatic database → calendar updates
- **Manual sync** for calendar → database imports
- **Webhook support** for real-time calendar updates

### AI Agent Integration
- **Intelligent booking assistance**
- **Natural language processing**
- **Context-aware responses**

### User Management
- **JWT authentication**
- **OAuth2 for Google Calendar**
- **User profiles and preferences**

## 📡 API Endpoints

### Calendar Sync
- `POST /api/v1/calendar-sync/pull-from-calendar` - Pull calendar events to database
- `POST /api/v1/calendar-sync/force-sync` - Force sync database to calendar
- `GET /api/v1/calendar-sync/sync/status` - Get sync status

### Webhooks
- `POST /api/v1/webhooks/google-calendar` - Google Calendar webhook endpoint

### Dashboard
- `GET /dashboard` - Main dashboard page
- `GET /dashboard/api/data` - Dashboard data (database only)

### Bookings
- `GET /bookings` - Bookings page
- `GET /bookings/api/stats` - Booking statistics
- `GET /bookings/api/list` - Booking list

## 🔄 Sync Status

The system tracks sync status for each booking:
- **`pending`**: Not yet synced
- **`synced`**: Successfully synced to calendar
- **`failed`**: Sync failed, needs retry
- **`conflict`**: Sync conflict detected

## 🛠️ Development

### Adding New Calendar Providers
1. Implement `BaseCalendarProvider` interface
2. Add provider type to `CalendarProviderType` enum
3. Update `create_calendar_provider()` factory function

### Adding New Sync Features
1. Add methods to `BackgroundSyncService`
2. Create API endpoints in `calendar_sync.py`
3. Update webhook handlers if needed

## 📝 Configuration

### Sync Configuration (`app/core/sync_config.py`)
- Background sync intervals
- Enabled providers
- Sync timeouts and retries

### Environment Variables
- `DATABASE_URL`: PostgreSQL connection string
- `GOOGLE_CLIENT_ID`: Google OAuth client ID
- `GOOGLE_CLIENT_SECRET`: Google OAuth client secret
- `SECRET_KEY`: JWT signing key

## 🔍 Troubleshooting

### Common Issues

1. **Calendar not connecting:**
   - Check Google OAuth credentials in `.env`
   - Verify `client_secret.json` exists
   - Check OAuth redirect URI configuration

2. **Sync not working:**
   - Check user has valid Google tokens
   - Verify calendar permissions
   - Check sync logs in application logs

3. **Dashboard showing no data:**
   - Verify database has bookings
   - Check if calendar sync pulled events
   - Ensure user is authenticated

### Debug Commands
```bash
# Check sync status
curl -X GET "http://localhost:8000/api/v1/calendar-sync/sync/status"

# Manual calendar sync
curl -X POST "http://localhost:8000/api/v1/calendar-sync/pull-from-calendar"

# Force database sync
curl -X POST "http://localhost:8000/api/v1/calendar-sync/force-sync"
```

## 📄 License

This project is licensed under the MIT License.
