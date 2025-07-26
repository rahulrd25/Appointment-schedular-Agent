import uuid

from sqlalchemy.orm import Session

from app.core.hashing import get_password_hash, verify_password
from app.models.models import User
from app.schemas.schemas import UserCreate


async def get_user(db: Session, user_id: str):
    return db.query(User).filter(User.id == user_id).first()


async def get_user_by_email(db: Session, email: str):
    return db.query(User).filter(User.email == email).first()


async def get_user_by_scheduling_slug(db: Session, scheduling_slug: str):
    return (
        db.query(User)
        .filter(User.scheduling_slug == scheduling_slug)
        .filter(User.is_active == True)
        .first()
    )


async def create_user(db: Session, user: UserCreate):
    # Generate a simple slug from the email for now
    scheduling_slug = user.email.split("@")[0] + "-" + str(uuid.uuid4())[:4]
    
    # Handle Google users (no password) vs regular users
    if user.password:
        hashed_password = get_password_hash(user.password)
    else:
        # For Google users, set a special hashed password that can't be used for login
        hashed_password = get_password_hash("google_user_" + str(uuid.uuid4()))
    
    db_user = User(
        email=user.email,
        hashed_password=hashed_password,
        scheduling_slug=scheduling_slug,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


async def authenticate_user(db: Session, email: str, password: str):
    user = await get_user_by_email(db, email)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user
