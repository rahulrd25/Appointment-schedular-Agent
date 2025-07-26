from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_current_active_user
from app.schemas.schemas import User, UserCreate, UserInDB
from app.services.user_service import create_user, get_user_by_email

router = APIRouter()


@router.post("/users/", response_model=User)
async def create_new_user(user_in: UserCreate) -> Any:
    """Create new user."""
    user = await get_user_by_email(user_in.email)
    if user:
        raise HTTPException(
            status_code=400,
            detail="The user with this username already exists in the system.",
        )
    user = await create_user(user_in)
    return user


@router.get("/users/me", response_model=User)
async def read_users_me(
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Get current user."""
    return current_user
