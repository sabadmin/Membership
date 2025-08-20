# utils.py

from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from flask import session, redirect, url_for, flash, g

def hash_password(password):
    """Hashes a password using Werkzeug's secure method."""
    return generate_password_hash(password)

def check_hashed_password(hashed_password, password):
    """Checks a plain password against a hashed password."""
    return check_password_hash(hashed_password, password)

def login_required(f):
    """
    Decorator to ensure a user is logged in before accessing a route.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'info')
            return redirect(url_for('main.login'))
        return f(*args, **kwargs)
    return decorated_function

def role_required(roles):
    """
    Decorator to ensure a logged-in user has one of the specified roles.
    `roles` should be a list or tuple of allowed roles (e.g., ['admin', 'super_admin']).
    """
    def decorator(f):
        @wraps(f)
        @login_required # Ensure user is logged in first
        def decorated_function(*args, **kwargs):
            from models import User # Import here to avoid circular dependency
            user = g.db_session.query(User).get(session['user_id'])
            if not user or user.role not in roles:
                flash("You don't have permission to access that page.", 'error')
                return redirect(url_for('main.dashboard')) # Or a specific unauthorized page
            return f(*args, **kwargs)
        return decorated_function
    return decorator

