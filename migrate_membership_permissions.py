#!/usr/bin/env python3
"""
Database migration to add permission fields to membership_types table
"""

from app import create_app
from database import get_tenant_db_session
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate_membership_permissions():
    """Add permission columns to membership_types table"""
    app = create_app()
    
    with app.app_context():
        # Get all tenant databases
        from config import Config
        
        for tenant_id in Config.TENANT_DATABASES.keys():
            logger.info(f"Migrating permissions for tenant: {tenant_id}")
            
            try:
                with get_tenant_db_session(tenant_id) as s:
                    # Add new permission columns to membership_types table
                    try:
                        s.execute(text("ALTER TABLE membership_types ADD COLUMN can_edit_attendance BOOLEAN DEFAULT FALSE NOT NULL"))
                        logger.info(f"Added can_edit_attendance column for {tenant_id}")
                    except Exception as e:
                        if "already exists" in str(e).lower():
                            logger.info(f"can_edit_attendance column already exists for {tenant_id}")
                        else:
                            raise
                    
                    try:
                        s.execute(text("ALTER TABLE membership_types ADD COLUMN can_edit_demographics BOOLEAN DEFAULT FALSE NOT NULL"))
                        logger.info(f"Added can_edit_demographics column for {tenant_id}")
                    except Exception as e:
                        if "already exists" in str(e).lower():
                            logger.info(f"can_edit_demographics column already exists for {tenant_id}")
                        else:
                            raise
                    
                    try:
                        s.execute(text("ALTER TABLE membership_types ADD COLUMN can_edit_dues BOOLEAN DEFAULT FALSE NOT NULL"))
                        logger.info(f"Added can_edit_dues column for {tenant_id}")
                    except Exception as e:
                        if "already exists" in str(e).lower():
                            logger.info(f"can_edit_dues column already exists for {tenant_id}")
                        else:
                            raise
                    
                    try:
                        s.execute(text("ALTER TABLE membership_types ADD COLUMN can_edit_referrals BOOLEAN DEFAULT FALSE NOT NULL"))
                        logger.info(f"Added can_edit_referrals column for {tenant_id}")
                    except Exception as e:
                        if "already exists" in str(e).lower():
                            logger.info(f"can_edit_referrals column already exists for {tenant_id}")
                        else:
                            raise
                    
                    # Remove user_role column from users table if it exists
                    try:
                        s.execute(text("ALTER TABLE users DROP COLUMN user_role"))
                        logger.info(f"Removed user_role column for {tenant_id}")
                    except Exception as e:
                        if "does not exist" in str(e).lower():
                            logger.info(f"user_role column already removed for {tenant_id}")
                        else:
                            logger.warning(f"Could not remove user_role column for {tenant_id}: {str(e)}")
                    
                    s.commit()
                    logger.info(f"Successfully migrated permissions for {tenant_id}")
                    
            except Exception as e:
                logger.error(f"Error migrating {tenant_id}: {str(e)}")
                raise

def create_default_membership_types():
    """Create default membership types with appropriate permissions"""
    app = create_app()
    
    with app.app_context():
        from config import Config
        from app.models import MembershipType
        
        default_types = [
            {
                'name': 'Regular Member',
                'description': 'Standard membership with basic access',
                'can_edit_attendance': False,
                'can_edit_demographics': False,
                'can_edit_dues': False,
                'can_edit_referrals': False,
                'sort_order': 1
            },
            {
                'name': 'Board Member',
                'description': 'Board member with elevated permissions',
                'can_edit_attendance': True,
                'can_edit_demographics': True,
                'can_edit_dues': True,
                'can_edit_referrals': True,
                'sort_order': 2
            },
            {
                'name': 'President',
                'description': 'Organization president with full access',
                'can_edit_attendance': True,
                'can_edit_demographics': True,
                'can_edit_dues': True,
                'can_edit_referrals': True,
                'sort_order': 3
            },
            {
                'name': 'Administrator',
                'description': 'System administrator with full access',
                'can_edit_attendance': True,
                'can_edit_demographics': True,
                'can_edit_dues': True,
                'can_edit_referrals': True,
                'sort_order': 4
            }
        ]
        
        for tenant_id in Config.TENANT_DATABASES.keys():
            logger.info(f"Creating default membership types for tenant: {tenant_id}")
            
            try:
                with get_tenant_db_session(tenant_id) as s:
                    for type_data in default_types:
                        # Check if type already exists
                        existing = s.query(MembershipType).filter_by(name=type_data['name']).first()
                        if not existing:
                            new_type = MembershipType(**type_data)
                            s.add(new_type)
                            logger.info(f"Created membership type '{type_data['name']}' for {tenant_id}")
                        else:
                            # Update existing with new permissions
                            existing.can_edit_attendance = type_data['can_edit_attendance']
                            existing.can_edit_demographics = type_data['can_edit_demographics']
                            existing.can_edit_dues = type_data['can_edit_dues']
                            existing.can_edit_referrals = type_data['can_edit_referrals']
                            logger.info(f"Updated permissions for '{type_data['name']}' in {tenant_id}")
                    
                    s.commit()
                    logger.info(f"Successfully created/updated membership types for {tenant_id}")
                    
            except Exception as e:
                logger.error(f"Error creating membership types for {tenant_id}: {str(e)}")
                raise

if __name__ == "__main__":
    print("=" * 60)
    print("MEMBERSHIP PERMISSIONS MIGRATION")
    print("=" * 60)
    
    try:
        logger.info("Starting database migration...")
        migrate_membership_permissions()
        
        logger.info("Creating default membership types...")
        create_default_membership_types()
        
        print("\n✅ SUCCESS: Membership permissions migration completed!")
        print("   - Added permission columns to membership_types table")
        print("   - Removed user_role column from users table")
        print("   - Created default membership types with permissions")
        
    except Exception as e:
        print(f"\n❌ FAILURE: Migration failed - {str(e)}")
        logger.error(f"Migration failed: {str(e)}")