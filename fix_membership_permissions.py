#!/usr/bin/env python3
"""
Fix membership permissions database issues
"""

from app import create_app
from database import get_tenant_db_session
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_membership_permissions():
    """Fix permission columns in membership_types table"""
    app = create_app()
    
    with app.app_context():
        from config import Config
        
        for tenant_id in Config.TENANT_DATABASES.keys():
            logger.info(f"Fixing permissions for tenant: {tenant_id}")
            
            try:
                with get_tenant_db_session(tenant_id) as s:
                    # First, add columns with default values if they don't exist
                    try:
                        s.execute(text("ALTER TABLE membership_types ADD COLUMN can_edit_attendance BOOLEAN DEFAULT FALSE"))
                        logger.info(f"Added can_edit_attendance column for {tenant_id}")
                    except Exception as e:
                        logger.info(f"can_edit_attendance column already exists for {tenant_id}")

                    try:
                        s.execute(text("ALTER TABLE membership_types ADD COLUMN can_edit_demographics BOOLEAN DEFAULT FALSE"))
                        logger.info(f"Added can_edit_demographics column for {tenant_id}")
                    except Exception as e:
                        logger.info(f"can_edit_demographics column already exists for {tenant_id}")

                    try:
                        s.execute(text("ALTER TABLE membership_types ADD COLUMN can_edit_dues BOOLEAN DEFAULT FALSE"))
                        logger.info(f"Added can_edit_dues column for {tenant_id}")
                    except Exception as e:
                        logger.info(f"can_edit_dues column already exists for {tenant_id}")

                    try:
                        s.execute(text("ALTER TABLE membership_types ADD COLUMN can_edit_referrals BOOLEAN DEFAULT FALSE"))
                        logger.info(f"Added can_edit_referrals column for {tenant_id}")
                    except Exception as e:
                        logger.info(f"can_edit_referrals column already exists for {tenant_id}")

                    # Update NULL values to FALSE for all permission columns
                    s.execute(text("UPDATE membership_types SET can_edit_attendance = FALSE WHERE can_edit_attendance IS NULL"))
                    s.execute(text("UPDATE membership_types SET can_edit_demographics = FALSE WHERE can_edit_demographics IS NULL"))
                    s.execute(text("UPDATE membership_types SET can_edit_dues = FALSE WHERE can_edit_dues IS NULL"))
                    s.execute(text("UPDATE membership_types SET can_edit_referrals = FALSE WHERE can_edit_referrals IS NULL"))
                    
                    # Add NOT NULL constraints
                    try:
                        s.execute(text("ALTER TABLE membership_types ALTER COLUMN can_edit_attendance SET NOT NULL"))
                        s.execute(text("ALTER TABLE membership_types ALTER COLUMN can_edit_demographics SET NOT NULL"))
                        s.execute(text("ALTER TABLE membership_types ALTER COLUMN can_edit_dues SET NOT NULL"))
                        s.execute(text("ALTER TABLE membership_types ALTER COLUMN can_edit_referrals SET NOT NULL"))
                        logger.info(f"Added NOT NULL constraints for {tenant_id}")
                    except Exception as e:
                        logger.info(f"Constraints already exist for {tenant_id}")

                    # Set appropriate permissions for known types
                    s.execute(text("""
                        UPDATE membership_types 
                        SET can_edit_attendance = TRUE, can_edit_demographics = TRUE, 
                            can_edit_dues = TRUE, can_edit_referrals = TRUE 
                        WHERE name IN ('Board Member', 'President', 'Administrator', 'Treasurer')
                    """))
                    
                    s.commit()
                    logger.info(f"Successfully fixed permissions for {tenant_id}")
                    
            except Exception as e:
                logger.error(f"Error fixing {tenant_id}: {str(e)}")
                raise

if __name__ == "__main__":
    print("=" * 60)
    print("FIXING MEMBERSHIP PERMISSIONS")
    print("=" * 60)
    
    try:
        fix_membership_permissions()
        print("\n✅ SUCCESS: Membership permissions fixed!")
        
    except Exception as e:
        print(f"\n❌ FAILURE: Fix failed - {str(e)}")
        logger.error(f"Fix failed: {str(e)}")