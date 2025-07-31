from fastapi import APIRouter, Request, Form, HTTPException, Depends, File, UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from fastapi.templating import Jinja2Templates
import os
import shutil
from pathlib import Path
from datetime import datetime

from app.core.database import get_db
from app.services.user_service import get_user_by_email
from app.core.security import verify_token, get_password_hash, verify_password
from app.services.google_calendar_service import GoogleCalendarService

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/settings")
async def settings_page(request: Request, db: Session = Depends(get_db)):
    """Settings page"""
    access_token = request.cookies.get("access_token")

    if not access_token:
        return RedirectResponse(url="/login", status_code=302)

    try:
        payload = verify_token(access_token)
        if not payload:
            return RedirectResponse(url="/login", status_code=302)

        user_email = payload.get("sub")
        user = get_user_by_email(db, user_email)

        if not user:
            return RedirectResponse(url="/login", status_code=302)

        return templates.TemplateResponse("settings.html", {
            "request": request,
            "current_user": user
        })

    except Exception as e:
        print(f"Settings page error: {e}")
        return RedirectResponse(url="/login", status_code=302)


@router.post("/settings/api/profile")
async def update_profile(
    request: Request,
    full_name: str = Form(...),
    scheduling_slug: str = Form(...),
    timezone: str = Form(...),
    db: Session = Depends(get_db)
):
    """Update user profile"""
    access_token = request.cookies.get("access_token")
    if not access_token:
        return {"error": "Not authenticated"}
    
    try:
        payload = verify_token(access_token)
        if not payload:
            return {"error": "Invalid token"}
        
        user_email = payload.get("sub")
        user = get_user_by_email(db, user_email)
        
        if not user:
            return {"error": "User not found"}
        
        # Update user profile
        user.full_name = full_name
        user.scheduling_slug = scheduling_slug
        user.timezone = timezone
        
        db.commit()
        
        return {"success": True, "message": "Profile updated successfully"}
        
    except Exception as e:
        print(f"Error updating profile: {e}")
        return {"error": str(e)}


@router.post("/settings/api/calendar-preferences")
async def update_calendar_preferences(
    request: Request,
    default_duration: int = Form(30),
    buffer_time: int = Form(10),
    db: Session = Depends(get_db)
):
    """Update calendar preferences"""
    access_token = request.cookies.get("access_token")
    if not access_token:
        return {"error": "Not authenticated"}
    
    try:
        payload = verify_token(access_token)
        if not payload:
            return {"error": "Invalid token"}
        
        user_email = payload.get("sub")
        user = get_user_by_email(db, user_email)
        
        if not user:
            return {"error": "User not found"}
        
        # Update calendar preferences
        user.default_duration = default_duration
        user.buffer_time = buffer_time
        
        db.commit()
        
        return {"success": True, "message": "Calendar preferences updated successfully"}
        
    except Exception as e:
        print(f"Error updating calendar preferences: {e}")
        return {"error": str(e)}


@router.post("/settings/api/notifications")
async def update_notifications(
    request: Request,
    email_notifications: bool = Form(False),
    booking_reminders: bool = Form(False),
    calendar_sync_notifications: bool = Form(False),
    db: Session = Depends(get_db)
):
    """Update notification preferences"""
    access_token = request.cookies.get("access_token")
    if not access_token:
        return {"error": "Not authenticated"}
    
    try:
        payload = verify_token(access_token)
        if not payload:
            return {"error": "Invalid token"}
        
        user_email = payload.get("sub")
        user = get_user_by_email(db, user_email)
        
        if not user:
            return {"error": "User not found"}
        
        # Update notification preferences
        user.email_notifications = email_notifications
        user.booking_reminders = booking_reminders
        user.calendar_sync_notifications = calendar_sync_notifications
        
        db.commit()
        
        return {"success": True, "message": "Notification preferences updated successfully"}
        
    except Exception as e:
        print(f"Error updating notifications: {e}")
        return {"error": str(e)}


@router.post("/settings/api/disconnect-calendar")
async def disconnect_calendar(
    request: Request,
    db: Session = Depends(get_db)
):
    """Disconnect Google Calendar"""
    access_token = request.cookies.get("access_token")
    if not access_token:
        return {"error": "Not authenticated"}
    
    try:
        payload = verify_token(access_token)
        if not payload:
            return {"error": "Invalid token"}
        
        user_email = payload.get("sub")
        user = get_user_by_email(db, user_email)
        
        if not user:
            return {"error": "User not found"}
        
        # Clear Google Calendar tokens
        user.google_access_token = None
        user.google_refresh_token = None
        user.google_calendar_connected = False
        
        db.commit()
        
        return {"success": True, "message": "Google Calendar disconnected successfully"}
        
    except Exception as e:
        print(f"Error disconnecting calendar: {e}")
        return {"error": str(e)}


@router.post("/settings/api/change-password")
async def change_password(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db)
):
    """Change user password"""
    access_token = request.cookies.get("access_token")
    if not access_token:
        return {"error": "Not authenticated"}
    
    try:
        payload = verify_token(access_token)
        if not payload:
            return {"error": "Invalid token"}
        
        user_email = payload.get("sub")
        user = get_user_by_email(db, user_email)
        
        if not user:
            return {"error": "User not found"}
        
        # Verify current password
        if not verify_password(current_password, user.hashed_password):
            return {"error": "Current password is incorrect"}
        
        # Check if new passwords match
        if new_password != confirm_password:
            return {"error": "New passwords do not match"}
        
        # Update password
        user.hashed_password = get_password_hash(new_password)
        db.commit()
        
        return {"success": True, "message": "Password changed successfully"}
        
    except Exception as e:
        print(f"Error changing password: {e}")
        return {"error": str(e)}


@router.post("/settings/api/personalization")
async def update_personalization(
    request: Request,
    profile_image_url: str = Form(None),
    meeting_title: str = Form(...),
    meeting_description: str = Form(...),
    meeting_duration: int = Form(...),
    theme_color: str = Form(...),
    accent_color: str = Form(...),
    db: Session = Depends(get_db)
):
    """Update personalization settings"""
    access_token = request.cookies.get("access_token")
    if not access_token:
        return {"error": "Not authenticated"}
    
    try:
        payload = verify_token(access_token)
        if not payload:
            return {"error": "Invalid token"}
        
        user_email = payload.get("sub")
        user = get_user_by_email(db, user_email)
        
        if not user:
            return {"error": "User not found"}
        
        # Update personalization settings
        if profile_image_url:
            user.profile_image_url = profile_image_url
        user.meeting_title = meeting_title
        user.meeting_description = meeting_description
        user.meeting_duration = meeting_duration
        user.theme_color = theme_color
        user.accent_color = accent_color
        
        db.commit()
        
        return {"success": True, "message": "Personalization settings updated successfully"}
        
    except Exception as e:
        print(f"Error updating personalization: {e}")
        return {"error": str(e)}


@router.post("/settings/api/upload-profile-image")
async def upload_profile_image(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Upload profile image"""
    access_token = request.cookies.get("access_token")
    if not access_token:
        return {"error": "Not authenticated"}
    
    try:
        payload = verify_token(access_token)
        if not payload:
            return {"error": "Invalid token"}
        
        user_email = payload.get("sub")
        user = get_user_by_email(db, user_email)
        
        if not user:
            return {"error": "User not found"}
        
        # Validate file type
        if not file.content_type.startswith('image/'):
            return {"error": "File must be an image"}
        
        # Create uploads directory if it doesn't exist
        upload_dir = Path("uploads")
        upload_dir.mkdir(exist_ok=True)
        
        # Generate unique filename
        file_extension = Path(file.filename).suffix
        filename = f"profile_{user.id}_{int(datetime.now().timestamp())}{file_extension}"
        file_path = upload_dir / filename
        
        # Save file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Update user profile image URL
        user.profile_image_url = f"/uploads/{filename}"
        db.commit()
        
        return {
            "success": True, 
            "message": "Profile image uploaded successfully",
            "image_url": user.profile_image_url
        }
        
    except Exception as e:
        print(f"Error uploading profile image: {e}")
        return {"error": str(e)} 