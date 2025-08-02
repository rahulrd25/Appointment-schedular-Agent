import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from app.core.config import settings


class GmailService:
    def __init__(self, access_token: str, refresh_token: str):
        """Initialize Gmail service with OAuth credentials."""
        self.credentials = Credentials(
            token=access_token,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.GOOGLE_CLIENT_ID,
            client_secret=settings.GOOGLE_CLIENT_SECRET,
            scopes=['https://www.googleapis.com/auth/gmail.send']
        )
        self.service = build('gmail', 'v1', credentials=self.credentials)

    def send_email(self, to_email: str, subject: str, html_body: str, from_name: str = None):
        """Send email using Gmail API."""
        try:
            # Create message
            message = MIMEMultipart('alternative')
            message['to'] = to_email
            message['subject'] = subject
            
            # Attach HTML content
            html_part = MIMEText(html_body, 'html')
            message.attach(html_part)
            
            # Encode message
            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
            
            # Send email
            sent_message = self.service.users().messages().send(
                userId='me',
                body={'raw': raw_message}
            ).execute()
            
            print(f"✅ Email sent successfully: {sent_message['id']}")
            return True
            
        except HttpError as error:
            print(f"❌ Gmail API error: {error}")
            return False
        except Exception as e:
            print(f"❌ Gmail service error: {e}")
            return False

    def send_reschedule_notification(self, to_email: str, to_name: str, host_name: str, booking, old_time, reason=""):
        """Send reschedule notification email."""
        subject = f"Booking Rescheduled with {host_name}"
        
        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background-color: #f59e0b; color: white; padding: 20px; text-align: center;">
                <h1>Booking Rescheduled! 🔄</h1>
            </div>
            
            <div style="padding: 20px;">
                <p>Hi {to_name},</p>
                
                <p>Your booking with <strong>{host_name}</strong> has been rescheduled.</p>
                
                <div style="background-color: #f3f4f6; padding: 15px; border-radius: 8px; margin: 20px 0;">
                    <h3 style="margin-top: 0;">📅 Updated Booking Details</h3>
                    <p><strong>New Date & Time:</strong> {booking.start_time.strftime('%B %d, %Y at %I:%M %p')}</p>
                    <p><strong>Previous Date & Time:</strong> {old_time.strftime('%B %d, %Y at %I:%M %p')}</p>
                    <p><strong>Booking ID:</strong> #{booking.id}</p>
                </div>
                
                {f'<div style="background-color: #eff6ff; padding: 15px; border-radius: 8px; margin: 20px 0;"><p><strong>Reason for Rescheduling:</strong></p><p style="font-style: italic;">"{reason}"</p></div>' if reason else ''}
                
                <p>If you have any questions, please contact {host_name} directly.</p>
                <p>Best regards,<br>The SmartCal Team</p>
            </div>
        </body>
        </html>
        """
        
        return self.send_email(to_email, subject, html_body, host_name)
    
    def send_cancellation_notification(self, to_email: str, to_name: str, host_name: str, booking):
        """Send cancellation notification email."""
        subject = f"Booking Cancelled with {host_name}"
        
        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background-color: #ef4444; color: white; padding: 20px; text-align: center;">
                <h1>Booking Cancelled ❌</h1>
            </div>
            
            <div style="padding: 20px;">
                <p>Hi {to_name},</p>
                
                <p>Your booking with <strong>{host_name}</strong> has been cancelled.</p>
                
                <div style="background-color: #f3f4f6; padding: 15px; border-radius: 8px; margin: 20px 0;">
                    <h3 style="margin-top: 0;">📅 Cancelled Booking Details</h3>
                    <p><strong>Date & Time:</strong> {booking.start_time.strftime('%B %d, %Y at %I:%M %p')}</p>
                    <p><strong>Booking ID:</strong> #{booking.id}</p>
                    <p><strong>Guest:</strong> {booking.guest_name}</p>
                    <p><strong>Email:</strong> {booking.guest_email}</p>
                </div>
                
                <p>If you have any questions, please contact {host_name} directly.</p>
                <p>Best regards,<br>The SmartCal Team</p>
            </div>
        </body>
        </html>
        """
        
        return self.send_email(to_email, subject, html_body, host_name) 
    
    def send_booking_confirmation_notification(self, to_email: str, to_name: str, host_name: str, booking, is_host=False):
        """Send booking confirmation notification email."""
        
        if is_host:
            # Email for the host
            subject = f"New Booking Received - {booking.guest_name}"
            html_body = f"""
            <html>
            <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <div style="background-color: #10b981; color: white; padding: 20px; text-align: center;">
                    <h1>New Booking Received! 📅</h1>
                </div>
                
                <div style="padding: 20px;">
                    <p>Hi {to_name},</p>
                    
                    <p>You have received a <strong>new booking</strong>!</p>
                    
                    <div style="background-color: #f3f4f6; padding: 15px; border-radius: 8px; margin: 20px 0;">
                        <h3 style="margin-top: 0;">📅 Booking Details</h3>
                        <p><strong>Date & Time:</strong> {booking.start_time.strftime('%B %d, %Y at %I:%M %p')}</p>
                        <p><strong>Duration:</strong> {int((booking.end_time - booking.start_time).total_seconds() / 60)} minutes</p>
                        <p><strong>Booking ID:</strong> #{booking.id}</p>
                        <p><strong>Guest:</strong> {booking.guest_name}</p>
                        <p><strong>Guest Email:</strong> {booking.guest_email}</p>
                        <p><strong>Notes:</strong> {booking.guest_message or 'No additional notes'}</p>
                    </div>
                    
                    <p>This booking has been automatically added to your calendar.</p>
                    <p>Best regards,<br>The SmartCal Team</p>
                </div>
            </body>
            </html>
            """
        else:
            # Email for the guest
            subject = f"Booking Confirmed with {host_name}"
            html_body = f"""
            <html>
            <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <div style="background-color: #10b981; color: white; padding: 20px; text-align: center;">
                    <h1>Booking Confirmed! ✅</h1>
                </div>
                
                <div style="padding: 20px;">
                    <p>Hi {to_name},</p>
                    
                    <p>Your booking with <strong>{host_name}</strong> has been confirmed!</p>
                    
                    <div style="background-color: #f3f4f6; padding: 15px; border-radius: 8px; margin: 20px 0;">
                        <h3 style="margin-top: 0;">📅 Booking Details</h3>
                        <p><strong>Date & Time:</strong> {booking.start_time.strftime('%B %d, %Y at %I:%M %p')}</p>
                        <p><strong>Duration:</strong> {int((booking.end_time - booking.start_time).total_seconds() / 60)} minutes</p>
                        <p><strong>Booking ID:</strong> #{booking.id}</p>
                        <p><strong>Host:</strong> {host_name}</p>
                    </div>
                    
                    <p>If you have any questions, please contact {host_name} directly.</p>
                    <p>Best regards,<br>The SmartCal Team</p>
                </div>
            </body>
            </html>
            """
        
        return self.send_email(to_email, subject, html_body, host_name) 