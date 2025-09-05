#!/usr/bin/env python3
"""
Comprehensive database migration script for membership system improvements:
1. Remove tenant_id columns from all tables (separate databases eliminate need)
2. Update User table to separate company address fields
3. Create new tables for attendance, dues, and referrals subsystems

Run this ONCE after updating models to migrate existing databases.
"""

import os
import sys
import logging
from sqlalchemy import create_engine, text, inspect
from config import Config
from app.models import Base, User, UserAuthDetails, AttendanceRecord, DuesRecord, ReferralRecord
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

def migrate_tenant_database(tenant_id, db_url):
    """Migrate a single tenant database with all schema updates"""
    logger.info(f"Starting comprehensive migration for tenant: {tenant_id}")
    
    try:
        engine = create_engine(db_url)
        inspector = inspect(engine)
        
        with engine.begin() as conn:
            logger.info(f"=== STEP 1: Update User table structure for {tenant_id} ===")
            
            # Check current User table structure
            user_columns = [col['name'] for col in inspector.get_columns('users')]
            logger.info(f"Current user columns: {user_columns}")
            
            # Add new company address columns if they don't exist
            new_company_columns = [
                'company_address_line1', 'company_address_line2', 
                'company_city', 'company_state', 'company_zip_code'
            ]
            
            for col in new_company_columns:
                if col not in user_columns:
                    conn.execute(text(f"ALTER TABLE users ADD COLUMN {col} VARCHAR(255)"))
                    logger.info(f"  Added column: {col}")
            
            # Migrate data from old company_address to new structure
            if 'company_address' in user_columns:
                conn.execute(text("UPDATE users SET company_address_line1 = company_address WHERE company_address IS NOT NULL"))
                conn.execute(text("ALTER TABLE users DROP COLUMN company_address"))
                logger.info("  Migrated company_address to company_address_line1")
            
            # Add new personal address columns if they don't exist
            personal_address_columns = ['address_line1', 'address_line2', 'city', 'state', 'zip_code']
            for col in personal_address_columns:
                if col not in user_columns:
                    if col == 'address_line1':
                        conn.execute(text(f"ALTER TABLE users ADD COLUMN {col} VARCHAR(255)"))
                    elif col == 'address_line2':
                        conn.execute(text(f"ALTER TABLE users ADD COLUMN {col} VARCHAR(255)"))
                    elif col == 'city':
                        conn.execute(text(f"ALTER TABLE users ADD COLUMN {col} VARCHAR(100)"))
                    elif col == 'state':
                        conn.execute(text(f"ALTER TABLE users ADD COLUMN {col} VARCHAR(2)"))
                    elif col == 'zip_code':
                        conn.execute(text(f"ALTER TABLE users ADD COLUMN {col} VARCHAR(10)"))
                    logger.info(f"  Added column: {col}")
            
            # Migrate from old address field to new structure
            if 'address' in user_columns:
                conn.execute(text("UPDATE users SET address_line1 = address WHERE address IS NOT NULL"))
                conn.execute(text("ALTER TABLE users DROP COLUMN address"))
                logger.info("  Migrated address to address_line1")
            
            # Add new user fields if they don't exist
            if 'membership_type_id' not in user_columns:
                conn.execute(text("ALTER TABLE users ADD COLUMN membership_type_id INTEGER"))
                logger.info("  Added membership_type_id column")
            
            if 'user_role' not in user_columns:
                conn.execute(text("ALTER TABLE users ADD COLUMN user_role VARCHAR(20) DEFAULT 'member'"))
                logger.info("  Added user_role column")
            
            # Remove tenant_id from users table if it exists
            if 'tenant_id' in user_columns:
                conn.execute(text("ALTER TABLE users DROP COLUMN tenant_id"))
                logger.info("  Removed tenant_id from users table")
            
            logger.info(f"=== STEP 2: Update UserAuthDetails table for {tenant_id} ===")
            
            # Check if user_auth_details table exists and update it
            if inspector.has_table('user_auth_details'):
                auth_columns = [col['name'] for col in inspector.get_columns('user_auth_details')]
                if 'tenant_id' in auth_columns:
                    conn.execute(text("ALTER TABLE user_auth_details DROP COLUMN tenant_id"))
                    logger.info("  Removed tenant_id from user_auth_details table")
            
            logger.info(f"=== STEP 3: Create/Update subsystem tables for {tenant_id} ===")
            
            # Drop existing tables if they have tenant_id (they'll be recreated properly)
            subsystem_tables = ['attendance_records', 'dues_records', 'referral_records']
            for table in subsystem_tables:
                if inspector.has_table(table):
                    table_columns = [col['name'] for col in inspector.get_columns(table)]
                    if 'tenant_id' in table_columns:
                        conn.execute(text(f"DROP TABLE {table}"))
                        logger.info(f"  Dropped {table} (had tenant_id - will be recreated)")
                        
        # Create all tables with new schema
        logger.info(f"=== STEP 4: Ensure all tables exist with correct schema for {tenant_id} ===")
        Base.metadata.create_all(engine)
        logger.info(f"✅ All tables ensured for {tenant_id}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to migrate {tenant_id}: {str(e)}")
        raise

def main():
    """Run comprehensive migration for all tenants"""
    logger.info("=== COMPREHENSIVE DATABASE SCHEMA MIGRATION ===")
    logger.info("Applying all improvements:")
    logger.info("- Remove tenant_id columns (separate databases)")
    logger.info("- Separate company address fields") 
    logger.info("- Update personal address structure")
    logger.info("- Create attendance/dues/referrals tables")
    
    success_count = 0
    total_count = len(Config.TENANT_DATABASES)
    
    for tenant_id, db_url in Config.TENANT_DATABASES.items():
        try:
            logger.info(f"\n{'='*50}")
            logger.info(f"MIGRATING TENANT: {tenant_id}")
            logger.info(f"{'='*50}")
            
            migrate_tenant_database(tenant_id, db_url)
            success_count += 1
            logger.info(f"✅ {tenant_id} migration completed successfully")
            
        except Exception as e:
            logger.error(f"❌ Migration failed for {tenant_id}: {str(e)}")
    
    logger.info(f"\n{'='*50}")
    logger.info(f"MIGRATION SUMMARY")
    logger.info(f"{'='*50}")
    logger.info(f"Successfully migrated: {success_count}/{total_count} tenants")
    
    if success_count == total_count:
        logger.info("🎉 ALL DATABASE MIGRATIONS COMPLETED SUCCESSFULLY!")
        logger.info("\nYour membership system now has:")
        logger.info("✅ Separate company address fields")
        logger.info("✅ No tenant_id columns (clean separate databases)")
        logger.info("✅ Complete subsystem tables (attendance, dues, referrals)")
        logger.info("✅ Enhanced security with login tracking")
        return True
    else:
        logger.error("⚠️  Some migrations failed. Check logs above.")
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)