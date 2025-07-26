import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.core.config import settings

def send_verification_email(email: str, token: str):
    """Send verification email to user"""
    try:
        # Create message
        msg = MIMEMultipart()
        msg['From'] = settings.SMTP_USERNAME
        msg['To'] = email
        msg['Subject'] = "Verify Your Email - Appointment Agent"
        
        # Create verification link
        verification_url = f"{settings.FRONTEND_URL}/verify-email?token={token}"
        
        # Email body
        body = f"""
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
        
        msg.attach(MIMEText(body, 'html'))
        
        # Send email
        server = smtplib.SMTP(settings.SMTP_SERVER, settings.SMTP_PORT)
        server.starttls()
        server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()
        
        return True
    except Exception as e:
        print(f"Email sending error: {e}")
        return False 