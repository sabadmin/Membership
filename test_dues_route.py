#!/usr/bin/env python3

import sys
import os
sys.path.append('.')

try:
    from app import create_app
    from app.models import User, UserAuthDetails, MembershipType
    from database import get_tenant_db_session
    from datetime import datetime

    app = create_app()
    print('App created successfully')

    with app.test_client() as client:
        # Create a test user in the database first
        with app.app_context():
            with get_tenant_db_session('tenant1') as session:
                # Check if test user exists, create if not
                test_user = session.query(User).filter_by(email='test@example.com').first()
                if not test_user:
                    # Create membership type if it doesn't exist
                    membership_type = session.query(MembershipType).filter_by(name='Test Member').first()
                    if not membership_type:
                        membership_type = MembershipType(
                            name='Test Member',
                            can_edit_attendance=True,
                            can_edit_demographics=True,
                            can_edit_dues=True,
                            can_edit_referrals=True
                        )
                        session.add(membership_type)
                        session.commit()

                    # Create test user
                    test_user = User(
                        first_name='Test',
                        last_name='User',
                        email='test@example.com',
                        membership_type_id=membership_type.id,
                        is_active=True
                    )
                    session.add(test_user)
                    session.commit()

                    # Create auth details for the user
                    auth_details = UserAuthDetails(
                        user_id=test_user.id,
                        can_edit_attendance=True,
                        can_edit_demographics=True,
                        can_edit_dues=True,
                        can_edit_referrals=True,
                        can_edit_security=True
                    )
                    session.add(auth_details)
                    session.commit()

                    print(f'Created test user with ID: {test_user.id}')
                else:
                    print(f'Using existing test user with ID: {test_user.id}')

        # Set up a proper authenticated session
        with client.session_transaction() as sess:
            sess['user_id'] = test_user.id
            sess['tenant_id'] = 'tenant1'
            sess['user_permissions'] = {
                'can_edit_attendance': True,
                'can_edit_demographics': True,
                'can_edit_dues': True,
                'can_edit_referrals': True,
                'can_edit_security': True
            }

        # Try to access the correct dues paid report route with /dues prefix
        response = client.get('/dues/tenant1/paid_report')
        print(f'Response status: {response.status_code}')
        if response.status_code == 500:
            print('Response data:', response.get_data(as_text=True))
        elif response.status_code == 200:
            print('Route accessible - no error!')
        else:
            print(f'Other status: {response.status_code}')
            print('Response data:', response.get_data(as_text=True))
except Exception as e:
    print(f'Error: {e}')
    import traceback
    traceback.print_exc()
