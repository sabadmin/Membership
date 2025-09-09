# app/members/routes.py

from flask import Blueprint, request, render_template, redirect, url_for, session, flash, g
from config import Config
from database import get_tenant_db_session
from app.models import User, UserAuthDetails, AttendanceRecord, MembershipType, DuesRecord, DuesType
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
                           format_phone_number=_format_phone)

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


@members_bp.route('/attendance/<tenant_id>/create', methods=['GET', 'POST'])
def attendance_create(tenant_id):
    if 'user_id' not in session or session['tenant_id'] != tenant_id:
        flash("You must be logged in to view this page.", "danger")
        return redirect(url_for('auth.login', tenant_id=tenant_id))
    
    # Check if user has permission to create attendance
    with get_tenant_db_session(tenant_id) as s:
        current_user = s.query(User).options(joinedload(User.membership_type)).filter_by(id=session['user_id']).first()
        if not current_user or not current_user.membership_type or not current_user.membership_type.can_edit_attendance:
            # Redirect to personal attendance history instead of showing warning
            return redirect(url_for('members.attendance_history', tenant_id=tenant_id))
    
    return _attendance_view(tenant_id, editable=True)


@members_bp.route('/attendance/<tenant_id>/history', methods=['GET', 'POST'])
def attendance_history(tenant_id):
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        logger.info(f"Starting attendance_history for tenant: {tenant_id}")
        
        if 'user_id' not in session or session['tenant_id'] != tenant_id:
            flash("You must be logged in to view this page.", "danger")
            return redirect(url_for('auth.login', tenant_id=tenant_id))
        
        tenant_display_name = Config.TENANT_DISPLAY_NAMES.get(tenant_id, tenant_id.capitalize())
        
        # Get selected date from form or default to today
        from datetime import date, datetime
        selected_date = date.today()
        
        if request.method == 'POST':
            date_str = request.form.get('selected_date')
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
            can_view_all = current_user and current_user.membership_type and current_user.membership_type.can_edit_attendance
            logger.info(f"User membership type: {current_user.membership_type.name if current_user.membership_type else 'None'}, can_view_all: {can_view_all}")
            
            if can_view_all:
                # Show all users for privileged users
                all_users = s.query(User).options(joinedload(User.membership_type)).order_by(User.first_name, User.last_name).all()
                page_title = "Attendance History - All Members"
            else:
                # Show only current user for regular members
                all_users = [current_user] if current_user else []
                page_title = "My Attendance History"
            
            logger.info(f"Retrieved {len(all_users)} users")
            
            # Get attendance records for the selected date
            attendance_records = s.query(AttendanceRecord).filter(
                AttendanceRecord.event_date == selected_date
            ).all()
            
            logger.info(f"Found {len(attendance_records)} attendance records for {selected_date}")
            
            # Create attendance dictionary and event names dictionary
            existing_attendance = {}
            event_names = {}  # Maps user_id to their specific event name
            default_event_name = "Meeting"  # Default for template compatibility
            
            for record in attendance_records:
                existing_attendance[record.user_id] = record.status
                event_names[record.user_id] = record.event_name  # Store individual event names
                default_event_name = record.event_name  # Keep last one as fallback
        
        logger.info("Rendering attendance_history.html template")
        return render_template('attendance_history.html',
                             tenant_id=tenant_id,
                             tenant_display_name=tenant_display_name,
                             all_users=all_users,
                             existing_attendance=existing_attendance,
                             selected_date=selected_date.strftime('%Y-%m-%d'),
                             event_name=default_event_name,  # Keep for compatibility
                             event_names=event_names,  # Individual event names per user
                             can_view_all=can_view_all,
                             page_title=page_title)
                             
    except Exception as e:
        logger.error(f"Error in attendance_history: {str(e)}")
        logger.error(f"Error type: {type(e).__name__}")
        flash("An error occurred while retrieving attendance history.", "danger")
        return redirect(url_for('members.my_demographics', tenant_id=tenant_id))

def _attendance_view(tenant_id, editable=True):
    """Common attendance view logic"""
    tenant_display_name = Config.TENANT_DISPLAY_NAMES.get(tenant_id, tenant_id.capitalize())
    
    with get_tenant_db_session(tenant_id) as s:
        # Get all users for attendance matrix
        all_users = s.query(User).order_by(User.first_name, User.last_name).all()
        
        if request.method == 'POST' and editable:
            try:
                event_date = request.form.get('event_date')
                event_name = request.form.get('event_name', 'Meeting')
                
                if not event_date:
                    flash("Event date is required.", "danger")
                    return redirect(url_for('members.attendance_create', tenant_id=tenant_id))
                
                # Parse the date
                from datetime import datetime
                try:
                    parsed_date = datetime.strptime(event_date, '%Y-%m-%d')
                except ValueError:
                    flash("Invalid date format.", "danger")
                    return redirect(url_for('members.attendance_create', tenant_id=tenant_id))
                
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
            
            return redirect(url_for('members.attendance_create', tenant_id=tenant_id))
        
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
            
        return render_template('attendance_matrix.html',
                             tenant_id=tenant_id,
                             tenant_display_name=tenant_display_name,
                             all_users=all_users,
                             existing_attendance=existing_attendance,
                             today=today.strftime('%Y-%m-%d'),
                             editable=editable)

@members_bp.route('/dues/<tenant_id>')
def dues(tenant_id):
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        logger.info(f"Starting dues route for tenant: {tenant_id}")
        
        if 'user_id' not in session or session['tenant_id'] != tenant_id:
            flash("You must be logged in to view this page.", "danger")
            return redirect(url_for('auth.login', tenant_id=tenant_id))
        
        with get_tenant_db_session(tenant_id) as s:
            logger.info("Database session opened successfully")
            current_user = s.query(User).options(joinedload(User.membership_type)).filter_by(id=session['user_id']).first()
            if not current_user:
                flash("User not found.", "danger")
                return redirect(url_for('auth.login', tenant_id=tenant_id))
            
            # Check if user has permission to manage dues
            can_manage_dues = current_user and current_user.membership_type and current_user.membership_type.can_edit_dues
            logger.info(f"User can manage dues: {can_manage_dues}")
            
            # Show dues management interface directly for privileged users
            # Show dues history for regular users
            tenant_display_name = Config.TENANT_DISPLAY_NAMES.get(tenant_id, tenant_id.capitalize())
            
            if can_manage_dues:
                # Get all users for dues generation
                all_users = s.query(User).order_by(User.last_name, User.first_name).all()
                
                # Get dues types from auxiliary table
                dues_types = []
                try:
                    dt_list = s.query(DuesType).filter_by(is_active=True).order_by(DuesType.sort_order, DuesType.name).all()
                    dues_types = [{'id': dt.id, 'name': dt.name} for dt in dt_list]
                    logger.info(f"Found {len(dues_types)} dues types from auxiliary table")
                except Exception as dt_error:
                    logger.error(f"Error loading dues types: {str(dt_error)}")
                    dues_types = []
                
                logger.info("Rendering dues_management.html directly")
                return render_template('dues_management.html',
                                     tenant_id=tenant_id,
                                     tenant_display_name=tenant_display_name,
                                     dues_data=[],  # Empty for now
                                     dues_types=dues_types,
                                     all_users=all_users,
                                     can_manage_dues=True)
            else:
                # Regular users: redirect to dues history to see their own dues
                return redirect(url_for('members.my_dues_history', tenant_id=tenant_id))
                
    except Exception as e:
        logger.error(f"Error in dues route: {str(e)}")
        logger.error(f"Error type: {type(e).__name__}")
        flash("An error occurred while accessing dues. Please contact administrator.", "danger")
        return redirect(url_for('auth.index'))

@members_bp.route('/dues/<tenant_id>/management')
def dues_management(tenant_id):
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        logger.info(f"Starting dues_management route for tenant: {tenant_id}")
        
        if 'user_id' not in session or session['tenant_id'] != tenant_id:
            flash("You must be logged in to view this page.", "danger")
            return redirect(url_for('auth.login', tenant_id=tenant_id))
        
        with get_tenant_db_session(tenant_id) as s:
            logger.info("Database session opened successfully")
            current_user = s.query(User).options(joinedload(User.membership_type)).filter_by(id=session['user_id']).first()
            if not current_user or not current_user.membership_type or not current_user.membership_type.can_edit_dues:
                flash("You do not have permission to manage dues.", "danger")
                return redirect(url_for('members.my_dues_history', tenant_id=tenant_id))
            
            # Create simple dues types list for dropdown
            dues_types = [
                {'id': 'A', 'name': 'Annual'},
                {'id': 'Q', 'name': 'Quarterly'},
                {'id': 'F', 'name': 'Assessment'}
            ]
            logger.info("Created simple dues types list")
            
            # Get all users first
            all_users = s.query(User).order_by(User.last_name, User.first_name).all()
            logger.info(f"Found {len(all_users)} users")
            
            # For now, create empty dues data to avoid schema errors
            # This allows the page to load while migration is pending
            dues_data = []
            
            # Try to get dues records if they exist
            try:
                dues_records = s.query(DuesRecord).all()
                logger.info(f"Found {len(dues_records)} dues records")
                
                # Create simple data structure with legacy support
                for user in all_users:
                    user_dues = [d for d in dues_records if d.user_id == user.id]
                    if user_dues:
                        for dues in user_dues:
                            # Use old dues_type field if it exists
                            dues_type_name = getattr(dues, 'dues_type', 'Legacy')
                            mock_dues_type = type('MockDuesType', (), {'name': dues_type_name})()
                            dues_data.append((user, dues, mock_dues_type))
                
                logger.info(f"Created dues_data with {len(dues_data)} entries")
                
            except Exception as query_error:
                logger.error(f"Error querying dues records: {str(query_error)}")
                # Show users without dues for now
                dues_data = [(user, None, None) for user in all_users[:5]]  # Limit to prevent template errors
        
        tenant_display_name = Config.TENANT_DISPLAY_NAMES.get(tenant_id, tenant_id.capitalize())
        logger.info("Rendering dues_management.html")
        return render_template('dues_management.html',
                             tenant_id=tenant_id,
                             tenant_display_name=tenant_display_name,
                             dues_data=dues_data,
                             dues_types=dues_types,
                             all_users=all_users,
                             can_manage_dues=True)
                             
    except Exception as e:
        logger.error(f"Error in dues_management route: {str(e)}")
        logger.error(f"Error type: {type(e).__name__}")
        flash("An error occurred while accessing dues management. Please contact administrator.", "danger")
        return redirect(url_for('auth.index'))

@members_bp.route('/dues/<tenant_id>/generate', methods=['POST'])
def generate_dues(tenant_id):
    if 'user_id' not in session or session['tenant_id'] != tenant_id:
        flash("You must be logged in to view this page.", "danger")
        return redirect(url_for('auth.login', tenant_id=tenant_id))
    
    with get_tenant_db_session(tenant_id) as s:
        current_user = s.query(User).options(joinedload(User.membership_type)).filter_by(id=session['user_id']).first()
        if not current_user or not current_user.membership_type or not current_user.membership_type.can_edit_dues:
            flash("You do not have permission to generate dues.", "danger")
            return redirect(url_for('members.my_dues_history', tenant_id=tenant_id))
        
        try:
            dues_type_id = request.form.get('dues_type_id')
            amount_due = request.form.get('amount_due')
            due_date_str = request.form.get('due_date')
            
            if not all([dues_type_id, amount_due, due_date_str]):
                flash("All fields are required for dues generation.", "danger")
                return redirect(url_for('members.dues_management', tenant_id=tenant_id))
            
            # Parse date
            from datetime import datetime
            try:
                due_date = datetime.strptime(due_date_str, '%Y-%m-%d')
            except ValueError:
                flash("Invalid date format.", "danger")
                return redirect(url_for('members.dues_management', tenant_id=tenant_id))
            
            # Validate amount
            try:
                amount = float(amount_due)
                if amount <= 0:
                    raise ValueError("Amount must be positive")
            except ValueError:
                flash("Invalid amount.", "danger")
                return redirect(url_for('members.dues_management', tenant_id=tenant_id))
            
            # Get all active users
            all_users = s.query(User).all()
            
            # Create dues records for all users (using existing schema)
            records_created = 0
            
            for user in all_users:
                # Check if user already has this type of dues for this date (using foreign key)
                existing_record = s.query(DuesRecord).filter_by(
                    user_id=user.id,
                    dues_type_id=dues_type_id,  # This is now the foreign key ID
                    due_date=due_date
                ).first()
                
                if not existing_record:
                    # Create new record using foreign key
                    new_dues = DuesRecord(
                        user_id=user.id,
                        dues_type_id=dues_type_id,  # Store the foreign key ID
                        amount_due=amount,  # Use decimal amount
                        due_date=due_date,
                        status='unpaid'
                    )
                    s.add(new_dues)
                    records_created += 1
            
            s.commit()
            flash(f"Generated {records_created} dues records successfully.", "success")
            
        except Exception as e:
            s.rollback()
            flash(f"Error generating dues: {str(e)}", "danger")
    
    return redirect(url_for('members.dues_management', tenant_id=tenant_id))

@members_bp.route('/dues/<tenant_id>/my-history')
def my_dues_history(tenant_id):
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        logger.info(f"Starting my_dues_history route for tenant: {tenant_id}")
        
        if 'user_id' not in session or session['tenant_id'] != tenant_id:
            flash("You must be logged in to view this page.", "danger")
            return redirect(url_for('auth.login', tenant_id=tenant_id))
        
        with get_tenant_db_session(tenant_id) as s:
            logger.info("Database session opened successfully")
            current_user = s.query(User).options(joinedload(User.membership_type)).filter_by(id=session['user_id']).first()
            if not current_user:
                flash("User not found.", "danger")
                return redirect(url_for('auth.login', tenant_id=tenant_id))
            
            # Check user permissions first
            can_manage_dues = current_user.membership_type and current_user.membership_type.can_edit_dues if current_user.membership_type else False
            logger.info(f"User can manage dues: {can_manage_dues}")
            
            # Get dues records based on user permissions
            my_dues = []
            try:
                # Use raw SQL to bypass any model issues
                from sqlalchemy import text
                
                if can_manage_dues:
                    # Privileged users: get ALL dues records from all users with proper joins including User
                    logger.info("Querying ALL dues records for privileged user with joins...")
                    my_dues_query = s.query(DuesRecord, DuesType).join(
                        DuesType, DuesRecord.dues_type_id == DuesType.id
                    ).join(
                        User, DuesRecord.user_id == User.id
                    ).options(
                        joinedload(DuesRecord.user)
                    ).order_by(DuesRecord.due_date.desc()).all()
                    logger.info(f"Found {len(my_dues_query)} total dues records")
                    my_dues = my_dues_query
                else:
                    # Regular users: get only their own dues records with joins
                    logger.info("Querying dues records for current user with joins...")
                    my_dues_query = s.query(DuesRecord, DuesType).join(
                        DuesType, DuesRecord.dues_type_id == DuesType.id
                    ).filter(
                        DuesRecord.user_id == current_user.id
                    ).order_by(DuesRecord.due_date.desc()).all()
                    logger.info(f"Found {len(my_dues_query)} dues records for user")
                    my_dues = my_dues_query
                    
            except Exception as dues_error:
                logger.error(f"Error querying dues records: {str(dues_error)}")
                # Return empty list but don't show error message
                my_dues = []
        
        tenant_display_name = Config.TENANT_DISPLAY_NAMES.get(tenant_id, tenant_id.capitalize())
        logger.info("Rendering my_dues_history.html")
        return render_template('my_dues_history.html',
                             tenant_id=tenant_id,
                             tenant_display_name=tenant_display_name,
                             my_dues=my_dues,
                             current_user=current_user,
                             can_manage_dues=can_manage_dues)
                             
    except Exception as e:
        logger.error(f"Error in my_dues_history route: {str(e)}")
        logger.error(f"Error type: {type(e).__name__}")
        
        # Show error page instead of redirecting
        tenant_display_name = Config.TENANT_DISPLAY_NAMES.get(tenant_id, tenant_id.capitalize())
        flash("Dues history is temporarily unavailable. Please try again later or contact administrator.", "warning")
        return render_template('my_dues_history.html',
                             tenant_id=tenant_id,
                             tenant_display_name=tenant_display_name,
                             my_dues=[],  # Empty list
                             current_user=None,
                             can_manage_dues=False)

@members_bp.route('/dues/<tenant_id>/member/<int:member_id>')
def member_dues_history(tenant_id, member_id):
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        logger.info(f"Starting member_dues_history route for tenant: {tenant_id}, member: {member_id}")
        
        if 'user_id' not in session or session['tenant_id'] != tenant_id:
            flash("You must be logged in to view this page.", "danger")
            return redirect(url_for('auth.login', tenant_id=tenant_id))
        
        with get_tenant_db_session(tenant_id) as s:
            logger.info("Database session opened successfully")
            current_user = s.query(User).options(joinedload(User.membership_type)).filter_by(id=session['user_id']).first()
            if not current_user or not current_user.membership_type or not current_user.membership_type.can_edit_dues:
                flash("You do not have permission to view member dues history.", "danger")
                return redirect(url_for('members.my_dues_history', tenant_id=tenant_id))
            
            # Get selected member
            selected_member = s.query(User).filter_by(id=member_id).first()
            if not selected_member:
                flash("Member not found.", "danger")
                return redirect(url_for('members.dues_management', tenant_id=tenant_id))
            
            # Try to get member's dues records with schema compatibility
            member_dues = []
            try:
                logger.info("Attempting to query member dues records with new schema...")
                member_dues = s.query(DuesRecord, DuesType).join(
                    DuesType, DuesRecord.dues_type_id == DuesType.id
                ).filter(
                    DuesRecord.user_id == member_id
                ).order_by(
                    DuesRecord.due_date.desc()
                ).all()
                logger.info(f"Found {len(member_dues)} dues records with new schema")
            except Exception as schema_error:
                logger.warning(f"New schema query failed: {str(schema_error)}")
                
                # Fallback to old schema or simple query
                try:
                    logger.info("Attempting fallback query...")
                    dues_records = s.query(DuesRecord).filter_by(user_id=member_id).all()
                    logger.info(f"Found {len(dues_records)} dues records with fallback query")
                    
                    # Create mock data for template compatibility
                    member_dues = []
                    for record in dues_records:
                        # Create simple dues type name from record
                        dues_type_name = record.dues_type_name if hasattr(record, 'dues_type_name') else getattr(record, 'dues_type', 'Unknown')
                        mock_dues_type = type('MockDuesType', (), {
                            'name': dues_type_name,
                            'description': f'{dues_type_name} dues'
                        })()
                        member_dues.append((record, mock_dues_type))
                        
                except Exception as fallback_error:
                    logger.error(f"Fallback query also failed: {str(fallback_error)}")
                    member_dues = []
        
        tenant_display_name = Config.TENANT_DISPLAY_NAMES.get(tenant_id, tenant_id.capitalize())
        logger.info("Rendering member_dues_history.html")
        return render_template('member_dues_history.html',
                             tenant_id=tenant_id,
                             tenant_display_name=tenant_display_name,
                             member_dues=member_dues,
                             selected_member=selected_member,
                             can_manage_dues=True)
                             
    except Exception as e:
        logger.error(f"Error in member_dues_history route: {str(e)}")
        logger.error(f"Error type: {type(e).__name__}")
        flash("Member dues history temporarily unavailable. Please contact administrator.", "danger")
        return redirect(url_for('auth.index'))

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
