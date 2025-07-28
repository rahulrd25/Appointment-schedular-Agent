from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

@router.get("/public-booking-test")
def public_booking_test(request: Request):
    # Pass the same context as your main booking page
    return templates.TemplateResponse("public_booking_test.html", {"request": request, "user": ...}) 