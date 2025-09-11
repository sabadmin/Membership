#!/usr/bin/env python3
"""
Fix Foreign Key Constraints
Updates foreign key constraints to point to the correct user table
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

# List of databases to fix - all tenant databases
TENANT_DATABASES = [
    'tenant1_db',
    'tenant2_db', 
    'website_db',
    'closers_db',
    'liconnects_db',
    'lieg_db'
]

# SQL commands to fix foreign key constraints
FIX_FOREIGN_KEY_COMMANDS = """
-- Drop the incorrect foreign key constraint
ALTER TABLE user_auth_details DROP CONSTRAINT IF EXISTS user_auth_details_user_id_fkey;

-- Add the correct foreign key constraint pointing to "user" table
ALTER TABLE user_auth_details ADD CONSTRAINT user_auth_details_user_id_fkey 
    FOREIGN KEY (user_id) REFERENCES "user"(id);

-- Fix other tables that might have the same issue
ALTER TABLE attendance_record DROP CONSTRAINT IF EXISTS attendance_record_user_id_fkey;
ALTER TABLE attendance_record ADD CONSTRAINT attendance_record_user_id_fkey 
    FOREIGN KEY (user_id) REFERENCES "user"(id);

ALTER TABLE dues_record DROP CONSTRAINT IF EXISTS dues_record_member_id_fkey;
ALTER TABLE dues_record ADD CONSTRAINT dues_record_member_id_fkey 
    FOREIGN KEY (member_id) REFERENCES "user"(id);

ALTER TABLE referral_record DROP CONSTRAINT IF EXISTS referral_record_referrer_id_fkey;
ALTER TABLE referral_record ADD CONSTRAINT referral_record_referrer_id_fkey 
    FOREIGN KEY (referrer_id) REFERENCES "user"(id);

ALTER TABLE referral_record DROP CONSTRAINT IF EXISTS referral_record_referred_id_fkey;
ALTER TABLE referral_record ADD CONSTRAINT referral_record_referred_id_fkey 
    FOREIGN KEY (referred_id) REFERENCES "user"(id);

-- Show table counts
SELECT 'user table' as table_name, COUNT(*) as count FROM "user"
UNION ALL
SELECT 'users table' as table_name, COUNT(*) as count FROM users
UNION ALL
SELECT 'user_auth_details table' as table_name, COUNT(*) as count FROM user_auth_details;
"""

def fix_foreign_keys(db_name: str) -> bool:
    """Fix foreign key constraints in a specific database"""
    try:
        cmd = [
            'psql',
            '-h', DB_CONFIG['host'],
            '-U', DB_CONFIG['user'],
            '-d', db_name,
            '-c', FIX_FOREIGN_KEY_COMMANDS
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
        
        print_info(f"Foreign key fix results for {db_name}:")
        print(result.stdout)
        return True
        
    except subprocess.CalledProcessError as e:
        print_error(f"Foreign key fix failed for {db_name}: {e.stderr}")
        return False
    except Exception as e:
        print_error(f"Unexpected error fixing foreign keys for {db_name}: {e}")
        return False

def main():
    """Main execution function"""
    print("=" * 50)
    print("FIX FOREIGN KEY CONSTRAINTS")
    print("=" * 50)
    print()
    
    print("This script will fix foreign key constraints to point to the correct")
    print("'user' table instead of 'users' table in liconnects and website databases.")
    print()
    
    # Track results
    successful_fixes = []
    failed_fixes = []
    
    # Process each tenant database
    for db_name in TENANT_DATABASES:
        print(f"Processing database: {db_name}")
        print("-" * 40)
        
        # Fix foreign key constraints
        if fix_foreign_keys(db_name):
            print_status(f"Successfully fixed foreign keys for {db_name}")
            successful_fixes.append(db_name)
        else:
            print_error(f"Failed to fix foreign keys for {db_name}")
            failed_fixes.append(db_name)
        
        print()
    
    # Summary
    print("=" * 50)
    print("FOREIGN KEY FIX COMPLETED")
    print("=" * 50)
    
    if successful_fixes:
        print_status(f"Successfully fixed {len(successful_fixes)} databases:")
        for db in successful_fixes:
            print(f"  • {db}")
    
    if failed_fixes:
        print_error(f"Failed to fix {len(failed_fixes)} databases:")
        for db in failed_fixes:
            print(f"  • {db}")
    
    print()
    print("Next steps:")
    print("1. Run fix_missing_auth_details.py to create missing auth records")
    print("2. Restart the gunicorn application")
    print("3. Test user login")
    print()
    
    if failed_fixes:
        print_error("Some databases failed to fix. Please check the errors above.")
        sys.exit(1)
    else:
        print_status("Foreign key constraints fixed successfully!")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print_error("\nOperation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        sys.exit(1)
