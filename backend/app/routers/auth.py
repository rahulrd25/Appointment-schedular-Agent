from fastapi import APIRouter, Request, Form, HTTPException, Depends
from fastapi.responses import RedirectResponse, HTMLResponse
from sqlalchemy.orm import Session
from fastapi.templating import Jinja2Templates

from app.core.database import get_db
from app.services.user_service import authenticate_user, create_user, get_user_by_email
from app.core.security import create_access_token, verify_token
from app.schemas.schemas import UserCreate

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")





@router.get("/register")
async def register_get(request: Request):
    """Register page"""
    return templates.TemplateResponse("register.html", {"request": request})


@router.post("/register")
async def register_post(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    """Handle registration form submission"""
    try:
        # Check if user already exists
        existing_user = get_user_by_email(db, email)
        if existing_user:
            return templates.TemplateResponse("register.html", {
                "request": request,
                "error": "Email already registered"
            })
        
        # Create new user
        user_data = UserCreate(email=email, password=password)
        user = create_user(db, user_data)
        
        if not user:
            return templates.TemplateResponse("register.html", {
                "request": request,
                "error": "Failed to create user"
            })
        
        # Create access token
        access_token = create_access_token(data={"sub": user.email})
        
        # Create response with redirect
        response = RedirectResponse(url="/dashboard", status_code=302)
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            max_age=86400,  # 24 hours (1440 minutes * 60 seconds)
            samesite="lax",
            secure=False,  # Set to True in production with HTTPS
            path="/"  # Make cookie available across all paths
        )
        
        return response
        
    except Exception as e:
        return templates.TemplateResponse("register.html", {
            "request": request,
            "error": "An error occurred during registration"
        })


@router.get("/verify-email")
async def verify_email(request: Request, token: str, db: Session = Depends(get_db)):
    """Verify email with token"""
    try:
        # Verify token and get user
        payload = verify_token(token)
        if not payload:
            return templates.TemplateResponse("verify_email.html", {
                "request": request,
                "success": False,
                "message": "Invalid or expired verification token"
            })
        
        user_email = payload.get("sub")
        user = get_user_by_email(db, user_email)
        
        if not user:
            return templates.TemplateResponse("verify_email.html", {
                "request": request,
                "success": False,
                "message": "User not found"
            })
        
        # Mark user as verified
        user.is_verified = True
        db.commit()
        
        return templates.TemplateResponse("verify_email.html", {
            "request": request,
            "success": True,
            "message": "Email verified successfully! You can now log in."
        })
        
    except Exception as e:
        return templates.TemplateResponse("verify_email.html", {
            "request": request,
            "success": False,
            "message": "An error occurred during email verification"
        })


@router.post("/connect-email")
async def connect_email(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    """Handle email login/signup from landing page"""
    try:
        # First try to authenticate existing user
        user = authenticate_user(db, email, password)
        
        if not user:
            # User doesn't exist or password is wrong, try to create new user
            existing_user = get_user_by_email(db, email)
            if existing_user:
                # User exists but password is wrong
                return templates.TemplateResponse("index.html", {
                    "request": request,
                    "error": "Invalid email or password"
                })
            else:
                # Create new user
                from app.schemas.schemas import UserCreate
                user_data = UserCreate(email=email, password=password, full_name=email.split('@')[0])
                user = create_user(db, user_data)
                
                if not user:
                    return templates.TemplateResponse("index.html", {
                        "request": request,
                        "error": "Failed to create account"
                    })
        
        # Create access token
        access_token = create_access_token(data={"sub": user.email})
        
        # Create response with redirect
        response = RedirectResponse(url="/dashboard", status_code=302)
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            max_age=86400,  # 24 hours (1440 minutes * 60 seconds)
            samesite="lax",
            secure=False,  # Set to True in production with HTTPS
            path="/"  # Make cookie available across all paths
        )
        
        return response
        
    except Exception as e:
        return templates.TemplateResponse("index.html", {
            "request": request,
            "error": "An error occurred during login"
        })


@router.get("/logout")
async def logout():
    """Logout user"""
    response = RedirectResponse(url="/", status_code=302)
    response.delete_cookie("access_token")
    return response 