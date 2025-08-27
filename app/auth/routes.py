# app/auth/routes.py

from flask import Blueprint, request, jsonify, g, render_template, redirect, url_for, session
from config import Config
from database import get_tenant_db_session
from app.models import User  # Import User model from models.py

# Define the Blueprint
auth_bp = Blueprint('auth', __name__)

# Helper function to infer tenant from hostname
def _infer_tenant_from_hostname():
    current_hostname = request.host.split(':')[0]
    inferred_tenant = 'website'
    for tenant_key in Config.TENANT_DATABASES.keys():
        if f"{tenant_key}.unfc.it" == current_hostname:
            inferred_tenant = tenant_key
            break
    return inferred_tenant

# Helper function to render templates with common context
def _render_template(template_name, **kwargs):
    inferred_tenant = _infer_tenant_from_hostname()
    inferred_tenant_display_name = Config.TENANT_DISPLAY_NAMES.get(
        inferred_tenant, inferred_tenant.capitalize()
    )
    show_tenant_dropdown = inferred_tenant in ['website', 'member']
    return render_template(
        template_name,
        inferred_tenant=inferred_tenant,
        inferred_tenant_display_name=inferred_tenant_display_name,
        tenant_display_names=Config.TENANT_DISPLAY_NAMES,
        show_tenant_dropdown=show_tenant_dropdown,
        **kwargs,
    )

# Index route
@auth_bp.route('/')
def index():
    if 'user_id' in session and 'tenant_id' in session:
        return redirect(url_for('members.demographics', tenant_id=session['tenant_id']))
    return _render_template('index.html')

# Register route
@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        data = request.form
        tenant_id = data.get('tenant_id', _infer_tenant_from_hostname())
        email = data.get('email')
        password = data.get('password')

        if not all([tenant_id, email, password]):
            return _render_template('register.html', error="Email and Password are required."), 400

        if tenant_id not in Config.TENANT_DATABASES:
            return _render_template('register.html', error=f"Invalid tenant ID: {tenant_id}"), 400

        with get_tenant_db_session(tenant_id) as s:
            existing_user = s.query(User).filter_by(tenant_id=tenant_id, email=email).first()
            if existing_user:
                return _render_template('register.html', error="User with this email already exists."), 409

            new_user = User(tenant_id=tenant_id, email=email)
            new_user.set_password(password)
            try:
                s.add(new_user)
                s.commit()
                session['user_id'] = new_user.id
                session['tenant_id'] = new_user.tenant_id
                session['user_email'] = new_user.email
                session['user_name'] = new_user.email
                return redirect(url_for('members.demographics', tenant_id=new_user.tenant_id))
            except Exception as e:
                s.rollback()
                return _render_template('register.html', error=f"Registration failed: {str(e)}"), 500

    return _render_template('register.html')

# Login route
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.form
        tenant_id = data.get('tenant_id', _infer_tenant_from_hostname())
        email = data.get('email')
        password = data.get('password')

        if not all([tenant_id, email, password]):
            return _render_template('login.html', error="All fields are required."), 400

        if tenant_id not in Config.TENANT_DATABASES:
            return _render_template('login.html', error=f"Invalid tenant ID: {tenant_id}"), 400

        with get_tenant_db_session(tenant_id) as s:
            user = s.query(User).filter_by(tenant_id=tenant_id, email=email).first()
            if user and user.check_password(password) and user.is_active:
                session['user_id'] = user.id
                session['tenant_id'] = user.tenant_id
                session['user_email'] = user.email
                session['user_name'] = f"{user.first_name or ''} {user.last_name or ''}".strip() or user.email
                return redirect(url_for('members.demographics', tenant_id=user.tenant_id))
            else:
                return _render_template('login.html', error="Invalid email or password."), 401

    return _render_template('login.html')

# Logout route
@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.index'))

# API route for managing users
@auth_bp.route('/api/<tenant_id>/users', methods=['GET', 'POST'])
def manage_users_api(tenant_id):
    if tenant_id != g.tenant_id:
        return jsonify({"error": f"Invalid tenant ID: {g.tenant_id}"}), 403

    if request.method == 'POST':
        data = request.get_json()
        if not all([tenant_id, data.get('first_name'), data.get('last_name'), data.get('email'), data.get('password')]):
            return jsonify({"error": "First Name, Last Name, Email, and Password are required"}), 400

        new_user = User(
            tenant_id=g.tenant_id,
            first_name=data.get('first_name'),
            middle_initial=data.get('middle_initial'),
            last_name=data.get('last_name'),
            email=data.get('email'),
            address=data.get('address'),
            cell_phone=data.get('cell_phone'),
            company=data.get('company'),
            company_address=data.get('company_address'),
            company_phone=data.get('company_phone'),
            company_title=data.get('company_title'),
            network_group_title=data.get('network_group_title'),
            member_anniversary=data.get('member_anniversary')
        )
        new_user.set_password(data['password'])

        try:
            with get_tenant_db_session(g.tenant_id) as session:
                session.add(new_user)
                session.commit()
                session.refresh(new_user)
            return jsonify({"message": "User added successfully!", "user": {"id": new_user.id, "first_name": new_user.first_name, "last_name": new_user.last_name, "email": new_user.email}}), 201
        except Exception as e:
            session.rollback()
            return jsonify({"error": f"Failed to add user: {str(e)}"}), 500

    elif request.method == 'GET':
        try:
            with get_tenant_db_session(g.tenant_id) as session:
                users = s.query(User).filter_by(tenant_id=g.tenant_id).all()
                user_list = [
                    {
                        "id": user.id,
                        "first_name": user.first_name,
                        "middle_initial": user.middle_initial,
                        "last_name": user.last_name,
                        "email": user.email,
                        "address": user.address,
                        "cell_phone": user.cell_phone,
                        "company": user.company,
                        "company_address": user.company_address,
                        "company_phone": user.company_phone,
                        "company_title": user.company_title,
                        "network_group_title": user.network_group_title,
                        "member_anniversary": user.member_anniversary
                    } for user in users
                ]
            return jsonify({"tenant": g.tenant_id, "users": user_list})
        except Exception as e:
            return jsonify({"error": f"Failed to retrieve users: {str(e)}"}), 500
