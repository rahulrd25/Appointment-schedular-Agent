<<<<<<< HEAD
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import TYPE_CHECKING

from app.core.config import settings

=======
from datetime import datetime
from typing import TYPE_CHECKING, Optional, Any

from app.core.config import settings
from app.services.gmail_service import GmailService
from app.services.token_refresh_service import get_token_refresh_service

>>>>>>> e3b999cd02f578d5176e7dbc287d1a2a1f5f3840
if TYPE_CHECKING:
    from app.models.models import Booking


<<<<<<< HEAD
def send_verification_email(email: str, token: str):
    """Send verification email to user"""
=======
def send_verification_email(email: str, token: str, host_access_token: str = None, host_refresh_token: str = None):
    """Send verification email using Gmail API."""
>>>>>>> e3b999cd02f578d5176e7dbc287d1a2a1f5f3840
    try:
        # Use Gmail API if tokens are available
        if host_access_token and host_refresh_token:
            gmail_service = GmailService(host_access_token, host_refresh_token)
            
            verification_url = f"{settings.FRONTEND_URL}/verify-email?token={token}"
            
            html_body = f"""
            <html>
            <body>
                <h2>Welcome to Appointment Agent!</h2>
                <p>Please verify your email address by clicking the link below:</p>
                <a href="{verification_url}">Verify Email</a>
                <p>If the link doesn't work, copy and paste this URL into your browser:</p>
                <p>{verification_url}</p>
                <p>This link will expire in 24 hours.</p>
            </body>
            </html>
            """
            
            return gmail_service.send_email(email, "Verify Your Email - Appointment Agent", html_body)
        
        print("No Google OAuth tokens available for email verification")
        return False
        
    except Exception as e:
        print(f"Email sending error: {e}")
        return False


def send_booking_confirmation_email(
    guest_email: str,
    guest_name: str,
    host_email: str,
    host_name: str,
<<<<<<< HEAD
    booking: "Booking"
):
    """Send booking confirmation emails to both guest and host."""
    
    # Send confirmation to guest
    send_guest_confirmation_email(guest_email, guest_name, host_name, booking)
    
    # Send notification to host
    send_host_notification_email(host_email, host_name, guest_name, guest_email, booking)
=======
    booking: "Booking",
    host_access_token: str = None,
    host_refresh_token: str = None,
    db: Optional[Any] = None
):
    """Send booking confirmation emails using Gmail API with automatic token refresh."""
    
    # If we have a database session, try to refresh tokens automatically
    if db:
        try:
            from app.services.token_refresh_service import get_token_refresh_service
            token_service = get_token_refresh_service(db)
            
            # Get the host user
            host_user = token_service.get_user_by_email(host_email)
            if host_user:
                # Ensure tokens are valid
                token_status = token_service.ensure_valid_tokens(host_user)
                if token_status["success"]:
                    # Use the refreshed tokens
                    host_access_token = token_status["access_token"]
                    host_refresh_token = token_status["refresh_token"]
                    print(f"✅ Tokens refreshed automatically for {host_email}")
                else:
                    print(f"⚠️  Token refresh failed for {host_email}: {token_status['message']}")
                    if token_status.get("requires_reconnection"):
                        print(f"   User {host_email} needs to reconnect Google Calendar")
        except Exception as e:
            print(f"Token refresh error: {e}")
    
    # Send confirmation to guest
    guest_email_sent = send_guest_confirmation_email(guest_email, guest_name, host_name, booking, host_access_token, host_refresh_token)
    
    # Send notification to host
    host_email_sent = send_host_notification_email(host_email, host_name, guest_name, guest_email, booking, host_access_token, host_refresh_token)
    
    # Return success if at least one email was sent
    return guest_email_sent or host_email_sent
>>>>>>> e3b999cd02f578d5176e7dbc287d1a2a1f5f3840


def send_guest_confirmation_email(
    guest_email: str,
    guest_name: str,
    host_name: str,
<<<<<<< HEAD
    booking: "Booking"
):
    """Send booking confirmation email to the guest."""
    try:
        msg = MIMEMultipart()
        msg['From'] = settings.SMTP_USERNAME
        msg['To'] = guest_email
        msg['Subject'] = f"Booking Confirmed with {host_name}"
        
        # Format datetime for display
        start_time = booking.start_time.strftime("%B %d, %Y at %I:%M %p UTC")
        end_time = booking.end_time.strftime("%I:%M %p UTC")
        
        body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background-color: #4f46e5; color: white; padding: 20px; text-align: center;">
                <h1>Booking Confirmed! 🎉</h1>
            </div>
            
            <div style="padding: 20px;">
                <p>Hi {guest_name},</p>
                
                <p>Great news! Your booking with <strong>{host_name}</strong> has been confirmed.</p>
                
                <div style="background-color: #f3f4f6; padding: 15px; border-radius: 8px; margin: 20px 0;">
                    <h3 style="margin-top: 0;">📅 Booking Details</h3>
                    <p><strong>Date & Time:</strong> {start_time} - {end_time}</p>
                    <p><strong>Host:</strong> {host_name}</p>
                    <p><strong>Booking ID:</strong> #{booking.id}</p>
                </div>
                
                {f'<p><strong>Your Message:</strong> {booking.guest_message}</p>' if booking.guest_message else ''}
                
                <div style="background-color: #fef3c7; padding: 15px; border-radius: 8px; margin: 20px 0;">
                    <p><strong>📝 What's Next?</strong></p>
                    <ul>
                        <li>You should receive a Google Calendar invitation shortly</li>
                        <li>Add this event to your calendar</li>
                        <li>If you need to reschedule or cancel, please contact {host_name} directly</li>
                    </ul>
                </div>
                
                <p>Looking forward to your meeting!</p>
                <p>Best regards,<br>The Appointment Agent Team</p>
            </div>
            
            <div style="background-color: #f9fafb; padding: 20px; text-align: center; font-size: 12px; color: #6b7280;">
                <p>This is an automated message from Appointment Agent.</p>
            </div>
        </body>
        </html>
        """
        
        msg.attach(MIMEText(body, 'html'))
        
        server = smtplib.SMTP(settings.SMTP_SERVER, settings.SMTP_PORT)
        server.starttls()
        server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()
        
        return True
=======
    booking: "Booking",
    host_access_token: str = None,
    host_refresh_token: str = None
):
    """Send booking confirmation email to the guest."""
    try:
        # Use Gmail API if tokens are available
        if host_access_token and host_refresh_token:
            gmail_service = GmailService(host_access_token, host_refresh_token)
            
            html_body = f"""
            <html>
            <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <div style="background-color: #4f46e5; color: white; padding: 20px; text-align: center;">
                    <h1>Booking Confirmed! 🎉</h1>
                </div>
                
                <div style="padding: 20px;">
                    <p>Hi {guest_name},</p>
                    
                    <p>Great news! Your booking with <strong>{host_name}</strong> has been confirmed.</p>
                    
                    <div style="background-color: #f3f4f6; padding: 15px; border-radius: 8px; margin: 20px 0;">
                        <h3 style="margin-top: 0;">📅 Booking Details</h3>
                        <p><strong>Date & Time:</strong> {booking.start_time.strftime('%B %d, %Y at %I:%M %p')}</p>
                        <p><strong>Host:</strong> {host_name}</p>
                        <p><strong>Booking ID:</strong> #{booking.id}</p>
                    </div>
                    
                    <p>Looking forward to your meeting!</p>
                    <p>Best regards,<br>The Appointment Agent Team</p>
                </div>
            </body>
            </html>
            """
            
            return gmail_service.send_email(guest_email, f"Booking Confirmed with {host_name}", html_body)
        
        print("No Google OAuth tokens available for guest confirmation email")
        return False
        
>>>>>>> e3b999cd02f578d5176e7dbc287d1a2a1f5f3840
    except Exception as e:
        print(f"Guest confirmation email error: {e}")
        return False


def send_host_notification_email(
    host_email: str,
    host_name: str,
    guest_name: str,
    guest_email: str,
<<<<<<< HEAD
    booking: "Booking"
):
    """Send booking notification email to the host."""
    try:
        msg = MIMEMultipart()
        msg['From'] = settings.SMTP_USERNAME
        msg['To'] = host_email
        msg['Subject'] = f"New Booking: {guest_name}"
        
        # Format datetime for display
        start_time = booking.start_time.strftime("%B %d, %Y at %I:%M %p UTC")
        end_time = booking.end_time.strftime("%I:%M %p UTC")
        
        body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background-color: #059669; color: white; padding: 20px; text-align: center;">
                <h1>New Booking Received! 📅</h1>
            </div>
            
            <div style="padding: 20px;">
                <p>Hi {host_name},</p>
                
                <p>You have a new booking! Here are the details:</p>
                
                <div style="background-color: #f3f4f6; padding: 15px; border-radius: 8px; margin: 20px 0;">
                    <h3 style="margin-top: 0;">📋 Booking Details</h3>
                    <p><strong>Guest:</strong> {guest_name}</p>
                    <p><strong>Email:</strong> {guest_email}</p>
                    <p><strong>Date & Time:</strong> {start_time} - {end_time}</p>
                    <p><strong>Booking ID:</strong> #{booking.id}</p>
                </div>
                
                {f'<div style="background-color: #eff6ff; padding: 15px; border-radius: 8px; margin: 20px 0;"><p><strong>Guest Message:</strong></p><p style="font-style: italic;">"{booking.guest_message}"</p></div>' if booking.guest_message else ''}
                
                <div style="background-color: #f0f9ff; padding: 15px; border-radius: 8px; margin: 20px 0;">
                    <p><strong>🎯 Action Items:</strong></p>
                    <ul>
                        <li>The event has been automatically added to your Google Calendar</li>
                        <li>Both you and {guest_name} will receive calendar invitations</li>
                        <li>Prepare any materials or agenda items for the meeting</li>
                    </ul>
                </div>
                
                <p>The booking system has handled all the scheduling details for you!</p>
                <p>Best regards,<br>The Appointment Agent Team</p>
            </div>
            
            <div style="background-color: #f9fafb; padding: 20px; text-align: center; font-size: 12px; color: #6b7280;">
                <p>This is an automated message from Appointment Agent.</p>
            </div>
        </body>
        </html>
        """
        
        msg.attach(MIMEText(body, 'html'))
        
        server = smtplib.SMTP(settings.SMTP_SERVER, settings.SMTP_PORT)
        server.starttls()
        server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()
        
        return True
    except Exception as e:
        print(f"Host notification email error: {e}")
=======
    booking: "Booking",
    host_access_token: str = None,
    host_refresh_token: str = None
):
    """Send booking notification email to the host."""
    try:
        # Use Gmail API if tokens are available
        if host_access_token and host_refresh_token:
            gmail_service = GmailService(host_access_token, host_refresh_token)
            
            html_body = f"""
            <html>
            <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <div style="background-color: #059669; color: white; padding: 20px; text-align: center;">
                    <h1>New Booking Received! 📅</h1>
                </div>
                
                <div style="padding: 20px;">
                    <p>Hi {host_name},</p>
                    
                    <p>You have a new booking! Here are the details:</p>
                    
                    <div style="background-color: #f3f4f6; padding: 15px; border-radius: 8px; margin: 20px 0;">
                        <h3 style="margin-top: 0;">📋 Booking Details</h3>
                        <p><strong>Guest:</strong> {guest_name}</p>
                        <p><strong>Email:</strong> {guest_email}</p>
                        <p><strong>Date & Time:</strong> {booking.start_time.strftime('%B %d, %Y at %I:%M %p')}</p>
                        <p><strong>Booking ID:</strong> #{booking.id}</p>
                    </div>
                    
                    <p>Best regards,<br>The Appointment Agent Team</p>
                </div>
            </body>
            </html>
            """
            
            return gmail_service.send_email(host_email, f"New Booking: {guest_name}", html_body)
        
        print("No Google OAuth tokens available for host notification email")
        return False
        
    except Exception as e:
        print(f"Host notification email error: {e}")
        return False


def send_host_to_guest_email(
    host_email: str,
    host_name: str,
    guest_email: str,
    guest_name: str,
    subject: str,
    message: str,
    booking: "Booking",
    host_access_token: str = None,
    host_refresh_token: str = None
):
    """Send email from host to guest using Gmail API."""
    try:
        # Use Gmail API if tokens are available
        if host_access_token and host_refresh_token:
            gmail_service = GmailService(host_access_token, host_refresh_token)
            
            start_time = booking.start_time.strftime("%B %d, %Y at %I:%M %p UTC")
            end_time = booking.end_time.strftime("%I:%M %p UTC")
            
            html_body = f"""
            <html>
            <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <div style="background-color: #4f46e5; color: white; padding: 20px; text-align: center;">
                    <h1>Message from {host_name}</h1>
                </div>
                
                <div style="padding: 20px;">
                    <p>Hi {guest_name},</p>
                    
                    <div style="background-color: #f3f4f6; padding: 15px; border-radius: 8px; margin: 20px 0;">
                        <h3 style="margin-top: 0;">📅 Booking Reference</h3>
                        <p><strong>Date & Time:</strong> {start_time} - {end_time}</p>
                        <p><strong>Booking ID:</strong> #{booking.id}</p>
                    </div>
                    
                    <div style="background-color: #eff6ff; padding: 15px; border-radius: 8px; margin: 20px 0;">
                        <h3 style="margin-top: 0;">💬 Message from {host_name}</h3>
                        <div style="white-space: pre-wrap; font-family: Arial, sans-serif;">
                            {message}
                        </div>
                    </div>
                    
                    <p>If you have any questions, please reply to this email or contact {host_name} directly.</p>
                    <p>Best regards,<br>{host_name}</p>
                </div>
                
                <div style="background-color: #f9fafb; padding: 20px; text-align: center; font-size: 12px; color: #6b7280;">
                    <p>This message was sent via Appointment Agent.</p>
                </div>
            </body>
            </html>
            """
            
            return gmail_service.send_email(guest_email, subject, html_body, host_name)
        
        print("No Google OAuth tokens available for host-to-guest email")
        return False
        
    except Exception as e:
        print(f"Host to guest email error: {e}")
>>>>>>> e3b999cd02f578d5176e7dbc287d1a2a1f5f3840
        return False 