#!/usr/bin/env python3
"""
Script to populate initial membership types for each tenant database.
Run this after the schema migration to set up default membership categories.
"""

import os
import sys
import logging
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from config import Config
from app.models import MembershipType
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

def seed_membership_types(tenant_id, db_url):
    """Seed membership types for a single tenant"""
    logger.info(f"Seeding membership types for tenant: {tenant_id}")
    
    # Default membership types for all tenants
    default_types = [
        {'name': 'Regular Member', 'description': 'Standard active member', 'sort_order': 1},
        {'name': 'Board Member', 'description': 'Board of directors member', 'sort_order': 2},
        {'name': 'Officer', 'description': 'Elected officer', 'sort_order': 3},
        {'name': 'Honorary Member', 'description': 'Honorary membership status', 'sort_order': 4},
        {'name': 'New Member', 'description': 'Recently joined member', 'sort_order': 5},
        {'name': 'Inactive', 'description': 'Inactive membership status', 'sort_order': 6},
    ]
    
    try:
        engine = create_engine(db_url)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        # Check if types already exist
        existing_count = session.query(MembershipType).count()
        if existing_count > 0:
            logger.info(f"✅ {tenant_id}: Already has {existing_count} membership types")
            session.close()
            return 0
        
        # Create membership types
        created_count = 0
        for type_data in default_types:
            membership_type = MembershipType(
                name=type_data['name'],
                description=type_data['description'],
                is_active=True,
                sort_order=type_data['sort_order'],
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            session.add(membership_type)
            created_count += 1
            logger.info(f"  Created: {type_data['name']}")
        
        session.commit()
        session.close()
        
        logger.info(f"✅ {tenant_id}: Created {created_count} membership types")
        return created_count
        
    except Exception as e:
        logger.error(f"❌ Failed to seed {tenant_id}: {str(e)}")
        if 'session' in locals():
            session.rollback()
            session.close()
        raise

def main():
    """Seed membership types for all tenants"""
    logger.info("=== SEEDING MEMBERSHIP TYPES ===")
    
    total_created = 0
    success_count = 0
    total_count = len(Config.TENANT_DATABASES)
    
    for tenant_id, db_url in Config.TENANT_DATABASES.items():
        try:
            created = seed_membership_types(tenant_id, db_url)
            total_created += created
            success_count += 1
        except Exception as e:
            logger.error(f"Failed to seed {tenant_id}: {str(e)}")
    
    logger.info(f"Seeding completed: {success_count}/{total_count} tenants successful")
    logger.info(f"Total membership types created: {total_created}")
    
    if success_count == total_count:
        logger.info("🎉 All membership types seeded successfully!")
        logger.info("\nDefault membership types available:")
        logger.info("- Regular Member, Board Member, Officer")
        logger.info("- Honorary Member, New Member, Inactive")
        return True
    else:
        logger.error("⚠️  Some seeding failed. Check logs above.")
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)