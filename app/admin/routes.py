# app/admin/routes.py

from flask import Blueprint, render_template, request, jsonify, redirect, url_for, g, flash
from config import Config
from database import get_tenant_db_session, _tenant_engines # Corrected import
from app.models import Base, User, UserAuthDetails, AttendanceRecord, DuesRecord, ReferralRecord
from sqlalchemy import MetaData, Table, inspect, text
from sqlalchemy.orm import relationship, joinedload
from datetime import datetime

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
                if request.method == 'POST':
                    action = request.form.get('action')
                    row_id = request.form.get('id')
                    
                    if action == 'add':
                        new_row_data = {
                            key: value for key, value in request.form.items() if key not in ['action', 'id', 'tenant_to_manage', 'table_name']
                        }
                        if 'password_hash' in new_row_data and new_row_data['password_hash']:
                            # Create a temporary user to hash the password correctly
                            temp_user = User()
                            temp_user.set_password(new_row_data['password_hash'])
                            new_row_data['password_hash'] = temp_user.password_hash
                        
                        try:
                            s.add(model(**new_row_data))
                            s.commit()
                            flash("Row added successfully.", "success")
                        except Exception as e:
                            s.rollback()
                            flash(f"Error adding row: {str(e)}", "danger")

                    elif action == 'update' and row_id:
                        row = s.query(model).filter_by(id=row_id).first()
                        if row:
                            for key, value in request.form.items():
                                if key not in ['action', 'id', 'tenant_to_manage', 'table_name'] and key != 'password_hash':
                                    setattr(row, key, value)
                            s.commit()
                            flash("Row updated successfully.", "success")
                        else:
                            flash("Row not found.", "danger")
                    
                    elif action == 'delete' and row_id:
                        row = s.query(model).filter_by(id=row_id).first()
                        if row:
                            s.delete(row)
                            s.commit()
                            flash("Row deleted successfully.", "success")
                        else:
                            flash("Row not found.", "danger")
                
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
