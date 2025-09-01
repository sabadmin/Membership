# app/auth/routes.py

from flask import Blueprint, request, jsonify, g, render_template, redirect, url_for, session, flash
from config import Config
from database import get_tenant_db_session
from app.models import User, UserAuthDetails
from app.utils import infer_tenant_from_hostname
from datetime import datetime

# Define the Blueprint
auth_bp = Blueprint('auth', __name__)

# Helper function to infer tenant details
def get_tenant_details():
    inferred_tenant_id = infer_tenant_from_hostname()
    inferred_tenant_display_name = Config.TENANT_DISPLAY_NAMES.get(inferred_tenant_id, inferred_tenant_id.capitalize())
    show_tenant_dropdown = (inferred_tenant_id == 'website' or inferred_tenant_id == 'member')
    return inferred_tenant_id, inferred_tenant_display_name, show_tenant_dropdown

# Helper function to set session variables
def set_session_variables(user):
    session['user_id'] = user.id
    session['tenant_id'] = user.tenant_id
    session['user_email'] = user.email
    session['user_name'] = f"{user.first_name or ''} {user.last_name or ''}".strip() or user.email
    session['tenant_name'] = Config.TENANT_DISPLAY_NAMES.get(user.tenant_id, user.tenant_id.capitalize())

# Routes
@auth_bp.route('/')
def index():
    if 'user_id' in session and 'tenant_id' in session:
        # Redirect to admin_panel if the user is a super admin
        if session['tenant_id'] == Config.SUPERADMIN_TENANT_ID:
            return redirect(url_for('admin.admin_panel', selected_tenant_id=session['tenant_id']))
        # Otherwise, redirect to demographics
        return redirect(url_for('members.demographics', tenant_id=session['tenant_id']))
    
    # If no session, infer tenant details and render the index page
    inferred_tenant_id, inferred_tenant_display_name, show_tenant_dropdown = get_tenant_details()
    return render_template('index.html', inferred_tenant=inferred_tenant_id, inferred_tenant_display_name=inferred_tenant_display_name, show_tenant_dropdown=show_tenant_dropdown)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    inferred_tenant_id, inferred_tenant_display_name, show_tenant_dropdown = get_tenant_details()

    if request.method == 'POST':
        data = request.form
        tenant_id = data.get('tenant_id', inferred_tenant_id)
        email = data.get('email')
        password = data.get('password')

        if not all([tenant_id, email, password]):
            return render_template('register.html', error="Email and Password are required.", inferred_tenant=inferred_tenant_id, inferred_tenant_display_name=inferred_tenant_display_name, tenant_display_names=Config.TENANT_DISPLAY_NAMES, show_tenant_dropdown=show_tenant_dropdown), 400
        
        if tenant_id not in Config.TENANT_DATABASES:
            return render_template('register.html', error=f"Invalid tenant ID: {tenant_id}", inferred_tenant=inferred_tenant_id, inferred_tenant_display_name=inferred_tenant_display_name, tenant_display_names=Config.TENANT_DISPLAY_NAMES, show_tenant_dropdown=show_tenant_dropdown), 400

        with get_tenant_db_session(tenant_id) as s:
            user = s.query(User).filter_by(tenant_id=tenant_id, email=email).first()
            if user:
                return render_template('register.html', error="You are already registered, please use Login.", inferred_tenant=inferred_tenant_id, inferred_tenant_display_name=inferred_tenant_display_name, tenant_display_names=Config.TENANT_DISPLAY_NAMES, show_tenant_dropdown=show_tenant_dropdown), 409
            
            new_user = User(tenant_id=tenant_id, email=email)
            new_user.set_password(password)

            try:
                s.add(new_user)
                s.flush()
                new_auth_details = UserAuthDetails(user_id=new_user.id, tenant_id=new_user.tenant_id, is_active=True, last_login_1=datetime.utcnow())
                s.add(new_auth_details)
                s.commit()

                set_session_variables(new_user)

                flash("Registration successful! Please fill in your demographic information.", "success")
                return redirect(url_for('members.demographics', tenant_id=new_user.tenant_id))
            except Exception as e:
                s.rollback()
                flash(f"Registration failed: {str(e)}", "danger")
                return redirect(url_for('auth.register', tenant_id=tenant_id))

    return render_template('register.html', inferred_tenant=inferred_tenant_id, inferred_tenant_display_name=inferred_tenant_display_name, tenant_display_names=Config.TENANT_DISPLAY_NAMES, show_tenant_dropdown=show_tenant_dropdown)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.form
        tenant_id = data.get('tenant_id')  # Retrieve tenant_id from the form

        # If tenant_id is not provided, infer it from the hostname
        if not tenant_id:
            tenant_id = infer_tenant_from_hostname()

        email = data.get('email')
        password = data.get('password')

        # Validate that tenant_id, email, and password are provided
        if not all([tenant_id, email, password]):
            return render_template('login.html', error="All fields are required.")

        # Check if tenant_id exists in the database configuration
        if tenant_id not in Config.TENANT_DATABASES:
            return render_template('login.html', error=f"Invalid tenant ID: {tenant_id}")

        # Attempt to retrieve the user from the database
        try:
            with get_tenant_db_session(tenant_id) as s:
                user = s.query(User).filter_by(tenant_id=tenant_id, email=email).first()
                if user and user.check_password(password):
                    session['user_id'] = user.id
                    session['tenant_id'] = user.tenant_id
                    session['user_email'] = user.email
                    session['user_name'] = f"{user.first_name or ''} {user.last_name or ''}".strip() or user.email
                    return redirect(url_for('auth.index'))
                else:
                    return render_template('login.html', error="Invalid email or password.")
        except RuntimeError as e:
            return render_template('login.html', error=str(e))

    return render_template('login.html')

@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.index'))

# API routes
@auth_bp.route('/api/<tenant_id>/users', methods=['GET', 'POST'])
def manage_users_api(tenant_id): 
    if tenant_id != g.tenant_id:
        return jsonify({"error": "Tenant ID mismatch in URL and request context"}), 403

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
                session.flush()
                new_auth_details = UserAuthDetails(
                    user_id=new_user.id,
                    tenant_id=new_user.tenant_id,
                    is_active=True,
                    last_login_1=datetime.utcnow()
                )
                session.add(new_auth_details)
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