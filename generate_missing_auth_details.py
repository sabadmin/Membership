#!/usr/bin/env python3
"""
Script to generate missing UserAuthDetails for users that don't have them.
This ensures all users have proper authentication details.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from database import db
from config import Config

def generate_missing_auth_details():
    """Generate UserAuthDetails for users that don't have them."""
    app = create_app()

    with app.app_context():
        print("Starting generation of missing UserAuthDetails...")

        total_processed = 0
        total_created = 0

        # Process each tenant database
        for tenant_id in Config.TENANT_DATABASES.keys():
            print(f"\nProcessing tenant: {tenant_id}")

            # Get the tenant engine from the database module
            from database import _tenant_engines
            if tenant_id not in _tenant_engines:
                print(f"Warning: Engine not initialized for tenant {tenant_id}, skipping...")
                continue

            engine = _tenant_engines[tenant_id]

            with db.session.connection(engine) as conn:
                # Find users without UserAuthDetails
                result = conn.execute(db.text("""
                    SELECT u.id, u.email
                    FROM "user" u
                    LEFT JOIN user_auth_details uad ON u.id = uad.user_id
                    WHERE uad.user_id IS NULL
                """))

                users_without_auth = result.fetchall()

                if not users_without_auth:
                    print(f"No users missing UserAuthDetails in tenant {tenant_id}")
                    continue

                print(f"Found {len(users_without_auth)} users missing UserAuthDetails in tenant {tenant_id}")

                # Create UserAuthDetails for each user
                for user_id, email in users_without_auth:
                    try:
                        # Insert new UserAuthDetails record
                        conn.execute(db.text("""
                            INSERT INTO user_auth_details (
                                user_id, password_hash, is_active, last_login_1,
                                can_edit_dues, can_edit_security, can_edit_referrals,
                                can_edit_members, can_edit_attendance
                            ) VALUES (
                                :user_id, NULL, true, NULL,
                                false, false, false, false, false
                            )
                        """), {"user_id": user_id})

                        print(f"Created UserAuthDetails for user: {email} (ID: {user_id})")
                        total_created += 1

                    except Exception as e:
                        print(f"Error creating UserAuthDetails for user {email} (ID: {user_id}): {str(e)}")

                conn.commit()
                total_processed += len(users_without_auth)

        print("\nSummary:")
        print(f"Total users processed: {total_processed}")
        print(f"Total UserAuthDetails created: {total_created}")

        if total_created > 0:
            print("\nNOTE: New UserAuthDetails were created with NULL password_hash.")
            print("Users will need to reset their passwords or set them through the registration process.")
        else:
            print("\nAll users already have UserAuthDetails.")

if __name__ == "__main__":
    generate_missing_auth_details()
