import logging
from flask import Blueprint, request, render_template, redirect, url_for, session, flash, g, jsonify
from config import Config
from database import get_tenant_db_session
from app.models import User, ReferralRecord, ReferralType
from datetime import date, datetime
from sqlalchemy.orm import joinedload
from . import referrals_bp

logger = logging.getLogger(__name__)


@referrals_bp.route('/<tenant_id>/my')
def my_referrals(tenant_id):
    if 'user_id' not in session or session['tenant_id'] != tenant_id:
        flash("You must be logged in to view this page.", "danger")
        return redirect(url_for('auth.login', tenant_id=tenant_id))

    tenant_display_name = Config.TENANT_DISPLAY_NAMES.get(tenant_id, tenant_id.capitalize())
    current_user_id = session['user_id']

    with get_tenant_db_session(tenant_id) as s:
        # Get current user's referrals with related data
        my_referrals = s.query(ReferralRecord).options(
            joinedload(ReferralRecord.referral_type),
            joinedload(ReferralRecord.referred_member),
            joinedload(ReferralRecord.verified_by)
        ).filter_by(referrer_id=current_user_id).order_by(ReferralRecord.date_referred.desc()).all()

        # Calculate referral statistics
        total_referrals = len(my_referrals)
        verified_referrals = len([r for r in my_referrals if r.is_verified])
        pending_referrals = len([r for r in my_referrals if not r.is_verified])

        return render_template('my_referrals.html',
                             tenant_id=tenant_id,
                             tenant_display_name=tenant_display_name,
                             my_referrals=my_referrals,
                             total_referrals=total_referrals,
                             verified_referrals=verified_referrals,
                             pending_referrals=pending_referrals)


@referrals_bp.route('/<tenant_id>/add', methods=['GET', 'POST'])
def add_referral(tenant_id):
    if 'user_id' not in session or session['tenant_id'] != tenant_id:
        flash("You must be logged in to view this page.", "danger")
        return redirect(url_for('auth.login', tenant_id=tenant_id))

    tenant_display_name = Config.TENANT_DISPLAY_NAMES.get(tenant_id, tenant_id.capitalize())

    with get_tenant_db_session(tenant_id) as s:
        # Get all active referral types
        referral_types = s.query(ReferralType).filter_by(is_active=True).order_by(ReferralType.sort_order).all()

        # Get all active users for member selection (for "In Group" referrals)
        all_users = s.query(User).filter_by(is_active=True).order_by(User.first_name, User.last_name).all()

        # Get prior referrals for subscription type dropdown
        prior_referrals = s.query(ReferralRecord).options(
            joinedload(ReferralRecord.referred_member)
        ).filter_by(referrer_id=session['user_id']).order_by(ReferralRecord.date_referred.desc()).all()

        if request.method == 'POST':
            try:
                # Get form data
                referral_type_id = request.form.get('referral_type_id')
                referral_level = request.form.get('referral_level') or request.form.get('referral_level_2')
                referral_value = request.form.get('referral_value')
                notes = request.form.get('notes')

                if not referral_type_id:
                    flash("Referral type is required.", "danger")
                    return redirect(url_for('referrals.add_referral', tenant_id=tenant_id))

                # Get the referral type to determine required fields
                referral_type = s.query(ReferralType).filter_by(id=referral_type_id).first()
                if not referral_type:
                    flash("Invalid referral type.", "danger")
                    return redirect(url_for('referrals.add_referral', tenant_id=tenant_id))

                # Validate referral level (1-5) - not required for subscription type
                if referral_type.type_name != "Subscription":
                    if not referral_level:
                        flash("Referral level is required for this referral type.", "danger")
                        return redirect(url_for('referrals.add_referral', tenant_id=tenant_id))
                    try:
                        referral_level = int(referral_level)
                        if not 1 <= referral_level <= 5:
                            raise ValueError()
                    except ValueError:
                        flash("Referral level must be between 1 and 5.", "danger")
                        return redirect(url_for('referrals.add_referral', tenant_id=tenant_id))
                else:
                    # For subscription type, level is not required
                    referral_level = None

                # Get date_referred from form
                date_referred_str = request.form.get('date_referred')
                if date_referred_str:
                    try:
                        date_referred = datetime.strptime(date_referred_str, '%Y-%m-%d')
                    except ValueError:
                        date_referred = datetime.utcnow()
                else:
                    date_referred = datetime.utcnow()

                # Handle different referral types
                referral_data = {
                    'referrer_id': session['user_id'],
                    'referral_type_id': referral_type_id,
                    'referral_level': referral_level,
                    'referral_value': float(referral_value) if referral_value else None,
                    'notes': notes,
                    'date_referred': date_referred,
                    'is_verified': False
                }

                if referral_type.requires_member_selection:
                    # "In Group" referral - requires member selection
                    referred_id = request.form.get('referred_id')
                    if not referred_id:
                        flash("Please select a member for this referral type.", "danger")
                        return redirect(url_for('referrals.add_referral', tenant_id=tenant_id))

                    # Check if referral already exists for this member
                    existing_referral = s.query(ReferralRecord).filter_by(
                        referrer_id=session['user_id'],
                        referred_id=referred_id,
                        referral_type_id=referral_type_id
                    ).first()

                    if existing_referral:
                        flash("You have already made this type of referral for this member.", "warning")
                        return redirect(url_for('referrals.my_referrals', tenant_id=tenant_id))

                    referral_data['referred_id'] = referred_id

                elif referral_type.requires_contact_info:
                    # "Out of Group" referral - requires contact info
                    referred_name = request.form.get('referred_name')
                    contact_email = request.form.get('contact_email')
                    contact_phone = request.form.get('contact_phone')

                    if not referred_name or not contact_email:
                        flash("Name and email are required for out-of-group referrals.", "danger")
                        return redirect(url_for('referrals.add_referral', tenant_id=tenant_id))

                    # Check if referral already exists for this contact
                    existing_referral = s.query(ReferralRecord).filter_by(
                        referrer_id=session['user_id'],
                        contact_email=contact_email,
                        referral_type_id=referral_type_id
                    ).first()

                    if existing_referral:
                        flash("You have already made this type of referral for this contact.", "warning")
                        return redirect(url_for('referrals.my_referrals', tenant_id=tenant_id))

                    referral_data.update({
                        'referred_name': referred_name,
                        'contact_email': contact_email,
                        'contact_phone': contact_phone
                    })

                elif referral_type.type_name == "Subscription":
                    # "Subscription" referral - uses prior referral selection
                    prior_referral_id = request.form.get('prior_referral_id')
                    if not prior_referral_id:
                        flash("Please select a prior referral for subscription type.", "danger")
                        return redirect(url_for('referrals.add_referral', tenant_id=tenant_id))

                    # Get the prior referral to copy contact info
                    prior_referral = s.query(ReferralRecord).filter_by(id=prior_referral_id, referrer_id=session['user_id']).first()
                    if not prior_referral:
                        flash("Invalid prior referral selected.", "danger")
                        return redirect(url_for('referrals.add_referral', tenant_id=tenant_id))

                    # Check if subscription already exists for this prior referral
                    existing_subscription = s.query(ReferralRecord).filter_by(
                        referrer_id=session['user_id'],
                        referred_id=prior_referral.referred_id if prior_referral.referred_id else None,
                        contact_email=prior_referral.contact_email,
                        referral_type_id=referral_type_id
                    ).first()

                    if existing_subscription:
                        flash("You have already made a subscription referral for this contact.", "warning")
                        return redirect(url_for('referrals.my_referrals', tenant_id=tenant_id))

                    # Copy contact info from prior referral
                    referral_data.update({
                        'referred_id': prior_referral.referred_id,
                        'referred_name': prior_referral.referred_name,
                        'contact_email': prior_referral.contact_email,
                        'contact_phone': prior_referral.contact_phone
                    })

                # Set closed_date based on referral type
                if not referral_type.allows_closed_date:
                    referral_data['closed_date'] = None
                else:
                    # For types that allow closed date, it will be set later when verified
                    pass

                # Create new referral
                new_referral = ReferralRecord(**referral_data)
                s.add(new_referral)
                s.commit()

                flash("Referral added successfully!", "success")
                return redirect(url_for('referrals.my_referrals', tenant_id=tenant_id))

            except Exception as e:
                s.rollback()
                logger.error(f"Error adding referral: {str(e)}")
                flash(f"Failed to add referral: {str(e)}", "danger")
                return redirect(url_for('referrals.add_referral', tenant_id=tenant_id))

        return render_template('add_referral.html',
                             tenant_id=tenant_id,
                             tenant_display_name=tenant_display_name,
                             referral_types=referral_types,
                             all_users=all_users,
                             prior_referrals=prior_referrals,
                             today=date.today())


@referrals_bp.route('/<tenant_id>/verify/<int:referral_id>', methods=['POST'])
def verify_referral(tenant_id, referral_id):
    if 'user_id' not in session or session['tenant_id'] != tenant_id:
        return jsonify({'success': False, 'message': 'Not logged in'})

    # Check if user has permission to verify referrals
    user_permissions = session.get('user_permissions', {})
    if not user_permissions.get('can_edit_referrals', False):
        return jsonify({'success': False, 'message': 'No permission to verify referrals'})

    try:
        with get_tenant_db_session(tenant_id) as s:
            referral = s.query(ReferralRecord).options(joinedload(ReferralRecord.referral_type)).filter_by(id=referral_id).first()

            if not referral:
                return jsonify({'success': False, 'message': 'Referral not found'})

            # Toggle verification status
            referral.is_verified = not referral.is_verified
            if referral.is_verified:
                referral.verified_by_id = session['user_id']
                referral.verified_date = datetime.utcnow()
                # Set closed date if the referral type allows it
                if referral.referral_type.allows_closed_date:
                    referral.closed_date = datetime.utcnow()
            else:
                referral.verified_by_id = None
                referral.verified_date = None
                if referral.referral_type.allows_closed_date:
                    referral.closed_date = None

            s.commit()

            return jsonify({
                'success': True,
                'message': f'Referral {"verified" if referral.is_verified else "unverified"} successfully',
                'is_verified': referral.is_verified
            })

    except Exception as e:
        logger.error(f"Error verifying referral: {str(e)}")
        return jsonify({'success': False, 'message': 'Failed to update referral status'})


@referrals_bp.route('/<tenant_id>/close/<int:referral_id>', methods=['POST'])
def close_referral(tenant_id, referral_id):
    if 'user_id' not in session or session['tenant_id'] != tenant_id:
        return jsonify({'success': False, 'message': 'Not logged in'})

    try:
        # Get the close value from form data
        close_value = request.form.get('close_value')
        if close_value:
            close_value = float(close_value)
        else:
            close_value = None

        with get_tenant_db_session(tenant_id) as s:
            referral = s.query(ReferralRecord).options(joinedload(ReferralRecord.referral_type)).filter_by(id=referral_id).first()

            if not referral:
                return jsonify({'success': False, 'message': 'Referral not found'})

            # Check if user can close this referral (owner or privileged user)
            user_permissions = session.get('user_permissions', {})
            can_manage_referrals = user_permissions.get('can_edit_referrals', False)

            if referral.referrer_id != session['user_id'] and not can_manage_referrals:
                return jsonify({'success': False, 'message': 'No permission to close this referral'})

            # Only allow closing if referral type allows closed date (not subscription)
            if not referral.referral_type.allows_closed_date:
                return jsonify({'success': False, 'message': 'This referral type cannot be closed'})

            # Set closed date and value
            referral.closed_date = datetime.utcnow()
            if close_value is not None:
                referral.referral_value = close_value

            s.commit()

            return jsonify({
                'success': True,
                'message': 'Referral closed successfully',
                'closed_date': referral.closed_date.strftime('%Y-%m-%d') if referral.closed_date else None,
                'referral_value': referral.referral_value
            })

    except Exception as e:
        logger.error(f"Error closing referral: {str(e)}")
        return jsonify({'success': False, 'message': 'Failed to close referral'})


@referrals_bp.route('/<tenant_id>/history')
def referral_history(tenant_id):
    if 'user_id' not in session or session['tenant_id'] != tenant_id:
        flash("You must be logged in to view this page.", "danger")
        return redirect(url_for('auth.login', tenant_id=tenant_id))

    tenant_display_name = Config.TENANT_DISPLAY_NAMES.get(tenant_id, tenant_id.capitalize())
    current_user_id = session['user_id']

    # Get date range parameters
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')

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

    # Check if user has permission to view all referrals
    user_permissions = session.get('user_permissions', {})
    can_manage_referrals = user_permissions.get('can_edit_referrals', False)

    with get_tenant_db_session(tenant_id) as s:
        # Get selected user for privileged users
        selected_user_id = request.args.get('user_id')
        selected_user = None
        all_users = []

        if can_manage_referrals:
            # Get all users for dropdown
            all_users = s.query(User).order_by(User.last_name, User.first_name).all()

            if selected_user_id:
                selected_user = s.query(User).filter_by(id=selected_user_id).first()

        # Build query based on permissions
        query = s.query(ReferralRecord).options(
            joinedload(ReferralRecord.referral_type),
            joinedload(ReferralRecord.referrer),
            joinedload(ReferralRecord.referred_member),
            joinedload(ReferralRecord.verified_by)
        )

        if not can_manage_referrals:
            # Non-privileged users can only see their own referrals
            query = query.filter_by(referrer_id=current_user_id)
        elif selected_user_id:
            # Privileged users can filter by specific referrer
            query = query.filter_by(referrer_id=selected_user_id)

        # Apply date range filter
        if start_date:
            query = query.filter(ReferralRecord.date_referred >= datetime.combine(start_date, datetime.min.time()))
        if end_date:
            query = query.filter(ReferralRecord.date_referred <= datetime.combine(end_date, datetime.max.time()))

        # Get referrals
        all_referrals = query.order_by(ReferralRecord.date_referred.desc()).all()

        # Calculate statistics
        total_referrals = len(all_referrals)
        verified_referrals = len([r for r in all_referrals if r.is_verified])
        pending_referrals = len([r for r in all_referrals if not r.is_verified])

        return render_template('referral_history.html',
                             tenant_id=tenant_id,
                             tenant_display_name=tenant_display_name,
                             all_referrals=all_referrals,
                             total_referrals=total_referrals,
                             verified_referrals=verified_referrals,
                             pending_referrals=pending_referrals,
                             can_manage_referrals=can_manage_referrals,
                             selected_user=selected_user,
                             all_users=all_users,
                             start_date=start_date_str,
                             end_date=end_date_str)


@referrals_bp.route('/<tenant_id>/get_referral_types')
def get_referral_types(tenant_id):
    """AJAX endpoint to get referral type details"""
    if 'user_id' not in session or session['tenant_id'] != tenant_id:
        return jsonify({'error': 'Not logged in'})

    try:
        with get_tenant_db_session(tenant_id) as s:
            referral_types = s.query(ReferralType).filter_by(is_active=True).order_by(ReferralType.sort_order).all()

            types_data = []
            for rt in referral_types:
                types_data.append({
                    'id': rt.id,
                    'type_name': rt.type_name,
                    'description': rt.description,
                    'requires_member_selection': rt.requires_member_selection,
                    'requires_contact_info': rt.requires_contact_info,
                    'allows_closed_date': rt.allows_closed_date
                })

            return jsonify({'referral_types': types_data})

    except Exception as e:
        logger.error(f"Error getting referral types: {str(e)}")
        return jsonify({'error': 'Failed to load referral types'})
