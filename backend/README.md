# Appointment Agent Backend

Welcome to the backend of **Appointment Agent** – an AI-powered appointment scheduling system that makes booking and managing meetings effortless for both hosts and guests.

---

## What is Appointment Agent?

Appointment Agent is a modern scheduling platform that combines:
- **AI-powered conversation** for natural, intelligent scheduling
- **Google Calendar integration** for real-time availability and event management
- **A clean, user-friendly interface** built with Jinja2 templates and Tailwind CSS

Whether you're a solo professional or a team, Appointment Agent helps you automate your scheduling, avoid double-bookings, and provide a seamless experience for your clients or guests.

---

## Key Features

### User Management & Authentication
- Register and log in with email/password or Google OAuth
- Email verification for new users
- Profile management with customizable booking links
- Timezone support for accurate scheduling

### AI Agent System
- Natural language chat for scheduling and managing appointments
- Understands requests like "Book a meeting next Friday at 2pm" or "Show my upcoming appointments"
- Context-aware conversation and intent recognition

### Google Calendar Integration
- Secure OAuth connection to your Google Calendar
- Real-time sync: see your true availability, prevent double-booking
- Automatic event creation, updates, and deletion
- Handles token refresh and permission errors gracefully

### Availability Management
- Create single, recurring, or bulk availability slots
- Use templates for business hours, mornings, afternoons, or custom times
- All slots are synced with Google Calendar (if connected)

### Booking System
- Shareable public booking pages for guests
- Guests see only your real available times
- Simple booking form (name, email, message)
- Automatic Google Calendar event creation for each booking

### Booking Management
- Dashboard to view upcoming bookings, stats, and calendar status
- Cancel, reschedule, or email guests directly from the dashboard
- Filter and search bookings by status, date, or guest
- Email notifications for confirmations, cancellations, and reschedules

### Advanced Features
- Reschedule workflow with available slot selection
- Host can send custom emails to guests
- Automatic Google token refresh
- Friendly error handling and user notifications

---

## Technical Overview

- **Backend**: FastAPI, SQLAlchemy ORM, PostgreSQL
- **Frontend**: Jinja2 templates, Tailwind CSS (no JavaScript required for time formatting)
- **Authentication**: JWT (secure cookies), Google OAuth
- **AI Services**: Pluggable (OpenAI, Claude, etc.)
- **Email**: Gmail API for notifications

---

## Development

To set up the development environment:

1.  **Install `uv`**: If you don't have `uv` installed, follow the instructions [here](https://github.com/astral-sh/uv).

2.  **Install dependencies**: Navigate to the `backend` directory and run:
    ```bash
    uv sync
    ```

3.  **Run the application**: 
    ```bash
    uv run python main.py
    ```

    The application will be available at `http://localhost:8000`.

---

## Project Structure

-   `app/api/v1`: API endpoints for different resources (users, calendar, auth)
-   `app/core`: Core configurations, database settings, security utilities
-   `app/models`: Database models (using SQLAlchemy)
-   `app/schemas`: Pydantic schemas for request and response validation
-   `app/services`: Business logic and integrations (AI, Google Calendar, email, etc.)
-   `app/static`: Static files (CSS, images)
-   `app/templates`: Jinja2 templates for all pages

---

## Database

The application uses PostgreSQL. Make sure you have a PostgreSQL instance running and configure the connection string in `app/core/config.py`.

---

## Frontend (Tailwind CSS)

This project uses Tailwind CSS for styling. To compile the CSS:

1.  **Install Tailwind CSS**: Make sure you have Tailwind CSS installed globally. Then, in the `backend` directory, run:
2.  **Build Tailwind CSS**: To compile `input.css` into `output.css`:
    ```bash
    tailwindcss -i ./app/static/css/input.css -o ./app/static/css/output.css
    ```

    For development with live reloading:
    ```bash
    tailwindcss -i ./app/static/css/input.css -o ./app/static/css/output.css --watch
    ```
