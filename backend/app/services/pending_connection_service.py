"""
Service for managing pending calendar connections in the database.
This replaces in-memory storage with persistent database storage.
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from app.models.models import PendingCalendarConnection, User
import uuid

class PendingConnectionService:
    """Service for managing pending calendar connections."""
    
    @staticmethod
    def create_pending_connection(
        db: Session,
        calendar_email: str,
        calendar_name: str,
        access_token: str,
        refresh_token: Optional[str],
        scope: str,
        user_id: Optional[int] = None
    ) -> str:
        """
        Create a pending calendar connection in the database.
        
        Args:
            db: Database session
            user_id: ID of the user
            calendar_email: Email of the calendar account
            calendar_name: Name of the calendar account
            access_token: OAuth access token
            refresh_token: OAuth refresh token (optional)
            scope: OAuth scope
            
        Returns:
            Connection ID for the pending connection
        """
        # Generate unique connection ID
        connection_id = str(uuid.uuid4())
        
        # Set expiration (10 minutes from now)
        expires_at = datetime.utcnow() + timedelta(minutes=10)
        
        # Create pending connection record
        pending_connection = PendingCalendarConnection(
            id=connection_id,
            user_id=user_id,
            calendar_email=calendar_email,
            calendar_name=calendar_name,
            access_token=access_token,
            refresh_token=refresh_token,
            scope=scope,
            expires_at=expires_at
        )
        
        db.add(pending_connection)
        db.commit()
        
        return connection_id
    
    @staticmethod
    def get_pending_connection(
        db: Session,
        connection_id: str
    ) -> Optional[PendingCalendarConnection]:
        """
        Get a pending connection by ID.
        
        Args:
            db: Database session
            connection_id: The connection ID
            
        Returns:
            PendingCalendarConnection object or None if not found/expired
        """
        pending_connection = db.query(PendingCalendarConnection).filter(
            PendingCalendarConnection.id == connection_id,
            PendingCalendarConnection.expires_at > datetime.utcnow()
        ).first()
        
        return pending_connection
    
    @staticmethod
    def delete_pending_connection(
        db: Session,
        connection_id: str
    ) -> bool:
        """
        Delete a pending connection.
        
        Args:
            db: Database session
            connection_id: The connection ID
            
        Returns:
            True if deleted, False if not found
        """
        pending_connection = db.query(PendingCalendarConnection).filter(
            PendingCalendarConnection.id == connection_id
        ).first()
        
        if pending_connection:
            db.delete(pending_connection)
            db.commit()
            return True
        else:
            print(f"❌ Pending connection {connection_id} not found for deletion")
            return False
    
    @staticmethod
    def cleanup_expired_connections(db: Session) -> int:
        """
        Clean up expired pending connections.
        
        Args:
            db: Database session
            
        Returns:
            Number of connections deleted
        """
        expired_connections = db.query(PendingCalendarConnection).filter(
            PendingCalendarConnection.expires_at <= datetime.utcnow()
        ).all()
        
        count = len(expired_connections)
        for connection in expired_connections:
            db.delete(connection)
        
        db.commit()
        
        if count > 0:
            print(f"🧹 Cleaned up {count} expired pending connections")
        
        return count
    
    @staticmethod
    def get_connection_summary(db: Session) -> Dict[str, Any]:
        """
        Get a summary of pending connections for debugging.
        
        Args:
            db: Database session
            
        Returns:
            Dictionary with connection summary
        """
        total_connections = db.query(PendingCalendarConnection).count()
        active_connections = db.query(PendingCalendarConnection).filter(
            PendingCalendarConnection.expires_at > datetime.utcnow()
        ).count()
        expired_connections = total_connections - active_connections
        
        return {
            "total": total_connections,
            "active": active_connections,
            "expired": expired_connections
        } 