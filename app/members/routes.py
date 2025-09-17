# app/members/routes.py

from flask import Blueprint, request, render_template, redirect, url_for, session, flash, g
from config import Config
from database import get_tenant_db_session
from app.models import User, UserAuthDetails, AttendanceRecord, AttendanceType, MembershipType, DuesRecord, DuesType
from app.utils import infer_tenant_from_hostname
from sqlalchemy.orm import joinedload
from datetime import date, datetime
from .forms import DuesCreateForm, DuesPaymentForm, DuesUpdateForm


# Define the Blueprint
members_bp = Blueprint('members', __name__, url_prefix='/')

@members_bp.before_request
def before_request():
    # If not a superadmin, ensure a user is logged in
    if g.tenant_id != Config.SUPERADMIN_TENANT_ID and 'user_id' not in session:
        return redirect(url_for('auth.login', tenant_id=g.tenant_id))
    
    # Load current user permissions for template access
    if 'user_id' in session:
        with get_tenant_db_session(g.tenant_id) as s:
            current_user = s.query(User).options(joinedload(User.auth_details)).filter_by(id=session['user_id']).first()
            if current_user and current_user.auth_details:
                # Store permissions in session for template access
                session['user_permissions'] = {
                    'can_edit_dues': current_user.auth_details.can_edit_dues,
                    'can_edit_security': current_user.auth_details.can_edit_security,
                    'can_edit_referrals': current_user.auth_details.can_edit_referrals,
                    'can_edit_members': current_user.auth_details.can_edit_members,
                    'can_edit_attendance': current_user.auth_details.can_edit_attendance
                }
            else:
                # Default to no permissions if no auth details
                session['user_permissions'] = {
                    'can_edit_dues': False,
                    'can_edit_security': False,
                    'can_edit_referrals': False,
                    'can_edit_members': False,
                    'can_edit_attendance': False
                }

def _get_current_user(s, user_id):
    return s.query(User).filter_by(id=user_id).options(joinedload(User.auth_details)).first()

def _format_phone(phone):
    if phone and len(phone) == 10 and phone.isdigit():
        return f"({phone[0:3]}) {phone[3:6]}-{phone[6:10]}"
    return phone


@members_bp.route('/dashboard/<tenant_id>')
def dashboard(tenant_id):
    if 'user_id' not in session or session['tenant_id'] != tenant_id:
        flash("You do not have permission to view this page.", "danger")
        return redirect(url_for('auth.login', tenant_id=tenant_id))
    
    tenant_display_name = Config.TENANT_DISPLAY_NAMES.get(tenant_id, tenant_id.capitalize())
    
    return render_template('dashboard.html',
                           tenant_id=tenant_id,
                           tenant_display_name=tenant_display_name)


@members_bp.route('/demographics/<tenant_id>/my', methods=['GET', 'POST'])
def my_demographics(tenant_id):
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
                current_user.membership_type_id = request.form.get('membership_type_id') or None

                s.commit()
                flash("Your information has been updated successfully!", "success")
                session['user_email'] = current_user.email
                session['user_name'] = f"{current_user.first_name or ''} {current_user.last_name or ''}".strip() or current_user.email
                
                return redirect(url_for('members.my_demographics', tenant_id=tenant_id))

            except Exception as e:
                s.rollback()
                flash(f"Failed to update information: {str(e)}", "danger")
                return redirect(url_for('members.my_demographics', tenant_id=tenant_id))

        # Get membership types for dropdown
        membership_types = s.query(MembershipType).filter_by(is_active=True).order_by(MembershipType.sort_order, MembershipType.name).all()

    return render_template('demographics_form.html',
                           tenant_id=tenant_id,
                           user=current_user,
                           tenant_display_name=tenant_display_name,
                           membership_types=membership_types,
                           editable=True,
                           page_title="My Demographics",
                           format_phone_number=_format_phone
                           )
@members_bp.route('/demographics/<tenant_id>/list')
def membership_list(tenant_id):
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        logger.info(f"Starting membership_list for tenant: {tenant_id}")
        
        if 'user_id' not in session or session['tenant_id'] != tenant_id:
            logger.warning(f"Access denied for membership_list. Session user_id: {session.get('user_id')}, Session tenant_id: {session.get('tenant_id')}")
            flash("You do not have permission to view this page.", "danger")
            return redirect(url_for('auth.login', tenant_id=tenant_id))
        
        tenant_display_name = Config.TENANT_DISPLAY_NAMES.get(tenant_id, tenant_id.capitalize())
        logger.info(f"Tenant display name: {tenant_display_name}")
        
        try:
            with get_tenant_db_session(tenant_id) as s:
                logger.info("Database session opened successfully")
                # Get all members with preloaded membership_type to avoid lazy loading issues
                all_members = s.query(User).options(joinedload(User.membership_type)).order_by(User.first_name, User.last_name).all()
                logger.info(f"Retrieved {len(all_members)} members from database")
                
                logger.info("Successfully loaded all members with relationships")
                
        except Exception as db_error:
            logger.error(f"Database error in membership_list: {str(db_error)}")
            logger.error(f"Database error type: {type(db_error).__name__}")
            flash("Database error occurred while retrieving members.", "danger")
            return redirect(url_for('members.my_demographics', tenant_id=tenant_id))
        
        logger.info("Rendering membership_list.html template")
        return render_template('membership_list.html',
                               tenant_id=tenant_id,
                               tenant_display_name=tenant_display_name,
                               all_members=all_members)
                               
    except Exception as e:
        logger.error(f"Unexpected error in membership_list: {str(e)}")
        logger.error(f"Error type: {type(e).__name__}")
        flash("An unexpected error occurred.", "danger")
        return redirect(url_for('members.my_demographics', tenant_id=tenant_id))

@members_bp.route('/demographics/<tenant_id>/view/<int:member_id>')
def view_member_demographics(tenant_id, member_id):
    if 'user_id' not in session or session['tenant_id'] != tenant_id:
        flash("You do not have permission to view this page.", "danger")
        return redirect(url_for('auth.login', tenant_id=tenant_id))
    
    tenant_display_name = Config.TENANT_DISPLAY_NAMES.get(tenant_id, tenant_id.capitalize())
    
    with get_tenant_db_session(tenant_id) as s:
        # Get the selected member with preloaded membership_type to avoid lazy loading issues
        selected_member = s.query(User).options(joinedload(User.membership_type)).filter_by(id=member_id).first()
        if not selected_member:
            flash("Member not found.", "danger")
            return redirect(url_for('members.membership_list', tenant_id=tenant_id))
        
        # Get all members for dropdown (to keep it available) with preloaded membership_type
        all_members = s.query(User).options(joinedload(User.membership_type)).order_by(User.first_name, User.last_name).all()
        
        # Get membership types for display
        membership_types = s.query(MembershipType).filter_by(is_active=True).order_by(MembershipType.sort_order, MembershipType.name).all()
        
    return render_template('demographics_form.html',
                           tenant_id=tenant_id,
                           user=selected_member,
                           tenant_display_name=tenant_display_name,
                           membership_types=membership_types,
                           all_members=all_members,
                           selected_member_id=member_id,
                           editable=False,
                           page_title=f"Viewing: {selected_member.first_name or ''} {selected_member.last_name or ''}".strip() or selected_member.email,
                           format_phone_number=_format_phone)



@members_bp.route('/attendance/<tenant_id>/history', methods=['GET', 'POST'])
def attendance_history(tenant_id):
    import logging
    from sqlalchemy import func
    logger = logging.getLogger(__name__)
    
    try:
        logger.info(f"Starting attendance_history for tenant: {tenant_id}")
        
        if 'user_id' not in session or session['tenant_id'] != tenant_id:
            flash("You must be logged in to view this page.", "danger")
            return redirect(url_for('auth.login', tenant_id=tenant_id))
        
        tenant_display_name = Config.TENANT_DISPLAY_NAMES.get(tenant_id, tenant_id.capitalize())
        
        # Get selected date from form or default to today
        selected_date = date.today()
        navigation_action = None
        
        if request.method == 'POST':
            date_str = request.form.get('selected_date')
            navigation_action = request.form.get('navigation_action')
            
            if date_str:
                try:
                    selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                    logger.info(f"Selected date: {selected_date}")
                except ValueError:
                    logger.error(f"Invalid date format: {date_str}")
                    flash("Invalid date format.", "danger")
        
        with get_tenant_db_session(tenant_id) as s:
            logger.info("Database session opened successfully")
            
            current_user = s.query(User).options(joinedload(User.membership_type)).filter_by(id=session['user_id']).first()
            if not current_user:
                logger.error("Current user not found")
                flash("User not found.", "danger")
                return redirect(url_for('auth.login', tenant_id=tenant_id))
            
            # Check if user has permission to see all users or just their own
            user_permissions = session.get('user_permissions', {})
            can_view_all = user_permissions.get('can_edit_attendance', False)
            logger.info(f"User permissions: {user_permissions}, can_view_all: {can_view_all}")
            
            if can_view_all:
                # Show all users for privileged users
                all_users = s.query(User).options(joinedload(User.membership_type)).order_by(User.first_name, User.last_name).all()
                page_title = "Attendance History - All Members"
            else:
                # Show only current user for regular members
                all_users = [current_user] if current_user else []
                page_title = "My Attendance History"
            
            logger.info(f"Retrieved {len(all_users)} users")
            
            # If this is a GET request (initial page load) and no navigation action,
            # check if there are records for the selected date. If not, jump to most recent date with records.
            if request.method == 'GET' and not navigation_action:
                # Check if there are any records for the selected date
                if can_view_all:
                    records_exist = s.query(AttendanceRecord).filter(
                        AttendanceRecord.event_date == selected_date
                    ).first()
                else:
                    records_exist = s.query(AttendanceRecord).filter(
                        AttendanceRecord.event_date == selected_date,
                        AttendanceRecord.user_id == current_user.id
                    ).first()
                
                # If no records exist for selected date, jump to most recent date with records
                if not records_exist:
                    if can_view_all:
                        # Find most recent date with any attendance records
                        most_recent_date = s.query(AttendanceRecord.event_date).order_by(
                            AttendanceRecord.event_date.desc()
                        ).first()
                    else:
                        # Find most recent date with attendance records for current user
                        most_recent_date = s.query(AttendanceRecord.event_date).filter(
                            AttendanceRecord.user_id == current_user.id
                        ).order_by(AttendanceRecord.event_date.desc()).first()
                    
                    if most_recent_date:
                        selected_date = most_recent_date[0]
                        logger.info(f"No records found for today, jumping to most recent date: {selected_date}")
            
            # Handle navigation actions (next/prev day)
            if navigation_action:
                if navigation_action == 'next':
                    if can_view_all:
                        # Privileged users: Find next date with any attendance records
                        next_date = s.query(AttendanceRecord.event_date).filter(
                            AttendanceRecord.event_date > selected_date
                        ).order_by(AttendanceRecord.event_date.asc()).first()
                    else:
                        # Non-privileged users: Find next date with attendance records for current user only
                        next_date = s.query(AttendanceRecord.event_date).filter(
                            AttendanceRecord.event_date > selected_date,
                            AttendanceRecord.user_id == current_user.id
                        ).order_by(AttendanceRecord.event_date.asc()).first()

                    if next_date:
                        selected_date = next_date[0]
                    else:
                        # No further history - stay on current date and show message
                        flash("No further history available.", "info")

                elif navigation_action == 'prev':
                    if can_view_all:
                        # Privileged users: Find previous date with any attendance records
                        prev_date = s.query(AttendanceRecord.event_date).filter(
                            AttendanceRecord.event_date < selected_date
                        ).order_by(AttendanceRecord.event_date.desc()).first()
                    else:
                        # Non-privileged users: Find previous date with attendance records for current user only
                        prev_date = s.query(AttendanceRecord.event_date).filter(
                            AttendanceRecord.event_date < selected_date,
                            AttendanceRecord.user_id == current_user.id
                        ).order_by(AttendanceRecord.event_date.desc()).first()

                    if prev_date:
                        selected_date = prev_date[0]
                    else:
                        # No further history - stay on current date and show message
                        flash("No further history available.", "info")
            
            # Get attendance records for the selected date with attendance types
            # Handle case where attendance_type_id column doesn't exist yet
            try:
                attendance_records = s.query(AttendanceRecord).options(
                    joinedload(AttendanceRecord.attendance_type)
                ).filter(
                    AttendanceRecord.event_date == selected_date
                ).all()
            except Exception as e:
                # Fallback to basic query without attendance_type join if column doesn't exist
                logger.warning(f"AttendanceType join failed, using fallback query: {e}")
                attendance_records = s.query(AttendanceRecord).filter(
                    AttendanceRecord.event_date == selected_date
                ).all()

            # Filter out records with empty meeting types
            filtered_records = []
            for record in attendance_records:
                meeting_type = ""
                try:
                    if hasattr(record, 'attendance_type') and record.attendance_type:
                        meeting_type = record.attendance_type.type or ""
                    elif hasattr(record, 'event_name') and record.event_name:
                        meeting_type = record.event_name or ""
                except Exception:
                    pass

                # Only include records with non-empty meeting types
                if meeting_type.strip():
                    filtered_records.append(record)

            attendance_records = filtered_records
            
            logger.info(f"Found {len(attendance_records)} attendance records for {selected_date}")
            
            # Get all dates with attendance records for calendar highlighting
            attendance_dates = s.query(func.distinct(AttendanceRecord.event_date)).all()
            attendance_dates_list = [date_tuple[0].strftime('%Y-%m-%d') for date_tuple in attendance_dates]
            
            # Create attendance dictionary and attendance types dictionary
            existing_attendance = {}
            attendance_types_dict = {}  # Maps user_id to their attendance type
            default_attendance_type = "Meeting"  # Default for template compatibility
            
            for record in attendance_records:
                existing_attendance[record.user_id] = record.status
                # Handle attendance type safely - may not exist if column doesn't exist yet
                try:
                    if hasattr(record, 'attendance_type') and record.attendance_type:
                        attendance_types_dict[record.user_id] = record.attendance_type.type
                        default_attendance_type = record.attendance_type.type  # Keep last one as fallback
                    elif hasattr(record, 'event_name') and record.event_name:
                        # Fallback to event_name for legacy records
                        attendance_types_dict[record.user_id] = record.event_name
                        default_attendance_type = record.event_name
                except Exception:
                    # If there's any issue accessing attendance_type, skip it
                    pass
        
        logger.info("Rendering attendance_history.html template")
        return render_template('attendance_history.html',
                             tenant_id=tenant_id,
                             tenant_display_name=tenant_display_name,
                             all_users=all_users,
                             existing_attendance=existing_attendance,
                             selected_date=selected_date.strftime('%Y-%m-%d'),
                             attendance_type=default_attendance_type,  # Keep for compatibility
                             attendance_types_dict=attendance_types_dict,  # Individual attendance types per user
                             attendance_dates=attendance_dates_list,  # For calendar highlighting
                             can_view_all=can_view_all,
                             page_title=page_title)
                              
    except Exception as e:
        logger.error(f"Error in attendance_history: {str(e)}")
        logger.error(f"Error type: {type(e).__name__}")
        flash("An error occurred while retrieving attendance history.", "danger")
        return redirect(url_for('members.my_demographics', tenant_id=tenant_id))


@members_bp.route('/attendance/<tenant_id>/create', methods=['GET', 'POST'])
def attendance_create(tenant_id):
    if 'user_id' not in session or session['tenant_id'] != tenant_id:
        flash("You must be logged in to view this page.", "danger")
        return redirect(url_for('auth.login', tenant_id=tenant_id))
    
    # Check if user has permission to create attendance records
    user_permissions = session.get('user_permissions', {})
    if not user_permissions.get('can_edit_attendance', False):
        flash("You do not have permission to create attendance records.", "danger")
        return redirect(url_for('members.attendance_history', tenant_id=tenant_id))
    
    return _attendance_view(tenant_id)

def _attendance_view(tenant_id, editable=True):
    """Common attendance view logic"""
    tenant_display_name = Config.TENANT_DISPLAY_NAMES.get(tenant_id, tenant_id.capitalize())
    
    with get_tenant_db_session(tenant_id) as s:
        # Get all users for attendance matrix
        all_users = s.query(User).order_by(User.first_name, User.last_name).all()
        
        # Get attendance types for dropdown - handle case where table doesn't exist yet
        attendance_types = []
        try:
            attendance_types = s.query(AttendanceType).filter_by(is_active=True).order_by(AttendanceType.sort_order, AttendanceType.type).all()
        except Exception as e:
            # AttendanceType table doesn't exist yet - create a default type for backward compatibility
            from collections import namedtuple
            DefaultType = namedtuple('AttendanceType', ['id', 'type', 'description'])
            attendance_types = [DefaultType(id=1, type='Meeting', description='Regular membership meeting')]
        
        if request.method == 'POST' and editable:
            try:
                event_date = request.form.get('event_date')
                attendance_type_id = request.form.get('attendance_type_id')
                
                if not event_date:
                    flash("Event date is required.", "danger")
                    return redirect(url_for('members.attendance_create', tenant_id=tenant_id))
                
                # Parse the date
                try:
                    parsed_date = datetime.strptime(event_date, '%Y-%m-%d')
                except ValueError:
                    flash("Invalid date format.", "danger")
                    return redirect(url_for('members.attendance_create', tenant_id=tenant_id))
                
                # Check if we have AttendanceType table or need to use legacy mode
                use_legacy_mode = len(attendance_types) == 1 and hasattr(attendance_types[0], '_fields')

                if not use_legacy_mode and not attendance_type_id:
                    flash("Meeting type is required.", "danger")
                    return redirect(url_for('members.attendance_create', tenant_id=tenant_id))
                
                # Process attendance only for selected users (those with checkboxes checked)
                records_created = 0
                for user in all_users:
                    # Check if this user was selected via checkbox
                    user_selected = request.form.get(f'select_{user.id}') == 'on'
                    attendance_value = request.form.get(f'attendance_{user.id}')
                    
                    # Only process if user is selected AND has attendance value
                    if user_selected and attendance_value:
                        if use_legacy_mode:
                            # Legacy mode: use event_name field (before migration)
                            existing_record = s.query(AttendanceRecord).filter_by(
                                user_id=user.id,
                                event_date=parsed_date
                            ).first()
                            
                            if existing_record:
                                # Update existing record
                                existing_record.status = attendance_value
                                existing_record.updated_at = datetime.utcnow()
                            else:
                                # Create new record with event_name
                                new_record = AttendanceRecord(
                                    user_id=user.id,
                                    event_name='Meeting',  # Default event name
                                    event_date=parsed_date,
                                    status=attendance_value,
                                    created_at=datetime.utcnow(),
                                    updated_at=datetime.utcnow()
                                )
                                s.add(new_record)
                                records_created += 1
                        else:
                            # New mode: use attendance_type_id
                            existing_record = s.query(AttendanceRecord).filter_by(
                                user_id=user.id,
                                event_date=parsed_date,
                                attendance_type_id=attendance_type_id
                            ).first()
                            
                            if existing_record:
                                # Update existing record
                                existing_record.status = attendance_value
                                existing_record.updated_at = datetime.utcnow()
                            else:
                                # Create new record
                                new_record = AttendanceRecord(
                                    user_id=user.id,
                                    attendance_type_id=attendance_type_id,
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
            
            return redirect(url_for('members.attendance_create', tenant_id=tenant_id))
        
        # Get existing attendance for today if available (GET request)
        today = date.today()
        existing_attendance = {}
        
        if editable: # Only fetch existing attendance if view is editable
            # Get attendance records for today
            today_records = s.query(AttendanceRecord).filter_by(
                event_date=today
            ).all()
            
            for record in today_records:
                existing_attendance[record.user_id] = record.status
            
        return render_template('attendance_matrix.html',
                             tenant_id=tenant_id,
                             tenant_display_name=tenant_display_name,
                             all_users=all_users,
                             attendance_types=attendance_types,
                             existing_attendance=existing_attendance,
                             today=today.strftime('%Y-%m-%d'),
                             editable=editable)


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



@members_bp.route('/dues/<tenant_id>', methods=['GET', 'POST'])
def dues(tenant_id):

    with get_tenant_db_session(tenant_id) as s:
        current_user = s.query(User).get(session['user_id'])
        can_edit = current_user.membership_type.can_edit_attendance if current_user and current_user.membership_type else False

        dues_types = s.query(DuesType).filter_by(is_active=True).all()
        dues_create_form = DuesCreateForm()
        dues_create_form.dues_type_id.choices = [(dues_type.id, dues_type.dues_type) for dues_type in dues_types]
        dues_create_form.member_id.choices = [(user.id, f"{user.first_name} {user.last_name}") for user in s.query(User).all()]

        if request.method == 'POST' and can_edit:
            if dues_create_form.validate_on_submit():
                dues_record = DuesRecord(
                    member_id=dues_create_form.member_id.data,
                    dues_amount=dues_create_form.dues_amount.data,
                    dues_type_id=dues_create_form.dues_type_id.data,
                    due_date=dues_create_form.due_date.data,
                    date_dues_generated=date.today()
                )
                s.add(dues_record)
                s.commit()
                flash('Dues record created successfully!', 'success')
                return redirect(url_for('members.dues', tenant_id=tenant_id))

        # Query dues records, open dues first, then sorted
        dues_records = s.query(DuesRecord).join(User).join(DuesType).order_by(
            DuesRecord.amount_paid < DuesRecord.dues_amount,  # Open dues first
            DuesRecord.due_date,
            User.last_name,
            User.first_name
        ).all()

        return render_template('dues.html', tenant_id=tenant_id, dues_records=dues_records, form=dues_create_form, can_edit=can_edit, dues_types=dues_types)
    return "Dues subsystem is under construction."



@members_bp.route('/dues/<tenant_id>/payment/<int:dues_record_id>', methods=['GET', 'POST'])
def dues_payment(tenant_id, dues_record_id):
    with get_tenant_db_session(tenant_id) as s:
        dues_record = s.query(DuesRecord).get(dues_record_id)
        if not dues_record:
            flash('Dues record not found.', 'danger')
            return redirect(url_for('members.dues', tenant_id=tenant_id))

        form = DuesPaymentForm(obj=dues_record) # Pre-populate form with existing data

        if form.validate_on_submit():
            dues_record.amount_paid = form.amount_paid.data
            dues_record.document_number = form.document_number.data
            dues_record.payment_received_date = form.payment_received_date.data
            s.commit()
            flash('Payment recorded successfully!', 'success')
            return redirect(url_for('members.dues', tenant_id=tenant_id))

        return render_template('dues_payment.html', tenant_id=tenant_id, form=form, dues_record=dues_record)


@members_bp.route('/dues/<tenant_id>/update/<int:dues_record_id>', methods=['GET', 'POST'])
def dues_update(tenant_id, dues_record_id):
    with get_tenant_db_session(tenant_id) as s:
        dues_record = s.query(DuesRecord).get(dues_record_id)

        if not dues_record:
            flash('Dues record not found.', 'danger')
            return redirect(url_for('members.dues', tenant_id=tenant_id))

        form = DuesUpdateForm(obj=dues_record)

        if form.validate_on_submit():
            dues_record.dues_amount = form.dues_amount.data
            dues_record.due_date = form.due_date.data
            s.commit()
            flash('Dues record updated successfully!', 'success')
            return redirect(url_for('members.dues', tenant_id=tenant_id))

        return render_template('dues_update.html', tenant_id=tenant_id, form=form, dues_record=dues_record)


@members_bp.route('/dues/<tenant_id>/generate', methods=['GET', 'POST'])
def generate_dues(tenant_id):
    if 'user_id' not in session or session['tenant_id'] != tenant_id:
        flash("You must be logged in to view this page.", "danger")
        return redirect(url_for('auth.login', tenant_id=tenant_id))

    # Check if user has permission to create dues records
    user_permissions = session.get('user_permissions', {})
    if not user_permissions.get('can_edit_dues', False):
        flash("You do not have permission to generate dues records.", "danger")
        return redirect(url_for('members.dues', tenant_id=tenant_id))

    tenant_display_name = Config.TENANT_DISPLAY_NAMES.get(tenant_id, tenant_id.capitalize())

    with get_tenant_db_session(tenant_id) as s:
        # Get all active dues types
        dues_types = s.query(DuesType).filter_by(is_active=True).order_by(DuesType.dues_type).all()

        if request.method == 'POST':
            try:
                dues_type_id = request.form.get('dues_type_id')
                amount_due = request.form.get('amount_due')
                due_date_str = request.form.get('due_date')

                if not dues_type_id or not amount_due or not due_date_str:
                    flash("All fields are required.", "danger")
                    return redirect(url_for('members.generate_dues', tenant_id=tenant_id))

                # Parse amount and date
                try:
                    amount_due = float(amount_due)
                    due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
                except ValueError:
                    flash("Invalid amount or date format.", "danger")
                    return redirect(url_for('members.generate_dues', tenant_id=tenant_id))

                # Get all active users
                all_users = s.query(User).filter_by(is_active=True).order_by(User.first_name, User.last_name).all()

                records_created = 0
                for user in all_users:
                    # Check if user was selected (checkbox checked)
                    user_selected = request.form.get(f'select_{user.id}') == 'on'

                    if user_selected:
                        # Check if dues record already exists for this user, dues type, and due date
                        existing_record = s.query(DuesRecord).filter_by(
                            member_id=user.id,
                            dues_type_id=dues_type_id,
                            due_date=due_date
                        ).first()

                        if existing_record:
                            # Update existing record
                            existing_record.dues_amount = amount_due
                            existing_record.date_dues_generated = date.today()
                        else:
                            # Create new record
                            new_record = DuesRecord(
                                member_id=user.id,
                                dues_amount=amount_due,
                                dues_type_id=dues_type_id,
                                due_date=due_date,
                                date_dues_generated=date.today()
                            )
                            s.add(new_record)
                            records_created += 1

                s.commit()
                flash(f"Dues generated successfully! {records_created} new records created.", "success")

            except Exception as e:
                s.rollback()
                flash(f"Failed to generate dues: {str(e)}", "danger")

            return redirect(url_for('members.generate_dues', tenant_id=tenant_id))

        # GET request - show the form
        all_users = s.query(User).filter_by(is_active=True).order_by(User.first_name, User.last_name).all()

        return render_template('dues_create.html',
                             tenant_id=tenant_id,
                             tenant_display_name=tenant_display_name,
                             all_users=all_users,
                             dues_types=dues_types)


@members_bp.route('/dues/<tenant_id>/collection', methods=['GET', 'POST'])
def dues_collection(tenant_id):
    if 'user_id' not in session or session['tenant_id'] != tenant_id:
        flash("You must be logged in to view this page.", "danger")
        return redirect(url_for('auth.login', tenant_id=tenant_id))

    # Check if user has permission to manage dues
    user_permissions = session.get('user_permissions', {})
    if not user_permissions.get('can_edit_dues', False):
        flash("You do not have permission to manage dues collection.", "danger")
        return redirect(url_for('members.dues', tenant_id=tenant_id))

    tenant_display_name = Config.TENANT_DISPLAY_NAMES.get(tenant_id, tenant_id.capitalize())

    with get_tenant_db_session(tenant_id) as s:
        if request.method == 'POST':
            try:
                # Process bulk payment updates for selected members
                dues_records = s.query(DuesRecord).join(User).join(DuesType).filter(
                    DuesRecord.amount_paid < DuesRecord.dues_amount
                ).all()
                payments_processed = 0

                for record in dues_records:
                    # Check if this record was selected for payment
                    selected = request.form.get(f'select_{record.id}') == 'on'
                    payment_amount_str = request.form.get(f'payment_{record.id}')

                    if selected and payment_amount_str:
                        try:
                            payment_amount = float(payment_amount_str)
                            if payment_amount > 0:
                                # Add payment to existing amount paid
                                record.amount_paid += payment_amount
                                # Set payment date if not already set
                                if not record.payment_received_date:
                                    record.payment_received_date = date.today()
                                payments_processed += 1
                        except ValueError:
                            continue  # Skip invalid payment amounts

                s.commit()
                flash(f"Payments processed successfully! {payments_processed} payment(s) recorded.", "success")

            except Exception as e:
                s.rollback()
                flash(f"Failed to process payments: {str(e)}", "danger")

            return redirect(url_for('members.dues_collection', tenant_id=tenant_id))

        # GET request - show outstanding dues for collection
        # Get dues records with outstanding balances, ordered by: open balance first, then due date, then user name
        dues_records = s.query(DuesRecord).join(User).join(DuesType).filter(
            DuesRecord.amount_paid < DuesRecord.dues_amount
        ).order_by(
            DuesRecord.amount_paid < DuesRecord.dues_amount,  # Open dues first
            DuesRecord.due_date,
            User.last_name,
            User.first_name
        ).all()

        return render_template('dues_collection.html',
                             tenant_id=tenant_id,
                             tenant_display_name=tenant_display_name,
                             dues_records=dues_records)


@members_bp.route('/dues/<tenant_id>/history')
def my_dues_history(tenant_id):
    if 'user_id' not in session or session['tenant_id'] != tenant_id:
        flash("You must be logged in to view this page.", "danger")
        return redirect(url_for('auth.login', tenant_id=tenant_id))

    tenant_display_name = Config.TENANT_DISPLAY_NAMES.get(tenant_id, tenant_id.capitalize())
    current_user_id = session['user_id']

    with get_tenant_db_session(tenant_id) as s:
        current_user = s.query(User).options(joinedload(User.auth_details)).filter_by(id=current_user_id).first()
        if not current_user:
            session.clear()
            flash("User not found.", "danger")
            return redirect(url_for('auth.login', tenant_id=tenant_id))

        # Check if user can view all dues or just their own
        can_manage_dues = current_user.auth_details and current_user.auth_details.can_edit_dues

        if can_manage_dues:
            # Show all dues records for privileged users
            dues_query = s.query(DuesRecord, DuesType).join(DuesType).join(DuesRecord.member)
            page_title = "All Dues History"
        else:
            # Show only current user's dues
            dues_query = s.query(DuesRecord, DuesType).join(DuesType).join(DuesRecord.member).filter(DuesRecord.member_id == current_user_id)
            page_title = "My Dues History"

        # Order by: unpaid dues first (by due date), then paid dues (by due date), then by name
        my_dues = dues_query.order_by(
            DuesRecord.amount_paid >= DuesRecord.dues_amount,  # Unpaid first, paid last
            DuesRecord.due_date.asc(),  # Earliest due dates first within each group
            DuesRecord.member.last_name,
            DuesRecord.member.first_name
        ).all()

        return render_template('my_dues_history.html',
                             tenant_id=tenant_id,
                             tenant_display_name=tenant_display_name,
                             my_dues=my_dues,
                             can_manage_dues=can_manage_dues,
                             page_title=page_title)


@members_bp.route('/dues/<tenant_id>/member/<int:member_id>/history')
def member_dues_history(tenant_id, member_id):
    if 'user_id' not in session or session['tenant_id'] != tenant_id:
        flash("You must be logged in to view this page.", "danger")
        return redirect(url_for('auth.login', tenant_id=tenant_id))

    # Check if user has permission to view member dues
    user_permissions = session.get('user_permissions', {})
    if not user_permissions.get('can_edit_dues', False):
        flash("You do not have permission to view member dues history.", "danger")
        return redirect(url_for('members.my_dues_history', tenant_id=tenant_id))

    tenant_display_name = Config.TENANT_DISPLAY_NAMES.get(tenant_id, tenant_id.capitalize())

    with get_tenant_db_session(tenant_id) as s:
        # Get the selected member
        selected_member = s.query(User).filter_by(id=member_id).first()
        if not selected_member:
            flash("Member not found.", "danger")
            return redirect(url_for('members.my_dues_history', tenant_id=tenant_id))

        # Get member's dues records
        member_dues = s.query(DuesRecord, DuesType).join(DuesType).filter(
            DuesRecord.member_id == member_id
        ).order_by(DuesRecord.due_date.desc()).all()

        # Calculate summary
        total_due = sum(record.dues_amount for record, _ in member_dues)
        total_paid = sum(record.amount_paid for record, _ in member_dues)
        total_balance = total_due - total_paid

        return render_template('member_dues_history.html',
                             tenant_id=tenant_id,
                             tenant_display_name=tenant_display_name,
                             selected_member=selected_member,
                             member_dues=member_dues,
                             total_due=total_due,
                             total_paid=total_paid,
                             total_balance=total_balance)
