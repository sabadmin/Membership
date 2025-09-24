#!/usr/bin/env python3
"""
Script to create a superuser account in all tenant databases.
Superuser: saburstyn@unfrustratingcomputers.com
Password: Bellm0re (will be hashed)
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import Config
from database import get_tenant_db_session
from app.models import User, UserAuthDetails
from datetime import datetime, timezone

def create_superuser():
    """Create superuser in all tenant databases"""

    superuser_email = "saburstyn@unfrustratingcomputers.com"
    superuser_password = "Bellm0re"  # Will be hashed by set_password()

    print(f"Creating superuser: {superuser_email}")
    print(f"Password: {superuser_password} (will be hashed)")
    print()

    for tenant_id in Config.TENANT_DATABASES.keys():
        print(f"Processing tenant: {tenant_id}")

        try:
            with get_tenant_db_session(tenant_id) as session:
                # Check if user already exists
                existing_user = session.query(User).filter_by(email=superuser_email).first()

                if existing_user:
                    print(f"  ✓ User already exists in {tenant_id}, updating permissions...")
                    # Update existing user to ensure all permissions are set
                    if not existing_user.auth_details:
                        existing_user.auth_details = UserAuthDetails(
                            user_id=existing_user.id,
                            is_active=True,
                            last_login_1=datetime.now(timezone.utc)
                        )
                        session.add(existing_user.auth_details)
                        session.flush()

                    # Set all permissions to True for superuser
                    existing_user.auth_details.can_edit_dues = True
                    existing_user.auth_details.can_edit_security = True
                    existing_user.auth_details.can_edit_referrals = True
                    existing_user.auth_details.can_edit_members = True
                    existing_user.auth_details.can_edit_attendance = True
                    existing_user.auth_details.is_active = True

                    # Update user info
                    existing_user.first_name = "Super"
                    existing_user.last_name = "User"
                    existing_user.is_active = True

                else:
                    print(f"  + Creating new user in {tenant_id}...")

                    # Create new superuser
                    superuser = User(
                        email=superuser_email,
                        first_name="Super",
                        last_name="User",
                        is_active=True
                    )

                    session.add(superuser)
                    session.flush()  # Get the user ID

                    # Create auth details with all permissions
                    superuser.auth_details = UserAuthDetails(
                        user_id=superuser.id,
                        is_active=True,
                        last_login_1=datetime.now(timezone.utc),
                        can_edit_dues=True,
                        can_edit_security=True,
                        can_edit_referrals=True,
                        can_edit_members=True,
                        can_edit_attendance=True
                    )

                    # Set password (this creates the password hash)
                    superuser.set_password(superuser_password)

                    session.add(superuser.auth_details)

                session.commit()
                print(f"  ✓ Successfully processed {tenant_id}")

        except Exception as e:
            print(f"  ✗ Error processing {tenant_id}: {str(e)}")
            session.rollback()

    print()
    print("Superuser creation completed!")
    print(f"Email: {superuser_email}")
    print(f"Password: {superuser_password}")
    print("This user has full admin permissions in all tenants.")
    print("Login with any tenant to access the admin panel and select which tenant's data to review.")

if __name__ == "__main__":
    create_superuser()
