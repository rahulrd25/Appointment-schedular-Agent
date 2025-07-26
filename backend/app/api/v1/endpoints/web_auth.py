from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import EmailStr, ValidationError
import re
import requests

from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_access_token
from app.schemas.schemas import UserCreate
from app.services.user_service import authenticate_user, create_user, get_user_by_email
from sqlalchemy.orm import Session

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/login", response_class=HTMLResponse)
async def login_get(request: Request):
    """Render login page"""
    return templates.TemplateResponse("login.html", {"request": request})


@router.post("/login", response_class=HTMLResponse)
async def login_post(
    request: Request,
    response: Response,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    """Handle login form submission"""
    user = await authenticate_user(db, username, password)
    if not user:
        return HTMLResponse(
            content='<div class="text-red-500">Invalid email or password.</div>',
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    
    access_token = create_access_token(data={"sub": user.email})
    response = HTMLResponse(
        content='<div class="text-green-500">Login successful! Redirecting...</div><script>setTimeout(()=>window.location.href=\"/dashboard\", 1000);</script>'
    )
    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/"
    )
    return response


@router.get("/register", response_class=HTMLResponse)
async def register_get(request: Request):
    """Render registration page"""
    return templates.TemplateResponse("register.html", {"request": request})


@router.post("/register", response_class=HTMLResponse)
async def register_post(
    request: Request,
    response: Response,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    """Handle registration form submission"""
    # Validate email format
    try:
        email_obj = EmailStr.validate(email)
    except ValidationError:
        return HTMLResponse('<div class="text-red-500">Invalid email address.</div>', status_code=400)
    
    # Validate password strength (min 8 chars, at least 1 letter and 1 number)
    if len(password) < 8 or not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        return HTMLResponse('<div class="text-red-500">Password must be at least 8 characters and include a letter and a number.</div>', status_code=400)
    
    # Check for existing user
    existing = await get_user_by_email(db, email)
    if existing:
        return HTMLResponse('<div class="text-red-500">A user with this email already exists.</div>', status_code=400)
    
    # Create user
    try:
        user_in = UserCreate(email=email, password=password)
        user = await create_user(db, user_in)
    except Exception as e:
        return HTMLResponse(f'<div class="text-red-500">Registration failed: {str(e)}</div>', status_code=500)
    
    # Auto-login after registration
    access_token = create_access_token(data={"sub": user.email})
    response = HTMLResponse('<div class="text-green-500">Registration successful! Redirecting...</div><script>setTimeout(()=>window.location.href=\"/dashboard\", 1000);</script>')
    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/"
    )
    return response


@router.get("/auth/google")
async def google_auth():
    """Initiate Google OAuth2 flow"""
    google_auth_url = "https://accounts.google.com/o/oauth2/v2/auth"
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "consent"
    }
    auth_url = f"{google_auth_url}?{'&'.join([f'{k}={v}' for k, v in params.items()])}"
    return RedirectResponse(url=auth_url)


@router.get("/auth/google/callback")
async def google_auth_callback(
    code: str = Query(...),
    db: Session = Depends(get_db)
):
    """Handle Google OAuth2 callback"""
    if not code:
        return RedirectResponse(url="/login?error=no_code")
    
    try:
        # Exchange code for tokens
        token_url = "https://oauth2.googleapis.com/token"
        token_data = {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": settings.GOOGLE_REDIRECT_URI
        }
        
        token_response = requests.post(token_url, data=token_data)
        token_response.raise_for_status()
        tokens = token_response.json()
        
        # Get user info from Google
        user_info_url = "https://www.googleapis.com/oauth2/v2/userinfo"
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}
        user_info_response = requests.get(user_info_url, headers=headers)
        user_info_response.raise_for_status()
        user_info = user_info_response.json()
        
        email = user_info.get("email")
        if not email:
            return RedirectResponse(url="/login?error=no_email")
        
        # Check if user exists
        user = await get_user_by_email(db, email)
        if not user:
            # Create new user
            user_in = UserCreate(email=email, password="")  # No password for Google users
            user = await create_user(db, user_in)
        
        # Create session
        access_token = create_access_token(data={"sub": user.email})
        response = RedirectResponse(url="/dashboard")
        response.set_cookie(
            key="access_token",
            value=f"Bearer {access_token}",
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            path="/"
        )
        return response
        
    except Exception as e:
        return RedirectResponse(url=f"/login?error=auth_failed")


@router.get("/logout")
async def logout():
    """Logout user by clearing cookie"""
    response = RedirectResponse(url="/")
    response.delete_cookie("access_token")
    return response 