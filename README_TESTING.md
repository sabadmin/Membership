# Membership System Testing Guide

This guide provides instructions for testing the membership system fixes on the Linode server.

## Overview

The membership system had several issues that have been fixed:

1. **Syntax Error**: Fixed extra "a" character in models.py
2. **Import Errors**: Removed unused `Base` imports from all files
3. **Database Schema Issues**: Fixed table creation to use Flask-SQLAlchemy properly
4. **Missing Database Columns**: Added missing `password_hash` column to `user_auth_details` table

## Files Changed

### Core Application Files
- `app/models.py` - Fixed syntax error and removed unused imports
- `database.py` - Fixed table creation to use Flask-SQLAlchemy metadata
- `app/admin/routes.py` - Removed unused Base import

### Migration Scripts (Updated)
- `migrate_dues_schema.py` - Removed Base references
- `setup_dues_types.py` - Removed Base references  
- `migrate_address_schema.py` - Removed Base references
- `migrate_complete_schema.py` - Removed Base references

### New Testing Files
- `fix_database_schema.py` - **NEW** - Fixes database schema issues
- `test_application.py` - **NEW** - Tests application functionality
- `README_TESTING.md` - **NEW** - This testing guide

## Deployment Instructions

### Step 1: Pull Latest Changes from GitHub

On the Linode server, navigate to your application directory and pull the latest changes:

```bash
cd /var/www/member
git pull origin main
```

### Step 2: Stop the Application

Stop gunicorn if it's running:

```bash
sudo systemctl stop gunicorn
# OR if running manually:
# pkill -f gunicorn
```

### Step 3: Activate Virtual Environment

```bash
source venv/bin/activate
```

### Step 4: Run Database Schema Fix

This script will fix the database schema issues:

```bash
python3 fix_database_schema.py
```

Expected output:
```
=== DATABASE SCHEMA FIX SCRIPT ===
This script will fix database schema issues for the membership system
Run this after pulling the latest code changes to the testing server

==================================================
FIXING SCHEMA FOR TENANT: tenant1
==================================================
Checking user_auth_details table for tenant1...
Adding missing password_hash column...
✅ Added password_hash column
...
🎉 Database schema fix completed successfully!
```

### Step 5: Test the Application

Run the comprehensive test script:

```bash
python3 test_application.py
```

Expected output:
```
=== APPLICATION TESTING SCRIPT ===
This script will test the membership system functionality

==================================================
TESTING TENANT: liconnects
==================================================
Test 1: Database connectivity
✅ Database connection successful
Test 2: Table existence
✅ Table user exists
✅ Table user_auth_details exists
...
🎉 All application tests passed successfully!
```

### Step 6: Start the Application

Start gunicorn:

```bash
# If using systemd:
sudo systemctl start gunicorn

# OR manually:
gunicorn --bind 127.0.0.1:5000 'app:create_app()'
```

### Step 7: Verify Web Functionality

1. Open your browser and navigate to your application
2. Try to access the login page
3. Try to register a new user
4. Verify that the registration process works without the "password_hash column does not exist" error

## Troubleshooting

### If the schema fix script fails:

1. Check the database connection settings in `config.py`
2. Ensure PostgreSQL is running: `sudo systemctl status postgresql`
3. Check database permissions for the application user
4. Review the error logs for specific issues

### If the application still won't start:

1. Check the gunicorn logs: `journalctl -u gunicorn -f`
2. Verify all Python dependencies are installed: `pip install -r requirements.txt`
3. Check file permissions in the application directory
4. Ensure the virtual environment is activated

### If registration still fails:

1. Run the test script again to verify database schema
2. Check that all required tables exist in the database
3. Verify the `user_auth_details` table has the `password_hash` column:
   ```sql
   \d user_auth_details
   ```

## Testing Checklist

- [ ] Code pulled from GitHub successfully
- [ ] Virtual environment activated
- [ ] Database schema fix script ran without errors
- [ ] Application test script passed all tests
- [ ] Gunicorn starts without errors
- [ ] Web pages load correctly
- [ ] User registration works without database errors
- [ ] User login functionality works
- [ ] Admin panel accessible (if applicable)

## Common Issues and Solutions

### Issue: "cannot import name 'Base'"
**Solution**: This was fixed by removing unused Base imports. If you still see this, ensure you pulled the latest code.

### Issue: "relation 'user' does not exist"
**Solution**: Run the database schema fix script which handles table creation and naming issues.

### Issue: "column 'password_hash' does not exist"
**Solution**: The schema fix script adds this missing column. Ensure the script completed successfully.

### Issue: Application starts but pages show errors
**Solution**: Run the test script to identify specific issues with database connectivity or model relationships.

## Support

If you encounter issues not covered in this guide:

1. Check the application logs for specific error messages
2. Run the test script to identify the failing component
3. Verify database connectivity and permissions
4. Ensure all dependencies are properly installed

## Next Steps

After successful testing:

1. Monitor the application for any runtime errors
2. Test all major functionality (registration, login, member management, etc.)
3. Consider setting up automated testing for future deployments
4. Document any additional configuration needed for production deployment
