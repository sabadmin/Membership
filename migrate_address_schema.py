#!/usr/bin/env python3
"""
Database migration script to update User table schema from single address field
to separate address_line1, address_line2, city, state, zip_code fields.

Run this ONCE after deploying the new models to update existing databases.
"""

import os
import sys
import logging
from sqlalchemy import create_engine, text
from config import Config
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

def migrate_tenant_database(tenant_id, db_url):
    """Migrate a single tenant database"""
    logger.info(f"Starting migration for tenant: {tenant_id}")
    
    try:
        engine = create_engine(db_url)
        
        with engine.begin() as conn:
            # Check if old address column exists
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'users' AND column_name = 'address'
            """))
            
            has_old_address = result.fetchone() is not None
            
            if has_old_address:
                logger.info(f"Found old address column in {tenant_id}, migrating...")
                
                # Add new address columns
                conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS address_line1 VARCHAR(255)"))
                conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS address_line2 VARCHAR(255)"))
                conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS city VARCHAR(100)"))
                conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS state VARCHAR(2)"))
                conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS zip_code VARCHAR(10)"))
                
                # Migrate existing address data to address_line1
                conn.execute(text("UPDATE users SET address_line1 = address WHERE address IS NOT NULL"))
                
                # Drop old address column
                conn.execute(text("ALTER TABLE users DROP COLUMN address"))
                
                logger.info(f"✅ Successfully migrated {tenant_id}")
            else:
                logger.info(f"✅ {tenant_id} already has new schema")
                
        # Ensure new tables are created for the other models
        logger.info(f"Creating new tables for {tenant_id}...")
        
        # Import models to ensure they're registered
        from app.models import User, UserAuthDetails, AttendanceRecord, DuesRecord, ReferralRecord
        
        # Tables should already be created by the app initialization
        logger.info(f"✅ Using existing tables for {tenant_id}")
        
    except Exception as e:
        logger.error(f"❌ Failed to migrate {tenant_id}: {str(e)}")
        raise

def main():
    """Run migration for all tenants"""
    logger.info("=== DATABASE SCHEMA MIGRATION ===")
    logger.info("Migrating from single 'address' field to separate address fields")
    
    success_count = 0
    total_count = len(Config.TENANT_DATABASES)
    
    for tenant_id, db_url in Config.TENANT_DATABASES.items():
        try:
            migrate_tenant_database(tenant_id, db_url)
            success_count += 1
        except Exception as e:
            logger.error(f"Migration failed for {tenant_id}: {str(e)}")
    
    logger.info(f"Migration completed: {success_count}/{total_count} tenants successful")
    
    if success_count == total_count:
        logger.info("🎉 All database migrations completed successfully!")
        return True
    else:
        logger.error("⚠️  Some migrations failed. Check logs above.")
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
