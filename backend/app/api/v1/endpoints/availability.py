from typing import List

from fastapi import APIRouter, Depends, HTTPException, status, Form
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user, get_db
from app.models.models import User
from app.schemas.schemas import (
    AvailabilitySlot,
    AvailabilitySlotCreate,
    AvailabilitySlotUpdate,
)
from app.services.availability_service import (
    create_availability_slot,
    get_availability_slots_for_user,
    get_available_slots_for_booking,
    get_availability_slot,
    update_availability_slot,
    delete_availability_slot,
)

router = APIRouter()


@router.post("/", response_model=AvailabilitySlot)
def create_slot(
    slot: AvailabilitySlotCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Create a new availability slot."""
    return create_availability_slot(db=db, slot=slot, user_id=current_user.id)


@router.get("/", response_model=List[AvailabilitySlot])
def get_user_slots(
    include_unavailable: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get all availability slots for the current user."""
    return get_availability_slots_for_user(
        db=db, user_id=current_user.id, include_unavailable=include_unavailable
    )


@router.get("/available", response_model=List[AvailabilitySlot])
def get_available_slots(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get available slots that can be booked."""
    return get_available_slots_for_booking(db=db, user_id=current_user.id)


@router.get("/{slot_id}", response_model=AvailabilitySlot)
def get_slot(
    slot_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get a specific availability slot."""
    slot = get_availability_slot(db=db, slot_id=slot_id, user_id=current_user.id)
    if not slot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Availability slot not found"
        )
    return slot


@router.put("/{slot_id}", response_model=AvailabilitySlot)
def update_slot(
    slot_id: int,
    slot_update: AvailabilitySlotUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Update an availability slot."""
    slot = update_availability_slot(
        db=db, slot_id=slot_id, slot_update=slot_update, user_id=current_user.id
    )
    if not slot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Availability slot not found"
        )
    return slot


    result = delete_availability_slot(db=db, slot_id=slot_id, user_id=current_user.id)
    
    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result["message"]
        )
    
    return result 