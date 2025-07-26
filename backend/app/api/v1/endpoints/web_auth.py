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


@router.get("/logout")
async def logout():
    """Logout user by clearing cookie"""
    response = RedirectResponse(url="/")
    response.delete_cookie("access_token")
    return response 