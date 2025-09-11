#!/usr/bin/env python3
"""
Fix Missing UserAuthDetails Records
Creates missing user_auth_details records for users who don't have them
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

# SQL commands to create missing auth_details records
FIX_AUTH_DETAILS_COMMANDS = """
-- Create missing user_auth_details records for users who don't have them
INSERT INTO user_auth_details (user_id, password_hash, is_active, last_login_1)
SELECT 
    u.id,
    NULL as password_hash,  -- Will need to be set when user logs in
    TRUE as is_active,
    NOW() as last_login_1
FROM "user" u
LEFT JOIN user_auth_details uad ON u.id = uad.user_id
WHERE uad.user_id IS NULL;

-- Show the results
SELECT 
    'Users without auth_details (before fix)' as status,
    COUNT(*) as count
FROM "user" u
LEFT JOIN user_auth_details uad ON u.id = uad.user_id
WHERE uad.user_id IS NULL

UNION ALL

SELECT 
    'Total users' as status,
    COUNT(*) as count
FROM "user"

UNION ALL

SELECT 
    'Total auth_details records' as status,
    COUNT(*) as count
FROM user_auth_details;
"""

def fix_auth_details(db_name: str) -> bool:
    """Create missing auth_details records in a specific database"""
    try:
        cmd = [
            'psql',
            '-h', DB_CONFIG['host'],
            '-U', DB_CONFIG['user'],
            '-d', db_name,
            '-c', FIX_AUTH_DETAILS_COMMANDS
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
        
        print_info(f"Auth details fix results for {db_name}:")
        print(result.stdout)
        return True
        
    except subprocess.CalledProcessError as e:
        print_error(f"Auth details fix failed for {db_name}: {e.stderr}")
        return False
    except Exception as e:
        print_error(f"Unexpected error fixing auth details for {db_name}: {e}")
        return False

def main():
    """Main execution function"""
    print("=" * 50)
    print("FIX MISSING USER AUTH DETAILS")
    print("=" * 50)
    print()
    
    print("This script will create missing user_auth_details records")
    print("for users who don't have them in liconnects and website databases.")
    print()
    
    # Track results
    successful_fixes = []
    failed_fixes = []
    
    # Process each tenant database
    for db_name in TENANT_DATABASES:
        print(f"Processing database: {db_name}")
        print("-" * 40)
        
        # Fix missing auth details
        if fix_auth_details(db_name):
            print_status(f"Successfully fixed auth details for {db_name}")
            successful_fixes.append(db_name)
        else:
            print_error(f"Failed to fix auth details for {db_name}")
            failed_fixes.append(db_name)
        
        print()
    
    # Summary
    print("=" * 50)
    print("AUTH DETAILS FIX COMPLETED")
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
    print("1. Restart the gunicorn application")
    print("2. Test user login (users will need to reset passwords)")
    print("3. Verify that login works without internal server errors")
    print()
    
    if failed_fixes:
        print_error("Some databases failed to fix. Please check the errors above.")
        sys.exit(1)
    else:
        print_status("Auth details fix completed successfully!")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print_error("\nOperation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        sys.exit(1)
