#!/usr/bin/env python3
"""
Reset User Passwords
Sets specific passwords for users in the membership system
"""

import subprocess
import sys
import os
from werkzeug.security import generate_password_hash

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

# Users to reset passwords for
USERS_TO_RESET = [
    {
        'email': 'jo@fdm.com',
        'password': 'Bellm0re',
        'database': 'liconnects_db'
    },
    {
        'email': 'saburstyn@unfrustratingcomputers.com',
        'password': 'Bellm0re',
        'database': 'website_db'
    }
]

def reset_user_password(email: str, password: str, db_name: str) -> bool:
    """Reset password for a specific user"""
    try:
        # Generate password hash
        password_hash = generate_password_hash(password)
        
        # SQL to update the password
        sql_command = f"""
        UPDATE user_auth_details 
        SET password_hash = '{password_hash}'
        WHERE user_id = (
            SELECT id FROM "user" WHERE email = '{email}'
        );
        
        -- Show the result
        SELECT 
            u.email,
            CASE 
                WHEN uad.password_hash IS NOT NULL THEN 'Password Set'
                ELSE 'No Password'
            END as password_status
        FROM "user" u
        LEFT JOIN user_auth_details uad ON u.id = uad.user_id
        WHERE u.email = '{email}';
        """
        
        cmd = [
            'psql',
            '-h', DB_CONFIG['host'],
            '-U', DB_CONFIG['user'],
            '-d', db_name,
            '-c', sql_command
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
        
        print_info(f"Password reset results for {email} in {db_name}:")
        print(result.stdout)
        return True
        
    except subprocess.CalledProcessError as e:
        print_error(f"Password reset failed for {email} in {db_name}: {e.stderr}")
        return False
    except Exception as e:
        print_error(f"Unexpected error resetting password for {email}: {e}")
        return False

def main():
    """Main execution function"""
    print("=" * 50)
    print("RESET USER PASSWORDS")
    print("=" * 50)
    print()
    
    print("This script will reset passwords for specific users:")
    for user in USERS_TO_RESET:
        print(f"  • {user['email']} in {user['database']}")
    print()
    
    # Track results
    successful_resets = []
    failed_resets = []
    
    # Process each user
    for user in USERS_TO_RESET:
        email = user['email']
        password = user['password']
        database = user['database']
        
        print(f"Resetting password for: {email}")
        print("-" * 40)
        
        # Reset the password
        if reset_user_password(email, password, database):
            print_status(f"Successfully reset password for {email}")
            successful_resets.append(email)
        else:
            print_error(f"Failed to reset password for {email}")
            failed_resets.append(email)
        
        print()
    
    # Summary
    print("=" * 50)
    print("PASSWORD RESET COMPLETED")
    print("=" * 50)
    
    if successful_resets:
        print_status(f"Successfully reset {len(successful_resets)} passwords:")
        for email in successful_resets:
            print(f"  • {email}")
    
    if failed_resets:
        print_error(f"Failed to reset {len(failed_resets)} passwords:")
        for email in failed_resets:
            print(f"  • {email}")
    
    print()
    print("Next steps:")
    print("1. Test user login with the new passwords")
    print("2. Users can now log in with password: Bellm0re")
    print()
    
    if failed_resets:
        print_error("Some password resets failed. Please check the errors above.")
        sys.exit(1)
    else:
        print_status("All password resets completed successfully!")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print_error("\nOperation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        sys.exit(1)
