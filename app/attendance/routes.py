import logging
from flask import Blueprint, request, render_template, redirect, url_for, session, flash, g
from config import Config
from database import get_tenant_db_session
from app.models import User, AttendanceRecord, AttendanceType
from sqlalchemy.orm import joinedload
from datetime import date, datetime
from sqlalchemy import func
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
