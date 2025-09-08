#!/usr/bin/env python3
"""
Safe migration to add permission fields to membership_types table
"""

from app import create_app
from database import get_tenant_db_session
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def safe_add_columns():
    """Safely add permission columns to membership_types table"""
    app = create_app()
    
    with app.app_context():
        from config import Config
        
        for tenant_id in Config.TENANT_DATABASES.keys():
            logger.info(f"Processing tenant: {tenant_id}")
            
            try:
                with get_tenant_db_session(tenant_id) as s:
                    # Check if columns exist first
                    result = s.execute(text("""
                        SELECT column_name 
                        FROM information_schema.columns 
                        WHERE table_name = 'membership_types' 
                        AND column_name IN ('can_edit_attendance', 'can_edit_demographics', 'can_edit_dues', 'can_edit_referrals')
                    """))
                    existing_columns = [row[0] for row in result]
                    logger.info(f"Existing permission columns for {tenant_id}: {existing_columns}")
                    
                    # Add missing columns one by one with separate transactions
                    columns_to_add = [
                        ('can_edit_attendance', 'BOOLEAN DEFAULT FALSE NOT NULL'),
                        ('can_edit_demographics', 'BOOLEAN DEFAULT FALSE NOT NULL'), 
                        ('can_edit_dues', 'BOOLEAN DEFAULT FALSE NOT NULL'),
                        ('can_edit_referrals', 'BOOLEAN DEFAULT FALSE NOT NULL')
                    ]
                    
                    for column_name, column_def in columns_to_add:
                        if column_name not in existing_columns:
                            try:
                                logger.info(f"Adding {column_name} to {tenant_id}")
                                s.execute(text(f"ALTER TABLE membership_types ADD COLUMN {column_name} {column_def}"))
                                s.commit()
                                logger.info(f"Successfully added {column_name} to {tenant_id}")
                            except Exception as e:
                                s.rollback()
                                logger.error(f"Error adding {column_name} to {tenant_id}: {str(e)}")
                        else:
                            logger.info(f"{column_name} already exists for {tenant_id}")
                    
                    # Set permissions for known leadership roles
                    try:
                        s.execute(text("""
                            UPDATE membership_types 
                            SET can_edit_attendance = TRUE, can_edit_demographics = TRUE, 
                                can_edit_dues = TRUE, can_edit_referrals = TRUE 
                            WHERE LOWER(name) IN ('board member', 'president', 'administrator', 'treasurer', 'admin')
                        """))
                        s.commit()
                        logger.info(f"Set leadership permissions for {tenant_id}")
                    except Exception as e:
                        s.rollback()
                        logger.warning(f"Could not set leadership permissions for {tenant_id}: {str(e)}")
                        
            except Exception as e:
                logger.error(f"Error processing {tenant_id}: {str(e)}")

if __name__ == "__main__":
    print("=" * 60)
    print("SAFE MEMBERSHIP PERMISSIONS MIGRATION")
    print("=" * 60)
    
    safe_add_columns()
    print("\n✅ Migration completed!")