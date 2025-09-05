#!/usr/bin/env python3
"""
Script to create missing UserAuthDetails records for existing users.
This fixes the "Account is inactive" error for users who existed before the auth details system.
"""

import os
import sys
import logging
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from config import Config
from app.models import User, UserAuthDetails
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

def fix_tenant_auth_details(tenant_id, db_url):
    """Fix missing auth details for a single tenant"""
    logger.info(f"Checking tenant: {tenant_id}")
    
    try:
        engine = create_engine(db_url)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        # Find users without auth details
        users_without_auth = session.query(User).filter(
            ~User.id.in_(session.query(UserAuthDetails.user_id))
        ).all()
        
        if not users_without_auth:
            logger.info(f"✅ {tenant_id}: All users have auth details")
            session.close()
            return 0
            
        logger.info(f"Found {len(users_without_auth)} users without auth details in {tenant_id}")
        
        # Create missing auth details
        created_count = 0
        for user in users_without_auth:
            auth_details = UserAuthDetails(
                user_id=user.id,
                tenant_id=user.tenant_id,
                is_active=True,  # Default to active for existing users
                last_login_1=None  # Will be set on first login
            )
            session.add(auth_details)
            created_count += 1
            logger.info(f"  Created auth details for user: {user.email}")
        
        session.commit()
        session.close()
        
        logger.info(f"✅ {tenant_id}: Created {created_count} auth detail records")
        return created_count
        
    except Exception as e:
        logger.error(f"❌ Failed to fix {tenant_id}: {str(e)}")
        if 'session' in locals():
            session.rollback()
            session.close()
        raise

def main():
    """Fix missing auth details for all tenants"""
    logger.info("=== FIXING MISSING USER AUTH DETAILS ===")
    
    total_created = 0
    success_count = 0
    total_count = len(Config.TENANT_DATABASES)
    
    for tenant_id, db_url in Config.TENANT_DATABASES.items():
        try:
            created = fix_tenant_auth_details(tenant_id, db_url)
            total_created += created
            success_count += 1
        except Exception as e:
            logger.error(f"Failed to fix {tenant_id}: {str(e)}")
    
    logger.info(f"Fix completed: {success_count}/{total_count} tenants successful")
    logger.info(f"Total auth details created: {total_created}")
    
    if success_count == total_count:
        logger.info("🎉 All missing auth details fixed successfully!")
        return True
    else:
        logger.error("⚠️  Some fixes failed. Check logs above.")
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)