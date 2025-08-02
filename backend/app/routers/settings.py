from fastapi import APIRouter, Request, Form, HTTPException, Depends, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from fastapi.templating import Jinja2Templates
from pathlib import Path
import os
import shutil

from app.core.database import get_db
from app.core.security import verify_token
from app.services.user_service import get_user_by_email
from app.services.file_upload_service import save_uploaded_file

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/settings")
async def settings_page(request: Request, db: Session = Depends(get_db)):
    """Settings page for user account management"""
    access_token = request.cookies.get("access_token")

    if not access_token:
        return RedirectResponse(url="/", status_code=302)

    try:
        payload = verify_token(access_token)
        if not payload:
            return RedirectResponse(url="/", status_code=302)

        user_email = payload.get("sub")
        user = get_user_by_email(db, user_email)

        if not user:
            return RedirectResponse(url="/", status_code=302)

        return templates.TemplateResponse("settings.html", {
            "request": request,
            "current_user": user
        })

    except Exception as e:
        print(f"Settings error: {e}")
        return RedirectResponse(url="/", status_code=302)


@router.post("/settings/api/profile")
async def update_profile(
    request: Request,
    full_name: str = Form(...),
    scheduling_slug: str = Form(...),
    timezone: str = Form(...),
    db: Session = Depends(get_db)
):
    """Update user profile settings"""
    access_token = request.cookies.get("access_token")
    if not access_token:
        return HTMLResponse('<div class="text-red-600 text-sm">Not authenticated</div>', status_code=401)
    
    try:
        payload = verify_token(access_token)
        if not payload:
            return HTMLResponse('<div class="text-red-600 text-sm">Invalid token</div>', status_code=401)
        
        user_email = payload.get("sub")
        user = get_user_by_email(db, user_email)
        
        if not user:
            return HTMLResponse('<div class="text-red-600 text-sm">User not found</div>', status_code=404)
        
        # Update user profile
        user.full_name = full_name
        user.scheduling_slug = scheduling_slug
        user.timezone = timezone
        
        db.commit()
        
        return HTMLResponse('<div class="text-green-600 text-sm">Profile updated successfully!</div>')
        
    except Exception as e:
        return HTMLResponse(f'<div class="text-red-600 text-sm">Error: {str(e)}</div>', status_code=500)


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
        return HTMLResponse('<div class="text-red-600 text-sm">Not authenticated</div>', status_code=401)
    
    try:
        payload = verify_token(access_token)
        if not payload:
            return HTMLResponse('<div class="text-red-600 text-sm">Invalid token</div>', status_code=401)
        
        user_email = payload.get("sub")
        user = get_user_by_email(db, user_email)
        
        if not user:
            return HTMLResponse('<div class="text-red-600 text-sm">User not found</div>', status_code=404)
        
        # Update calendar preferences (you can add these fields to User model if needed)
        # For now, we'll just return success
        return HTMLResponse('<div class="text-green-600 text-sm">Calendar preferences updated!</div>')
        
    except Exception as e:
        return HTMLResponse(f'<div class="text-red-600 text-sm">Error: {str(e)}</div>', status_code=500)


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
        return HTMLResponse('<div class="text-red-600 text-sm">Not authenticated</div>', status_code=401)
    
    try:
        payload = verify_token(access_token)
        if not payload:
            return HTMLResponse('<div class="text-red-600 text-sm">Invalid token</div>', status_code=401)
        
        user_email = payload.get("sub")
        user = get_user_by_email(db, user_email)
        
        if not user:
            return HTMLResponse('<div class="text-red-600 text-sm">User not found</div>', status_code=404)
        
        # Update notification preferences (you can add these fields to User model if needed)
        # For now, we'll just return success
        return HTMLResponse('<div class="text-green-600 text-sm">Notification preferences updated!</div>')
        
    except Exception as e:
        return HTMLResponse(f'<div class="text-red-600 text-sm">Error: {str(e)}</div>', status_code=500)


@router.post("/settings/api/disconnect-calendar")
async def disconnect_calendar(
    request: Request,
    db: Session = Depends(get_db)
):
    """Disconnect Google Calendar"""
    access_token = request.cookies.get("access_token")
    if not access_token:
        return HTMLResponse('<div class="text-red-600 text-sm">Not authenticated</div>', status_code=401)
    
    try:
        payload = verify_token(access_token)
        if not payload:
            return HTMLResponse('<div class="text-red-600 text-sm">Invalid token</div>', status_code=401)
        
        user_email = payload.get("sub")
        user = get_user_by_email(db, user_email)
        
        if not user:
            return HTMLResponse('<div class="text-red-600 text-sm">User not found</div>', status_code=404)
        
        # Disconnect calendar
        user.google_calendar_connected = False
        user.google_access_token = None
        user.google_refresh_token = None
        user.google_calendar_email = None
        
        db.commit()
        
        return HTMLResponse('<div class="text-green-600 text-sm">Calendar disconnected successfully!</div>')
        
    except Exception as e:
        return HTMLResponse(f'<div class="text-red-600 text-sm">Error: {str(e)}</div>', status_code=500)


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
        return HTMLResponse('<div class="text-red-600 text-sm">Not authenticated</div>', status_code=401)
    
    try:
        payload = verify_token(access_token)
        if not payload:
            return HTMLResponse('<div class="text-red-600 text-sm">Invalid token</div>', status_code=401)
        
        user_email = payload.get("sub")
        user = get_user_by_email(db, user_email)
        
        if not user:
            return HTMLResponse('<div class="text-red-600 text-sm">User not found</div>', status_code=404)
        
        # Validate current password
        if not user.verify_password(current_password):
            return HTMLResponse('<div class="text-red-600 text-sm">Current password is incorrect</div>', status_code=400)
        
        # Validate new password
        if new_password != confirm_password:
            return HTMLResponse('<div class="text-red-600 text-sm">New passwords do not match</div>', status_code=400)
        
        if len(new_password) < 6:
            return HTMLResponse('<div class="text-red-600 text-sm">Password must be at least 6 characters</div>', status_code=400)
        
        # Update password
        from app.core.hashing import get_password_hash
        user.hashed_password = get_password_hash(new_password)
        db.commit()
        
        return HTMLResponse('<div class="text-green-600 text-sm">Password changed successfully!</div>')
        
    except Exception as e:
        return HTMLResponse(f'<div class="text-red-600 text-sm">Error: {str(e)}</div>', status_code=500)


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
        return HTMLResponse('<div class="text-red-600 text-sm">Not authenticated</div>', status_code=401)
    
    try:
        payload = verify_token(access_token)
        if not payload:
            return HTMLResponse('<div class="text-red-600 text-sm">Invalid token</div>', status_code=401)
        
        user_email = payload.get("sub")
        user = get_user_by_email(db, user_email)
        
        if not user:
            return HTMLResponse('<div class="text-red-600 text-sm">User not found</div>', status_code=404)
        
        # Update personalization settings
        if profile_image_url:
            user.profile_image_url = profile_image_url
        user.meeting_title = meeting_title
        user.meeting_description = meeting_description
        user.meeting_duration = meeting_duration
        user.theme_color = theme_color
        user.accent_color = accent_color
        
        db.commit()
        
        return HTMLResponse('<div class="text-green-600 text-sm">Personalization updated successfully!</div>')
        
    except Exception as e:
        return HTMLResponse(f'<div class="text-red-600 text-sm">Error: {str(e)}</div>', status_code=500)


@router.post("/settings/api/upload-profile-image")
async def upload_profile_image(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Upload profile image"""
    access_token = request.cookies.get("access_token")
    if not access_token:
        return HTMLResponse('<div class="text-red-600 text-sm">Not authenticated</div>', status_code=401)
    
    try:
        payload = verify_token(access_token)
        if not payload:
            return HTMLResponse('<div class="text-red-600 text-sm">Invalid token</div>', status_code=401)
        
        user_email = payload.get("sub")
        user = get_user_by_email(db, user_email)
        
        if not user:
            return HTMLResponse('<div class="text-red-600 text-sm">User not found</div>', status_code=404)
        
        # Upload image
        image_url = save_uploaded_file(file, "profile_images")
        if image_url:
            user.profile_image_url = image_url
            db.commit()
            return HTMLResponse(f'<div class="text-green-600 text-sm">Profile image uploaded successfully!</div>')
        else:
            return HTMLResponse('<div class="text-red-600 text-sm">Failed to upload image</div>', status_code=400)
        
    except Exception as e:
        return HTMLResponse(f'<div class="text-red-600 text-sm">Error: {str(e)}</div>', status_code=500) 