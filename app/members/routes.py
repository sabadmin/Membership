# app/members/routes.py

from flask import Blueprint, request, jsonify, g, render_template, redirect, url_for, session, flash # Import flash
from config import Config
from database import get_tenant_db_session
from app.models import User, UserAuthDetails
from app.utils import infer_tenant_from_hostname
from sqlalchemy.orm import relationship, joinedload
from datetime import datetime

# Define the Blueprint
members_bp = Blueprint('members', __name__, url_prefix='/')

@members_bp.route('/demographics/<tenant_id>', methods=['GET', 'POST'])
def demographics(tenant_id):
    if 'user_id' not in session or session['tenant_id'] != tenant_id:
        return redirect(url_for('auth.login', tenant_id=tenant_id)) 
    
    current_user_id = session['user_id']
    current_user = None
    
    # Removed error_message and success_message local variables, will use flash instead

    with get_tenant_db_session(tenant_id) as s:
        current_user = s.query(User).filter_by(id=current_user_id, tenant_id=tenant_id).options(joinedload(User.auth_details)).first()
        if not current_user:
            session.pop('user_id', None)
            session.pop('tenant_id', None)
            session.pop('user_email', None)
            session.pop('user_name', None)
            session.pop('tenant_name', None)
            flash("User not found.", "danger") # Use flash message
            return redirect(url_for('auth.login'))

        if request.method == 'POST':
            try:
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

                s.commit()
                flash("Your information has been updated successfully!", "success") # Use flash message
                session['user_email'] = current_user.email
                session['user_name'] = f"{current_user.first_name or ''} {current_user.last_name or ''}".strip() or current_user.email

                # NEW: Redirect to admin_panel if superadmin
                if tenant_id == Config.SUPERADMIN_TENANT_ID:
                    return redirect(url_for('admin.admin_panel', selected_tenant_id=tenant_id))
                
                # For other tenants, re-render the demographics page with success message
                return redirect(url_for('members.demographics', tenant_id=tenant_id))

            except Exception as e:
                s.rollback()
                flash(f"Failed to update information: {str(e)}", "danger") # Use flash message
                # If update fails, re-render the demographics page with error message
                return redirect(url_for('members.demographics', tenant_id=tenant_id))


    tenant_display_name = Config.TENANT_DISPLAY_NAMES.get(tenant_id, tenant_id.capitalize())
    return render_template('demographics.html', 
                           tenant_id=tenant_id, 
                           user=current_user,
                           tenant_display_name=tenant_display_name) # Removed error/success from render_template

@members_bp.route('/attendance/<tenant_id>')
def attendance(tenant_id):
    if 'user_id' not in session or session['tenant_id'] != tenant_id:
        return redirect(url_for('auth.login', tenant_id=tenant_id))
    tenant_display_name = Config.TENANT_DISPLAY_NAMES.get(tenant_id, tenant_id.capitalize())
    return render_template('attendance.html', tenant_id=tenant_id, tenant_display_name=tenant_display_name)

@members_bp.route('/dues/<tenant_id>')
def dues(tenant_id):
    if 'user_id' not in session or session['tenant_id'] != tenant_id:
        return redirect(url_for('auth.login', tenant_id=tenant_id))
    tenant_display_name = Config.TENANT_DISPLAY_NAMES.get(tenant_id, tenant_id.capitalize())
    return render_template('dues.html', tenant_id=tenant_id, tenant_display_name=tenant_display_name)

@members_bp.route('/security/<tenant_id>', methods=['GET', 'POST'])
def security(tenant_id):
    if 'user_id' not in session or session['tenant_id'] != tenant_id:
        return redirect(url_for('auth.login', tenant_id=tenant_id))
    
    current_user_id = session['user_id']
    # Removed error_message and success_message local variables
    current_user_auth_details = None

    with get_tenant_db_session(tenant_id) as s:
        current_user = s.query(User).filter_by(id=current_user_id, tenant_id=tenant_id).options(joinedload(User.auth_details)).first()
        if not current_user:
            session.pop('user_id', None)
            session.pop('tenant_id', None)
            session.pop('user_email', None)
            session.pop('user_name', None)
            session.pop('tenant_name', None)
            flash("User not found.", "danger") # Use flash message
            return redirect(url_for('auth.login'))
        
        current_user_auth_details = current_user.auth_details

        if request.method == 'POST':
            new_password = request.form.get('password')
            confirm_password = request.form.get('confirm_password')

            if not new_password:
                flash("Password field cannot be empty.", "danger") # Use flash message
            elif new_password != confirm_password:
                flash("New password and confirmation do not match.", "danger") # Use flash message
            else:
                try:
                    current_user.set_password(new_password)
                    s.commit()
                    flash("Your password has been updated successfully!", "success") # Use flash message
                except Exception as e:
                    s.rollback()
                    flash(f"Failed to update password: {str(e)}", "danger") # Use flash message
            
            # Always redirect after POST to prevent form resubmission
            return redirect(url_for('members.security', tenant_id=tenant_id))

    tenant_display_name = Config.TENANT_DISPLAY_NAMES.get(tenant_id, tenant_id.capitalize())
    return render_template('security.html', 
                           tenant_id=tenant_id, 
                           tenant_display_name=tenant_display_name,
                           auth_details=current_user_auth_details) # Removed error/success from render_template

