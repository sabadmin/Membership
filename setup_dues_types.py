#!/usr/bin/env python3
"""
Setup script for dues types table
This script creates the initial dues types: Annual, Quarterly, Assessment
"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

from database import get_tenant_db_session, _tenant_engines
from app.models import DuesType
from config import Config
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def setup_dues_types():
    """Setup initial dues types for all tenants"""
    
    # Initial dues types to create
    initial_types = [
        {'name': 'Annual', 'description': 'Annual membership dues', 'sort_order': 1},
        {'name': 'Quarterly', 'description': 'Quarterly membership dues', 'sort_order': 2},
        {'name': 'Assessment', 'description': 'Special assessment dues', 'sort_order': 3},
    ]
    
    for tenant_id in Config.TENANT_DATABASES.keys():
        try:
            logger.info(f"Setting up dues types for tenant: {tenant_id}")
            
            # Ensure tables exist
            engine = _tenant_engines[tenant_id]
            # Tables should already be created by the app initialization
            logger.info(f"Using existing tables for tenant: {tenant_id}")
            
            with get_tenant_db_session(tenant_id) as session:
                # Check if dues types already exist
                existing_count = session.query(DuesType).count()
                if existing_count > 0:
                    logger.info(f"Dues types already exist for {tenant_id} ({existing_count} found)")
                    continue
                
                # Create initial dues types
                for type_data in initial_types:
                    dues_type = DuesType(**type_data)
                    session.add(dues_type)
                    logger.info(f"Created dues type: {type_data['name']} for {tenant_id}")
                
                session.commit()
                logger.info(f"Successfully set up dues types for {tenant_id}")
                
        except Exception as e:
            logger.error(f"Error setting up dues types for {tenant_id}: {str(e)}")
            continue

if __name__ == "__main__":
    logger.info("Starting dues types setup...")
    setup_dues_types()
    logger.info("Dues types setup completed!")
