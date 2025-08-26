# routes.py

from flask import Blueprint, render_template, request, redirect, url_for, session, g, flash, current_app
from models import User
from database import get_db_session, init_db_for_tenant, get_all_table_names, get_table_model, get_table_columns, get_table_data, add_record, update_record, delete_record
from utils import hash_password, check_hashed_password, login_required, role_required
from config import Config # Import Config to get SUPERADMIN_TENANT_ID
import os

# Create a Blueprint for our application routes
main_bp = Blueprint('main', __name__)

@main_bp.before_request
def identify_tenant_and_connect_db():
    """
    Identifies the tenant based on the X-Tenant-ID header set by Nginx
    and sets up the database connection.
    """
    g.tenant_id = request.headers.get('X-Tenant-ID', 'default')

    # Set the current database session for this request.
    g.db_session = get_db_session(g.tenant_id)

    # Optional: For debugging, print which tenant is active for the request
    # print(f"Request Host: {request.host}, Determined Tenant (from X-Tenant-ID): {g.tenant_id}")


# --- Custom Decorator for Superadmin Access ---
def superadmin_required(f):
    """
    Decorator to ensure the user is logged in, has the 'super_admin' role,
    AND is accessing the application via the SUPERADMIN_TENANT_ID domain.
    """
    @role_required(['super_admin']) # Ensures role is super_admin
    def decorated_function(*args, **kwargs):
        if g.tenant_id != Config.SUPERADMIN_TENANT_ID:
            flash("Superadmin access is restricted to the superadmin tenant.", "danger")
            return redirect(url_for('main.index')) # Redirect to a safe page
        return f(*args, **kwargs)
    return decorated_function

@main_bp.route('/')
def index():
    return render_template('index.html')

@main_bp.route('/login', methods=['GET', 'POST'])
def login():
    # ... existing login code ...

@main_bp.route('/logout')
def logout():
    # ... existing logout code ...

@main_bp.route('/<path:subpath>')
def catch_all(subpath):
    # This will catch all undefined routes
    return render_template('404.html'), 404

def _infer_tenant_from_hostname():
    current_hostname = request.host.split(':')[0]
    for tenant_key in Config.TENANT_DATABASES.keys():
        if f"{tenant_key}.unfc.it" == current_hostname:
            return tenant_key
    return 'website'
