from datetime import datetime
from typing import TYPE_CHECKING, Optional, Any

from app.core.config import settings
from app.services.gmail_service import GmailService
from app.services.token_refresh_service import get_token_refresh_service

if TYPE_CHECKING:
    from app.models.models import Booking

# This file is kept for potential future use of email verification and host-to-guest messaging
# The booking confirmation emails are now handled by NotificationService 