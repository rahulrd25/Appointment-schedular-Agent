import os
from fastapi import FastAPI, Request, Form, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
import requests
import json

from app.api.v1.api import api_router
from app.core.config import settings
from app.core.database import Base, engine, get_db
from app.services.user_service import authenticate_user, create_user, get_user_by_email
from app.core.security import create_access_token, verify_token
from app.schemas.schemas import UserCreate
from app.models.models import User

# Create database tables - Updated to drop all tables and recreate
Base.metadata.drop_all(bind=engine)  # This will drop ALL tables including dependent ones
Base.metadata.create_all(bind=engine)  # Create all tables with updated schema

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="AI-powered appointment scheduling agent",
    version="1.0.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Include API router
app.include_router(api_router, prefix=settings.API_V1_STR)

# Templates for HTML responses
templates = Jinja2Templates(directory="app/templates")

# Google OAuth routes
@app.get("/auth/google")
async def google_auth():
    """Start Google OAuth flow"""
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=500, detail="Google OAuth not configured")
    
    google_auth_url = (
        "https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={settings.GOOGLE_CLIENT_ID}&"
        "response_type=code&"
        "scope=openid email profile&"
        f"redirect_uri={settings.GOOGLE_REDIRECT_URI}&"
        "access_type=offline"
    )
    
    return RedirectResponse(url=google_auth_url)

@app.get("/api/v1/auth/google/callback")
async def google_auth_callback_api(
    code: str = Query(...),
    db: Session = Depends(get_db)
):
    try:
        print("=== GOOGLE OAUTH CALLBACK STARTED ===")
        print("Received code:", code)
        print("Using redirect_uri:", settings.GOOGLE_REDIRECT_URI)
        print("Client ID:", settings.GOOGLE_CLIENT_ID)
        print("Client Secret:", settings.GOOGLE_CLIENT_SECRET)
        
        token_url = "https://oauth2.googleapis.com/token"
        token_data = {
            "code": code,
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "redirect_uri": settings.GOOGLE_REDIRECT_URI,
            "grant_type": "authorization_code",
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        print("Token data:", token_data)
        
        token_response = requests.post(token_url, data=token_data, headers=headers)
        print("Token response status:", token_response.status_code)
        print("Token response text:", token_response.text)
        token_response.raise_for_status()
        tokens = token_response.json()
        access_token = tokens.get("access_token")
        if not access_token:
            raise Exception("No access token in response")
        
        # Get user info from Google
        user_info_url = "https://www.googleapis.com/oauth2/v2/userinfo"
        user_response = requests.get(user_info_url, headers={"Authorization": f"Bearer {access_token}"})
        print("User info response status:", user_response.status_code)
        print("User info response text:", user_response.text)
        user_response.raise_for_status()
        user_info = user_response.json()
        
        print("User info:", user_info)
        
        # Check if user exists - FIXED: Remove await since function is not async
        user = get_user_by_email(db, user_info["email"])
        
        if not user:
            # Create new user
            print("Creating new user...")
            user_data = UserCreate(
                email=user_info["email"],
                password="",  # Google users don't need password
                full_name=user_info.get("name", ""),
                google_id=user_info["id"]
            )
            user = create_user(db, user_data)  # FIXED: Remove await here too
            print("New user created:", user.email)
        else:
            # Update existing user's Google ID and full name if not set
            print("User exists, updating if needed...")
            updated = False
            if not user.google_id:
                user.google_id = user_info["id"]
                updated = True
            if not user.full_name and user_info.get("name"):
                user.full_name = user_info["name"]
                updated = True
            if updated:
                db.commit()
                print("User updated")
        
        # Create access token for our app
        jwt_token = create_access_token(data={"sub": user.email})
        print("JWT token created for user:", user.email)
        
        # Redirect to dashboard with cookie
        response = RedirectResponse(url="/dashboard", status_code=302)
        response.set_cookie(
            key="access_token",
            value=jwt_token,
            httponly=True,
            max_age=1800,
            secure=False,
            samesite="lax"
        )
        print("Redirecting to dashboard...")
        return response
        
    except Exception as e:
        print(f"=== GOOGLE OAUTH ERROR ===")
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return RedirectResponse(url="/login?error=google_auth_failed", status_code=302)

# Add web routes directly
@app.get("/login")
async def login_get(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login_post(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    try:
        user = authenticate_user(db, email, password)
        if not user:
            return templates.TemplateResponse(
                "login.html", 
                {"request": request, "error": "Invalid email or password"},
                status_code=400
            )
        
        # Create access token
        access_token = create_access_token(data={"sub": user.email})
        
        # Create response with redirect
        response = RedirectResponse(url="/dashboard", status_code=302)
        
        # Set HTTP-only cookie
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            max_age=1800,  # 30 minutes
            secure=False,  # Set to True in production with HTTPS
            samesite="lax"
        )
        
        return response
        
    except Exception as e:
        return templates.TemplateResponse(
            "login.html", 
            {"request": request, "error": "An error occurred during login"},
            status_code=500
        )

@app.get("/register")
async def register_get(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@app.post("/register")
async def register_post(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    full_name: str = Form(...),
    db: Session = Depends(get_db)
):
    try:
        # Check if user already exists
        existing_user = db.query(User).filter(User.email == email).first()
        if existing_user:
            return templates.TemplateResponse(
                "register.html", 
                {"request": request, "error": "Email already registered"},
                status_code=400
            )
        
        # Create new user
        user_data = UserCreate(
            email=email,
            password=password,
            full_name=full_name
        )
        
        user = await create_user(db, user_data)
        
        # Send verification email
        if user.verification_token:
            from app.services.email_service import send_verification_email
            send_verification_email(user.email, user.verification_token)
        
        return templates.TemplateResponse(
            "register.html", 
            {"request": request, "success": "Registration successful! Please check your email to verify your account."},
            status_code=200
        )
        
    except Exception as e:
        return templates.TemplateResponse(
            "register.html", 
            {"request": request, "error": "An error occurred during registration"},
            status_code=500
        )

@app.get("/verify-email")
async def verify_email(request: Request, token: str, db: Session = Depends(get_db)):
    user = verify_user_email(db, token)
    if user:
        return templates.TemplateResponse(
            "email_verified.html", 
            {"request": request, "success": "Email verified successfully! You can now log in."}
        )
    else:
        return templates.TemplateResponse(
            "email_verified.html", 
            {"request": request, "error": "Invalid or expired verification token."}
        )

@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/", status_code=302)
    response.delete_cookie("access_token")
    return response

@app.get("/dashboard")
async def dashboard(request: Request, db: Session = Depends(get_db)):
    access_token = request.cookies.get("access_token")
    print(f"Dashboard - Access token: {access_token}")

    if not access_token:
        print("No access token found")
        return RedirectResponse(url="/login", status_code=302)

    try:
        payload = verify_token(access_token)
        print(f"Token payload: {payload}")

        if not payload:
            print("Token verification failed")
            return RedirectResponse(url="/login", status_code=302)

        user_email = payload.get("sub")
        print(f"User email from token: {user_email}")
        user = get_user_by_email(db, user_email)
        print(f"User from DB: {user}")

        if not user:
            print(f"User not found for email: {user_email}")
            return RedirectResponse(url="/login", status_code=302)

        print(f"User authenticated: {user.email}")
        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "current_user": user
        })

    except Exception as e:
        print(f"Dashboard error: {e}")
        return RedirectResponse(url="/login", status_code=302)

@app.get("/")
async def root(request: Request):
    """Root endpoint - redirect to landing page"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    """Handle 404 errors"""
    return templates.TemplateResponse(
        "404.html", 
        {"request": request}, 
        status_code=404
    )

@app.exception_handler(500)
async def internal_error_handler(request: Request, exc):
    """Handle 500 errors"""
    return templates.TemplateResponse(
        "500.html", 
        {"request": request}, 
        status_code=500
    )
