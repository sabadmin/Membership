#!/usr/bin/env python3
"""
Script to completely purge a specific user from all tenant databases
This will remove:
- User record (if exists)
- UserAuthDetails record (if exists) 
- All AttendanceRecord entries for the user
- All DuesRecord entries for the user
- All ReferralRecord entries for the user

Usage: python3 purge_specific_user.py <user_id>
"""

import sys
import subprocess
from config import Config

def run_sql_command(database_name, sql_command):
    """Execute SQL command on specified database"""
    try:
        # Use psql to execute the SQL command
        cmd = [
            'psql',
            '-h', 'localhost',
            '-U', 'sabadmin',
            '-d', database_name,
            '-c', sql_command
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, env={'PGPASSWORD': 'Bellm0re'})
        
        if result.returncode == 0:
            print(f"✓ Successfully executed SQL on {database_name}")
            if result.stdout.strip():
                # Parse the output to show affected rows
                lines = result.stdout.strip().split('\n')
                for line in lines:
                    if 'DELETE' in line and line.strip():
                        print(f"  {line.strip()}")
            return True
        else:
            print(f"✗ Error executing SQL on {database_name}: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"✗ Exception executing SQL on {database_name}: {str(e)}")
        return False

def purge_user_from_database(database_name, user_id):
    """Purge user from a single database"""
    print(f"\n--- Purging user {user_id} from {database_name} ---")
    
    success = True
    
    # Step 1: Delete attendance records
    delete_attendance_sql = f"DELETE FROM attendance_record WHERE user_id = {user_id};"
    if not run_sql_command(database_name, delete_attendance_sql):
        success = False
    
    # Step 2: Delete dues records
    delete_dues_sql = f"DELETE FROM dues_record WHERE member_id = {user_id};"
    if not run_sql_command(database_name, delete_dues_sql):
        success = False
    
    # Step 3: Delete referral records (both as referrer and referee)
    delete_referrals_sql = f"DELETE FROM referral_record WHERE referrer_id = {user_id} OR referee_id = {user_id};"
    if not run_sql_command(database_name, delete_referrals_sql):
        success = False
    
    # Step 4: Delete user auth details (if exists)
    delete_auth_sql = f"DELETE FROM user_auth_details WHERE user_id = {user_id};"
    if not run_sql_command(database_name, delete_auth_sql):
        success = False
    
    # Step 5: Delete user record (if exists)
    delete_user_sql = f"DELETE FROM \"user\" WHERE id = {user_id};"
    if not run_sql_command(database_name, delete_user_sql):
        success = False
    
    if success:
        print(f"✓ Successfully purged user {user_id} from {database_name}")
    else:
        print(f"✗ Some operations failed for user {user_id} in {database_name}")
    
    return success

def main():
    """Main purge function"""
    if len(sys.argv) != 2:
        print("Usage: python3 purge_specific_user.py <user_id>")
        print("Example: python3 purge_specific_user.py 123")
        return 1
    
    try:
        user_id = int(sys.argv[1])
    except ValueError:
        print("Error: user_id must be a valid integer")
        return 1
    
    print(f"WARNING: This will completely purge user {user_id} from ALL tenant databases!")
    print("This includes:")
    print("- User record")
    print("- User authentication details")
    print("- All attendance records")
    print("- All dues records")
    print("- All referral records")
    print()
    
    confirm = input("Are you sure you want to proceed? Type 'YES' to confirm: ")
    if confirm != 'YES':
        print("Operation cancelled.")
        return 0
    
    # List of all tenant databases
    databases = [
        'tenant1_db',
        'tenant2_db', 
        'website_db',
        'closers_db',
        'liconnects_db',
        'lieg_db'
    ]
    
    success_count = 0
    total_count = len(databases)
    
    print(f"\nStarting purge of user {user_id} from all tenant databases...")
    
    for database in databases:
        if purge_user_from_database(database, user_id):
            success_count += 1
        else:
            print(f"✗ Failed to completely purge user {user_id} from {database}")
    
    print(f"\n--- Purge Summary ---")
    print(f"Successfully processed: {success_count}/{total_count} databases")
    
    if success_count == total_count:
        print(f"✓ User {user_id} has been completely purged from all databases!")
        return 0
    else:
        print(f"✗ Some databases failed to purge user {user_id}. Please check the errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
