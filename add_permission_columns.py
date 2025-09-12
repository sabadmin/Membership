#!/usr/bin/env python3
"""
Add Permission Columns to UserAuthDetails
Adds the new granular permission fields to user_auth_details table
"""

import subprocess
import sys
import os

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

# List of databases to update - all tenant databases
TENANT_DATABASES = [
    'tenant1_db',
    'tenant2_db', 
    'website_db',
    'closers_db',
    'liconnects_db',
    'lieg_db'
]

# SQL commands to add permission columns
ADD_PERMISSION_COLUMNS_SQL = """
-- Add new granular permission columns to user_auth_details table
ALTER TABLE user_auth_details ADD COLUMN IF NOT EXISTS can_edit_dues BOOLEAN DEFAULT FALSE NOT NULL;
ALTER TABLE user_auth_details ADD COLUMN IF NOT EXISTS can_edit_security BOOLEAN DEFAULT FALSE NOT NULL;
ALTER TABLE user_auth_details ADD COLUMN IF NOT EXISTS can_edit_referrals BOOLEAN DEFAULT FALSE NOT NULL;
ALTER TABLE user_auth_details ADD COLUMN IF NOT EXISTS can_edit_members BOOLEAN DEFAULT FALSE NOT NULL;
ALTER TABLE user_auth_details ADD COLUMN IF NOT EXISTS can_edit_attendance BOOLEAN DEFAULT FALSE NOT NULL;

-- Show the updated schema
SELECT 'Updated user_auth_details columns:' as info;
SELECT column_name, data_type, is_nullable, column_default 
FROM information_schema.columns 
WHERE table_name = 'user_auth_details' 
AND column_name LIKE 'can_edit_%'
ORDER BY column_name;

-- Show count of records that will be affected
SELECT 'Total user_auth_details records:' as info, COUNT(*) as count FROM user_auth_details;
"""

def add_permission_columns(db_name: str) -> bool:
    """Add permission columns to a specific database"""
    try:
        cmd = [
            'psql',
            '-h', DB_CONFIG['host'],
            '-U', DB_CONFIG['user'],
            '-d', db_name,
            '-c', ADD_PERMISSION_COLUMNS_SQL
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
        
        print_info(f"Permission columns added to {db_name}:")
        print(result.stdout)
        return True
        
    except subprocess.CalledProcessError as e:
        print_error(f"Failed to add permission columns to {db_name}: {e.stderr}")
        return False
    except Exception as e:
        print_error(f"Unexpected error adding permission columns to {db_name}: {e}")
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

def main():
    """Main execution function"""
    print("=" * 60)
    print("ADD PERMISSION COLUMNS TO USER_AUTH_DETAILS")
    print("=" * 60)
    print()
    
    print("This script will add granular permission columns to user_auth_details:")
    print("  • can_edit_dues")
    print("  • can_edit_security") 
    print("  • can_edit_referrals")
    print("  • can_edit_members")
    print("  • can_edit_attendance")
    print()
    
    # Track results
    successful_updates = []
    failed_updates = []
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
        
        # Add permission columns
        if add_permission_columns(db_name):
            print_status(f"Successfully added permission columns to {db_name}")
            successful_updates.append(db_name)
        else:
            print_error(f"Failed to add permission columns to {db_name}")
            failed_updates.append(db_name)
        
        print()
    
    # Summary
    print("=" * 60)
    print("PERMISSION COLUMNS UPDATE COMPLETED")
    print("=" * 60)
    
    if successful_updates:
        print_status(f"Successfully updated {len(successful_updates)} databases:")
        for db in successful_updates:
            print(f"  • {db}")
    
    if failed_updates:
        print_error(f"Failed to update {len(failed_updates)} databases:")
        for db in failed_updates:
            print(f"  • {db}")
    
    if skipped_databases:
        print_warning(f"Skipped {len(skipped_databases)} databases (not found):")
        for db in skipped_databases:
            print(f"  • {db}")
    
    print()
    print("Next steps:")
    print("1. Restart the gunicorn application")
    print("2. Use Admin Panel to set user permissions")
    print("3. Test menu access based on permissions")
    print()
    
    if failed_updates:
        print_error("Some databases failed to update. Please check the errors above.")
        sys.exit(1)
    else:
        print_status("Permission columns added successfully!")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print_error("\nOperation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        sys.exit(1)
