#!/usr/bin/env python3
"""
Script to purge dues-related tables from the tenant databases.
"""

import sys
sys.path.append('.')

from database import get_tenant_db_session
from config import Config
import logging
from sqlalchemy import text

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def purge_dues_tables():
    """Purge dues tables from all tenants"""

    tenant_ids = list(Config.TENANT_DATABASES.keys())
    logger.info(f"Found {len(tenant_ids)} tenants: {tenant_ids}")

    for tenant_id in tenant_ids:
        try:
            logger.info(f"Processing tenant: {tenant_id}")

            with get_tenant_db_session(tenant_id) as s:
                # Drop dues_records table
                try:
                    s.execute(text("DROP TABLE IF EXISTS dues_records"))
                    s.commit()
                    logger.info(f"Dropped dues_records table for tenant {tenant_id}")
                except Exception as e:
                    logger.error(f"Error dropping dues_records table for tenant {tenant_id}: {str(e)}")

                # Drop dues_types table
                try:
                    s.execute(text("DROP TABLE IF EXISTS dues_types"))
                    s.commit()
                    logger.info(f"Dropped dues_types table for tenant {tenant_id}")
                except Exception as e:
                    logger.error(f"Error dropping dues_types table for tenant {tenant_id}: {str(e)}")

        except Exception as e:
            logger.error(f"Error processing tenant {tenant_id}: {str(e)}")
            continue

    logger.info("Purge complete.")


if __name__ == "__main__":
    print("WARNING: This will delete ALL dues-related tables from ALL tenants!")
    print("This action cannot be undone.")

    response = input("Are you sure you want to continue? (yes/no): ").strip().lower()

    if response == 'yes':
        purge_dues_tables()
        print("Successfully purged dues tables.")
    else:
        print("Operation cancelled.")
