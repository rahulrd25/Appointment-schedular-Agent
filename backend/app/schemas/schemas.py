import uuid
from typing import Optional

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

    class Config:
        from_attributes = True


class User(UserInDBBase):
    pass


class UserInDB(UserInDBBase):
    hashed_password: str
