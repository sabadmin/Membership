#!/usr/bin/env python3
"""
Debug script to test membership system startup without running the full server.
Use this to validate fixes before deploying to Linode.
"""

import os
import sys
import logging
from dotenv import load_dotenv

# Set up comprehensive logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('startup_debug.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def test_imports():
    """Test all critical imports"""
    logger.info("=== TESTING IMPORTS ===")
    try:
        logger.info("Testing config import...")
        from config import Config
        logger.info(f"✅ Config loaded - {len(Config.TENANT_DATABASES)} tenants configured")
        
        logger.info("Testing database import...")
        from database import db, get_tenant_db_session, init_db_for_tenant
        logger.info("✅ Database modules imported successfully")
        
        logger.info("Testing models import...")
        from app.models import User, UserAuthDetails, AttendanceRecord, DuesRecord, ReferralRecord
        logger.info("✅ All models imported successfully")
        
        logger.info("Testing blueprint imports...")
        from app.auth.routes import auth_bp
        from app.members.routes import members_bp
        from app.admin.routes import admin_bp
        logger.info("✅ All blueprints imported successfully")
        
        return True
    except Exception as e:
        logger.error(f"❌ Import failed: {str(e)}")
        logger.error(f"Error type: {type(e).__name__}")
        return False

def test_app_creation():
    """Test Flask app creation"""
    logger.info("=== TESTING APP CREATION ===")
    try:
        from app import create_app
        logger.info("Creating Flask app...")
        app = create_app()
        logger.info("✅ Flask app created successfully")
        
        with app.app_context():
            logger.info("✅ App context works")
            
        return True
    except Exception as e:
        logger.error(f"❌ App creation failed: {str(e)}")
        logger.error(f"Error type: {type(e).__name__}")
        return False

def main():
    logger.info("Starting Membership System Startup Debug")
    load_dotenv()
    
    # Test imports first
    if not test_imports():
        logger.error("Import test failed - cannot proceed")
        return False
        
    # Test app creation
    if not test_app_creation():
        logger.error("App creation test failed")
        return False
        
    logger.info("🎉 All startup tests passed! App should work with gunicorn.")
    return True

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)