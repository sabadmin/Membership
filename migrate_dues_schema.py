#!/usr/bin/env python3
"""
Migration script to update dues_records schema
This script migrates from dues_type (string) to dues_type_id (foreign key)
"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

from database import get_tenant_db_session, _tenant_engines
from app.models import DuesType, DuesRecord, Base
from config import Config
from sqlalchemy import text, inspect
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate_dues_schema():
    """Migrate dues_records schema for all tenants"""
    
    for tenant_id in Config.TENANT_DATABASES.keys():
        try:
            logger.info(f"Migrating dues schema for tenant: {tenant_id}")
            
            # Ensure tables exist
            engine = _tenant_engines[tenant_id]
            Base.metadata.create_all(engine)
            
            # Check if migration is needed
            inspector = inspect(engine)
            dues_records_columns = [col['name'] for col in inspector.get_columns('dues_records')]
            
            if 'dues_type_id' in dues_records_columns:
                logger.info(f"Migration already completed for {tenant_id}")
                continue
                
            if 'dues_type' not in dues_records_columns:
                logger.info(f"No dues_type column found in {tenant_id}, skipping migration")
                continue
            
            with get_tenant_db_session(tenant_id) as session:
                logger.info(f"Starting schema migration for {tenant_id}")
                
                # Step 1: Add the new dues_type_id column
                session.execute(text("""
                    ALTER TABLE dues_records 
                    ADD COLUMN dues_type_id INTEGER;
                """))
                logger.info(f"Added dues_type_id column for {tenant_id}")
                
                # Step 2: Ensure dues types exist
                annual_type = session.query(DuesType).filter_by(name='Annual').first()
                if not annual_type:
                    annual_type = DuesType(name='Annual', description='Annual membership dues', sort_order=1)
                    session.add(annual_type)
                    session.flush()
                
                quarterly_type = session.query(DuesType).filter_by(name='Quarterly').first()
                if not quarterly_type:
                    quarterly_type = DuesType(name='Quarterly', description='Quarterly membership dues', sort_order=2)
                    session.add(quarterly_type)
                    session.flush()
                
                assessment_type = session.query(DuesType).filter_by(name='Assessment').first()
                if not assessment_type:
                    assessment_type = DuesType(name='Assessment', description='Special assessment dues', sort_order=3)
                    session.add(assessment_type)
                    session.flush()
                
                # Step 3: Map old dues_type values to new dues_type_id
                # Update existing records based on their dues_type string value
                session.execute(text("""
                    UPDATE dues_records 
                    SET dues_type_id = :annual_id 
                    WHERE dues_type = 'A' OR dues_type = 'Annual'
                """), {'annual_id': annual_type.id})
                
                session.execute(text("""
                    UPDATE dues_records 
                    SET dues_type_id = :quarterly_id 
                    WHERE dues_type = 'Q' OR dues_type = 'Quarterly'
                """), {'quarterly_id': quarterly_type.id})
                
                session.execute(text("""
                    UPDATE dues_records 
                    SET dues_type_id = :assessment_id 
                    WHERE dues_type = 'F' OR dues_type = 'Assessment'
                """), {'assessment_id': assessment_type.id})
                
                # Set any remaining NULL values to Annual (default)
                session.execute(text("""
                    UPDATE dues_records 
                    SET dues_type_id = :annual_id 
                    WHERE dues_type_id IS NULL
                """), {'annual_id': annual_type.id})
                
                logger.info(f"Updated dues_type mappings for {tenant_id}")
                
                # Step 4: Make dues_type_id NOT NULL and add foreign key constraint
                session.execute(text("""
                    ALTER TABLE dues_records 
                    ALTER COLUMN dues_type_id SET NOT NULL;
                """))
                
                session.execute(text("""
                    ALTER TABLE dues_records 
                    ADD CONSTRAINT fk_dues_records_dues_type_id 
                    FOREIGN KEY (dues_type_id) REFERENCES dues_types(id);
                """))
                logger.info(f"Added foreign key constraint for {tenant_id}")
                
                # Step 5: Drop the old dues_type column
                session.execute(text("""
                    ALTER TABLE dues_records 
                    DROP COLUMN dues_type;
                """))
                logger.info(f"Dropped old dues_type column for {tenant_id}")
                
                # Step 6: Update amount columns to use DECIMAL if they're still strings
                try:
                    session.execute(text("""
                        ALTER TABLE dues_records 
                        ALTER COLUMN amount_due TYPE DECIMAL(10,2) USING amount_due::DECIMAL(10,2);
                    """))
                    session.execute(text("""
                        ALTER TABLE dues_records 
                        ALTER COLUMN amount_paid TYPE DECIMAL(10,2) USING amount_paid::DECIMAL(10,2);
                    """))
                    logger.info(f"Updated amount columns to DECIMAL for {tenant_id}")
                except Exception as e:
                    logger.warning(f"Amount columns may already be DECIMAL for {tenant_id}: {e}")
                
                session.commit()
                logger.info(f"Successfully migrated dues schema for {tenant_id}")
                
        except Exception as e:
            logger.error(f"Error migrating dues schema for {tenant_id}: {str(e)}")
            continue

if __name__ == "__main__":
    logger.info("Starting dues schema migration...")
    migrate_dues_schema()
    logger.info("Dues schema migration completed!")