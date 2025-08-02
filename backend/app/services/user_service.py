import uuid
import secrets
import string

from sqlalchemy.orm import Session

from app.core.hashing import get_password_hash, verify_password
from app.models.models import User
from app.schemas.schemas import UserCreate


async def get_user(db: Session, user_id: str):
    return db.query(User).filter(User.id == user_id).first()


def get_user_by_email(db: Session, email: str):
    return db.query(User).filter(User.email == email).first()


async def get_user_by_scheduling_slug(db: Session, scheduling_slug: str):
    return (
        db.query(User)
        .filter(User.scheduling_slug == scheduling_slug)
        .filter(User.is_active == True)
        .first()
    )


def generate_unique_scheduling_slug(db: Session, base_name: str = None) -> str:
    """Generate a unique scheduling slug for a user."""
    if base_name:
        # Clean the base name for URL safety
        clean_name = "".join(c for c in base_name.lower() if c.isalnum() or c == "-")
        clean_name = clean_name[:20]  # Limit length
    else:
        clean_name = "user"
    
    # Try the clean name first
    if not db.query(User).filter(User.scheduling_slug == clean_name).first():
        return clean_name
    
    # If taken, add random suffix
    for attempt in range(10):  # Try up to 10 times
        suffix = ''.join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(6))
        slug = f"{clean_name}-{suffix}"
        if not db.query(User).filter(User.scheduling_slug == slug).first():
            return slug
    
    # If all else fails, use a completely random slug
    return ''.join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(12))


def create_user(db: Session, user: UserCreate):
    hashed_password = get_password_hash(user.password) if user.password else None
    verification_token = str(uuid.uuid4()) if not user.google_id else None
    
    # Generate unique scheduling slug
    scheduling_slug = generate_unique_scheduling_slug(db, user.full_name)
    
    db_user = User(
        email=user.email,
        full_name=user.full_name,
        hashed_password=hashed_password,
        google_id=user.google_id,
        is_verified=bool(user.google_id),  # Google users are auto-verified
        verification_token=verification_token,
        scheduling_slug=scheduling_slug
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    return db_user


def authenticate_user(db: Session, email: str, password: str):
    user = get_user_by_email(db, email)
    if not user:
        return None
    if not user.is_verified:
        return None  # Require email verification for standard users
    if not verify_password(password, user.hashed_password):
        return None
    return user


def verify_user_email(db: Session, token: str):
    user = db.query(User).filter(User.verification_token == token).first()
    if user:
        user.is_verified = True
        user.verification_token = None
        db.commit()
        return user
    return None
