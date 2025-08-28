# app/auth/routes.py

from flask import Blueprint, request, jsonify, g, render_template, redirect, url_for, session
from config import Config
from database import get_tenant_db_session
from app.models import User # Import User model from new models.py
from app.utils import infer_tenant_from_hostname # Import helper from new utils.py

# Define the Blueprint
auth_bp = Blueprint('auth', __name__)

# Routes
@auth_bp.route('/')
def index():
    if 'user_id' in session and 'tenant_id' in session:
        return redirect(url_for('members.demographics', tenant_id=session['tenant_id']))
    
    inferred_tenant = infer_tenant_from_hostname()
    inferred_tenant_display_name = Config.TENANT_DISPLAY_NAMES.get(inferred_tenant, inferred_tenant.capitalize())
    show_tenant_dropdown_on_index = (inferred_tenant == 'website' or inferred_tenant == 'member')
    
    return render_template('index.html', inferred_tenant=inferred_tenant, inferred_tenant_display_name=inferred_tenant_display_name, show_tenant_dropdown=show_tenant_dropdown_on_index)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    inferred_tenant_id = infer_tenant_from_hostname()
    inferred_tenant_display_name = Config.TENANT_DISPLAY_NAMES.get(inferred_tenant_id, inferred_tenant_id.capitalize())
    show_tenant_dropdown = (inferred_tenant_id == 'website' or inferred_tenant_id == 'member')

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
            existing_user = s.query(User).filter_by(tenant_id=tenant_id, email=email).first()
            if existing_user:
                # UPDATED: Specific error message for existing users
                return render_template('register.html', error="You are already registered, please use Login.", inferred_tenant=inferred_tenant_id, inferred_tenant_display_name=inferred_tenant_display_name, tenant_display_names=Config.TENANT_DISPLAY_NAMES, show_tenant_dropdown=show_tenant_dropdown), 409

            new_user = User(
                tenant_id=tenant_id,
                email=email,
                first_name=None, middle_initial=None, last_name=None,
                address=None, cell_phone=None, company=None,
                company_address=None, company_phone=None, company_title=None,
                network_group_title=None, member_anniversary=None
            )
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
                return render_template('register.html', error=f"Registration failed: {str(e)}", inferred_tenant=inferred_tenant_id, inferred_tenant_display_name=inferred_tenant_display_name, tenant_display_names=Config.TENANT_DISPLAY_NAMES, show_tenant_dropdown=show_tenant_dropdown), 500
    return render_template('register.html', inferred_tenant=inferred_tenant_id, inferred_tenant_display_name=inferred_tenant_display_name, tenant_display_names=Config.TENANT_DISPLAY_NAMES, show_tenant_dropdown=show_tenant_dropdown)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    inferred_tenant_id = infer_tenant_from_hostname()
    inferred_tenant_display_name = Config.TENANT_DISPLAY_NAMES.get(inferred_tenant_id, inferred_tenant_id.capitalize())
    show_tenant_dropdown = (inferred_tenant_id == 'website' or inferred_tenant_id == 'member')

    if request.method == 'POST':
        data = request.form
        tenant_id = data.get('tenant_id', inferred_tenant_id)
        email = data.get('email')
        password = data.get('password')

        if not all([tenant_id, email, password]):
            return render_template('login.html', error="All fields are required.", inferred_tenant=inferred_tenant_id, inferred_tenant_display_name=inferred_tenant_display_name, tenant_display_names=Config.TENANT_DISPLAY_NAMES, show_tenant_dropdown=show_tenant_dropdown), 400

        if tenant_id not in Config.TENANT_DATABASES:
             return render_template('login.html', error=f"Invalid tenant ID: {tenant_id}", inferred_tenant=inferred_tenant_id, inferred_tenant_display_name=inferred_tenant_display_name, tenant_display_names=Config.TENANT_DISPLAY_NAMES, show_tenant_dropdown=show_tenant_dropdown), 400

        with get_tenant_db_session(tenant_id) as s:
            user = s.query(User).filter_by(tenant_id=tenant_id, email=email).first()
            
            if user and user.check_password(password) and user.is_active:
                session['user_id'] = user.id
                session['tenant_id'] = user.tenant_id
                session['user_email'] = user.email
                session['user_name'] = f"{user.first_name or ''} {user.last_name or ''}".strip() or user.email
                return redirect(url_for('members.demographics', tenant_id=user.tenant_id))
            else:
                return render_template('login.html', error="Invalid email or password.", inferred_tenant=inferred_tenant_id, inferred_tenant_display_name=inferred_tenant_display_name, tenant_display_names=Config.TENANT_DISPLAY_NAMES, show_tenant_dropdown=show_tenant_dropdown), 401
    return render_template('login.html', inferred_tenant=inferred_tenant_id, inferred_tenant_display_name=inferred_tenant_display_name, tenant_display_names=Config.TENANT_DISPLAY_NAMES, show_tenant_dropdown=show_tenant_dropdown)

@auth_bp.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('tenant_id', None)
    session.pop('user_email', None) 
    session.pop('user_name', None)
    return redirect(url_for('auth.index'))

# API routes (moved from original app.py)
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

