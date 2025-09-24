import logging
from flask import Blueprint, request, render_template, redirect, url_for, session, flash, g
from config import Config
from database import get_tenant_db_session
from app.models import User, ReferralRecord
from datetime import date, datetime
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
        # Get current user's referrals
        my_referrals = s.query(ReferralRecord).filter_by(referrer_id=current_user_id).order_by(ReferralRecord.date_referred.desc()).all()

        # Calculate referral statistics
        total_referrals = len(my_referrals)
        successful_referrals = len([r for r in my_referrals if r.membership_status == 'active'])
        pending_referrals = len([r for r in my_referrals if r.membership_status == 'pending'])

        return render_template('my_referrals.html',
                             tenant_id=tenant_id,
                             tenant_display_name=tenant_display_name,
                             my_referrals=my_referrals,
                             total_referrals=total_referrals,
                             successful_referrals=successful_referrals,
                             pending_referrals=pending_referrals)


@referrals_bp.route('/<tenant_id>/add', methods=['GET', 'POST'])
def add_referral(tenant_id):
    if 'user_id' not in session or session['tenant_id'] != tenant_id:
        flash("You must be logged in to view this page.", "danger")
        return redirect(url_for('auth.login', tenant_id=tenant_id))

    # Check if user has permission to add referrals
    user_permissions = session.get('user_permissions', {})
    if not user_permissions.get('can_edit_referrals', False):
        flash("You do not have permission to add referrals.", "danger")
        return redirect(url_for('referrals.my_referrals', tenant_id=tenant_id))

    tenant_display_name = Config.TENANT_DISPLAY_NAMES.get(tenant_id, tenant_id.capitalize())

    if request.method == 'POST':
        try:
            # Get form data
            first_name = request.form.get('first_name')
            last_name = request.form.get('last_name')
            email = request.form.get('email')
            phone = request.form.get('phone')
            company = request.form.get('company')
            notes = request.form.get('notes')

            if not first_name or not last_name or not email:
                flash("First name, last name, and email are required.", "danger")
                return redirect(url_for('referrals.add_referral', tenant_id=tenant_id))

            with get_tenant_db_session(tenant_id) as s:
                # Check if referral already exists for this email
                existing_referral = s.query(ReferralRecord).filter_by(
                    email=email,
                    referrer_id=session['user_id']
                ).first()

                if existing_referral:
                    flash("You have already referred this person.", "warning")
                    return redirect(url_for('referrals.my_referrals', tenant_id=tenant_id))

                # Create new referral
                new_referral = ReferralRecord(
                    referrer_id=session['user_id'],
                    first_name=first_name,
                    last_name=last_name,
                    email=email,
                    phone=phone,
                    company=company,
                    notes=notes,
                    date_referred=date.today(),
                    membership_status='pending'
                )

                s.add(new_referral)
                s.commit()

                flash("Referral added successfully!", "success")
                return redirect(url_for('referrals.my_referrals', tenant_id=tenant_id))

        except Exception as e:
            flash(f"Failed to add referral: {str(e)}", "danger")
            return redirect(url_for('referrals.add_referral', tenant_id=tenant_id))

    return render_template('add_referral.html',
                         tenant_id=tenant_id,
                         tenant_display_name=tenant_display_name)


@referrals_bp.route('/<tenant_id>/history')
def referral_history(tenant_id):
    if 'user_id' not in session or session['tenant_id'] != tenant_id:
        flash("You must be logged in to view this page.", "danger")
        return redirect(url_for('auth.login', tenant_id=tenant_id))

    # Check if user has permission to view all referrals
    user_permissions = session.get('user_permissions', {})
    if not user_permissions.get('can_edit_referrals', False):
        flash("You do not have permission to view referral history.", "danger")
        return redirect(url_for('referrals.my_referrals', tenant_id=tenant_id))

    tenant_display_name = Config.TENANT_DISPLAY_NAMES.get(tenant_id, tenant_id.capitalize())

    with get_tenant_db_session(tenant_id) as s:
        # Get all referrals with referrer information
        all_referrals = s.query(ReferralRecord).join(
            User, ReferralRecord.referrer_id == User.id
        ).order_by(ReferralRecord.date_referred.desc()).all()

        # Calculate overall statistics
        total_referrals = len(all_referrals)
        successful_referrals = len([r for r in all_referrals if r.membership_status == 'active'])
        pending_referrals = len([r for r in all_referrals if r.membership_status == 'pending'])

        return render_template('referral_history.html',
                             tenant_id=tenant_id,
                             tenant_display_name=tenant_display_name,
                             all_referrals=all_referrals,
                             total_referrals=total_referrals,
                             successful_referrals=successful_referrals,
                             pending_referrals=pending_referrals)


@referrals_bp.route('/<tenant_id>/update/<int:referral_id>', methods=['POST'])
def update_referral_status(tenant_id, referral_id):
    if 'user_id' not in session or session['tenant_id'] != tenant_id:
        flash("You must be logged in to view this page.", "danger")
        return redirect(url_for('auth.login', tenant_id=tenant_id))

    # Check if user has permission to update referrals
    user_permissions = session.get('user_permissions', {})
    if not user_permissions.get('can_edit_referrals', False):
        flash("You do not have permission to update referral status.", "danger")
        return redirect(url_for('referrals.my_referrals', tenant_id=tenant_id))

    try:
        new_status = request.form.get('status')

        if new_status not in ['pending', 'active', 'inactive']:
            flash("Invalid status.", "danger")
            return redirect(url_for('referrals.referral_history', tenant_id=tenant_id))

        with get_tenant_db_session(tenant_id) as s:
            referral = s.query(ReferralRecord).filter_by(id=referral_id).first()

            if not referral:
                flash("Referral not found.", "danger")
                return redirect(url_for('referrals.referral_history', tenant_id=tenant_id))

            referral.membership_status = new_status
            if new_status == 'active':
                referral.membership_date = date.today()

            s.commit()

            flash("Referral status updated successfully!", "success")

    except Exception as e:
        flash(f"Failed to update referral status: {str(e)}", "danger")

    return redirect(url_for('referrals.referral_history', tenant_id=tenant_id))
