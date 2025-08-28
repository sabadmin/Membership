# app/members/routes.py

from flask import Blueprint, request, jsonify, g, render_template, redirect, url_for, session
from config import Config
from database import get_tenant_db_session
from app.models import User # Import User model from models.py

# Define the Blueprint
members_bp = Blueprint('members', __name__, url_prefix='/demographics') # Set url_prefix for this blueprint

@members_bp.route('/<tenant_id>', methods=['GET', 'POST'])
def demographics(tenant_id):
    if 'user_id' not in session or session['tenant_id'] != tenant_id:
        # Redirect to auth blueprint's login route
        return redirect(url_for('auth.login', tenant_id=tenant_id)) 
    
    current_user_id = session['user_id']
    current_user = None
    error_message = None
    success_message = None

    with get_tenant_db_session(tenant_id) as s:
        current_user = s.query(User).filter_by(id=current_user_id, tenant_id=tenant_id).first()
        if not current_user:
            # Clear session if user not found (e.g., deleted)
            session.pop('user_id', None)
            session.pop('tenant_id', None)
            session.pop('user_email', None)
            session.pop('user_name', None)
            return redirect(url_for('auth.login')) # Redirect to auth blueprint's login

        if request.method == 'POST':
            try:
                # Update user data from form
                current_user.first_name = request.form['first_name']
                current_user.middle_initial = request.form.get('middle_initial')
                current_user.last_name = request.form['last_name']
                current_user.email = request.form['email']
                current_user.address = request.form.get('address')
                current_user.cell_phone = request.form.get('cell_phone')
                current_user.company = request.form.get('company')
                current_user.company_address = request.form.get('company_address')
                current_user.company_phone = request.form.get('company_phone')
                current_user.company_title = request.form.get('company_title')
                current_user.network_group_title = request.form.get('network_group_title')
                current_user.member_anniversary = request.form.get('member_anniversary')

                # Handle password change only if provided
                new_password = request.form.get('password')
                if new_password:
                    current_user.set_password(new_password)

                s.commit()
                success_message = "Your information has been updated successfully!"
                # Update session name/email in case they changed
                session['user_email'] = current_user.email
                session['user_name'] = f"{current_user.first_name or ''} {current_user.last_name or ''}".strip() or current_user.email
            except Exception as e:
                s.rollback()
                error_message = f"Failed to update information: {str(e)}"

    tenant_display_name = Config.TENANT_DISPLAY_NAMES.get(tenant_id, tenant_id.capitalize())
    return render_template('demographics.html', 
                           tenant_id=tenant_id, 
                           user=current_user, # Pass the current user object
                           tenant_display_name=tenant_display_name,
                           error=error_message,
                           success=success_message)

