# config.py

import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'a_very_secret_key_for_development'
    
    SQLALCHEMY_DATABASE_URI = os.environ.get('DEFAULT_DATABASE_URL', 'postgresql://sabadmin:Bellm0re@localhost:5432/default_db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    TENANT_DATABASES = {
        'tenant1': os.environ.get('DATABASE_URL_TENANT1', 'postgresql://sabadmin:Bellm0re@localhost:5432/tenant1_db'),
        'tenant2': os.environ.get('DATABASE_URL_TENANT2', 'postgresql://sabadmin:Bellm0re@localhost:5432/tenant2_db'),
        'closers': os.environ.get('DATABASE_URL_CLOSERS', 'postgresql://sabadmin:Bellm0re@localhost:5432/closers_db'),
        'liconnects': os.environ.get('DATABASE_URL_LICONNECTS', 'postgresql://sabadmin:Bellm0re@localhost:5432/liconnects_db'),
        'lieg': os.environ.get('DATABASE_URL_LIEG', 'postgresql://sabadmin:Bellm0re@localhost:5432/lieg_db'),
    }

    TENANT_DISPLAY_NAMES = {
        'tenant1': 'Tenant One',
        'tenant2': 'Tenant Two',
        'closers': 'IBO Closers',
        'liconnects': 'LI Connects',
        'lieg': 'L.I.E.G',
    }

    DEBUG = os.environ.get('FLASK_DEBUG') == '1'
    if DEBUG:
        print("DEBUG mode is ON. Do NOT use in production.")
    else:
        print("DEBUG mode is OFF. Good for production.")

    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
