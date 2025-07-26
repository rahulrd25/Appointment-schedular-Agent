# Backend

This is the backend for the Appointment Agent application, built with FastAPI.

## Development

To set up the development environment:

1.  **Install `uv`**: If you don't have `uv` installed, follow the instructions [here](https://github.com/astral-sh/uv).

2.  **Install dependencies**: Navigate to the `backend` directory and run:
    ```bash
    uv pip install -r requirements.txt
    ```

3.  **Run the application**: 
    ```bash
    uv run python main.py
    ```

    The application will be available at `http://localhost:8000`.

## Project Structure

-   `app/api/v1`: API endpoints for different resources (users, calendar, auth).
-   `app/core`: Core configurations, database settings, security utilities.
-   `app/models`: Database models (using SQLAlchemy).
-   `app/schemas`: Pydantic schemas for request and response validation.
-   `app/services`: Business logic and interactions with external services (e.g., Google Calendar).
-   `app/static`: Static files (CSS, JS, images).
-   `app/templates`: Jinja2 templates for server-side rendered pages.
-   `app/utils`: Utility functions (e.g., email).

## Database

The application uses PostgreSQL. Ensure you have a PostgreSQL instance running and configure the connection string in `app/core/config.py`.

## Frontend (Tailwind CSS)

This project uses Tailwind CSS for styling. To compile the CSS:

1.  **Install Node.js dependencies**: Make sure you have Node.js installed. Then, in the `backend` directory, run:
    ```bash
    npm install
    ```

2.  **Build Tailwind CSS**: To compile `input.css` into `output.css`:
    ```bash
    npm run css:build
    ```

    For development with live reloading:
    ```bash
    npm run css:watch
    ```
