# config.py

import os

class Config:
    # Flask application configuration
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'a_very_secret_key_for_development'

    # Explicitly set SQLALCHEMY_DATABASE_URI using sabadmin credentials
    # This is the default connection for Flask-SQLAlchemy itself.
    SQLALCHEMY_DATABASE_URI = os.environ.get('DEFAULT_DATABASE_URL', 'postgresql://sabadmin:Bellm0re@localhost:5432/default_db')

    # Optional: Suppress Flask-SQLAlchemy warning about tracking modifications
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Define your tenant-specific PostgreSQL database configurations
    # Each key is a tenant ID, and the value is the PostgreSQL connection string.
    # IMPORTANT: Ensure these databases are created in your PostgreSQL server.
    TENANT_DATABASES = {
        'tenant1': os.environ.get('DATABASE_URL_TENANT1', 'postgresql://sabadmin:Bellm0re@localhost:5432/tenant1_db'),
        'tenant2': os.environ.get('DATABASE_URL_TENANT2', 'postgresql://sabadmin:Bellm0re@localhost:5432/tenant2_db'),
        'website': os.environ.get('DATABASE_URL_WEBSITE', 'postgresql://sabadmin:Bellm0re@localhost:5432/website_db'), # Example for a public website or shared data
        'closers': os.environ.get('DATABASE_URL_CLOSERS', 'postgresql://sabadmin:Bellm0re@localhost:5432/closers_db'),
        'liconnects': os.environ.get('DATABASE_URL_LICONNECTS', 'postgresql://sabadmin:Bellm0re@localhost:5432/liconnects_db'),
        'lieg': os.environ.get('DATABASE_URL_LIEG', 'postgresql://sabadmin:Bellm0re@localhost:5432/lieg_db'),
        # Add more tenants as needed
    }

    # NEW: Define display names for tenants
    TENANT_DISPLAY_NAMES = {
        'tenant1': 'Tenant One',
        'tenant2': 'Tenant Two',
        'website': 'Main Website',
        'closers': 'IBO Closers',
        'liconnects': 'LI Connects',
        'lieg': 'L.I.E.G',
    }

    # Debug mode. Set to False in production!
    DEBUG = os.environ.get('FLASK_DEBUG') == '1'
    if DEBUG:
        print("DEBUG mode is ON. Do NOT use in production.")
    else:
        print("DEBUG mode is OFF. Good for production.")

    # Other configurations can go here
    # Example: Session cookie settings
    SESSION_COOKIE_SECURE = True # Ensure cookies are only sent over HTTPS
    SESSION_COOKIE_HTTPONLY = True # Prevent client-side JavaScript access to session cookies
    SESSION_COOKIE_SAMESITE = 'Lax' # Protect against CSRF

