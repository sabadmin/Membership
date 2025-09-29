#!/usr/bin/env python3

import sys
import os
sys.path.append('.')

try:
    from app import create_app
    app = create_app()
    print('App created successfully')

    with app.test_client() as client:
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
