#!/usr/bin/env python3
"""
Migration script to add location and topic fields to the referral system.
This script adds the new columns for the "One to One" referral type.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from database import get_tenant_db_session
from config import Config

def migrate_referral_location_topic():
    """Add location and topic fields to referral tables for all tenants."""

    print("Adding location and topic fields to referral system...")

    # Create the app
    app = create_app()

    with app.app_context():
        # Migrate schema for each tenant
        for tenant_id in Config.TENANT_DATABASES.keys():
            print(f"Adding location/topic fields for tenant: {tenant_id}")

            try:
                # Get a raw database connection for schema changes
                from database import _tenant_engines, get_tenant_db_url
                from sqlalchemy import create_engine

                # Get or create the engine for the tenant
                if tenant_id not in _tenant_engines:
                    db_url = get_tenant_db_url(tenant_id)
                    engine = create_engine(db_url)
                    _tenant_engines[tenant_id] = engine
                else:
                    engine = _tenant_engines[tenant_id]

                with engine.connect() as conn:
                    # Start a transaction
                    trans = conn.begin()

                    try:
                        from sqlalchemy import text

                        # Add new columns to referral_record table
                        print(f"  Adding location and topic columns to referral_record table for {tenant_id}")
                        conn.execute(text("ALTER TABLE referral_record ADD COLUMN IF NOT EXISTS location VARCHAR(255)"))
                        conn.execute(text("ALTER TABLE referral_record ADD COLUMN IF NOT EXISTS topic VARCHAR(255)"))

                        # Add requires_location_topic column to referral_type table
                        print(f"  Adding requires_location_topic column to referral_type table for {tenant_id}")
                        conn.execute(text("ALTER TABLE referral_type ADD COLUMN IF NOT EXISTS requires_location_topic BOOLEAN DEFAULT FALSE"))

                        # Update "One to One" referral type if it exists
                        conn.execute(text("""
                            UPDATE referral_type
                            SET requires_location_topic = TRUE, requires_member_selection = TRUE
                            WHERE type_name = 'One to One'
                        """))

                        # Commit the transaction
                        trans.commit()

                        print(f"  Successfully added location/topic fields for {tenant_id}")

                    except Exception as e:
                        trans.rollback()
                        print(f"  Error adding location/topic fields for {tenant_id}: {str(e)}")
                        raise

            except Exception as e:
                print(f"  Error connecting to database for {tenant_id}: {str(e)}")
                raise

    print("Location and topic fields migration completed successfully!")

if __name__ == "__main__":
    migrate_referral_location_topic()
