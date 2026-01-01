import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
import secrets
import string
from datetime import datetime
from .config import settings

def send_email(to_email: str, subject: str, html_content: str):
    """Send email using SMTP"""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{settings.EMAILS_FROM_NAME} <{settings.EMAILS_FROM_EMAIL}>"
    msg["To"] = to_email
    
    # Create HTML part
    html_part = MIMEText(html_content, "html")
    msg.attach(html_part)
    
    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(msg)
        return True
    except Exception as e:
        print(f"Email send error: {e}")
        return False

def generate_verification_email(name: str, verification_url: str):
    """Generate verification email HTML"""
    return f"""
    <html>
    <body>
        <h2>Email Verification</h2>
        <p>Hello {name},</p>
        <p>Thank you for registering! Please click the link below to verify your email:</p>
        <p><a href="{verification_url}">Verify Email</a></p>
        <p>This link will expire in {settings.VERIFICATION_TOKEN_EXPIRE_HOURS} hours.</p>
        <br>
        <p>If you didn't create an account, please ignore this email.</p>
    </body>
    </html>
    """

def generate_password_reset_email(name: str, reset_url: str):
    """Generate password reset email HTML"""
    return f"""
    <html>
    <body>
        <h2>Password Reset Request</h2>
        <p>Hello {name},</p>
        <p>You requested to reset your password. Click the link below:</p>
        <p><a href="{reset_url}">Reset Password</a></p>
        <p>This link will expire in 1 hour.</p>
        <br>
        <p>If you didn't request this, please ignore this email.</p>
    </body>
    </html>
    """

def generate_random_password(length=12):
    """Generate random password"""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(secrets.choice(alphabet) for i in range(length))

def save_screenshot(file_content: bytes, user_id: int, trade_id: int) -> str:
    """Save screenshot and return path"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"screenshot_{user_id}_{trade_id}_{timestamp}.png"
    filepath = settings.UPLOAD_DIR / filename
    
    with open(filepath, "wb") as f:
        f.write(file_content)
    
    return str(filename)