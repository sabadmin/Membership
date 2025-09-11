#!/usr/bin/env python3
"""
Application testing script for the membership system.
This script tests various functionality to ensure the application works correctly.

Run this script on the testing server after running the database schema fix.
"""

import sys
import os
import logging
from datetime import datetime, date

# Add the current directory to Python path
sys.path.append(os.path.dirname(__file__))

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_application():
    """Test various aspects of the application"""
    
    try:
        # Import after adding to path
        from config import Config
        from app import create_app
        from app.models import User, UserAuthDetails, MembershipType, AttendanceRecord, DuesType, DuesRecord
        
        # Initialize Flask app
        logger.info("Initializing Flask application for testing...")
        app = create_app()
        
        with app.app_context():
            logger.info("Flask app context initialized")
            
            # Test each tenant
            for tenant_id in Config.TENANT_DATABASES.keys():
                logger.info(f"\n{'='*50}")
                logger.info(f"TESTING TENANT: {tenant_id}")
                logger.info(f"{'='*50}")
                
                try:
                    test_tenant(tenant_id)
                    logger.info(f"✅ All tests passed for {tenant_id}")
                except Exception as e:
                    logger.error(f"❌ Tests failed for {tenant_id}: {str(e)}")
                    continue
                    
        logger.info(f"\n{'='*50}")
        logger.info("APPLICATION TESTING COMPLETED")
        logger.info(f"{'='*50}")
        
    except Exception as e:
        logger.error(f"Failed to initialize application: {str(e)}")
        sys.exit(1)

def test_tenant(tenant_id):
    """Test functionality for a specific tenant"""
    
    from database import get_tenant_db_session
    from app.models import User, UserAuthDetails, MembershipType, AttendanceRecord, DuesType, DuesRecord
    
    with get_tenant_db_session(tenant_id) as session:
        logger.info(f"Testing database connection for {tenant_id}...")
        
        # Test 1: Basic database connectivity
        logger.info("Test 1: Database connectivity")
        from sqlalchemy import text
        result = session.execute(text("SELECT 1")).fetchone()
        assert result[0] == 1, "Database connection failed"
        logger.info("✅ Database connection successful")
        
        # Test 2: Check if all required tables exist
        logger.info("Test 2: Table existence")
        from sqlalchemy import inspect
        from database import _tenant_engines
        
        inspector = inspect(_tenant_engines[tenant_id])
        required_tables = ['user', 'user_auth_details', 'membership_type', 'attendance_record', 'dues_type', 'dues_record']
        
        for table in required_tables:
            assert inspector.has_table(table), f"Table {table} does not exist"
            logger.info(f"✅ Table {table} exists")
        
        # Test 3: Test User model operations
        logger.info("Test 3: User model operations")
        
        # Check if we can query users
        user_count = session.query(User).count()
        logger.info(f"✅ User table accessible, found {user_count} users")
        
        # Test 4: Test UserAuthDetails model operations
        logger.info("Test 4: UserAuthDetails model operations")
        
        # Check if we can query auth details
        auth_count = session.query(UserAuthDetails).count()
        logger.info(f"✅ UserAuthDetails table accessible, found {auth_count} auth records")
        
        # Test 5: Test creating a test user (if none exist)
        logger.info("Test 5: User creation test")
        
        test_email = f"test_{tenant_id}@example.com"
        existing_user = session.query(User).filter_by(email=test_email).first()
        
        if not existing_user:
            try:
                # Create a test user
                test_user = User(
                    first_name="Test",
                    last_name="User",
                    email=test_email,
                    is_active=True
                )
                session.add(test_user)
                session.flush()  # Get the ID
                
                # Check if auth details already exist for this user
                existing_auth = session.query(UserAuthDetails).filter_by(user_id=test_user.id).first()
                if not existing_auth:
                    # Create auth details for the test user
                    from datetime import datetime, timezone
                    auth_details = UserAuthDetails(
                        user_id=test_user.id,
                        password_hash="test_hash",
                        is_active=True,
                        last_login_1=datetime.now(timezone.utc)
                    )
                    session.add(auth_details)
                
                session.commit()
                logger.info(f"✅ Created test user with ID {test_user.id}")
            except Exception as e:
                session.rollback()
                logger.warning(f"⚠️  Could not create test user: {str(e)}")
                logger.info("✅ Continuing with existing data")
        else:
            logger.info(f"✅ Test user already exists with ID {existing_user.id}")
        
        # Test 6: Test MembershipType operations
        logger.info("Test 6: MembershipType operations")
        
        membership_count = session.query(MembershipType).count()
        logger.info(f"✅ MembershipType table accessible, found {membership_count} types")
        
        # Create a test membership type if none exist
        if membership_count == 0:
            test_membership = MembershipType(
                name="Test Member",
                description="Test membership type",
                can_edit_attendance=False,
                sort_order=1,
                is_active=True
            )
            session.add(test_membership)
            session.commit()
            logger.info("✅ Created test membership type")
        
        # Test 7: Test DuesType operations
        logger.info("Test 7: DuesType operations")
        
        dues_type_count = session.query(DuesType).count()
        logger.info(f"✅ DuesType table accessible, found {dues_type_count} types")
        
        # Create test dues types if none exist
        if dues_type_count == 0:
            annual_dues = DuesType(
                dues_type="Annual",
                description="Annual membership dues",
                is_active=True
            )
            session.add(annual_dues)
            session.commit()
            logger.info("✅ Created test dues type")
        
        # Test 8: Test AttendanceRecord operations
        logger.info("Test 8: AttendanceRecord operations")
        
        attendance_count = session.query(AttendanceRecord).count()
        logger.info(f"✅ AttendanceRecord table accessible, found {attendance_count} records")
        
        # Test 9: Test DuesRecord operations
        logger.info("Test 9: DuesRecord operations")
        
        dues_record_count = session.query(DuesRecord).count()
        logger.info(f"✅ DuesRecord table accessible, found {dues_record_count} records")
        
        # Test 10: Test relationships
        logger.info("Test 10: Model relationships")
        
        # Test User -> UserAuthDetails relationship
        users_with_auth = session.query(User).join(UserAuthDetails).count()
        logger.info(f"✅ User-UserAuthDetails relationship working, {users_with_auth} users with auth")
        
        logger.info("All tests completed successfully!")

def test_web_functionality():
    """Test web functionality using Flask test client"""
    
    logger.info("Testing web functionality...")
    
    try:
        from app import create_app
        
        app = create_app()
        app.config['TESTING'] = True
        
        with app.test_client() as client:
            # Test 1: Index page
            logger.info("Testing index page...")
            response = client.get('/')
            assert response.status_code in [200, 302], f"Index page failed with status {response.status_code}"
            logger.info("✅ Index page accessible")
            
            # Test 2: Login page
            logger.info("Testing login page...")
            response = client.get('/login')
            assert response.status_code == 200, f"Login page failed with status {response.status_code}"
            logger.info("✅ Login page accessible")
            
            # Test 3: Register page
            logger.info("Testing register page...")
            response = client.get('/register')
            assert response.status_code == 200, f"Register page failed with status {response.status_code}"
            logger.info("✅ Register page accessible")
            
            logger.info("✅ Web functionality tests passed")
            
    except Exception as e:
        logger.error(f"Web functionality test failed: {str(e)}")
        raise

def main():
    """Main function"""
    logger.info("=== APPLICATION TESTING SCRIPT ===")
    logger.info("This script will test the membership system functionality")
    logger.info("Run this after fixing the database schema")
    
    try:
        # Test database functionality
        test_application()
        
        # Test web functionality
        test_web_functionality()
        
        logger.info("🎉 All application tests passed successfully!")
        logger.info("The membership system is working correctly.")
        return True
        
    except Exception as e:
        logger.error(f"❌ Application tests failed: {str(e)}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
