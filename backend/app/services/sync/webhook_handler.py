"""
Webhook Handler - Processes external calendar updates.
This module handles webhooks from calendar providers to keep our database in sync.
"""

from typing import Dict, Any, Optional
from datetime import datetime
import logging
import json

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.models import Booking, AvailabilitySlot, User
from app.core.calendar_architecture import CalendarProviderType
from app.core.sync_config import get_sync_config

# Configure logging
logger = logging.getLogger(__name__)


class WebhookHandler:
    """
    Handles webhooks from calendar providers to keep database in sync.
    Maintains existing functionality while adding external update processing.
    """
    
    def __init__(self, db: Session):
        """
        Initialize the webhook handler.
        
        Args:
            db: Database session
        """
        self.db = db
        self.sync_config = get_sync_config()
    
    def process_google_calendar_webhook(self, webhook_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process Google Calendar webhook.
        
        Args:
            webhook_data: Webhook payload from Google Calendar
            
        Returns:
            Processing result
        """
        try:
            logger.info("Processing Google Calendar webhook")
            
            # Extract event information from webhook
            event_data = self._extract_google_event_data(webhook_data)
            if not event_data:
                logger.warning("No valid event data found in Google Calendar webhook")
                return {"success": False, "error": "No valid event data"}
            
            # Find corresponding booking in database
            booking = self._find_booking_by_google_event_id(event_data.get('id'))
            if not booking:
                logger.warning(f"No booking found for Google event ID: {event_data.get('id')}")
                return {"success": False, "error": "No corresponding booking found"}
            
            # Update booking based on webhook data
            update_result = self._update_booking_from_external_event(booking, event_data)
            
            logger.info(f"Successfully processed Google Calendar webhook for booking {booking.id}")
            return {"success": True, "booking_id": booking.id, "update_result": update_result}
            
        except Exception as e:
            logger.error(f"Failed to process Google Calendar webhook: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def process_microsoft_calendar_webhook(self, webhook_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process Microsoft Calendar webhook (future implementation).
        
        Args:
            webhook_data: Webhook payload from Microsoft Calendar
            
        Returns:
            Processing result
        """
        try:
            logger.info("Processing Microsoft Calendar webhook")
            
            # Future implementation for Microsoft Calendar
            # This maintains the same pattern as Google Calendar
            
            return {"success": True, "message": "Microsoft Calendar webhook processing not yet implemented"}
            
        except Exception as e:
            logger.error(f"Failed to process Microsoft Calendar webhook: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def _extract_google_event_data(self, webhook_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Extract event data from Google Calendar webhook.
        
        Args:
            webhook_data: Raw webhook data from Google Calendar
            
        Returns:
            Extracted event data or None if invalid
        """
        try:
            # Google Calendar webhook structure
            if 'resource' in webhook_data:
                event_data = webhook_data['resource']
                
                # Extract relevant fields
                extracted_data = {
                    'id': event_data.get('id'),
                    'summary': event_data.get('summary'),
                    'description': event_data.get('description'),
                    'start': event_data.get('start', {}).get('dateTime'),
                    'end': event_data.get('end', {}).get('dateTime'),
                    'status': event_data.get('status'),
                    'updated': event_data.get('updated')
                }
                
                # Validate required fields
                if extracted_data['id'] and extracted_data['summary']:
                    return extracted_data
                
            return None
            
        except Exception as e:
            logger.error(f"Failed to extract Google event data: {str(e)}")
            return None
    
    def _find_booking_by_google_event_id(self, google_event_id: str) -> Optional[Booking]:
        """
        Find booking by Google Calendar event ID.
        
        Args:
            google_event_id: Google Calendar event ID
            
        Returns:
            Booking object or None if not found
        """
        try:
            # Search for booking with matching Google event ID
            booking = self.db.query(Booking).filter(
                Booking.google_event_id == google_event_id
            ).first()
            
            return booking
            
        except Exception as e:
            logger.error(f"Failed to find booking by Google event ID {google_event_id}: {str(e)}")
            return None
    
    def _update_booking_from_external_event(self, booking: Booking, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update booking from external calendar event.
        
        Args:
            booking: Booking to update
            event_data: External event data
            
        Returns:
            Update result
        """
        try:
            updates = {}
            
            # Update title/summary if changed
            if event_data.get('summary') and event_data['summary'] != booking.guest_name:
                booking.guest_name = event_data['summary']
                updates['guest_name'] = event_data['summary']
            
            # Update description if changed
            if event_data.get('description') and event_data['description'] != booking.guest_message:
                booking.guest_message = event_data['description']
                updates['guest_message'] = event_data['description']
            
            # Update times if changed
            if event_data.get('start'):
                new_start_time = datetime.fromisoformat(event_data['start'].replace('Z', '+00:00'))
                if new_start_time != booking.start_time:
                    booking.start_time = new_start_time
                    updates['start_time'] = new_start_time
            
            if event_data.get('end'):
                new_end_time = datetime.fromisoformat(event_data['end'].replace('Z', '+00:00'))
                if new_end_time != booking.end_time:
                    booking.end_time = new_end_time
                    updates['end_time'] = new_end_time
            
            # Update status if event was cancelled
            if event_data.get('status') == 'cancelled':
                booking.status = 'cancelled'
                updates['status'] = 'cancelled'
            
            # Commit changes if any updates were made
            if updates:
                self.db.commit()
                logger.info(f"Updated booking {booking.id} from external calendar: {list(updates.keys())}")
                return {"updated": True, "changes": updates}
            else:
                logger.info(f"No changes needed for booking {booking.id}")
                return {"updated": False, "changes": {}}
            
        except Exception as e:
            logger.error(f"Failed to update booking {booking.id} from external event: {str(e)}")
            self.db.rollback()
            return {"updated": False, "error": str(e)}
    
    def validate_webhook_signature(self, webhook_data: Dict[str, Any], signature: str, provider: str) -> bool:
        """
        Validate webhook signature for security.
        
        Args:
            webhook_data: Webhook payload
            signature: Signature from webhook headers
            provider: Calendar provider name
            
        Returns:
            True if signature is valid, False otherwise
        """
        try:
            # Future: Implement proper signature validation
            # For now, we'll accept all webhooks (not recommended for production)
            logger.warning("Webhook signature validation not implemented - accepting all webhooks")
            return True
            
        except Exception as e:
            logger.error(f"Failed to validate webhook signature: {str(e)}")
            return False
    
    def handle_webhook(self, provider: str, webhook_data: Dict[str, Any], signature: str = None) -> Dict[str, Any]:
        """
        Main webhook handler that routes to appropriate provider handler.
        
        Args:
            provider: Calendar provider name
            webhook_data: Webhook payload
            signature: Webhook signature for validation
            
        Returns:
            Processing result
        """
        try:
            # Validate webhook signature
            if not self.validate_webhook_signature(webhook_data, signature, provider):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid webhook signature"
                )
            
            # Route to appropriate provider handler
            if provider == "google":
                return self.process_google_calendar_webhook(webhook_data)
            elif provider == "microsoft":
                return self.process_microsoft_calendar_webhook(webhook_data)
            else:
                logger.warning(f"Unsupported calendar provider: {provider}")
                return {"success": False, "error": f"Unsupported provider: {provider}"}
                
        except HTTPException:
            """Re-raise HTTP exceptions."""
            raise
        except Exception as e:
            logger.error(f"Failed to handle webhook for provider {provider}: {str(e)}")
            return {"success": False, "error": str(e)} 