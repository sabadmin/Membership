#!/usr/bin/env python3
"""
Script to purge all dues records from the database.
This prepares the database for the new foreign key schema.
"""

import sys
sys.path.append('.')

from database import get_tenant_db_session
from app.models import DuesRecord
from config import Config
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def purge_dues_records():
    """Purge all dues records from all tenants"""
    
    # Get all tenant IDs from config
    tenant_ids = list(Config.TENANT_DATABASES.keys())
    logger.info(f"Found {len(tenant_ids)} tenants: {tenant_ids}")
    
    total_deleted = 0
    
    for tenant_id in tenant_ids:
        try:
            logger.info(f"Processing tenant: {tenant_id}")
            
            with get_tenant_db_session(tenant_id) as s:
                # Count existing records
                existing_count = s.query(DuesRecord).count()
                logger.info(f"Found {existing_count} dues records in tenant {tenant_id}")
                
                if existing_count > 0:
                    # Delete all dues records
                    deleted_count = s.query(DuesRecord).delete()
                    s.commit()
                    
                    logger.info(f"Deleted {deleted_count} dues records from tenant {tenant_id}")
                    total_deleted += deleted_count
                else:
                    logger.info(f"No dues records to delete in tenant {tenant_id}")
                    
        except Exception as e:
            logger.error(f"Error processing tenant {tenant_id}: {str(e)}")
            continue
    
    logger.info(f"Purge complete. Total records deleted: {total_deleted}")
    return total_deleted

if __name__ == "__main__":
    print("WARNING: This will delete ALL dues records from ALL tenants!")
    print("This action cannot be undone.")
    
    response = input("Are you sure you want to continue? (yes/no): ").strip().lower()
    
    if response == 'yes':
        deleted_count = purge_dues_records()
        print(f"Successfully deleted {deleted_count} dues records.")
    else:
        print("Operation cancelled.")