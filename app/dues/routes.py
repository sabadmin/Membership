import logging
from flask import Blueprint, request, render_template, redirect, url_for, session, flash, g, Response
from config import Config
from database import get_tenant_db_session
from app.models import User, DuesRecord, DuesType
from app.members.forms import DuesCreateForm, DuesPaymentForm, DuesUpdateForm
from sqlalchemy.orm import joinedload
from datetime import date, datetime
from io import StringIO, BytesIO
import csv
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

    with get_tenant_db_session(tenant_id) as s:
        if request.method == 'POST':
            try:
                # Process bulk payment updates for selected members
                # Apply date filter to the records being processed
                query = s.query(DuesRecord).join(User).join(DuesType).filter(
                    DuesRecord.amount_paid < DuesRecord.dues_amount
                )

                if start_date:
                    query = query.filter(DuesRecord.due_date >= start_date)
                if end_date:
                    query = query.filter(DuesRecord.due_date <= end_date)

                dues_records = query.all()
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

            # Preserve date range in redirect
            redirect_url = url_for('dues.dues_collection', tenant_id=tenant_id)
            if start_date_str:
                redirect_url += f'?start_date={start_date_str}'
                if end_date_str:
                    redirect_url += f'&end_date={end_date_str}'
            return redirect(redirect_url)

        # GET request - show outstanding dues for collection
        # Get dues records with outstanding balances, ordered by: open balance first, then due date, then user name
        query = s.query(DuesRecord).join(User).join(DuesType).filter(
            DuesRecord.amount_paid < DuesRecord.dues_amount
        )

        # Apply date range filter
        if start_date:
            query = query.filter(DuesRecord.due_date >= start_date)
        if end_date:
            query = query.filter(DuesRecord.due_date <= end_date)

        dues_records = query.order_by(
            DuesRecord.amount_paid < DuesRecord.dues_amount,  # Open dues first
            DuesRecord.due_date,
            User.last_name,
            User.first_name
        ).all()

        return render_template('dues_collection.html',
                             tenant_id=tenant_id,
                             tenant_display_name=tenant_display_name,
                             dues_records=dues_records,
                             start_date=start_date_str,
                             end_date=end_date_str)


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

            # Apply date range filter
            if start_date:
                dues_query = dues_query.filter(DuesRecord.due_date >= start_date)
            if end_date:
                dues_query = dues_query.filter(DuesRecord.due_date <= end_date)

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
                             all_users=all_users,
                             start_date=start_date_str,
                             end_date=end_date_str)

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


@dues_bp.route('/<tenant_id>/paid_report', methods=['GET', 'POST'])
def dues_paid_report(tenant_id):
    try:
        if 'user_id' not in session or session['tenant_id'] != tenant_id:
            flash("You must be logged in to view this page.", "danger")
            return redirect(url_for('auth.login', tenant_id=tenant_id))

        # Check if user has permission to view dues reports
        user_permissions = session.get('user_permissions', {})
        if not user_permissions.get('can_edit_dues', False):
            flash("You do not have permission to view dues reports.", "danger")
            return redirect(url_for('dues.dues', tenant_id=tenant_id))

        tenant_display_name = Config.TENANT_DISPLAY_NAMES.get(tenant_id, tenant_id.capitalize())

        # Get filter parameters
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        member_filter = request.args.get('member_filter', '')  # member id or empty for all
        report_format = request.args.get('format', 'html')  # html, pdf, csv
        sort_by = request.args.get('sort_by', 'member')  # member, amount, date

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

            # Get all members for the filter dropdown
            all_members = s.query(User).order_by(User.last_name, User.first_name).all()

            # Build query for paid dues records only
            query = s.query(DuesRecord).join(User).join(DuesType).filter(
                DuesRecord.amount_paid > 0  # Only records with payments
            )

            # Apply member filter if provided
            if member_filter:
                query = query.filter(DuesRecord.member_id == member_filter)

            # Apply date range filter if provided
            if start_date:
                query = query.filter(DuesRecord.payment_received_date >= start_date)
            if end_date:
                query = query.filter(DuesRecord.payment_received_date <= end_date)

            # Apply sorting
            if sort_by == 'member':
                query = query.order_by(User.last_name, User.first_name, DuesRecord.payment_received_date)
            elif sort_by == 'amount':
                query = query.order_by(DuesRecord.amount_paid.desc(), User.last_name, User.first_name)
            elif sort_by == 'date':
                query = query.order_by(DuesRecord.payment_received_date.desc(), User.last_name, User.first_name)
            else:
                query = query.order_by(User.last_name, User.first_name, DuesRecord.payment_received_date)

            paid_dues_records = query.all()

            # Calculate summary totals
            total_amount_paid = sum(record.amount_paid for record in paid_dues_records)
            total_records = len(paid_dues_records)

            # Generate reports based on format
            if report_format == 'csv':
                return generate_csv_report(paid_dues_records, tenant_display_name, current_user, start_date, end_date)
            elif report_format == 'pdf':
                return generate_pdf_report(paid_dues_records, tenant_display_name, current_user, start_date, end_date)
            else:
                # HTML format - show the form and results
                return render_template('dues_paid_report.html',
                                     tenant_id=tenant_id,
                                     tenant_display_name=tenant_display_name,
                                     paid_dues_records=paid_dues_records,
                                     total_amount_paid=total_amount_paid,
                                     total_records=total_records,
                                     start_date=start_date_str,
                                     end_date=end_date_str,
                                     sort_by=sort_by)

    except Exception as e:
        logger.error(f"Error in dues_paid_report: {str(e)}")
        flash("An error occurred while generating the dues paid report.", "danger")
        return redirect(url_for('dues.dues', tenant_id=tenant_id))


def generate_csv_report(records, tenant_name, current_user, start_date, end_date):
    """Generate CSV report for paid dues"""
    output = StringIO()
    writer = csv.writer(output)

    # Write headers
    writer.writerow([f'Dues Paid Report - {tenant_name}'])
    writer.writerow([f'Generated by: {current_user.first_name} {current_user.last_name} on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'])
    if start_date or end_date:
        date_range = 'Date Range: '
        if start_date:
            date_range += f'From {start_date}'
        if end_date:
            date_range += f' To {end_date}'
        writer.writerow([date_range])
    writer.writerow([])  # Empty row

    # Write column headers
    writer.writerow(['Member Name', 'Dues Type', 'Amount Paid', 'Payment Date', 'Document Number', 'Due Date'])

    # Write data rows
    for record in records:
        writer.writerow([
            f"{record.member.first_name} {record.member.last_name}",
            record.dues_type.dues_type,
            f"${record.amount_paid:.2f}",
            record.payment_received_date.strftime('%Y-%m-%d') if record.payment_received_date else '',
            record.document_number or '',
            record.due_date.strftime('%Y-%m-%d')
        ])

    # Write summary
    writer.writerow([])  # Empty row
    writer.writerow([f'Total Records: {len(records)}'])
    total_amount = sum(r.amount_paid for r in records)
    writer.writerow([f'Total Amount Paid: ${total_amount:.2f}'])

    # Prepare response
    output.seek(0)
    response = Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-disposition': f'attachment; filename=dues_paid_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'}
    )
    return response


def generate_pdf_report(records, tenant_name, current_user, start_date, end_date):
    """Generate PDF report for paid dues"""
    try:
        from reportlab.lib.pagesizes import letter, A4
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib import colors

        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        styles = getSampleStyleSheet()
        story = []

        # Title
        title = Paragraph(f"Dues Paid Report - {tenant_name}", styles['Title'])
        story.append(title)
        story.append(Spacer(1, 12))

        # Report info
        report_info = f"Generated by: {current_user.first_name} {current_user.last_name} on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        story.append(Paragraph(report_info, styles['Normal']))
        story.append(Spacer(1, 6))

        if start_date or end_date:
            date_range = 'Date Range: '
            if start_date:
                date_range += f'From {start_date}'
            if end_date:
                date_range += f' To {end_date}'
            story.append(Paragraph(date_range, styles['Normal']))
            story.append(Spacer(1, 12))

        # Table data
        data = [['Member Name', 'Dues Type', 'Amount Paid', 'Payment Date', 'Document Number', 'Due Date']]

        for record in records:
            data.append([
                f"{record.member.first_name} {record.member.last_name}",
                record.dues_type.dues_type,
                f"${record.amount_paid:.2f}",
                record.payment_received_date.strftime('%Y-%m-%d') if record.payment_received_date else '',
                record.document_number or '',
                record.due_date.strftime('%Y-%m-%d')
            ])

        # Summary row
        total_amount_pdf = sum(r.amount_paid for r in records)
        data.append([
            'TOTAL',
            f'{len(records)} Records',
            f"${total_amount_pdf:.2f}",
            '',
            '',
            ''
        ])

        # Create table
        table = Table(data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 14),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))

        story.append(table)

        # Build PDF
        doc.build(story)

        # Prepare response
        buffer.seek(0)
        response = Response(
            buffer.getvalue(),
            mimetype='application/pdf',
            headers={'Content-disposition': f'attachment; filename=dues_paid_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'}
        )
        return response

    except ImportError:
        flash("PDF generation requires reportlab library. Please install it first.", "danger")
        return redirect(url_for('dues.dues_paid_report', tenant_id=tenant_id))
