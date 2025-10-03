import logging
from flask import Blueprint, request, render_template, redirect, url_for, session, flash, g, Response
from config import Config
from database import get_tenant_db_session
from app.models import User, AttendanceRecord, AttendanceType
from sqlalchemy.orm import joinedload
from datetime import date, datetime
from sqlalchemy import func
from io import StringIO, BytesIO
import csv
from . import attendance_bp

logger = logging.getLogger(__name__)


@attendance_bp.route('/<tenant_id>/history', methods=['GET', 'POST'])
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
                # For privileged users, only show users who have attendance records for this date
                users_with_records = s.query(AttendanceRecord.user_id).filter(
                    AttendanceRecord.event_date == selected_date
                ).distinct().subquery()

                all_users = s.query(User).options(joinedload(User.membership_type)).join(
                    users_with_records, User.id == users_with_records.c.user_id
                ).order_by(User.first_name, User.last_name).all()
                page_title = f"Attendance History - {len(all_users)} Members"
            else:
                # Show only current user for regular members (only if they have a record for this date)
                has_record = s.query(AttendanceRecord).filter(
                    AttendanceRecord.event_date == selected_date,
                    AttendanceRecord.user_id == current_user.id
                ).first() is not None

                all_users = [current_user] if current_user and has_record else []
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
                        # Re-check if user has records for the new date (for non-privileged users)
                        if not can_view_all:
                            has_record = s.query(AttendanceRecord).filter(
                                AttendanceRecord.event_date == selected_date,
                                AttendanceRecord.user_id == current_user.id
                            ).first() is not None
                            if not has_record:
                                all_users = []

            # Check for available navigation dates before handling navigation actions
            has_prev_records = False
            has_next_records = False

            if can_view_all:
                # Privileged users: Check for any attendance records before/after current date
                prev_check = s.query(AttendanceRecord.event_date).filter(
                    AttendanceRecord.event_date < selected_date
                ).first()
                next_check = s.query(AttendanceRecord.event_date).filter(
                    AttendanceRecord.event_date > selected_date
                ).first()
            else:
                # Non-privileged users: Check for attendance records for current user only
                prev_check = s.query(AttendanceRecord.event_date).filter(
                    AttendanceRecord.event_date < selected_date,
                    AttendanceRecord.user_id == current_user.id
                ).first()
                next_check = s.query(AttendanceRecord.event_date).filter(
                    AttendanceRecord.event_date > selected_date,
                    AttendanceRecord.user_id == current_user.id
                ).first()

            has_prev_records = prev_check is not None
            has_next_records = next_check is not None

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
                        # Update user list for the new date (for non-privileged users)
                        if not can_view_all:
                            has_record = s.query(AttendanceRecord).filter(
                                AttendanceRecord.event_date == selected_date,
                                AttendanceRecord.user_id == current_user.id
                            ).first() is not None
                            all_users = [current_user] if current_user and has_record else []
                        # Re-check navigation availability after moving
                        has_prev_records = True  # We just moved from a previous date
                        if can_view_all:
                            next_check = s.query(AttendanceRecord.event_date).filter(
                                AttendanceRecord.event_date > selected_date
                            ).first()
                        else:
                            next_check = s.query(AttendanceRecord.event_date).filter(
                                AttendanceRecord.event_date > selected_date,
                                AttendanceRecord.user_id == current_user.id
                            ).first()
                        has_next_records = next_check is not None
                    # No flash message for no further history

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
                        # Update user list for the new date (for non-privileged users)
                        if not can_view_all:
                            has_record = s.query(AttendanceRecord).filter(
                                AttendanceRecord.event_date == selected_date,
                                AttendanceRecord.user_id == current_user.id
                            ).first() is not None
                            all_users = [current_user] if current_user and has_record else []
                        # Re-check navigation availability after moving
                        has_next_records = True  # We just moved from a next date
                        if can_view_all:
                            prev_check = s.query(AttendanceRecord.event_date).filter(
                                AttendanceRecord.event_date < selected_date
                            ).first()
                        else:
                            prev_check = s.query(AttendanceRecord.event_date).filter(
                                AttendanceRecord.event_date < selected_date,
                                AttendanceRecord.user_id == current_user.id
                            ).first()
                        has_prev_records = prev_check is not None
                    # No flash message for no further history

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
                             page_title=page_title,
                             has_prev_records=has_prev_records,
                             has_next_records=has_next_records)

    except Exception as e:
        logger.error(f"Error in attendance_history: {str(e)}")
        logger.error(f"Error type: {type(e).__name__}")
        flash("An error occurred while retrieving attendance history.", "danger")
        return redirect(url_for('members.my_demographics', tenant_id=tenant_id))


@attendance_bp.route('/<tenant_id>/create', methods=['GET', 'POST'])
def attendance_create(tenant_id):
    if 'user_id' not in session or session['tenant_id'] != tenant_id:
        flash("You must be logged in to view this page.", "danger")
        return redirect(url_for('auth.login', tenant_id=tenant_id))

    # Check if user has permission to create attendance records
    user_permissions = session.get('user_permissions', {})
    if not user_permissions.get('can_edit_attendance', False):
        flash("You do not have permission to create attendance records.", "danger")
        return redirect(url_for('attendance.attendance_history', tenant_id=tenant_id))

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
                    return redirect(url_for('attendance.attendance_create', tenant_id=tenant_id))

                # Parse the date
                try:
                    parsed_date = datetime.strptime(event_date, '%Y-%m-%d')
                except ValueError:
                    flash("Invalid date format.", "danger")
                    return redirect(url_for('attendance.attendance_create', tenant_id=tenant_id))

                # Check if we have AttendanceType table or need to use legacy mode
                use_legacy_mode = len(attendance_types) == 1 and hasattr(attendance_types[0], '_fields')

                if not use_legacy_mode and not attendance_type_id:
                    flash("Meeting type is required.", "danger")
                    return redirect(url_for('attendance.attendance_create', tenant_id=tenant_id))

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

            return redirect(url_for('attendance.attendance_create', tenant_id=tenant_id))

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


@attendance_bp.route('/<tenant_id>/pale_report_filter', methods=['GET', 'POST'])
def pale_report_filter(tenant_id):
   """
   Handle PALE report filter form and display.

   This function provides a secure interface for generating PALE (Present/Absent/Late/Excused)
   attendance reports with proper input validation and permission checks.
   """
   try:
       # Validate tenant_id parameter
       if not tenant_id or not isinstance(tenant_id, str):
           logger.warning(f"Invalid tenant_id parameter: {tenant_id}")
           flash("Invalid tenant identifier.", "danger")
           return redirect(url_for('auth.login', tenant_id=tenant_id))

       # Authenticate user session
       if 'user_id' not in session or session.get('tenant_id') != tenant_id:
           logger.warning(f"Unauthorized access attempt for tenant: {tenant_id}")
           flash("You must be logged in to view this page.", "danger")
           return redirect(url_for('auth.login', tenant_id=tenant_id))

       # Check user permissions for attendance reports
       user_permissions = session.get('user_permissions', {})
       if not user_permissions.get('can_edit_attendance', False):
           logger.warning(f"Permission denied for PALE report access - User ID: {session.get('user_id')}")
           flash("You do not have permission to view attendance reports.", "danger")
           return redirect(url_for('attendance.attendance_history', tenant_id=tenant_id))

       # Get tenant display name with fallback
       tenant_display_name = Config.TENANT_DISPLAY_NAMES.get(tenant_id, tenant_id.capitalize())

       if request.method == 'POST':
           # Validate and sanitize form inputs
           form_data = _validate_pale_report_form()
           if not form_data['is_valid']:
               flash(form_data['error_message'], "danger")
               return redirect(url_for('attendance.pale_report_filter', tenant_id=tenant_id))

           # Build secure query parameters
           query_params = _build_pale_report_query_params(form_data['data'])

           # Redirect to results page with validated parameters
           return redirect(url_for('attendance.pale_report', tenant_id=tenant_id) + '?' + query_params)

       # GET request - retrieve members for filter dropdown
       with get_tenant_db_session(tenant_id) as db_session:
           try:
               # Get all active members for the filter dropdown with proper error handling
               all_members = db_session.query(User).filter_by(is_active=True).order_by(
                   User.last_name, User.first_name
               ).all()

               # Log successful data retrieval
               logger.info(f"PALE report filter loaded successfully for tenant: {tenant_id}")

           except Exception as db_error:
               logger.error(f"Database error retrieving members for PALE report filter: {str(db_error)}")
               flash("Error retrieving member list. Please try again.", "danger")
               all_members = []

       return render_template('pale_report_filter.html',
                            tenant_id=tenant_id,
                            tenant_display_name=tenant_display_name,
                            all_members=all_members)

   except Exception as e:
       logger.error(f"Unexpected error in pale_report_filter for tenant {tenant_id}: {str(e)}")
       flash("An error occurred while loading the report filter.", "danger")
       return redirect(url_for('attendance.attendance_history', tenant_id=tenant_id))


def _validate_pale_report_form():
   """
   Validate and sanitize PALE report form inputs.

   Returns:
       dict: {'is_valid': bool, 'data': dict or 'error_message': str}
   """
   try:
       start_date = request.form.get('start_date', '').strip()
       end_date = request.form.get('end_date', '').strip()
       member_filter = request.form.get('member_filter', '').strip()
       output_format = request.form.get('output_format', 'pdf').strip()

       # Validate date formats if provided
       if start_date and not _is_valid_date_format(start_date):
           return {
               'is_valid': False,
               'error_message': "Invalid start date format. Please use YYYY-MM-DD format."
           }

       if end_date and not _is_valid_date_format(end_date):
           return {
               'is_valid': False,
               'error_message': "Invalid end date format. Please use YYYY-MM-DD format."
           }

       # Validate date range logic
       if start_date and end_date:
           start_dt = datetime.strptime(start_date, '%Y-%m-%d').date()
           end_dt = datetime.strptime(end_date, '%Y-%m-%d').date()
           if start_dt > end_dt:
               return {
                   'is_valid': False,
                   'error_message': "Start date must be before or equal to end date."
               }

       # Validate output format
       valid_formats = ['pdf', 'csv']
       if output_format not in valid_formats:
           return {
               'is_valid': False,
               'error_message': f"Invalid output format. Must be one of: {', '.join(valid_formats)}"
           }

       # Validate member_filter is either empty or a valid integer
       if member_filter:
           try:
               member_id = int(member_filter)
               if member_id <= 0:
                   return {
                       'is_valid': False,
                       'error_message': "Invalid member selection."
                   }
           except ValueError:
               return {
                   'is_valid': False,
                   'error_message': "Invalid member selection."
               }

       return {
           'is_valid': True,
           'data': {
               'start_date': start_date,
               'end_date': end_date,
               'member_filter': member_filter,
               'output_format': output_format
           }
       }

   except Exception as e:
       logger.error(f"Error validating PALE report form: {str(e)}")
       return {
           'is_valid': False,
           'error_message': "An error occurred while processing the form data."
       }


def _is_valid_date_format(date_string):
   """
   Validate date string format (YYYY-MM-DD).

   Args:
       date_string (str): Date string to validate

   Returns:
       bool: True if valid format, False otherwise
   """
   try:
       datetime.strptime(date_string, '%Y-%m-%d')
       return True
   except ValueError:
       return False


def _build_pale_report_query_params(form_data):
   """
   Build secure query parameters for PALE report.

   Args:
       form_data (dict): Validated form data

   Returns:
       str: URL-encoded query string
   """
   from urllib.parse import urlencode

   params = {}

   # Only include non-empty parameters
   if form_data.get('start_date'):
       params['start_date'] = form_data['start_date']
   if form_data.get('end_date'):
       params['end_date'] = form_data['end_date']
   if form_data.get('member_filter'):
       params['member_filter'] = form_data['member_filter']

   # Always include format, defaulting to pdf if not specified
   params['format'] = form_data.get('output_format', 'pdf')

   return urlencode(params)


@attendance_bp.route('/<tenant_id>/pale_report', methods=['GET', 'POST'])
def pale_report(tenant_id):
   try:
       if 'user_id' not in session or session['tenant_id'] != tenant_id:
           flash("You must be logged in to view this page.", "danger")
           return redirect(url_for('auth.login', tenant_id=tenant_id))

       # Check if user has permission to view attendance reports
       user_permissions = session.get('user_permissions', {})
       if not user_permissions.get('can_edit_attendance', False):
           flash("You do not have permission to view attendance reports.", "danger")
           return redirect(url_for('attendance.attendance_history', tenant_id=tenant_id))

       tenant_display_name = Config.TENANT_DISPLAY_NAMES.get(tenant_id, tenant_id.capitalize())

       # Get filter parameters
       start_date_str = request.args.get('start_date')
       end_date_str = request.args.get('end_date')
       member_filter = request.args.get('member_filter', '')  # member id or empty for all
       report_format = request.args.get('format', 'pdf')

       # Parse dates if provided
       start_date = None
       end_date = None
       if start_date_str:
           try:
               start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
           except ValueError:
               start_date = None
       if end_date_str:
           try:
               end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
           except ValueError:
               end_date = None

       with get_tenant_db_session(tenant_id) as s:
           # Get current user for report header
           current_user = s.query(User).get(session['user_id'])
           if not current_user:
               flash("User not found.", "danger")
               return redirect(url_for('auth.login', tenant_id=tenant_id))

           # Build attendance summary data
           attendance_summary = generate_pale_summary(s, start_date, end_date, member_filter)

           # Generate reports based on format
           if report_format == 'csv':
               return generate_pale_csv_report(attendance_summary, tenant_display_name, current_user, start_date, end_date)
           elif report_format == 'pdf':
               return generate_pale_pdf_report(attendance_summary, tenant_display_name, current_user, start_date, end_date)
           else:
               # Default to PDF download
               return generate_pale_pdf_report(attendance_summary, tenant_display_name, current_user, start_date, end_date)

   except Exception as e:
       logger.error(f"Error in pale_report: {str(e)}")
       flash("An error occurred while generating the PALE report.", "danger")
       return redirect(url_for('attendance.attendance_history', tenant_id=tenant_id))


def generate_pale_summary(db_session, start_date, end_date, member_filter):
   """Generate PALE attendance summary data"""
   try:
       # Query attendance records with filters
       query = db_session.query(AttendanceRecord).join(User)

       # Apply date range filter to event_date
       if start_date:
           query = query.filter(AttendanceRecord.event_date >= start_date)
       if end_date:
           query = query.filter(AttendanceRecord.event_date <= end_date)

       # Apply member filter if provided
       if member_filter:
           query = query.filter(AttendanceRecord.user_id == member_filter)

       attendance_records = query.all()

       # Group by member and aggregate attendance types
       member_summary = {}

       for record in attendance_records:
           member_id = record.user_id
           if member_id not in member_summary:
               member_summary[member_id] = {
                   'member': record.user,
                   'counts': {'P': 0, 'A': 0, 'L': 0, 'E': 0}
               }

           # Map attendance status to P/A/L/E codes
           status = record.status.upper()
           if status == 'PRESENT':
               member_summary[member_id]['counts']['P'] += 1
           elif status == 'ABSENT':
               member_summary[member_id]['counts']['A'] += 1
           elif status == 'LATE':
               member_summary[member_id]['counts']['L'] += 1
           elif status == 'EXCUSED':
               member_summary[member_id]['counts']['E'] += 1

       # Convert to list format for reporting
       summary_data = []
       for member_id, data in member_summary.items():
           member = data['member']
           counts = data['counts']

           # Get all phone numbers
           phone_numbers = []
           if hasattr(member, 'cell_phone') and member.cell_phone:
               phone_numbers.append(member.cell_phone)
           if hasattr(member, 'company_phone') and member.company_phone:
               phone_numbers.append(member.company_phone)

           summary_data.append({
               'member_name': f"{member.first_name} {member.last_name}",
               'company': getattr(member, 'company', ''),
               'phone_numbers': ', '.join(phone_numbers),
               'present_count': counts['P'],
               'absent_count': counts['A'],
               'late_count': counts['L'],
               'excused_count': counts['E']
           })

       # Sort by member name
       summary_data.sort(key=lambda x: x['member_name'])

       return summary_data

   except Exception as e:
       logger.error(f"Error generating PALE summary: {str(e)}")
       return []


def generate_pale_csv_report(summary_data, tenant_name, current_user, start_date, end_date):
   """Generate CSV report for PALE attendance summary"""
   output = StringIO()
   writer = csv.writer(output)

   # Write headers
   writer.writerow([tenant_name])
   writer.writerow(['PALE Attendance Report'])
   if start_date or end_date:
       date_range = ''
       if start_date:
           date_range += f'From {start_date}'
       if end_date:
           date_range += f' To {end_date}'
       writer.writerow([date_range])
   writer.writerow([f'{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'])
   writer.writerow([])  # Empty row

   # Write column headers
   writer.writerow(['Member Name', 'Company', 'Phone Numbers', 'P', 'A', 'L', 'E'])

   # Write data rows
   for record in summary_data:
       writer.writerow([
           record['member_name'],
           record['company'],
           record['phone_numbers'],
           record['present_count'],
           record['absent_count'],
           record['late_count'],
           record['excused_count']
       ])

   # Write summary
   writer.writerow([])  # Empty row
   total_present = sum(r['present_count'] for r in summary_data)
   total_absent = sum(r['absent_count'] for r in summary_data)
   total_late = sum(r['late_count'] for r in summary_data)
   total_excused = sum(r['excused_count'] for r in summary_data)
   total_records = len(summary_data)

   writer.writerow([f'Totals: {total_records} members, P: {total_present}, A: {total_absent}, L: {total_late}, E: {total_excused}'])

   # Prepare response
   output.seek(0)
   response = Response(
       output.getvalue(),
       mimetype='text/csv',
       headers={'Content-disposition': f'attachment; filename=pale_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'}
   )
   return response


def generate_pale_pdf_report(summary_data, tenant_name, current_user, start_date, end_date):
   """Generate PDF report for PALE attendance summary"""
   try:
       from reportlab.lib.pagesizes import letter
       from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
       from reportlab.lib.styles import getSampleStyleSheet
       from reportlab.lib import colors

       buffer = BytesIO()
       doc = SimpleDocTemplate(
           buffer,
           pagesize=letter,
           topMargin=0.75*72,
           bottomMargin=0.75*72,
           leftMargin=0.75*72,
           rightMargin=0.75*72
       )
       styles = getSampleStyleSheet()
       story = []

       # Title
       title = Paragraph(f"<para align='center'>{tenant_name}</para>", styles['Heading1'])
       story.append(title)
       story.append(Spacer(1, 1))

       # Report title
       report_title = Paragraph("<para align='center'>PALE Attendance Report</para>", styles['Heading2'])
       story.append(report_title)
       story.append(Spacer(1, 1))

       # Date range if provided
       if start_date or end_date:
           date_range_text = ''
           if start_date:
               date_range_text += f'From {start_date}'
           if end_date:
               date_range_text += f' To {end_date}'
           date_range = Paragraph(f"<para align='center'>{date_range_text}</para>", styles['Normal'])
           story.append(date_range)
           story.append(Spacer(1, 1))

       # Generation info
       gen_info = Paragraph(f"<para align='center'>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</para>", styles['Normal'])
       story.append(gen_info)
       story.append(Spacer(1, 3))

       # Table data
       data = [['Member Name', 'Company', 'Phone Numbers', 'P', 'A', 'L', 'E']]

       for record in summary_data:
           data.append([
               record['member_name'],
               record['company'],
               record['phone_numbers'],
               str(record['present_count']),
               str(record['absent_count']),
               str(record['late_count']),
               str(record['excused_count'])
           ])

       # Summary row
       total_present = sum(r['present_count'] for r in summary_data)
       total_absent = sum(r['absent_count'] for r in summary_data)
       total_late = sum(r['late_count'] for r in summary_data)
       total_excused = sum(r['excused_count'] for r in summary_data)
       total_members = len(summary_data)

       data.append([
           f'Totals: {total_members} members',
           '',
           '',
           str(total_present),
           str(total_absent),
           str(total_late),
           str(total_excused)
       ])

       # Create table
       table = Table(data)
       table.setStyle(TableStyle([
           ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
           ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
           ('FONTSIZE', (0, 0), (-1, 0), 14),
           ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
           ('FONTSIZE', (0, 1), (-1, -2), 12),
           ('BOTTOMPADDING', (0, 1), (-1, -2), 8),
           ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
           ('FONTSIZE', (0, -1), (-1, -1), 12),
           ('BOTTOMPADDING', (0, -1), (-1, -1), 8)
       ]))

       story.append(table)

       # Build PDF
       doc.build(story)

       # Prepare response
       buffer.seek(0)
       response = Response(
           buffer.getvalue(),
           mimetype='application/pdf',
           headers={'Content-disposition': f'attachment; filename=pale_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'}
       )
       return response

   except ImportError:
       error_response = Response(
           "PDF generation requires reportlab library. Please install it first.",
           status=500,
           mimetype='text/plain'
       )
       return error_response
