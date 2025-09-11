#!/usr/bin/env python3
"""
Database Schema Fix for Membership System
Combines apply_database_fix.sh and manual_database_fix.sql into a single Python script
"""

import subprocess
import sys
import os
from typing import List, Tuple

# ANSI color codes for terminal output
class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'  # No Color

def print_status(message: str):
    """Print success message in green"""
    print(f"{Colors.GREEN}✅ {message}{Colors.NC}")

def print_warning(message: str):
    """Print warning message in yellow"""
    print(f"{Colors.YELLOW}⚠️  {message}{Colors.NC}")

def print_error(message: str):
    """Print error message in red"""
    print(f"{Colors.RED}❌ {message}{Colors.NC}")

def print_info(message: str):
    """Print info message in blue"""
    print(f"{Colors.BLUE}ℹ️  {message}{Colors.NC}")

# Database connection configuration
DB_CONFIG = {
    'host': 'localhost',
    'user': 'sabadmin',
    'password': 'Bellm0re'
}

# List of databases to fix - focused on liconnects and admin panel (main website)
TENANT_DATABASES = [
    'liconnects_db',
    'website_db'
]

# SQL commands to fix the database schema
SQL_COMMANDS = """
-- Manual Database Schema Fix for Membership System
-- Add missing columns to user_auth_details table
ALTER TABLE user_auth_details ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255);
ALTER TABLE user_auth_details ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;
ALTER TABLE user_auth_details ADD COLUMN IF NOT EXISTS last_login_1 TIMESTAMP;
ALTER TABLE user_auth_details ADD COLUMN IF NOT EXISTS last_login_2 TIMESTAMP;
ALTER TABLE user_auth_details ADD COLUMN IF NOT EXISTS last_login_3 TIMESTAMP;

-- Add missing columns to user table
ALTER TABLE "user" ADD COLUMN IF NOT EXISTS membership_type_id INTEGER;
ALTER TABLE "user" ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;

-- Remove tenant_id columns if they exist (since we use separate databases)
ALTER TABLE "user" DROP COLUMN IF EXISTS tenant_id;
ALTER TABLE user_auth_details DROP COLUMN IF EXISTS tenant_id;
ALTER TABLE attendance_record DROP COLUMN IF EXISTS tenant_id;
ALTER TABLE dues_record DROP COLUMN IF EXISTS tenant_id;
ALTER TABLE referral_record DROP COLUMN IF EXISTS tenant_id;
"""

def check_postgresql_status() -> bool:
    """Check if PostgreSQL service is running"""
    try:
        result = subprocess.run(
            ['systemctl', 'is-active', 'postgresql'],
            capture_output=True,
            text=True,
            check=False
        )
        return result.returncode == 0
    except FileNotFoundError:
        print_warning("systemctl not found, assuming PostgreSQL is running")
        return True
    except Exception as e:
        print_error(f"Error checking PostgreSQL status: {e}")
        return False

def database_exists(db_name: str) -> bool:
    """Check if a database exists"""
    try:
        cmd = [
            'psql',
            '-h', DB_CONFIG['host'],
            '-U', DB_CONFIG['user'],
            '-lqt'
        ]
        
        env = os.environ.copy()
        env['PGPASSWORD'] = DB_CONFIG['password']
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env=env,
            check=True
        )
        
        # Parse the output to check if database exists
        databases = [line.split('|')[0].strip() for line in result.stdout.split('\n')]
        return db_name in databases
        
    except subprocess.CalledProcessError as e:
        print_error(f"Error checking database existence: {e}")
        return False
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        return False

def apply_sql_fix(db_name: str) -> bool:
    """Apply SQL schema fix to a specific database"""
    try:
        cmd = [
            'psql',
            '-h', DB_CONFIG['host'],
            '-U', DB_CONFIG['user'],
            '-d', db_name,
            '-c', SQL_COMMANDS
        ]
        
        env = os.environ.copy()
        env['PGPASSWORD'] = DB_CONFIG['password']
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env=env,
            check=True
        )
        
        return True
        
    except subprocess.CalledProcessError as e:
        print_error(f"SQL execution failed for {db_name}: {e.stderr}")
        return False
    except Exception as e:
        print_error(f"Unexpected error applying fix to {db_name}: {e}")
        return False

def show_schema_info(db_name: str):
    """Show updated schema information for verification"""
    try:
        schema_cmd = [
            'psql',
            '-h', DB_CONFIG['host'],
            '-U', DB_CONFIG['user'],
            '-d', db_name,
            '-c', '\\d user_auth_details; \\d "user";'
        ]
        
        env = os.environ.copy()
        env['PGPASSWORD'] = DB_CONFIG['password']
        
        result = subprocess.run(
            schema_cmd,
            capture_output=True,
            text=True,
            env=env,
            check=True
        )
        
        print_info(f"Schema information for {db_name}:")
        print(result.stdout)
        
    except Exception as e:
        print_warning(f"Could not retrieve schema info for {db_name}: {e}")

def main():
    """Main execution function"""
    print("=" * 50)
    print("DATABASE SCHEMA FIX FOR MEMBERSHIP SYSTEM")
    print("=" * 50)
    print()
    
    print("This script will add missing columns to user_auth_details and user tables")
    print("for all tenant databases.")
    print()
    
    # Check PostgreSQL status
    if not check_postgresql_status():
        print_error("PostgreSQL is not running. Please start it first:")
        print("sudo systemctl start postgresql")
        sys.exit(1)
    
    print_status("PostgreSQL is running")
    print()
    
    # Track results
    successful_fixes = []
    failed_fixes = []
    skipped_databases = []
    
    # Process each tenant database
    for db_name in TENANT_DATABASES:
        print(f"Processing database: {db_name}")
        print("-" * 40)
        
        # Check if database exists
        if not database_exists(db_name):
            print_warning(f"Database {db_name} does not exist, skipping")
            skipped_databases.append(db_name)
            print()
            continue
        
        print_status(f"Database {db_name} exists")
        
        # Apply the SQL fix
        if apply_sql_fix(db_name):
            print_status(f"Successfully applied schema fix to {db_name}")
            successful_fixes.append(db_name)
            
            # Optionally show schema info (comment out if too verbose)
            # show_schema_info(db_name)
        else:
            print_error(f"Failed to apply schema fix to {db_name}")
            failed_fixes.append(db_name)
        
        print()
    
    # Summary
    print("=" * 50)
    print("DATABASE SCHEMA FIX COMPLETED")
    print("=" * 50)
    
    if successful_fixes:
        print_status(f"Successfully fixed {len(successful_fixes)} databases:")
        for db in successful_fixes:
            print(f"  • {db}")
    
    if failed_fixes:
        print_error(f"Failed to fix {len(failed_fixes)} databases:")
        for db in failed_fixes:
            print(f"  • {db}")
    
    if skipped_databases:
        print_warning(f"Skipped {len(skipped_databases)} databases (not found):")
        for db in skipped_databases:
            print(f"  • {db}")
    
    print()
    print("Next steps:")
    print("1. Restart the gunicorn application")
    print("2. Test user registration")
    print("3. Verify that the password_hash column error is resolved")
    print()
    
    if failed_fixes:
        print_error("Some databases failed to update. Please check the errors above.")
        sys.exit(1)
    else:
        print_status("Database schema fix completed successfully!")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print_error("\nOperation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        sys.exit(1)
