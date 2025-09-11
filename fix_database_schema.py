#!/usr/bin/env python3
"""
Database schema fix script for the membership system.
This script fixes the database schema issues that prevent the application from working properly.

Run this script on the testing server after pulling the latest code changes.
"""

import sys
import os
import logging
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.exc import ProgrammingError

# Add the current directory to Python path
sys.path.append(os.path.dirname(__file__))

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def fix_database_schema():
    """Fix database schema issues for all tenants"""
    
    try:
        # Import after adding to path
        from config import Config
        from app import create_app
        from database import _tenant_engines
        
        # Initialize Flask app to set up database connections
        logger.info("Initializing Flask application...")
        app = create_app()
        
        with app.app_context():
            logger.info("Flask app context initialized")
            
            for tenant_id in Config.TENANT_DATABASES.keys():
                logger.info(f"\n{'='*50}")
                logger.info(f"FIXING SCHEMA FOR TENANT: {tenant_id}")
                logger.info(f"{'='*50}")
                
                try:
                    fix_tenant_schema(tenant_id, _tenant_engines[tenant_id])
                    logger.info(f"✅ Successfully fixed schema for {tenant_id}")
                except Exception as e:
                    logger.error(f"❌ Failed to fix schema for {tenant_id}: {str(e)}")
                    continue
                    
        logger.info(f"\n{'='*50}")
        logger.info("SCHEMA FIX COMPLETED")
        logger.info(f"{'='*50}")
        
    except Exception as e:
        logger.error(f"Failed to initialize application: {str(e)}")
        sys.exit(1)

def fix_tenant_schema(tenant_id, engine):
    """Fix schema issues for a specific tenant"""
    
    inspector = inspect(engine)
    
    with engine.begin() as conn:
        # Fix user_auth_details table
        logger.info(f"Checking user_auth_details table for {tenant_id}...")
        
        if inspector.has_table('user_auth_details'):
            # Get current columns
            columns = [col['name'] for col in inspector.get_columns('user_auth_details')]
            logger.info(f"Current columns: {columns}")
            
            # Add missing password_hash column if it doesn't exist
            if 'password_hash' not in columns:
                logger.info("Adding missing password_hash column...")
                conn.execute(text("ALTER TABLE user_auth_details ADD COLUMN password_hash VARCHAR(255)"))
                logger.info("✅ Added password_hash column")
            else:
                logger.info("✅ password_hash column already exists")
                
            # Add other missing columns if needed
            required_columns = {
                'is_active': 'BOOLEAN DEFAULT TRUE',
                'last_login_1': 'TIMESTAMP',
                'last_login_2': 'TIMESTAMP', 
                'last_login_3': 'TIMESTAMP'
            }
            
            for col_name, col_type in required_columns.items():
                if col_name not in columns:
                    logger.info(f"Adding missing {col_name} column...")
                    conn.execute(text(f"ALTER TABLE user_auth_details ADD COLUMN {col_name} {col_type}"))
                    logger.info(f"✅ Added {col_name} column")
        else:
            logger.info("user_auth_details table doesn't exist, it will be created by the app")
            
        # Fix user table - ensure it has the correct table name
        logger.info(f"Checking user table for {tenant_id}...")
        
        # Check if we have 'users' table instead of 'user'
        if inspector.has_table('users') and not inspector.has_table('user'):
            logger.info("Renaming 'users' table to 'user' to match model...")
            conn.execute(text("ALTER TABLE users RENAME TO \"user\""))
            logger.info("✅ Renamed users table to user")
            
        # Ensure user table has required columns
        if inspector.has_table('user'):
            user_columns = [col['name'] for col in inspector.get_columns('user')]
            logger.info(f"User table columns: {user_columns}")
            
            # Add missing columns that are required by the model
            required_user_columns = {
                'membership_type_id': 'INTEGER',
                'is_active': 'BOOLEAN DEFAULT TRUE'
            }
            
            for col_name, col_type in required_user_columns.items():
                if col_name not in user_columns:
                    logger.info(f"Adding missing {col_name} column to user table...")
                    conn.execute(text(f"ALTER TABLE \"user\" ADD COLUMN {col_name} {col_type}"))
                    logger.info(f"✅ Added {col_name} column to user table")
        
        # Create missing tables if they don't exist
        missing_tables = []
        required_tables = ['user', 'user_auth_details', 'membership_type', 'attendance_record', 'dues_type', 'dues_record', 'referral_record']
        
        for table in required_tables:
            if not inspector.has_table(table):
                missing_tables.append(table)
                
        if missing_tables:
            logger.info(f"Missing tables will be created by Flask-SQLAlchemy: {missing_tables}")
            
        # Remove any tenant_id columns if they exist (since we use separate databases)
        tables_to_check = ['user', 'user_auth_details', 'attendance_record', 'dues_record', 'referral_record']
        
        for table in tables_to_check:
            if inspector.has_table(table):
                columns = [col['name'] for col in inspector.get_columns(table)]
                if 'tenant_id' in columns:
                    logger.info(f"Removing tenant_id column from {table} table...")
                    try:
                        conn.execute(text(f"ALTER TABLE {table} DROP COLUMN tenant_id"))
                        logger.info(f"✅ Removed tenant_id from {table}")
                    except ProgrammingError as e:
                        logger.warning(f"Could not remove tenant_id from {table}: {str(e)}")

def main():
    """Main function"""
    logger.info("=== DATABASE SCHEMA FIX SCRIPT ===")
    logger.info("This script will fix database schema issues for the membership system")
    logger.info("Run this after pulling the latest code changes to the testing server")
    
    try:
        fix_database_schema()
        logger.info("🎉 Database schema fix completed successfully!")
        logger.info("You can now restart the application and it should work properly.")
        return True
    except Exception as e:
        logger.error(f"❌ Schema fix failed: {str(e)}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
