# app/admin/routes.py

from flask import Blueprint, request, jsonify, g, render_template, redirect, url_for, session, flash
from config import Config
from database import get_tenant_db_session, Base
from app.models import User, UserAuthDetails # Import all models that might be managed
from app.utils import infer_tenant_from_hostname
from sqlalchemy import inspect, text, String, Integer, Boolean, DateTime
from sqlalchemy.exc import IntegrityError, OperationalError
from datetime import datetime

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# Helper to check if current user is superadmin
def is_superadmin():
    return g.tenant_id == Config.SUPERADMIN_TENANT_ID and 'user_id' in session

# Admin panel dashboard
@admin_bp.route('/')
@admin_bp.route('/<selected_tenant_id>')
@admin_bp.route('/<selected_tenant_id>/<table>')
def admin_panel(selected_tenant_id=None, table=None):
    if not is_superadmin():
        flash("Unauthorized access. Admin privileges required.", "danger")
        return redirect(url_for('auth.login'))

    all_tenant_ids = list(Config.TENANT_DATABASES.keys())
    
    # Default to the superadmin tenant if none selected
    if not selected_tenant_id or selected_tenant_id not in all_tenant_ids:
        selected_tenant_id = Config.SUPERADMIN_TENANT_ID

    db_url = Config.TENANT_DATABASES[selected_tenant_id]
    tables = []
    columns = []
    data = []
    primary_keys = {}
    
    try:
        with get_tenant_db_session(selected_tenant_id) as s:
            inspector = inspect(s.bind)
            tables = inspector.get_table_names()

            if table and table in tables:
                columns_info = inspector.get_columns(table)
                columns = [{'name': col['name'], 'type': str(col['type'])} for col in columns_info]
                
                # Get primary key(s) for the table
                pk_constraints = inspector.get_pk_constraint(table)
                primary_keys[table] = pk_constraints['constrained_columns']

                # Dynamically fetch data
                # For simplicity, we'll fetch all rows. For large tables, pagination is needed.
                # Use text() for raw SQL execution
                result = s.execute(text(f"SELECT * FROM {table} ORDER BY {primary_keys[table][0] if primary_keys[table] else 'id'} ASC"))
                data = [row._asdict() for row in result.fetchall()]

    except Exception as e:
        flash(f"Error accessing database or table: {e}", "danger")
        tables = []
        columns = []
        data = []

    return render_template('admin_panel.html', 
                           all_tenant_ids=all_tenant_ids,
                           selected_tenant_id=selected_tenant_id,
                           tables=tables,
                           selected_table=table,
                           columns=columns,
                           data=data,
                           primary_keys=primary_keys)

# Add/Modify/Delete data
@admin_bp.route('/<selected_tenant_id>/<table>/manage', methods=['POST'])
def manage_data(selected_tenant_id, table):
    if not is_superadmin():
        flash("Unauthorized access. Admin privileges required.", "danger")
        return redirect(url_for('auth.login'))
        
    action = request.form.get('action')
    row_id = request.form.get('id') # Assuming 'id' is always the first PK

    try:
        with get_tenant_db_session(selected_tenant_id) as s:
            inspector = inspect(s.bind)
            columns_info = inspector.get_columns(table)
            column_names = [col['name'] for col in columns_info]
            pk_constraints = inspector.get_pk_constraint(table)
            pk_column = pk_constraints['constrained_columns'][0] if pk_constraints['constrained_columns'] else 'id'

            if action == 'add':
                insert_cols = []
                insert_vals = []
                for col in column_names:
                    if col != pk_column: # Don't try to insert into auto-incrementing PK
                        val = request.form.get(f'new_{col}')
                        if val is not None: # Only include if value is provided
                            insert_cols.append(col)
                            insert_vals.append(val)
                
                # Handle password_hash for new user if adding to 'users' table
                if table == 'users' and 'password_hash' in insert_cols:
                    raw_password = insert_vals[insert_cols.index('password_hash')]
                    insert_vals[insert_cols.index('password_hash')] = User().set_password(raw_password) # Hash the password

                cols_str = ', '.join(insert_cols)
                vals_placeholders = ', '.join([f'%({c})s' for c in insert_cols])
                params = dict(zip(insert_cols, insert_vals))
                
                s.execute(text(f"INSERT INTO {table} ({cols_str}) VALUES ({vals_placeholders})"), params)
                flash(f"Row added to {table}.", "success")

            elif action == 'edit' and row_id:
                update_parts = []
                params = {pk_column: row_id} # Use PK to identify row
                
                for col in column_names:
                    # Skip PK and password_hash for direct update
                    if col == pk_column:
                        continue
                    if col == 'password_hash': # Special handling for password_hash
                        if request.form.get(f'edit_{col}_delete') == 'true':
                            update_parts.append(f"{col} = NULL")
                        continue # Don't allow direct edit of hash
                    
                    val = request.form.get(f'edit_{col}')
                    if val is not None:
                        update_parts.append(f"{col} = %({col})s")
                        params[col] = val
                
                if update_parts:
                    update_str = ', '.join(update_parts)
                    s.execute(text(f"UPDATE {table} SET {update_str} WHERE {pk_column} = %({pk_column})s"), params)
                    flash(f"Row {row_id} updated in {table}.", "success")
                else:
                    flash("No fields to update.", "warning")

            elif action == 'delete' and row_id:
                s.execute(text(f"DELETE FROM {table} WHERE {pk_column} = %({pk_column})s"), {pk_column: row_id})
                flash(f"Row {row_id} deleted from {table}.", "success")
            
            s.commit()

    except IntegrityError as e:
        s.rollback()
        flash(f"Database error (Integrity): {e.orig}", "danger")
    except OperationalError as e:
        s.rollback()
        flash(f"Database error (Operational): {e.orig}", "danger")
    except Exception as e:
        s.rollback()
        flash(f"An unexpected error occurred: {e}", "danger")

    return redirect(url_for('admin.admin_panel', selected_tenant_id=selected_tenant_id, table=table))

