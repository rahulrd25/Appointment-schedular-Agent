import os
import uuid
from typing import Optional
from fastapi import UploadFile, HTTPException
from app.core.config import settings
import shutil


def save_uploaded_file(file: UploadFile, subdirectory: str = "") -> Optional[str]:
    """
    Save an uploaded file and return the file path
    
    Args:
        file: The uploaded file
        subdirectory: Optional subdirectory within uploads folder
    
    Returns:
        The relative path to the saved file, or None if failed
    """
    try:
        # Validate file type
        if file.content_type not in settings.ALLOWED_IMAGE_TYPES:
            raise HTTPException(
                status_code=400, 
                detail=f"File type {file.content_type} not allowed. Allowed types: {', '.join(settings.ALLOWED_IMAGE_TYPES)}"
            )
        
        # Validate file size
        file.file.seek(0, 2)  # Seek to end
        file_size = file.file.tell()
        file.file.seek(0)  # Reset to beginning
        
        if file_size > settings.MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"File too large. Maximum size is {settings.MAX_FILE_SIZE // (1024*1024)}MB"
            )
        
        # Create upload directory if it doesn't exist
        upload_path = os.path.join(settings.UPLOAD_DIR, subdirectory)
        os.makedirs(upload_path, exist_ok=True)
        
        # Generate unique filename
        file_extension = os.path.splitext(file.filename)[1] if file.filename else '.jpg'
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        
        # Save file
        file_path = os.path.join(upload_path, unique_filename)
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Return relative path for database storage
        relative_path = os.path.join(subdirectory, unique_filename) if subdirectory else unique_filename
        return relative_path
        
    except Exception as e:
        print(f"File upload error: {e}")
        return None


def delete_file(file_path: str) -> bool:
    """
    Delete a file from the uploads directory
    
    Args:
        file_path: Relative path to the file
    
    Returns:
        True if deleted successfully, False otherwise
    """
    try:
        full_path = os.path.join(settings.UPLOAD_DIR, file_path)
        if os.path.exists(full_path):
            os.remove(full_path)
            return True
        return False
    except Exception as e:
        print(f"File deletion error: {e}")
        return False


def get_file_url(file_path: str) -> str:
    """
    Get the URL for a file
    
    Args:
        file_path: Relative path to the file
    
    Returns:
        The URL to access the file
    """
    if not file_path:
        return ""
    
    # For development, serve from /uploads/ path
    return f"/uploads/{file_path}"


def validate_image_file(file: UploadFile) -> bool:
    """
    Validate that the uploaded file is a valid image
    
    Args:
        file: The uploaded file
    
    Returns:
        True if valid, False otherwise
    """
    if not file.content_type:
        return False
    
    return file.content_type in settings.ALLOWED_IMAGE_TYPES 