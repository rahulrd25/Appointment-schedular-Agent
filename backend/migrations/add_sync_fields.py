"""
Database Migration: Add sync fields to bookings table
This script adds the new sync tracking fields to the existing bookings table.
"""

import os
import sys
from pathlib import Path

# Add the backend directory to Python path
backend_dir = Path(__file__).parent
sys.path.append(str(backend_dir))

from sqlalchemy import text
from app.core.database import engine

def check_table_exists():
    """Check if the bookings table exists."""
    
    check_sql = """
    SELECT EXISTS (
        SELECT FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_name = 'bookings'
    );
    """
    
    try:
        with engine.connect() as connection:
            result = connection.execute(text(check_sql))
            exists = result.scalar()
            
        if exists:
            print("✅ Bookings table exists")
            return True
        else:
            print("❌ Bookings table does not exist")
            return False
            
    except Exception as e:
        print(f"❌ Error checking if table exists: {e}")
        return False

def check_sync_columns_exist():
    """Check if the sync columns already exist in the bookings table."""
    
    check_sql = """
    SELECT column_name
    FROM information_schema.columns 
    WHERE table_name = 'bookings' 
    AND column_name IN ('sync_status', 'last_synced', 'sync_error', 'sync_attempts')
    ORDER BY column_name;
    """
    
    try:
        with engine.connect() as connection:
            result = connection.execute(text(check_sql))
            existing_columns = [row[0] for row in result.fetchall()]
            
        if len(existing_columns) == 4:
            print("✅ All sync columns already exist")
            for col in existing_columns:
                print(f"   - {col}")
            return True
        elif len(existing_columns) > 0:
            print(f"⚠️  Some sync columns exist: {existing_columns}")
            return False
        else:
            print("ℹ️  No sync columns exist yet")
            return False
            
    except Exception as e:
        print(f"❌ Error checking sync columns: {e}")
        return False

def add_sync_fields_to_bookings():
    """Add sync tracking fields to the bookings table."""
    
    # SQL commands to add the new columns
    migration_sql = """
    -- Add sync status tracking fields to bookings table
    ALTER TABLE bookings ADD COLUMN IF NOT EXISTS sync_status VARCHAR(20) DEFAULT 'pending';
    ALTER TABLE bookings ADD COLUMN IF NOT EXISTS last_synced TIMESTAMP WITH TIME ZONE;
    ALTER TABLE bookings ADD COLUMN IF NOT EXISTS sync_error TEXT;
    ALTER TABLE bookings ADD COLUMN IF NOT EXISTS sync_attempts INTEGER DEFAULT 0;
    
    -- Update existing bookings to have 'synced' status if they have google_event_id
    UPDATE bookings 
    SET sync_status = 'synced', last_synced = updated_at 
    WHERE google_event_id IS NOT NULL AND sync_status = 'pending';
    
    -- Update existing bookings without google_event_id to have 'failed' status
    UPDATE bookings 
    SET sync_status = 'failed', sync_error = 'No calendar connection' 
    WHERE google_event_id IS NULL AND sync_status = 'pending';
    """
    
    try:
        with engine.connect() as connection:
            # Execute the migration
            for statement in migration_sql.split(';'):
                if statement.strip():
                    connection.execute(text(statement))
            connection.commit()
            
        print("✅ Successfully added sync fields to bookings table")
        print("✅ Updated existing bookings with appropriate sync status")
        
    except Exception as e:
        print(f"❌ Error during migration: {e}")
        raise

def verify_migration():
    """Verify that the migration was successful."""
    
    verify_sql = """
    SELECT column_name, data_type, is_nullable, column_default
    FROM information_schema.columns 
    WHERE table_name = 'bookings' 
    AND column_name IN ('sync_status', 'last_synced', 'sync_error', 'sync_attempts')
    ORDER BY column_name;
    """
    
    try:
        with engine.connect() as connection:
            result = connection.execute(text(verify_sql))
            columns = result.fetchall()
            
        if len(columns) == 4:
            print("✅ Migration verification successful - all sync fields present")
            for column in columns:
                print(f"   - {column[0]}: {column[1]} (nullable: {column[2]}, default: {column[3]})")
        else:
            print(f"❌ Migration verification failed - expected 4 columns, found {len(columns)}")
            
    except Exception as e:
        print(f"❌ Error during verification: {e}")
        raise

if __name__ == "__main__":
    print("🔄 Starting database migration: Add sync fields to bookings table")
    
    try:
        # First check if the bookings table exists
        if not check_table_exists():
            print("💥 Cannot proceed - bookings table does not exist")
            sys.exit(1)
        
        # Check if sync columns already exist
        if check_sync_columns_exist():
            print("✅ Migration not needed - all sync columns already exist")
            verify_migration()
        else:
            # Run the migration
            add_sync_fields_to_bookings()
            
            # Verify the migration
            verify_migration()
        
        print("🎉 Database migration completed successfully!")
        
    except Exception as e:
        print(f"💥 Migration failed: {e}")
        sys.exit(1) 