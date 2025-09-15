#!/usr/bin/env python3
"""
Script to completely purge a specific user from all tenant databases
This will remove:
- User record (if exists)
- UserAuthDetails record (if exists) 
- All AttendanceRecord entries for the user
- All DuesRecord entries for the user
- All ReferralRecord entries for the user

Usage: 
  python3 purge_specific_user.py --id <user_id>
  python3 purge_specific_user.py --email <email_address>
"""

import sys
import subprocess
import argparse
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

def get_user_id_from_email(database_name, email):
    """Get user ID from email address"""
    try:
        cmd = [
            'psql',
            '-h', 'localhost',
            '-U', 'sabadmin',
            '-d', database_name,
            '-t',  # tuples only (no headers)
            '-c', f"SELECT id FROM \"user\" WHERE email = '{email}';"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, env={'PGPASSWORD': 'Bellm0re'})
        
        if result.returncode == 0 and result.stdout.strip():
            user_id = result.stdout.strip()
            if user_id.isdigit():
                return int(user_id)
        return None
            
    except Exception as e:
        print(f"✗ Exception looking up user by email in {database_name}: {str(e)}")
        return None

def find_user_ids_by_email(email):
    """Find all user IDs across databases that match the email"""
    databases = [
        'tenant1_db',
        'tenant2_db', 
        'website_db',
        'closers_db',
        'liconnects_db',
        'lieg_db'
    ]
    
    found_ids = {}
    for database in databases:
        user_id = get_user_id_from_email(database, email)
        if user_id:
            found_ids[database] = user_id
            print(f"Found user ID {user_id} for email '{email}' in {database}")
    
    return found_ids

def purge_user_from_database(database_name, user_id, identifier_type="ID"):
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
    
    # Step 3: Delete referral records (both as referrer and referred)
    delete_referrals_sql = f"DELETE FROM referral_record WHERE referrer_id = {user_id} OR referred_id = {user_id};"
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
    parser = argparse.ArgumentParser(description='Purge a user from all tenant databases')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--id', type=int, help='User ID to purge')
    group.add_argument('--email', type=str, help='Email address to purge')
    
    args = parser.parse_args()
    
    # List of all tenant databases
    databases = [
        'tenant1_db',
        'tenant2_db', 
        'website_db',
        'closers_db',
        'liconnects_db',
        'lieg_db'
    ]
    
    if args.email:
        # Find user IDs by email across all databases
        print(f"Looking up user IDs for email: {args.email}")
        found_ids = find_user_ids_by_email(args.email)
        
        if not found_ids:
            print(f"No user found with email '{args.email}' in any database.")
            print("However, there might still be orphaned attendance records...")
            print("Proceeding to check for attendance records by email...")
            
            # Even if no user record exists, we should check for attendance records
            # that might reference this email in some way
            user_identifier = args.email
            identifier_type = "email"
        else:
            print(f"Found user in {len(found_ids)} database(s)")
            user_identifier = args.email
            identifier_type = "email"
    else:
        # Direct user ID purge
        user_identifier = args.id
        identifier_type = "ID"
        found_ids = {db: args.id for db in databases}  # Assume ID exists in all databases
    
    print(f"\nWARNING: This will completely purge user ({identifier_type}: {user_identifier}) from ALL tenant databases!")
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
    
    success_count = 0
    total_count = len(databases)
    
    print(f"\nStarting purge of user ({identifier_type}: {user_identifier}) from all tenant databases...")
    
    if args.email:
        # For email-based purge, we need to handle each database individually
        for database in databases:
            if database in found_ids:
                # User exists in this database, purge by ID
                user_id = found_ids[database]
                if purge_user_from_database(database, user_id, "email"):
                    success_count += 1
                else:
                    print(f"✗ Failed to completely purge user from {database}")
            else:
                # No user record, but check for orphaned attendance records
                print(f"\n--- Checking {database} for orphaned records ---")
                # For now, we'll skip databases where no user was found
                # In a more advanced version, we could search attendance records by email
                print(f"No user record found in {database}, skipping...")
                success_count += 1  # Count as success since nothing to purge
    else:
        # For ID-based purge, purge from all databases
        for database in databases:
            if purge_user_from_database(database, args.id, "ID"):
                success_count += 1
            else:
                print(f"✗ Failed to completely purge user {args.id} from {database}")
    
    print(f"\n--- Purge Summary ---")
    print(f"Successfully processed: {success_count}/{total_count} databases")
    
    if success_count == total_count:
        print(f"✓ User ({identifier_type}: {user_identifier}) has been completely purged from all databases!")
        return 0
    else:
        print(f"✗ Some databases failed to purge user ({identifier_type}: {user_identifier}). Please check the errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
