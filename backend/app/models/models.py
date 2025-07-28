import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.core.hashing import verify_password

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    full_name = Column(String)
    hashed_password = Column(String, nullable=True)  # Nullable for Google users
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)  # Email verification status
    verification_token = Column(String, nullable=True)  # For email verification
    google_id = Column(String, nullable=True)
    google_access_token = Column(String, nullable=True)
    google_refresh_token = Column(String, nullable=True)
    google_calendar_connected = Column(Boolean, default=False)  # Track if calendar is connected
    google_calendar_email = Column(String, nullable=True)  # Email of the Google account used for calendar
    scheduling_slug = Column(String, unique=True, index=True)  # For shareable booking links
    timezone = Column(String, default='UTC')  # User's timezone (e.g., 'America/New_York', 'Europe/London')
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    availability_slots = relationship("AvailabilitySlot", back_populates="user", cascade="all, delete-orphan")
    bookings_as_host = relationship("Booking", foreign_keys="[Booking.host_user_id]", back_populates="host")
    
    def verify_password(self, plain_password: str) -> bool:
        """Verify a password against the user's hashed password"""
        if not self.hashed_password:
            return False
        return verify_password(plain_password, self.hashed_password)


class AvailabilitySlot(Base):
    __tablename__ = "availability_slots"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=False)
    is_available = Column(Boolean, default=True)  # Can be made unavailable without deletion
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    google_event_id = Column(String, nullable=True)  # Store Google Calendar event ID
    # Relationships
    user = relationship("User", back_populates="availability_slots")
    bookings = relationship("Booking", back_populates="availability_slot")


class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True, index=True)
    host_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    availability_slot_id = Column(Integer, ForeignKey("availability_slots.id"), nullable=False)
    
    # Guest information
    guest_name = Column(String, nullable=False)
    guest_email = Column(String, nullable=False)
    guest_message = Column(String, nullable=True)  # Optional message from guest
    
    # Booking details
    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=False)
    status = Column(String, default="confirmed")  # confirmed, cancelled, rescheduled
    
    # Google Calendar integration
    google_event_id = Column(String, nullable=True)  # Store Google Calendar event ID
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    host = relationship("User", foreign_keys=[host_user_id], back_populates="bookings_as_host")
    availability_slot = relationship("AvailabilitySlot", back_populates="bookings")
