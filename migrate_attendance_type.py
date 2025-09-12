#!/usr/bin/env python3
"""
Database migration script to add AttendanceType table and update AttendanceRecord table
"""

import subprocess
import sys
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
                print(f"  Output: {result.stdout.strip()}")
            return True
        else:
            print(f"✗ Error executing SQL on {database_name}: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"✗ Exception executing SQL on {database_name}: {str(e)}")
        return False

def migrate_database(database_name):
    """Migrate a single database"""
    print(f"\n--- Migrating {database_name} ---")
    
    # Step 1: Create AttendanceType table
    create_attendance_type_sql = """
    CREATE TABLE IF NOT EXISTS attendance_type (
        id SERIAL PRIMARY KEY,
        type VARCHAR(64) NOT NULL,
        description TEXT,
        is_active BOOLEAN DEFAULT TRUE,
        sort_order INTEGER DEFAULT 0
    );
    """
    
    if not run_sql_command(database_name, create_attendance_type_sql):
        return False
    
    # Step 2: Insert default attendance types
    insert_default_types_sql = """
    INSERT INTO attendance_type (type, description, sort_order) 
    VALUES 
        ('Meeting', 'Regular membership meeting', 1),
        ('Training', 'Training session or workshop', 2),
        ('Event', 'Special event or gathering', 3),
        ('Conference', 'Conference or seminar', 4)
    ON CONFLICT DO NOTHING;
    """
    
    if not run_sql_command(database_name, insert_default_types_sql):
        return False
    
    # Step 3: Add attendance_type_id column to attendance_record if it doesn't exist
    add_column_sql = """
    ALTER TABLE attendance_record 
    ADD COLUMN IF NOT EXISTS attendance_type_id INTEGER;
    """
    
    if not run_sql_command(database_name, add_column_sql):
        return False
    
    # Step 4: Set default attendance_type_id for existing records (use 'Meeting' type)
    update_existing_records_sql = """
    UPDATE attendance_record 
    SET attendance_type_id = (SELECT id FROM attendance_type WHERE type = 'Meeting' LIMIT 1)
    WHERE attendance_type_id IS NULL;
    """
    
    if not run_sql_command(database_name, update_existing_records_sql):
        return False
    
    # Step 5: Add foreign key constraint
    add_foreign_key_sql = """
    ALTER TABLE attendance_record 
    ADD CONSTRAINT IF NOT EXISTS fk_attendance_record_attendance_type 
    FOREIGN KEY (attendance_type_id) REFERENCES attendance_type(id);
    """
    
    if not run_sql_command(database_name, add_foreign_key_sql):
        return False
    
    # Step 6: Make attendance_type_id NOT NULL after setting defaults
    make_not_null_sql = """
    ALTER TABLE attendance_record 
    ALTER COLUMN attendance_type_id SET NOT NULL;
    """
    
    if not run_sql_command(database_name, make_not_null_sql):
        return False
    
    print(f"✓ Successfully migrated {database_name}")
    return True

def main():
    """Main migration function"""
    print("Starting AttendanceType migration for all tenant databases...")
    
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
        return 0
    else:
        print("✗ Some databases failed to migrate. Please check the errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
