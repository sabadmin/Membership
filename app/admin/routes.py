# app/admin/routes.py

import logging
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, g, flash
from config import Config
from database import get_tenant_db_session, _tenant_engines # Corrected import
from app.models import Base, User, UserAuthDetails, AttendanceRecord, DuesRecord, ReferralRecord, MembershipType
from sqlalchemy import MetaData, Table, inspect, text
from sqlalchemy.orm import relationship, joinedload
from datetime import datetime

# Set up logging for debugging admin operations
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.before_request
def check_admin_access():
    if g.tenant_id != Config.SUPERADMIN_TENANT_ID:
        flash("You do not have permission to access the admin panel.", "danger")
        return redirect(url_for('auth.index'))

def get_all_table_names(engine):
    inspector = inspect(engine)
    return inspector.get_table_names()

def get_table_and_model(table_name, tenant_id):
    if table_name == 'users':
        return User
    elif table_name == 'user_auth_details':
        return UserAuthDetails
    elif table_name == 'attendance_records':
        return AttendanceRecord
    elif table_name == 'dues_records':
        return DuesRecord
    elif table_name == 'referral_records':
        return ReferralRecord
    elif table_name == 'membership_types':
        return MembershipType
    return None

def get_column_names(model):
    if model:
        return [c.key for c in model.__table__.columns]
    return []

def serialize_row(row):
    serialized = {}
    for column, value in row._asdict().items():
        if isinstance(value, datetime):
            serialized[column] = value.isoformat()
        else:
            serialized[column] = value
    return serialized

def _convert_form_value(model, column_name, value):
    """Convert HTML form string values to proper Python types based on model column types"""
    try:
        if hasattr(model, '__table__'):
            column = model.__table__.columns.get(column_name)
            if column is not None:
                # Boolean conversion
                if str(column.type) == 'BOOLEAN':
                    if value is None or value == '':
                        return False  # Default to False for empty boolean fields
                    return value.lower() in ['true', '1', 'yes', 'on']
                # Integer conversion
                elif 'INTEGER' in str(column.type):
                    return int(value) if value and value.isdigit() else 0
                # DateTime conversion
                elif 'DATETIME' in str(column.type):
                    if isinstance(value, str) and value:
                        from datetime import datetime
                        try:
                            return datetime.fromisoformat(value.replace('Z', '+00:00'))
                        except:
                            return value  # Return as-is if conversion fails
        return value  # Return original value if no conversion needed
    except Exception as e:
        logger.error(f"Error converting value {value} for column {column_name}: {str(e)}")
        return value  # Return original value on error

@admin_bp.route('/<selected_tenant_id>', methods=['GET', 'POST'])
def admin_panel(selected_tenant_id):
    if selected_tenant_id not in Config.TENANT_DATABASES:
        flash("Invalid tenant specified.", "danger")
        return redirect(url_for('admin.admin_panel', selected_tenant_id=Config.SUPERADMIN_TENANT_ID))
    
    tenant_id_to_manage = request.form.get('tenant_to_manage', selected_tenant_id)
    table_name = request.form.get('table_name')
    data = []
    columns = []
    
    with get_tenant_db_session(tenant_id_to_manage) as s:
        tables = get_all_table_names(_tenant_engines[tenant_id_to_manage])
        
        if table_name:
            model = get_table_and_model(table_name, tenant_id_to_manage)
            if model:
                columns = get_column_names(model)
                # For user_auth_details, add username column and modify columns list
                if table_name == 'user_auth_details':
                    columns = [col for col in columns if col != 'user_id'] + ['username']
                if request.method == 'POST':
                    action = request.form.get('action')
                    row_id = request.form.get('id')
                    
                    if action == 'add':
                        # Skip auto-managed and system fields
                        skip_fields = ['action', 'id', 'tenant_to_manage', 'table_name']
                        
                        new_row_data = {}
                        for key, value in request.form.items():
                            if key not in skip_fields:
                                # Skip empty timestamp fields - let model defaults handle them
                                if key in ['created_at', 'updated_at'] and (value == '' or value is None):
                                    continue
                                
                                if value == '':
                                    new_row_data[key] = None
                                else:
                                    # Convert data types properly
                                    converted_value = _convert_form_value(model, key, value)
                                    logger.info(f"Converted {key}: '{value}' -> {converted_value} (type: {type(converted_value)})")
                                    new_row_data[key] = converted_value
                        
                        # Handle password hashing for User model
                        if 'password_hash' in new_row_data and new_row_data['password_hash']:
                            temp_user = User()
                            temp_user.set_password(new_row_data['password_hash'])
                            new_row_data['password_hash'] = temp_user.password_hash
                        
                        try:
                            logger.info(f"Adding new {table_name} record with data: {new_row_data}")
                            new_record = model(**new_row_data)
                            s.add(new_record)
                            s.commit()
                            flash("Row added successfully.", "success")
                            logger.info(f"Successfully added {table_name} record")
                        except Exception as e:
                            s.rollback()
                            error_msg = f"Error adding {table_name} row: {str(e)}"
                            flash(error_msg, "danger")
                            logger.error(error_msg)

                    elif action == 'update' and row_id:
                        try:
                            logger.info(f"Updating {table_name} record ID {row_id}")
                            row = s.query(model).filter_by(id=row_id).first()
                            if row:
                                logger.info(f"Found record to update: {row}")
                                # Skip auto-managed timestamp fields
                                skip_fields = ['action', 'id', 'tenant_to_manage', 'table_name', 'password_hash', 'created_at', 'updated_at']
                                
                                for key, value in request.form.items():
                                    if key not in skip_fields:
                                        logger.info(f"Setting {key} = {value}")
                                        # Convert data types based on model column types
                                        converted_value = _convert_form_value(model, key, value)
                                        logger.info(f"Converted {key}: '{value}' -> {converted_value}")
                                        setattr(row, key, converted_value)
                                
                                # For MembershipType, update the updated_at field
                                if table_name == 'membership_types':
                                    row.updated_at = datetime.utcnow()
                                
                                s.commit()
                                flash("Row updated successfully.", "success")
                                logger.info(f"Successfully updated {table_name} ID {row_id}")
                            else:
                                flash("Row not found.", "danger")
                                logger.warning(f"Record not found for {table_name} ID {row_id}")
                        except Exception as e:
                            s.rollback()
                            error_msg = f"Error updating {table_name} record: {str(e)}"
                            flash(error_msg, "danger")
                            logger.error(error_msg)
                    
                    elif action == 'delete' and row_id:
                        try:
                            logger.info(f"Deleting {table_name} record ID {row_id}")
                            row = s.query(model).filter_by(id=row_id).first()
                            if row:
                                s.delete(row)
                                s.commit()
                                flash("Row deleted successfully.", "success")
                                logger.info(f"Successfully deleted {table_name} ID {row_id}")
                            else:
                                flash("Row not found.", "danger")
                                logger.warning(f"Record not found for {table_name} ID {row_id}")
                        except Exception as e:
                            s.rollback()
                            error_msg = f"Error deleting {table_name} record: {str(e)}"
                            flash(error_msg, "danger")
                            logger.error(error_msg)
                
                if table_name == 'user_auth_details':
                    # Join with users table to show usernames instead of user_id
                    rows = s.query(model, User.email, User.first_name, User.last_name).join(User, model.user_id == User.id).all()
                    data = []
                    for auth_detail, email, first_name, last_name in rows:
                        row_data = auth_detail.__dict__.copy()
                        row_data.pop('_sa_instance_state', None)
                        # Replace user_id with readable user info
                        username = f"{first_name or ''} {last_name or ''}".strip() or email
                        row_data['username'] = username
                        data.append(row_data)
                else:
                    rows = s.query(model).all()
                    data = [row.__dict__ for row in rows]
                    for row in data:
                        row.pop('_sa_instance_state', None)
    
    return render_template('admin_panel.html',
                           tables=tables,
                           selected_tenant_id=tenant_id_to_manage,
                           selected_table=table_name,  # Template expects this name
                           all_tenant_ids=list(Config.TENANT_DATABASES.keys()),  # For dropdown
                           columns=columns,
                           data=data,
                           tenant_display_names=Config.TENANT_DISPLAY_NAMES,
                           Config=Config)
