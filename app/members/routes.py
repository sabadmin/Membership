# app/members/routes.py

from flask import Blueprint, request, render_template, redirect, url_for, session, flash, g
from config import Config
from database import get_tenant_db_session
from app.models import User, UserAuthDetails
from app.utils import infer_tenant_from_hostname
from sqlalchemy.orm import joinedload
from datetime import datetime

# Define the Blueprint
members_bp = Blueprint('members', __name__, url_prefix='/')

@members_bp.before_request
def before_request():
    # If not a superadmin, ensure a user is logged in
    if g.tenant_id != Config.SUPERADMIN_TENANT_ID and 'user_id' not in session:
        return redirect(url_for('auth.login', tenant_id=g.tenant_id))

def _get_current_user(s, user_id, tenant_id):
    return s.query(User).filter_by(id=user_id, tenant_id=tenant_id).options(joinedload(User.auth_details)).first()

def _format_phone(phone):
    if phone and len(phone) == 10 and phone.isdigit():
        return f"({phone[0:3]}) {phone[3:6]}-{phone[6:10]}"
    return phone

@members_bp.route('/demographics/<tenant_id>', methods=['GET', 'POST'])
def demographics(tenant_id):
    if 'user_id' not in session or session['tenant_id'] != tenant_id:
        flash("You do not have permission to view this page.", "danger")
        return redirect(url_for('auth.login', tenant_id=tenant_id))
    
    current_user_id = session['user_id']
    tenant_display_name = Config.TENANT_DISPLAY_NAMES.get(tenant_id, tenant_id.capitalize())

    with get_tenant_db_session(tenant_id) as s:
        current_user = _get_current_user(s, current_user_id, tenant_id)
        if not current_user:
            session.clear()
            flash("User not found.", "danger")
            return redirect(url_for('auth.login', tenant_id=tenant_id))

        if request.method == 'POST':
            try:
                # Update user info from form
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
                flash("Your information has been updated successfully!", "success")
                session['user_email'] = current_user.email
                session['user_name'] = f"{current_user.first_name or ''} {current_user.last_name or ''}".strip() or current_user.email
                
                return redirect(url_for('members.demographics', tenant_id=tenant_id))

            except Exception as e:
                s.rollback()
                flash(f"Failed to update information: {str(e)}", "danger")
                return redirect(url_for('members.demographics', tenant_id=tenant_id))

    return render_template('demographics.html',
                           tenant_id=tenant_id,
                           user=current_user,
                           tenant_display_name=tenant_display_name,
                           format_phone_number=_format_phone)

@members_bp.route('/attendance/<tenant_id>')
def attendance(tenant_id):
    if 'user_id' not in session or session['tenant_id'] != tenant_id:
        flash("You must be logged in to view this page.", "danger")
        return redirect(url_for('auth.login', tenant_id=tenant_id))
    tenant_display_name = Config.TENANT_DISPLAY_NAMES.get(tenant_id, tenant_id.capitalize())
    return render_template('attendance.html', tenant_id=tenant_id, tenant_display_name=tenant_display_name)

@members_bp.route('/dues/<tenant_id>')
def dues(tenant_id):
    if 'user_id' not in session or session['tenant_id'] != tenant_id:
        flash("You must be logged in to view this page.", "danger")
        return redirect(url_for('auth.login', tenant_id=tenant_id))
    tenant_display_name = Config.TENANT_DISPLAY_NAMES.get(tenant_id, tenant_id.capitalize())
    return render_template('dues.html', tenant_id=tenant_id, tenant_display_name=tenant_display_name)

@members_bp.route('/security/<tenant_id>', methods=['GET', 'POST'])
def security(tenant_id):
    if 'user_id' not in session or session['tenant_id'] != tenant_id:
        flash("You must be logged in to view this page.", "danger")
        return redirect(url_for('auth.login', tenant_id=tenant_id))
    
    current_user_id = session['user_id']
    current_user_auth_details = None
    user = None

    with get_tenant_db_session(tenant_id) as s:
        user = _get_current_user(s, current_user_id, tenant_id)
        if not user:
            session.clear()
            flash("User not found.", "danger")
            return redirect(url_for('auth.login', tenant_id=tenant_id))
        
        current_user_auth_details = user.auth_details
        
        if request.method == 'POST':
            new_password = request.form.get('password')
            confirm_password = request.form.get('confirm_password')

            if not new_password:
                flash("Password field cannot be empty.", "danger")
            elif new_password != confirm_password:
                flash("New password and confirmation do not match.", "danger")
            else:
                try:
                    user.set_password(new_password)
                    s.commit()
                    flash("Your password has been updated successfully!", "success")
                except Exception as e:
                    s.rollback()
                    flash(f"Failed to update password: {str(e)}", "danger")
        
        return render_template('security.html',
                               tenant_id=tenant_id,
                               tenant_display_name=Config.TENANT_DISPLAY_NAMES.get(tenant_id, tenant_id.capitalize()),
                               auth_details=current_user_auth_details)
