# app/members/routes.py

from flask import Blueprint, request, render_template, redirect, url_for, session, flash, g
from config import Config
from database import get_tenant_db_session
from app.models import User, UserAuthDetails, AttendanceRecord
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

def _get_current_user(s, user_id):
    return s.query(User).filter_by(id=user_id).options(joinedload(User.auth_details)).first()

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
        current_user = _get_current_user(s, current_user_id)
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
                current_user.address_line1 = request.form.get('address_line1')
                current_user.address_line2 = request.form.get('address_line2')
                current_user.city = request.form.get('city')
                current_user.state = request.form.get('state')
                current_user.zip_code = request.form.get('zip_code')
                current_user.cell_phone = request.form.get('cell_phone')
                current_user.company = request.form.get('company')
                current_user.company_address_line1 = request.form.get('company_address_line1')
                current_user.company_address_line2 = request.form.get('company_address_line2')
                current_user.company_city = request.form.get('company_city')
                current_user.company_state = request.form.get('company_state')
                current_user.company_zip_code = request.form.get('company_zip_code')
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

@members_bp.route('/attendance/<tenant_id>', methods=['GET', 'POST'])
def attendance(tenant_id):
    if 'user_id' not in session or session['tenant_id'] != tenant_id:
        flash("You must be logged in to view this page.", "danger")
        return redirect(url_for('auth.login', tenant_id=tenant_id))
    
    tenant_display_name = Config.TENANT_DISPLAY_NAMES.get(tenant_id, tenant_id.capitalize())
    
    with get_tenant_db_session(tenant_id) as s:
        # Get all users for attendance matrix
        all_users = s.query(User).order_by(User.first_name, User.last_name).all()
        
        if request.method == 'POST':
            try:
                event_date = request.form.get('event_date')
                event_name = request.form.get('event_name', 'Meeting')
                
                if not event_date:
                    flash("Event date is required.", "danger")
                    return redirect(url_for('members.attendance', tenant_id=tenant_id))
                
                # Parse the date
                from datetime import datetime
                try:
                    parsed_date = datetime.strptime(event_date, '%Y-%m-%d')
                except ValueError:
                    flash("Invalid date format.", "danger")
                    return redirect(url_for('members.attendance', tenant_id=tenant_id))
                
                # Process attendance for each user
                records_created = 0
                for user in all_users:
                    attendance_value = request.form.get(f'attendance_{user.id}')
                    if attendance_value:
                        # Check if record already exists for this date
                        existing_record = s.query(AttendanceRecord).filter_by(
                            user_id=user.id,
                            event_date=parsed_date,
                            event_name=event_name
                        ).first()
                        
                        if existing_record:
                            # Update existing record
                            existing_record.status = attendance_value
                            existing_record.updated_at = datetime.utcnow()
                        else:
                            # Create new record
                            new_record = AttendanceRecord(
                                user_id=user.id,
                                event_name=event_name,
                                event_date=parsed_date,
                                status=attendance_value,
                                created_at=datetime.utcnow(),
                                updated_at=datetime.utcnow()
                            )
                            s.add(new_record)
                            records_created += 1
                
                s.commit()
                flash(f"Attendance saved successfully! {records_created} new records created.", "success")
                
            except Exception as e:
                s.rollback()
                flash(f"Failed to save attendance: {str(e)}", "danger")
            
            return redirect(url_for('members.attendance', tenant_id=tenant_id))
        
        # For GET requests, get existing attendance for today if available
        from datetime import date
        today = date.today()
        existing_attendance = {}
        
        # Get attendance records for today
        today_records = s.query(AttendanceRecord).filter_by(
            event_date=today
        ).all()
        
        for record in today_records:
            existing_attendance[record.user_id] = record.status
            
        return render_template('attendance.html',
                             tenant_id=tenant_id,
                             tenant_display_name=tenant_display_name,
                             all_users=all_users,
                             existing_attendance=existing_attendance,
                             today=today.strftime('%Y-%m-%d'))

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
        user = _get_current_user(s, current_user_id)
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
