#!/usr/bin/env python3

import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from app import create_app
    print("Flask app creation successful!")
    print("Application is ready to run with gunicorn.")
except Exception as e:
    print(f"Error creating Flask app: {e}")
    sys.exit(1)
