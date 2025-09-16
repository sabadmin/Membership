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

            # Use the proper tenant session management
            from database import get_tenant_db_session

            try:
                with get_tenant_db_session(tenant_id) as session:
                    # Find users without UserAuthDetails using raw SQL
                    from sqlalchemy import text
                    result = session.execute(text("""
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
                    from app.models import UserAuthDetails
                    for user_id, email in users_without_auth:
                        try:
                            # Create new UserAuthDetails record
                            new_auth = UserAuthDetails(
                                user_id=user_id,
                                password_hash=None,
                                is_active=True,
                                last_login_1=None,
                                can_edit_dues=False,
                                can_edit_security=False,
                                can_edit_referrals=False,
                                can_edit_members=False,
                                can_edit_attendance=False
                            )
                            session.add(new_auth)

                            print(f"Created UserAuthDetails for user: {email} (ID: {user_id})")
                            total_created += 1

                        except Exception as e:
                            print(f"Error creating UserAuthDetails for user {email} (ID: {user_id}): {str(e)}")

                    session.commit()
                    total_processed += len(users_without_auth)

            except Exception as e:
                print(f"Error processing tenant {tenant_id}: {str(e)}")
                continue

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
