from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.services.user_service import get_user_by_email
from app.core.security import verify_token

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

@router.get("/settings")
async def settings_page(request: Request, db: Session = Depends(get_db)):
    """Settings page"""
    access_token = request.cookies.get("access_token")

    if not access_token:
        return RedirectResponse(url="/", status_code=302)

    # Remove "Bearer " prefix if present
    if access_token.startswith("Bearer "):
        access_token = access_token[7:]

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
        print(f"Settings page error: {e}")
        return RedirectResponse(url="/", status_code=302) 