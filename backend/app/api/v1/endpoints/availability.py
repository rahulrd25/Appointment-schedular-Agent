from typing import List

<<<<<<< HEAD
from fastapi import APIRouter, Depends, HTTPException, status
=======
from fastapi import APIRouter, Depends, HTTPException, status, Form
>>>>>>> e3b999cd02f578d5176e7dbc287d1a2a1f5f3840
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


<<<<<<< HEAD
=======
@router.delete("/bulk-delete")
def bulk_delete_slots(
    slot_ids: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Delete multiple availability slots."""
    if not slot_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No slot IDs provided"
        )
    
    # Parse the slot_ids string into a list of integers
    try:
        slot_id_list = [int(id.strip()) for id in slot_ids.split(',') if id.strip()]
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid slot IDs format"
        )
    
    if not slot_id_list:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid slot IDs provided"
        )
    
    deleted_count = 0
    failed_count = 0
    calendar_deleted_count = 0
    calendar_failed_count = 0
    
    for slot_id in slot_id_list:
        result = delete_availability_slot(db=db, slot_id=slot_id, user_id=current_user.id)
        if result["success"]:
            deleted_count += 1
            if result.get("calendar_deleted") is True:
                calendar_deleted_count += 1
            elif result.get("calendar_deleted") is False:
                calendar_failed_count += 1
        else:
            failed_count += 1
    
    return {
        "message": f"Deleted {deleted_count} slots successfully",
        "deleted_count": deleted_count,
        "failed_count": failed_count,
        "calendar_deleted_count": calendar_deleted_count,
        "calendar_failed_count": calendar_failed_count
    }


>>>>>>> e3b999cd02f578d5176e7dbc287d1a2a1f5f3840
@router.delete("/{slot_id}")
def delete_slot(
    slot_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Delete an availability slot."""
<<<<<<< HEAD
    success = delete_availability_slot(db=db, slot_id=slot_id, user_id=current_user.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Availability slot not found"
        )
    return {"message": "Availability slot deleted successfully"} 
=======
    result = delete_availability_slot(db=db, slot_id=slot_id, user_id=current_user.id)
    
    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result["message"]
        )
    
    return result 
>>>>>>> e3b999cd02f578d5176e7dbc287d1a2a1f5f3840
