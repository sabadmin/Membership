#!/usr/bin/env python3
"""
Database migration script to remove the event_name column from attendance_record table
since we now use attendance_type_id to reference the attendance_type table
"""

import subprocess
import sys

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
                print(f"  Output: {result.stdout.strip()}")
            return True
        else:
            print(f"✗ Error executing SQL on {database_name}: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"✗ Exception executing SQL on {database_name}: {str(e)}")
        return False

def migrate_database(database_name):
    """Remove event_name column from a single database"""
    print(f"\n--- Removing event_name column from {database_name} ---")
    
    # Remove the event_name column since we now use attendance_type_id
    remove_event_name_sql = """
    ALTER TABLE attendance_record 
    DROP COLUMN IF EXISTS event_name;
    """
    
    if not run_sql_command(database_name, remove_event_name_sql):
        return False
    
    print(f"✓ Successfully removed event_name column from {database_name}")
    return True

def main():
    """Main migration function"""
    print("Removing event_name column from attendance_record table in all tenant databases...")
    
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
    
    for database in databases:
        if migrate_database(database):
            success_count += 1
        else:
            print(f"✗ Failed to migrate {database}")
    
    print(f"\n--- Migration Summary ---")
    print(f"Successfully migrated: {success_count}/{total_count} databases")
    
    if success_count == total_count:
        print("✓ All databases migrated successfully!")
        print("The event_name column has been removed from attendance_record table.")
        print("Attendance records now use attendance_type_id to reference the attendance_type table.")
        return 0
    else:
        print("✗ Some databases failed to migrate. Please check the errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
