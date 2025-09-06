#!/usr/bin/env python3
"""
Debug script to identify and fix admin panel issues.
Run this to test admin functionality without full server startup.
"""

import os
import sys
import logging
from datetime import datetime
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker
from config import Config
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

def check_database_schema(tenant_id, db_url):
    """Check if database has all required columns"""
    logger.info(f"Checking schema for tenant: {tenant_id}")
    
    try:
        engine = create_engine(db_url)
        inspector = inspect(engine)
        
        # Check Users table
        if inspector.has_table('users'):
            user_columns = [col['name'] for col in inspector.get_columns('users')]
            logger.info(f"Users table columns: {user_columns}")
            
            missing_columns = []
            required_columns = ['membership_type_id', 'user_role', 'company_address_line1', 'company_city']
            
            for col in required_columns:
                if col not in user_columns:
                    missing_columns.append(col)
            
            if missing_columns:
                logger.error(f"❌ {tenant_id}: Missing columns: {missing_columns}")
                return False
            else:
                logger.info(f"✅ {tenant_id}: All required columns present")
        
        # Check if MembershipType table exists
        if inspector.has_table('membership_types'):
            logger.info(f"✅ {tenant_id}: MembershipType table exists")
        else:
            logger.error(f"❌ {tenant_id}: MembershipType table missing")
            return False
            
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to check {tenant_id}: {str(e)}")
        return False

def main():
    """Check all tenant databases for schema issues"""
    logger.info("=== ADMIN PANEL DATABASE SCHEMA CHECK ===")
    
    all_good = True
    for tenant_id, db_url in Config.TENANT_DATABASES.items():
        if not check_database_schema(tenant_id, db_url):
            all_good = False
    
    logger.info(f"\n{'='*50}")
    if all_good:
        logger.info("🎉 All databases have correct schema!")
        logger.info("Admin panel should work properly.")
    else:
        logger.error("⚠️  Database schema issues found!")
        logger.error("SOLUTION: Run the migration script:")
        logger.error("  python migrate_complete_schema.py")
        logger.error("Then seed membership types:")
        logger.error("  python seed_membership_types.py")
    
    return all_good

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)