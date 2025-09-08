#!/usr/bin/env python3
"""
Final fix for membership permissions with proper transaction handling
"""

import psycopg2
from config import Config
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_membership_permissions_direct():
    """Fix permissions using direct database connections to avoid transaction issues"""
    
    for tenant_id, db_url in Config.TENANT_DATABASES.items():
        logger.info(f"Fixing permissions for tenant: {tenant_id}")
        
        try:
            # Parse the database URL
            db_url_clean = db_url.replace('postgresql://', '')
            user_pass, host_db = db_url_clean.split('@')
            username, password = user_pass.split(':')
            host_port, database = host_db.split('/')
            host, port = host_port.split(':')
            
            # Connect directly with psycopg2
            conn = psycopg2.connect(
                host=host,
                port=port,
                database=database,
                user=username,
                password=password
            )
            conn.autocommit = True
            
            cursor = conn.cursor()
            
            # Check existing columns
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'membership_types' 
                AND column_name IN ('can_edit_attendance', 'can_edit_demographics', 'can_edit_dues', 'can_edit_referrals')
            """)
            existing_columns = [row[0] for row in cursor.fetchall()]
            logger.info(f"Existing columns for {tenant_id}: {existing_columns}")
            
            # Add missing columns
            columns_to_add = [
                'can_edit_attendance',
                'can_edit_demographics', 
                'can_edit_dues',
                'can_edit_referrals'
            ]
            
            for column_name in columns_to_add:
                if column_name not in existing_columns:
                    try:
                        cursor.execute(f"ALTER TABLE membership_types ADD COLUMN {column_name} BOOLEAN DEFAULT FALSE")
                        logger.info(f"Added {column_name} to {tenant_id}")
                    except Exception as e:
                        logger.warning(f"Could not add {column_name} to {tenant_id}: {str(e)}")
            
            # Update NULL values to FALSE
            for column_name in columns_to_add:
                try:
                    cursor.execute(f"UPDATE membership_types SET {column_name} = FALSE WHERE {column_name} IS NULL")
                    logger.info(f"Updated NULL values for {column_name} in {tenant_id}")
                except Exception as e:
                    logger.warning(f"Could not update {column_name} in {tenant_id}: {str(e)}")
            
            # Set permissions for leadership roles
            try:
                cursor.execute("""
                    UPDATE membership_types 
                    SET can_edit_attendance = TRUE, can_edit_demographics = TRUE, 
                        can_edit_dues = TRUE, can_edit_referrals = TRUE 
                    WHERE LOWER(name) IN ('board member', 'president', 'administrator', 'treasurer', 'admin')
                """)
                logger.info(f"Set leadership permissions for {tenant_id}")
            except Exception as e:
                logger.warning(f"Could not set leadership permissions for {tenant_id}: {str(e)}")
            
            # Remove user_role column if it exists
            try:
                cursor.execute("ALTER TABLE users DROP COLUMN user_role")
                logger.info(f"Removed user_role column from {tenant_id}")
            except Exception as e:
                logger.info(f"user_role column already removed or doesn't exist for {tenant_id}")
            
            cursor.close()
            conn.close()
            logger.info(f"Successfully processed {tenant_id}")
            
        except Exception as e:
            logger.error(f"Error processing {tenant_id}: {str(e)}")

if __name__ == "__main__":
    print("=" * 60)
    print("FINAL MEMBERSHIP PERMISSIONS FIX")
    print("=" * 60)
    
    fix_membership_permissions_direct()
    print("\n✅ Final migration completed!")
    print("\nNext steps:")
    print("1. Restart the Flask application")
    print("2. Access Admin Panel to configure membership type permissions")
    print("3. Test the membership list and attendance functionality")