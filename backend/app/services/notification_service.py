from typing import Optional
from app.services.gmail_service import GmailService


class NotificationService:
    """Service for sending notifications using host's Gmail."""
    
    def send_reschedule_notifications(
        self,
        guest_email: str,
        guest_name: str,
        host_email: str,
        host_name: str,
        booking,
        old_start_time,
        reason: str = "",
        host_access_token: str = None,
        host_refresh_token: str = None
    ) -> dict:
        """Send reschedule notifications using host's Gmail."""
        
        results = {
            "guest_email_sent": False,
            "host_email_sent": False,
            "gmail_used": False,
            "errors": [],
            "success": False
        }
        
        # Use Gmail API if host has Google tokens
        if host_access_token and host_refresh_token:
            try:
                gmail_service = GmailService(host_access_token, host_refresh_token)
                
                # Send to guest
                guest_sent = gmail_service.send_reschedule_notification(
                    guest_email, guest_name, host_name, booking, old_start_time, reason
                )
                results["guest_email_sent"] = guest_sent
                
                # Send to host
                host_sent = gmail_service.send_reschedule_notification(
                    host_email, host_name, host_name, booking, old_start_time, reason
                )
                results["host_email_sent"] = host_sent
                
                results["gmail_used"] = True
                print("Gmail API used for notifications")
                
            except Exception as e:
                results["errors"].append(f"Gmail API failed: {str(e)}")
                print(f"Gmail API failed: {e}")
        else:
            results["errors"].append("No Google OAuth tokens available")
            print("No Google OAuth tokens available for email")
        
        # Determine overall success
        results["success"] = results["guest_email_sent"] or results["host_email_sent"]
        
        return results
    
    def send_cancellation_notifications(
        self,
        guest_email: str,
        guest_name: str,
        host_email: str,
        host_name: str,
        booking,
        host_access_token: str = None,
        host_refresh_token: str = None
    ) -> dict:
        """Send cancellation notifications using host's Gmail."""
        
        results = {
            "guest_email_sent": False,
            "host_email_sent": False,
            "gmail_used": False,
            "errors": [],
            "success": False
        }
        
        # Use Gmail API if host has Google tokens
        if host_access_token and host_refresh_token:
            try:
                gmail_service = GmailService(host_access_token, host_refresh_token)
                
                # Send to guest
                guest_sent = gmail_service.send_cancellation_notification(
                    guest_email, guest_name, host_name, booking
                )
                results["guest_email_sent"] = guest_sent
                
                # Send to host
                host_sent = gmail_service.send_cancellation_notification(
                    host_email, host_name, host_name, booking
                )
                results["host_email_sent"] = host_sent
                
                results["gmail_used"] = True
                print("Gmail API used for cancellation notifications")
                
            except Exception as e:
                results["errors"].append(f"Gmail API failed: {str(e)}")
                print(f"Gmail API failed: {e}")
        else:
            results["errors"].append("No Google OAuth tokens available")
            print("No Google OAuth tokens available for cancellation email")
        
        # Determine overall success
        results["success"] = results["guest_email_sent"] or results["host_email_sent"]
        
        return results
    
    def get_notification_summary(self, results: dict) -> dict:
        """Generate detailed notification results."""
        
        if results["success"]:
            if results["guest_email_sent"] and results["host_email_sent"]:
                return {
                    "status": "success",
                    "message": f"✅ Booking rescheduled successfully! Gmail notifications sent to both parties.",
                    "details": "Both guest and host have been notified via email from your Gmail."
                }
            elif results["guest_email_sent"]:
                return {
                    "status": "partial",
                    "message": f"⚠️ Booking rescheduled. Gmail notification sent to guest only.",
                    "details": "Guest was notified, but host notification failed."
                }
            else:
                return {
                    "status": "partial", 
                    "message": f"⚠️ Booking rescheduled. Gmail notification sent to host only.",
                    "details": "Host was notified, but guest notification failed."
                }
        else:
            return {
                "status": "failed",
                "message": "❌ Booking rescheduled in database, but Gmail notifications failed.",
                "details": f"Errors: {'; '.join(results['errors'])}. Please check your Google Calendar connection or manually notify the guest.",
                "errors": results["errors"]
            } 