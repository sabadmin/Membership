# app/members/routes.py

import logging
from flask import Blueprint, request, render_template, redirect, url_for, session, flash, g
from config import Config
from database import get_tenant_db_session
from app.models import User, UserAuthDetails, AttendanceRecord, AttendanceType, MembershipType, DuesRecord, DuesType
from app.utils import infer_tenant_from_hostname
from sqlalchemy.orm import joinedload
from datetime import date, datetime
from .forms import DuesCreateForm, DuesPaymentForm, DuesUpdateForm

logger = logging.getLogger(__name__)


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






@members_bp.route('/security/<tenant_id>', methods=['GET', 'POST'])
def security(tenant_id):
    try:
        if 'user_id' not in session or session['tenant_id'] != tenant_id:
            flash("You must be logged in to view this page.", "danger")
            return redirect(url_for('auth.login', tenant_id=tenant_id))

        current_user_id = session['user_id']
        current_user_auth_details = None
        user = None
        selected_user = None
        selected_user_auth_details = None
        all_users = []

        with get_tenant_db_session(tenant_id) as s:
            user = _get_current_user(s, current_user_id)
            if not user:
                session.clear()
                flash("User not found.", "danger")
                return redirect(url_for('auth.login', tenant_id=tenant_id))

            current_user_auth_details = user.auth_details

            # Check if current user can manage members (allows managing other users' privileges)
            can_manage_members = current_user_auth_details and current_user_auth_details.can_edit_members

            # Get all users for the dropdown (only if user can manage members)
            if can_manage_members:
                all_users = s.query(User).options(joinedload(User.auth_details)).order_by(User.last_name, User.first_name).all()

            # Get selected user (default to current user if no selection or not privileged)
            selected_user_id = request.args.get('user_id', current_user_id if not can_manage_members else None)
            if selected_user_id:
                selected_user = s.query(User).options(joinedload(User.auth_details)).filter_by(id=selected_user_id).first()
                if selected_user:
                    selected_user_auth_details = selected_user.auth_details

            if request.method == 'POST':
                # Handle password change (only for current user)
                if 'password' in request.form and not request.form.get('selected_user_id'):
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

                # Handle privilege and account management (for privileged users managing other users)
                elif can_manage_members and 'manage_user' in request.form:
                    selected_user_id = request.form.get('selected_user_id')
                    if selected_user_id:
                        target_user = s.query(User).options(joinedload(User.auth_details)).filter_by(id=selected_user_id).first()
                        if target_user:
                            try:
                                # Ensure target user has auth details
                                if not target_user.auth_details:
                                    from app.models import UserAuthDetails
                                    target_user.auth_details = UserAuthDetails(
                                        user_id=target_user.id,
                                        is_active=True
                                    )
                                    s.add(target_user.auth_details)

                                # Update privileges
                                target_user.auth_details.can_edit_dues = request.form.get('can_edit_dues') == 'on'
                                target_user.auth_details.can_edit_security = request.form.get('can_edit_security') == 'on'
                                target_user.auth_details.can_edit_referrals = request.form.get('can_edit_referrals') == 'on'
                                target_user.auth_details.can_edit_members = request.form.get('can_edit_members') == 'on'
                                target_user.auth_details.can_edit_attendance = request.form.get('can_edit_attendance') == 'on'

                                # Update account status
                                target_user.auth_details.is_active = request.form.get('is_active') == 'on'

                                s.commit()

                                # If updating current user's privileges, update session
                                if str(target_user.id) == str(current_user_id):
                                    session['user_permissions'] = {
                                        'can_edit_dues': target_user.auth_details.can_edit_dues,
                                        'can_edit_security': target_user.auth_details.can_edit_security,
                                        'can_edit_referrals': target_user.auth_details.can_edit_referrals,
                                        'can_edit_members': target_user.auth_details.can_edit_members,
                                        'can_edit_attendance': target_user.auth_details.can_edit_attendance
                                    }

                                flash(f"{target_user.first_name} {target_user.last_name}'s account has been updated successfully!", "success")

                                # Refresh selected user data
                                selected_user = target_user
                                selected_user_auth_details = target_user.auth_details

                            except Exception as e:
                                s.rollback()
                                flash(f"Failed to update user account: {str(e)}", "danger")
                        else:
                            flash("Selected user not found.", "danger")
                    else:
                        flash("No user selected for management.", "danger")

            return render_template('security.html',
                                   tenant_id=tenant_id,
                                   tenant_display_name=Config.TENANT_DISPLAY_NAMES.get(tenant_id, tenant_id.capitalize()),
                                   auth_details=current_user_auth_details,
                                   can_manage_members=can_manage_members,
                                   all_users=all_users,
                                   selected_user=selected_user,
                                   selected_user_auth_details=selected_user_auth_details)
    except Exception as e:
        logger.error(f"Error in security: {str(e)}")
        logger.error(f"Error type: {type(e).__name__}")
        flash(f"An error occurred while accessing security settings: {str(e)}", "danger")
        return redirect(url_for('members.my_demographics', tenant_id=tenant_id))
