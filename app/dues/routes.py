import logging
from flask import Blueprint, request, render_template, redirect, url_for, session, flash, g
from config import Config
from database import get_tenant_db_session
from app.models import User, DuesRecord, DuesType
from app.members.forms import DuesCreateForm, DuesPaymentForm, DuesUpdateForm
from sqlalchemy.orm import joinedload
from datetime import date, datetime
from . import dues_bp

logger = logging.getLogger(__name__)


@dues_bp.route('/<tenant_id>', methods=['GET', 'POST'])
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
                return redirect(url_for('dues.dues', tenant_id=tenant_id))

        # Query dues records, open dues first, then sorted
        dues_records = s.query(DuesRecord).join(User).join(DuesType).order_by(
            DuesRecord.amount_paid < DuesRecord.dues_amount,  # Open dues first
            DuesRecord.due_date,
            User.last_name,
            User.first_name
        ).all()

        return render_template('dues.html', tenant_id=tenant_id, dues_records=dues_records, form=dues_create_form, can_edit=can_edit, dues_types=dues_types)


@dues_bp.route('/<tenant_id>/payment/<int:dues_record_id>', methods=['GET', 'POST'])
def dues_payment(tenant_id, dues_record_id):
    with get_tenant_db_session(tenant_id) as s:
        dues_record = s.query(DuesRecord).get(dues_record_id)
        if not dues_record:
            flash('Dues record not found.', 'danger')
            return redirect(url_for('dues.dues', tenant_id=tenant_id))

        form = DuesPaymentForm(obj=dues_record) # Pre-populate form with existing data

        if form.validate_on_submit():
            dues_record.amount_paid = form.amount_paid.data
            dues_record.document_number = form.document_number.data
            dues_record.payment_received_date = form.payment_received_date.data
            s.commit()
            flash('Payment recorded successfully!', 'success')
            return redirect(url_for('dues.dues', tenant_id=tenant_id))

        return render_template('dues_payment.html', tenant_id=tenant_id, form=form, dues_record=dues_record)


@dues_bp.route('/<tenant_id>/update/<int:dues_record_id>', methods=['GET', 'POST'])
def dues_update(tenant_id, dues_record_id):
    with get_tenant_db_session(tenant_id) as s:
        dues_record = s.query(DuesRecord).get(dues_record_id)

        if not dues_record:
            flash('Dues record not found.', 'danger')
            return redirect(url_for('dues.dues', tenant_id=tenant_id))

        form = DuesUpdateForm(obj=dues_record)

        if form.validate_on_submit():
            dues_record.dues_amount = form.dues_amount.data
            dues_record.due_date = form.due_date.data
            s.commit()
            flash('Dues record updated successfully!', 'success')
            return redirect(url_for('dues.dues', tenant_id=tenant_id))

        return render_template('dues_update.html', tenant_id=tenant_id, form=form, dues_record=dues_record)


@dues_bp.route('/<tenant_id>/generate', methods=['GET', 'POST'])
def generate_dues(tenant_id):
    if 'user_id' not in session or session['tenant_id'] != tenant_id:
        flash("You must be logged in to view this page.", "danger")
        return redirect(url_for('auth.login', tenant_id=tenant_id))

    # Check if user has permission to create dues records
    user_permissions = session.get('user_permissions', {})
    if not user_permissions.get('can_edit_dues', False):
        flash("You do not have permission to generate dues records.", "danger")
        return redirect(url_for('dues.dues', tenant_id=tenant_id))

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
                    return redirect(url_for('dues.generate_dues', tenant_id=tenant_id))

                # Parse amount and date
                try:
                    amount_due = float(amount_due)
                    due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
                except ValueError:
                    flash("Invalid amount or date format.", "danger")
                    return redirect(url_for('dues.generate_dues', tenant_id=tenant_id))

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

            return redirect(url_for('dues.generate_dues', tenant_id=tenant_id))

        # GET request - show the form
        all_users = s.query(User).filter_by(is_active=True).order_by(User.first_name, User.last_name).all()

        return render_template('dues_create.html',
                             tenant_id=tenant_id,
                             tenant_display_name=tenant_display_name,
                             all_users=all_users,
                             dues_types=dues_types)


@dues_bp.route('/<tenant_id>/collection', methods=['GET', 'POST'])
def dues_collection(tenant_id):
    if 'user_id' not in session or session['tenant_id'] != tenant_id:
        flash("You must be logged in to view this page.", "danger")
        return redirect(url_for('auth.login', tenant_id=tenant_id))

    # Check if user has permission to manage dues
    user_permissions = session.get('user_permissions', {})
    if not user_permissions.get('can_edit_dues', False):
        flash("You do not have permission to manage dues collection.", "danger")
        return redirect(url_for('dues.dues', tenant_id=tenant_id))

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

            return redirect(url_for('dues.dues_collection', tenant_id=tenant_id))

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


@dues_bp.route('/<tenant_id>/history')
def my_dues_history(tenant_id):
    import logging
    logger = logging.getLogger(__name__)

    try:
        logger.info(f"Starting my_dues_history for tenant: {tenant_id}")

        if 'user_id' not in session or session['tenant_id'] != tenant_id:
            logger.warning(f"Access denied for my_dues_history. Session user_id: {session.get('user_id')}, Session tenant_id: {session.get('tenant_id')}")
            flash("You must be logged in to view this page.", "danger")
            return redirect(url_for('auth.login', tenant_id=tenant_id))

        tenant_display_name = Config.TENANT_DISPLAY_NAMES.get(tenant_id, tenant_id.capitalize())
        current_user_id = session['user_id']

        with get_tenant_db_session(tenant_id) as s:
            logger.info("Database session opened successfully")

            current_user = s.query(User).options(joinedload(User.auth_details)).filter_by(id=current_user_id).first()
            if not current_user:
                logger.error("Current user not found")
                session.clear()
                flash("User not found.", "danger")
                return redirect(url_for('auth.login', tenant_id=tenant_id))

            # Check if user can view all dues or just their own
            can_manage_dues = current_user.auth_details and current_user.auth_details.can_edit_dues
            logger.info(f"User permissions - can_manage_dues: {can_manage_dues}")

            # Get selected user for privileged users
            selected_user_id = request.args.get('user_id')
            selected_user = None
            all_users = []

            if can_manage_dues:
                # Get all users for dropdown
                all_users = s.query(User).order_by(User.last_name, User.first_name).all()

                if selected_user_id:
                    selected_user = s.query(User).filter_by(id=selected_user_id).first()
                    if selected_user:
                        # Show selected user's dues
                        dues_query = s.query(DuesRecord).join(DuesType).join(User).filter(DuesRecord.member_id == selected_user_id).options(joinedload(DuesRecord.dues_type), joinedload(DuesRecord.member))
                        page_title = f"Dues History - {selected_user.first_name or ''} {selected_user.last_name or ''}".strip() or selected_user.email
                    else:
                        # Invalid user selected, show all
                        dues_query = s.query(DuesRecord).join(DuesType).join(User).options(joinedload(DuesRecord.dues_type), joinedload(DuesRecord.member))
                        page_title = "All Dues History"
                else:
                    # No user selected, show all
                    dues_query = s.query(DuesRecord).join(DuesType).join(User).options(joinedload(DuesRecord.dues_type), joinedload(DuesRecord.member))
                    page_title = "All Dues History"
            else:
                # Show only current user's dues
                dues_query = s.query(DuesRecord).join(DuesType).join(User).filter(DuesRecord.member_id == current_user_id).options(joinedload(DuesRecord.dues_type), joinedload(DuesRecord.member))
                page_title = "My Dues History"

            # Order by: unpaid dues first (by due date), then paid dues (by due date), then by name
            my_dues = dues_query.order_by(
                DuesRecord.amount_paid >= DuesRecord.dues_amount,  # Unpaid first, paid last
                DuesRecord.due_date.asc(),  # Earliest due dates first within each group
                User.last_name,
                User.first_name
            ).all()

            logger.info(f"Retrieved {len(my_dues)} dues records")

        logger.info("Rendering my_dues_history.html template")
        return render_template('my_dues_history.html',
                             tenant_id=tenant_id,
                             tenant_display_name=tenant_display_name,
                             my_dues=my_dues,
                             can_manage_dues=can_manage_dues,
                             page_title=page_title,
                             selected_user=selected_user,
                             all_users=all_users)

    except Exception as e:
        logger.error(f"Error in my_dues_history: {str(e)}")
        logger.error(f"Error type: {type(e).__name__}")
        flash("An error occurred while retrieving dues history.", "danger")
        return redirect(url_for('dues.my_dues_history', tenant_id=tenant_id))


@dues_bp.route('/<tenant_id>/member/<int:member_id>/history')
def member_dues_history(tenant_id, member_id):
    if 'user_id' not in session or session['tenant_id'] != tenant_id:
        flash("You do not have permission to view this page.", "danger")
        return redirect(url_for('auth.login', tenant_id=tenant_id))

    # Check if user has permission to view member dues
    user_permissions = session.get('user_permissions', {})
    if not user_permissions.get('can_edit_dues', False):
        flash("You do not have permission to view member dues history.", "danger")
        return redirect(url_for('dues.my_dues_history', tenant_id=tenant_id))

    tenant_display_name = Config.TENANT_DISPLAY_NAMES.get(tenant_id, tenant_id.capitalize())

    with get_tenant_db_session(tenant_id) as s:
        # Get the selected member
        selected_member = s.query(User).filter_by(id=member_id).first()
        if not selected_member:
            flash("Member not found.", "danger")
            return redirect(url_for('dues.my_dues_history', tenant_id=tenant_id))

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
