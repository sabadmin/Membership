#!/usr/bin/env python3
"""
Script to migrate the dues_records table structure:
- Remove the dues_type column (string field)
- Add dues_type_id column (foreign key to dues_types table)
"""

import sys
sys.path.append('.')

from database import get_tenant_db_session, init_db_for_tenant
from app.models import DuesRecord, DuesType
from config import Config
import logging
from sqlalchemy import text

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate_dues_table_schema():
    """Migrate dues_records table schema for all tenants"""
    
    # Get all tenant IDs from config
    tenant_ids = list(Config.TENANT_DATABASES.keys())
    logger.info(f"Found {len(tenant_ids)} tenants: {tenant_ids}")
    
    for tenant_id in tenant_ids:
        try:
            logger.info(f"Processing tenant: {tenant_id}")
            
            # Initialize database engine and session for the current tenant
            init_db_for_tenant(Flask(__name__), tenant_id)  # Create a dummy Flask app for context
            
            with get_tenant_db_session(tenant_id) as s:
                # Check if the table exists and get current schema
                result = s.execute(text("""
                    SELECT column_name, data_type
                    FROM information_schema.columns
                    WHERE table_name = 'dues_records'
                    ORDER BY column_name
                """))
                
                columns = {row[0]: row[1] for row in result.fetchall()}
                logger.info(f"Current dues_records columns in {tenant_id}: {list(columns.keys())}")
                
                # Check if migration is needed
                has_dues_type = 'dues_type' in columns
                has_dues_type_id = 'dues_type_id' in columns
                
                if has_dues_type_id and not has_dues_type:
                    logger.info(f"Table already migrated for tenant {tenant_id}")
                    continue
                    
                if not has_dues_type:
                    logger.warning(f"No dues_type column found in tenant {tenant_id} - skipping")
                    continue
                
                # Step 1: Add dues_type_id column if it doesn't exist
                if not has_dues_type_id:
                    logger.info(f"Adding dues_type_id column for tenant {tenant_id}")
                    s.execute(text("""
                        ALTER TABLE dues_records
                        ADD COLUMN dues_type_id INTEGER
                    """))
                    s.commit()
                
                # Step 2: Create foreign key constraint
                logger.info(f"Adding foreign key constraint for tenant {tenant_id}")
                try:
                    s.execute(text("""
                        ALTER TABLE dues_records
                        ADD CONSTRAINT fk_dues_records_dues_type_id
                        FOREIGN KEY (dues_type_id) REFERENCES dues_types(id)
                    """))
                    s.commit()
                except Exception as fk_error:
                    logger.warning(f"Could not add foreign key constraint: {str(fk_error)}")
                    # Continue without foreign key if dues_types table doesn't exist
                
                # Step 3: Drop the old dues_type column
                logger.info(f"Dropping dues_type column for tenant {tenant_id}")
                s.execute(text("""
                    ALTER TABLE dues_records
                    DROP COLUMN IF EXISTS dues_type
                """))
                s.commit()
                
                logger.info(f"Successfully migrated dues_records table for tenant {tenant_id}")
                
        except Exception as e:
            logger.error(f"Error migrating tenant {tenant_id}: {str(e)}")
            continue
    
    logger.info("Schema migration complete")

def verify_migration():
    """Verify the migration was successful"""
    tenant_ids = list(Config.TENANT_DATABASES.keys())
    
    for tenant_id in tenant_ids:
        try:
            # Initialize database engine and session for verification
            init_db_for_tenant(Flask(__name__), tenant_id)
            
            with get_tenant_db_session(tenant_id) as s:
                result = s.execute(text("""
                    SELECT column_name, data_type
                    FROM information_schema.columns
                    WHERE table_name = 'dues_records'
                    ORDER BY column_name
                """))
                
                columns = {row[0]: row[1] for row in result.fetchall()}
                
                has_dues_type = 'dues_type' in columns
                has_dues_type_id = 'dues_type_id' in columns
                
                logger.info(f"Tenant {tenant_id}: dues_type={has_dues_type}, dues_type_id={has_dues_type_id}")
                
                if has_dues_type_id and not has_dues_type:
                    logger.info(f"✅ Tenant {tenant_id} migration successful")
                else:
                    logger.error(f"❌ Tenant {tenant_id} migration incomplete")
                    
        except Exception as e:
            logger.error(f"Error verifying tenant {tenant_id}: {str(e)}")

if __name__ == "__main__":
    print("This will modify the dues_records table structure for ALL tenants!")
    print("Changes:")
    print("- Remove 'dues_type' column (string)")
    print("- Add 'dues_type_id' column (foreign key to dues_types)")
    print("\nThis will make all existing dues records inaccessible until new ones are created!")
    
    response = input("Are you sure you want to continue? (yes/no): ").strip().lower()
    
    if response == 'yes':
        migrate_dues_table_schema()
        print("\nVerifying migration...")
        verify_migration()
        print("Migration complete!")
    else:
        print("Operation cancelled.")