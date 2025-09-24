#!/usr/bin/env python3
"""
Setup script for the referral system.
This script creates the necessary database tables and populates initial referral types.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from database import get_tenant_db_session
from app.models import ReferralType
from config import Config

def setup_referral_system():
    """Set up the referral system for all tenants."""

    print("Setting up referral system...")

    # Create the app
    app = create_app()

    with app.app_context():
        # Set up referral types for each tenant
        for tenant_id in Config.TENANT_DATABASES.keys():
            print(f"Setting up referral types for tenant: {tenant_id}")

            with get_tenant_db_session(tenant_id) as s:
                try:
                    # Check if referral types already exist
                    existing_types = s.query(ReferralType).count()
                    if existing_types > 0:
                        print(f"  Referral types already exist for {tenant_id}, skipping...")
                        continue

                    # Create default referral types
                    referral_types = [
                        ReferralType(
                            type_name="In Group",
                            description="Referral to an existing member of the organization",
                            requires_member_selection=True,
                            requires_contact_info=False,
                            allows_closed_date=True,
                            sort_order=1
                        ),
                        ReferralType(
                            type_name="Out of Group",
                            description="Referral to someone outside the organization",
                            requires_member_selection=False,
                            requires_contact_info=True,
                            allows_closed_date=True,
                            sort_order=2
                        ),
                        ReferralType(
                            type_name="Subscription",
                            description="Referral for a subscription service",
                            requires_member_selection=False,
                            requires_contact_info=True,
                            allows_closed_date=False,  # No closed date for subscriptions
                            sort_order=3
                        ),
                        ReferralType(
                            type_name="Business Partnership",
                            description="Referral for potential business partnership",
                            requires_member_selection=False,
                            requires_contact_info=True,
                            allows_closed_date=True,
                            sort_order=4
                        ),
                        ReferralType(
                            type_name="Networking Event",
                            description="Referral made at a networking event",
                            requires_member_selection=False,
                            requires_contact_info=True,
                            allows_closed_date=True,
                            sort_order=5
                        )
                    ]

                    # Add referral types to session
                    for rt in referral_types:
                        s.add(rt)

                    # Commit the changes
                    s.commit()

                    print(f"  Successfully created {len(referral_types)} referral types for {tenant_id}")

                except Exception as e:
                    s.rollback()
                    print(f"  Error setting up referral types for {tenant_id}: {str(e)}")
                    raise

    print("Referral system setup completed successfully!")

if __name__ == "__main__":
    setup_referral_system()
