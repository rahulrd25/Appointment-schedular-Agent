from datetime import datetime
from typing import TYPE_CHECKING, Optional

from app.core.config import settings
from app.services.gmail_service import GmailService

if TYPE_CHECKING:
    from app.models.models import Booking


def send_verification_email(email: str, token: str, host_access_token: str = None, host_refresh_token: str = None):
    """Send verification email using Gmail API."""
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
    booking: "Booking",
    host_access_token: str = None,
    host_refresh_token: str = None
):
    """Send booking confirmation emails using Gmail API."""
    
    # Send confirmation to guest
    send_guest_confirmation_email(guest_email, guest_name, host_name, booking, host_access_token, host_refresh_token)
    
    # Send notification to host
    send_host_notification_email(host_email, host_name, guest_name, guest_email, booking, host_access_token, host_refresh_token)


def send_guest_confirmation_email(
    guest_email: str,
    guest_name: str,
    host_name: str,
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
        
    except Exception as e:
        print(f"Guest confirmation email error: {e}")
        return False


def send_host_notification_email(
    host_email: str,
    host_name: str,
    guest_name: str,
    guest_email: str,
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
        return False 