from typing import List

from fastapi import APIRouter, Depends, HTTPException, status, Form
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user, get_db
from app.models.models import User
from app.schemas.schemas import (
    Booking,
    BookingCreate,
    BookingUpdate,
    BookingConfirmation,
    PublicBookingCreate,
)
from app.services.booking_service import (
    create_booking,
    get_bookings_for_user,
    get_booking,
    update_booking,
    cancel_booking,
    get_upcoming_bookings,
)
from app.services.user_service import get_user_by_scheduling_slug

router = APIRouter()


@router.post("/book-slot/{slot_id}", response_model=BookingConfirmation)
async def book_slot_public(
    slot_id: int,
    guest_name: str = Form(...),
    guest_email: str = Form(...),
    guest_message: str = Form(None),
    db: Session = Depends(get_db),
):
    """Public endpoint for booking a slot via scheduling link."""
    booking_data = PublicBookingCreate(
        guest_name=guest_name,
        guest_email=guest_email,
        guest_message=guest_message
    )
    
    # Get the slot to find the host user
    from app.services.availability_service import get_availability_slot
    slot = get_availability_slot(db, slot_id)
    if not slot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Availability slot not found"
        )
    
    # Get the host user
    host_user = db.query(User).filter(User.id == slot.user_id).first()
    if not host_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Host user not found"
        )
    
    # Create the booking
    booking = create_booking(db, booking_data, slot_id, host_user)
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Slot is no longer available or invalid"
        )
    
    return BookingConfirmation(
        booking=booking,
        message="Booking confirmed successfully! You will receive a confirmation email shortly.",
        google_event_url=None
    )


@router.post("/", response_model=Booking)
def create_user_booking(
    booking: BookingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Create a booking for a user's own slots (internal use)."""
    booking_data = PublicBookingCreate(
        guest_name=booking.guest_name,
        guest_email=booking.guest_email,
        guest_message=booking.guest_message
    )
    
    created_booking = create_booking(db, booking_data, booking.availability_slot_id, current_user)
    if not created_booking:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to create booking"
        )
    return created_booking


@router.get("/", response_model=List[Booking])
def get_user_bookings(
    status_filter: str = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get all bookings for the current user."""
    return get_bookings_for_user(db=db, user_id=current_user.id, status=status_filter)


@router.get("/upcoming", response_model=List[Booking])
def get_user_upcoming_bookings(
    limit: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get upcoming bookings for the current user."""
    return get_upcoming_bookings(db=db, user_id=current_user.id, limit=limit)


@router.get("/{booking_id}", response_model=Booking)
def get_user_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get a specific booking."""
    booking = get_booking(db=db, booking_id=booking_id, user_id=current_user.id)
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found"
        )
    return booking


@router.put("/{booking_id}", response_model=Booking)
def update_user_booking(
    booking_id: int,
    booking_update: BookingUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Update a booking."""
    booking = update_booking(
        db=db, booking_id=booking_id, booking_update=booking_update, user_id=current_user.id
    )
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found"
        )
    return booking


@router.delete("/{booking_id}")
def cancel_user_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Cancel a booking."""
    success = cancel_booking(db=db, booking_id=booking_id, user_id=current_user.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found"
        )
    return {"message": "Booking cancelled successfully"} 