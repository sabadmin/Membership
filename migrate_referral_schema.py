#!/usr/bin/env python3
"""
Migration script to update the referral system database schema.
This script adds the new columns and tables for the comprehensive referral system.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from database import get_tenant_db_session
from config import Config

def migrate_referral_schema():
    """Migrate the referral system schema for all tenants."""

    print("Migrating referral system schema...")

    # Create the app
    app = create_app()

    with app.app_context():
        # Migrate schema for each tenant
        for tenant_id in Config.TENANT_DATABASES.keys():
            print(f"Migrating referral schema for tenant: {tenant_id}")

            try:
                # Get a raw database connection for schema changes
                from database import get_tenant_db_engine
                engine = get_tenant_db_engine(tenant_id)

                with engine.connect() as conn:
                    # Start a transaction
                    trans = conn.begin()

                    try:
                        # Check if referral_type table exists
                        result = conn.execute("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'referral_type')")
                        referral_type_exists = result.fetchone()[0]

                        if not referral_type_exists:
                            print(f"  Creating referral_type table for {tenant_id}")
                            # Create referral_type table
                            conn.execute("""
                                CREATE TABLE referral_type (
                                    id SERIAL PRIMARY KEY,
                                    type_name VARCHAR(64) NOT NULL UNIQUE,
                                    description TEXT,
                                    requires_member_selection BOOLEAN DEFAULT FALSE,
                                    requires_contact_info BOOLEAN DEFAULT FALSE,
                                    allows_closed_date BOOLEAN DEFAULT TRUE,
                                    is_active BOOLEAN DEFAULT TRUE,
                                    sort_order INTEGER DEFAULT 0
                                )
                            """)

                            # Insert default referral types
                            conn.execute("""
                                INSERT INTO referral_type (type_name, description, requires_member_selection, requires_contact_info, allows_closed_date, sort_order) VALUES
                                ('In Group', 'Referral to an existing member of the organization', TRUE, FALSE, TRUE, 1),
                                ('Out of Group', 'Referral to someone outside the organization', FALSE, TRUE, TRUE, 2),
                                ('Subscription', 'Referral for a subscription service', FALSE, TRUE, FALSE, 3),
                                ('Business Partnership', 'Referral for potential business partnership', FALSE, TRUE, TRUE, 4),
                                ('Networking Event', 'Referral made at a networking event', FALSE, TRUE, TRUE, 5)
                            """)

                        # Check if referral_record table has the new columns
                        result = conn.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'referral_record' AND column_name = 'referral_type_id'")
                        has_referral_type_id = result.fetchone() is not None

                        if not has_referral_type_id:
                            print(f"  Adding new columns to referral_record table for {tenant_id}")

                            # Add new columns to referral_record table
                            conn.execute("ALTER TABLE referral_record ADD COLUMN IF NOT EXISTS referral_type_id INTEGER REFERENCES referral_type(id)")
                            conn.execute("ALTER TABLE referral_record ADD COLUMN IF NOT EXISTS referral_level INTEGER")
                            conn.execute("ALTER TABLE referral_record ADD COLUMN IF NOT EXISTS referral_value FLOAT")
                            conn.execute("ALTER TABLE referral_record ADD COLUMN IF NOT EXISTS date_referred TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
                            conn.execute("ALTER TABLE referral_record ADD COLUMN IF NOT EXISTS closed_date TIMESTAMP")
                            conn.execute("ALTER TABLE referral_record ADD COLUMN IF NOT EXISTS is_verified BOOLEAN DEFAULT FALSE")
                            conn.execute("ALTER TABLE referral_record ADD COLUMN IF NOT EXISTS verified_by_id INTEGER REFERENCES \"user\"(id)")
                            conn.execute("ALTER TABLE referral_record ADD COLUMN IF NOT EXISTS verified_date TIMESTAMP")
                            conn.execute("ALTER TABLE referral_record ADD COLUMN IF NOT EXISTS referred_name VARCHAR(128)")
                            conn.execute("ALTER TABLE referral_record ADD COLUMN IF NOT EXISTS contact_email VARCHAR(120)")
                            conn.execute("ALTER TABLE referral_record ADD COLUMN IF NOT EXISTS contact_phone VARCHAR(15)")
                            conn.execute("ALTER TABLE referral_record ADD COLUMN IF NOT EXISTS notes TEXT")

                            # Update existing records to have default values
                            # Set default referral type to "In Group" for existing records that have referred_id
                            conn.execute("""
                                UPDATE referral_record
                                SET referral_type_id = (SELECT id FROM referral_type WHERE type_name = 'In Group' LIMIT 1)
                                WHERE referral_type_id IS NULL AND referred_id IS NOT NULL
                            """)

                            # Set default referral type to "Out of Group" for existing records without referred_id
                            conn.execute("""
                                UPDATE referral_record
                                SET referral_type_id = (SELECT id FROM referral_type WHERE type_name = 'Out of Group' LIMIT 1)
                                WHERE referral_type_id IS NULL AND referred_id IS NULL
                            """)

                            # Set default referral level
                            conn.execute("UPDATE referral_record SET referral_level = 1 WHERE referral_level IS NULL")

                            # Set is_verified to FALSE for existing records
                            conn.execute("UPDATE referral_record SET is_verified = FALSE WHERE is_verified IS NULL")

                        # Commit the transaction
                        trans.commit()

                        print(f"  Successfully migrated referral schema for {tenant_id}")

                    except Exception as e:
                        trans.rollback()
                        print(f"  Error migrating referral schema for {tenant_id}: {str(e)}")
                        raise

            except Exception as e:
                print(f"  Error connecting to database for {tenant_id}: {str(e)}")
                raise

    print("Referral system schema migration completed successfully!")

if __name__ == "__main__":
    migrate_referral_schema()
