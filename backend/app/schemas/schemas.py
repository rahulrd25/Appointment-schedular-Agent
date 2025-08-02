import uuid
from typing import Optional, List
from datetime import datetime

from pydantic import BaseModel, EmailStr


class UserBase(BaseModel):
    email: EmailStr
    full_name: str


class UserCreate(UserBase):
    password: str = ""
    google_id: Optional[str] = None


class UserInDBBase(UserBase):
    id: int
    is_active: bool
    is_verified: bool
    google_id: Optional[str] = None
    scheduling_slug: Optional[str] = None

    class Config:
        from_attributes = True


class User(UserInDBBase):
    pass


class UserInDB(UserInDBBase):
    hashed_password: str


# Availability Slot Schemas
class AvailabilitySlotBase(BaseModel):
    start_time: datetime
    end_time: datetime
    is_available: bool = True


class AvailabilitySlotCreate(AvailabilitySlotBase):
    pass


class AvailabilitySlotUpdate(BaseModel):
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    is_available: Optional[bool] = None


class AvailabilitySlot(AvailabilitySlotBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# Booking Schemas
class BookingBase(BaseModel):
    guest_name: str
    guest_email: EmailStr
    guest_message: Optional[str] = None


class BookingCreate(BookingBase):
    availability_slot_id: int


class BookingUpdate(BaseModel):
    guest_name: Optional[str] = None
    guest_email: Optional[EmailStr] = None
    guest_message: Optional[str] = None
    status: Optional[str] = None


class Booking(BookingBase):
    id: int
    host_user_id: int
    availability_slot_id: int
    start_time: datetime
    end_time: datetime
    status: str
    google_event_id: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# Response Schemas
class BookingConfirmation(BaseModel):
    booking: Booking
    message: str
    google_event_url: Optional[str] = None


class AvailabilityResponse(BaseModel):
    user: User
    available_slots: List[AvailabilitySlot]


# Public Booking Schema (for external users)
class PublicBookingCreate(BaseModel):
    guest_name: str
    guest_email: EmailStr
    guest_message: Optional[str] = None
