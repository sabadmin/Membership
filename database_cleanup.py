#!/usr/bin/env python3
"""
Database Cleanup Script for Membership System
Fixes orphaned records and data consistency issues
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

# List of databases to clean
TENANT_DATABASES = [
    'liconnects_db',
    'website_db'
]

# SQL commands to clean up orphaned records
CLEANUP_COMMANDS = """
-- Remove orphaned user_auth_details records (where user doesn't exist)
DELETE FROM user_auth_details 
WHERE user_id NOT IN (SELECT id FROM "user");

-- Remove orphaned attendance_record records (where user doesn't exist)
DELETE FROM attendance_record 
WHERE user_id NOT IN (SELECT id FROM "user");

-- Remove orphaned dues_record records (where member doesn't exist)
DELETE FROM dues_record 
WHERE member_id NOT IN (SELECT id FROM "user");

-- Remove orphaned referral_record records (where referrer or referred user doesn't exist)
DELETE FROM referral_record 
WHERE referrer_id NOT IN (SELECT id FROM "user") 
   OR referred_id NOT IN (SELECT id FROM "user");

-- Show counts after cleanup
SELECT 'Users' as table_name, COUNT(*) as count FROM "user"
UNION ALL
SELECT 'User Auth Details' as table_name, COUNT(*) as count FROM user_auth_details
UNION ALL
SELECT 'Attendance Records' as table_name, COUNT(*) as count FROM attendance_record
UNION ALL
SELECT 'Dues Records' as table_name, COUNT(*) as count FROM dues_record
UNION ALL
SELECT 'Referral Records' as table_name, COUNT(*) as count FROM referral_record;
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

def cleanup_database(db_name: str) -> bool:
    """Clean up orphaned records in a specific database"""
    try:
        cmd = [
            'psql',
            '-h', DB_CONFIG['host'],
            '-U', DB_CONFIG['user'],
            '-d', db_name,
            '-c', CLEANUP_COMMANDS
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
        
        print_info(f"Cleanup results for {db_name}:")
        print(result.stdout)
        return True
        
    except subprocess.CalledProcessError as e:
        print_error(f"Cleanup failed for {db_name}: {e.stderr}")
        return False
    except Exception as e:
        print_error(f"Unexpected error cleaning {db_name}: {e}")
        return False

def show_orphaned_records(db_name: str):
    """Show orphaned records before cleanup"""
    try:
        check_cmd = [
            'psql',
            '-h', DB_CONFIG['host'],
            '-U', DB_CONFIG['user'],
            '-d', db_name,
            '-c', """
            SELECT 'Orphaned user_auth_details' as issue, COUNT(*) as count 
            FROM user_auth_details 
            WHERE user_id NOT IN (SELECT id FROM "user")
            UNION ALL
            SELECT 'Orphaned attendance_record' as issue, COUNT(*) as count 
            FROM attendance_record 
            WHERE user_id NOT IN (SELECT id FROM "user")
            UNION ALL
            SELECT 'Orphaned dues_record' as issue, COUNT(*) as count 
            FROM dues_record 
            WHERE member_id NOT IN (SELECT id FROM "user")
            UNION ALL
            SELECT 'Orphaned referral_record' as issue, COUNT(*) as count 
            FROM referral_record 
            WHERE referrer_id NOT IN (SELECT id FROM "user") 
               OR referred_id NOT IN (SELECT id FROM "user");
            """
        ]
        
        env = os.environ.copy()
        env['PGPASSWORD'] = DB_CONFIG['password']
        
        result = subprocess.run(
            check_cmd,
            capture_output=True,
            text=True,
            env=env,
            check=True
        )
        
        print_info(f"Orphaned records in {db_name}:")
        print(result.stdout)
        
    except Exception as e:
        print_warning(f"Could not check orphaned records for {db_name}: {e}")

def main():
    """Main execution function"""
    print("=" * 50)
    print("DATABASE CLEANUP FOR MEMBERSHIP SYSTEM")
    print("=" * 50)
    print()
    
    print("This script will remove orphaned records that reference non-existent users")
    print("for liconnects and admin panel databases.")
    print()
    
    # Check PostgreSQL status
    if not check_postgresql_status():
        print_error("PostgreSQL is not running. Please start it first:")
        print("sudo systemctl start postgresql")
        sys.exit(1)
    
    print_status("PostgreSQL is running")
    print()
    
    # Track results
    successful_cleanups = []
    failed_cleanups = []
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
        
        # Show orphaned records before cleanup
        show_orphaned_records(db_name)
        
        # Clean up the database
        if cleanup_database(db_name):
            print_status(f"Successfully cleaned up {db_name}")
            successful_cleanups.append(db_name)
        else:
            print_error(f"Failed to clean up {db_name}")
            failed_cleanups.append(db_name)
        
        print()
    
    # Summary
    print("=" * 50)
    print("DATABASE CLEANUP COMPLETED")
    print("=" * 50)
    
    if successful_cleanups:
        print_status(f"Successfully cleaned {len(successful_cleanups)} databases:")
        for db in successful_cleanups:
            print(f"  • {db}")
    
    if failed_cleanups:
        print_error(f"Failed to clean {len(failed_cleanups)} databases:")
        for db in failed_cleanups:
            print(f"  • {db}")
    
    if skipped_databases:
        print_warning(f"Skipped {len(skipped_databases)} databases (not found):")
        for db in skipped_databases:
            print(f"  • {db}")
    
    print()
    print("Next steps:")
    print("1. Restart the gunicorn application")
    print("2. Test user login")
    print("3. Verify that the foreign key constraint errors are resolved")
    print()
    
    if failed_cleanups:
        print_error("Some databases failed to clean. Please check the errors above.")
        sys.exit(1)
    else:
        print_status("Database cleanup completed successfully!")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print_error("\nOperation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        sys.exit(1)
