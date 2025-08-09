from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.services.user_service import get_user_by_email, create_user
from app.core.security import verify_token, create_access_token
from app.schemas.schemas import UserCreate

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

@router.get("/")
async def landing_page(request: Request):
    """Landing page - main homepage"""
    return templates.TemplateResponse("landing_page.html", {"request": request}) 