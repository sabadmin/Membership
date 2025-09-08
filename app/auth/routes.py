# app/auth/routes.py

from flask import Blueprint, request, jsonify, g, render_template, redirect, url_for, session, flash
from config import Config
from database import get_tenant_db_session
from app.models import User, UserAuthDetails
from app.utils import infer_tenant_from_hostname
from datetime import datetime

# Define the Blueprint
auth_bp = Blueprint('auth', __name__)

# Routes
@auth_bp.route('/')
def index():
    if 'user_id' in session and 'tenant_id' in session:
        # If superadmin or member tenant, redirect to Admin Panel immediately after login
        if session['tenant_id'] in [Config.SUPERADMIN_TENANT_ID, 'member']:
            return redirect(url_for('admin.admin_panel', selected_tenant_id=session['tenant_id']))
        else:
            return redirect(url_for('members.my_demographics', tenant_id=session['tenant_id']))
    
    inferred_tenant = infer_tenant_from_hostname()
    inferred_tenant_display_name = Config.TENANT_DISPLAY_NAMES.get(inferred_tenant, inferred_tenant.capitalize())
    show_tenant_dropdown_on_index = (inferred_tenant == 'website' or inferred_tenant == 'member')
    
    return render_template('index.html', inferred_tenant=inferred_tenant, inferred_tenant_display_name=inferred_tenant_display_name, show_tenant_dropdown=show_tenant_dropdown_on_index)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        logger.info("Starting register route")
        inferred_tenant_id = infer_tenant_from_hostname()
        inferred_tenant_display_name = Config.TENANT_DISPLAY_NAMES.get(inferred_tenant_id, inferred_tenant_id.capitalize())
        show_tenant_dropdown = (inferred_tenant_id == 'website' or inferred_tenant_id == 'member')
        logger.info(f"Inferred tenant: {inferred_tenant_id}")

        if request.method == 'POST':
            logger.info("Processing POST request for registration")
            data = request.form
            tenant_id = data.get('tenant_id', inferred_tenant_id)
            email = data.get('email')
            password = data.get('password')

            if not all([tenant_id, email, password]):
                return render_template('register.html', error="Email and Password are required.", inferred_tenant=inferred_tenant_id, inferred_tenant_display_name=inferred_tenant_display_name, tenant_display_names=Config.TENANT_DISPLAY_NAMES, show_tenant_dropdown=show_tenant_dropdown), 400
            
            if tenant_id not in Config.TENANT_DATABASES:
                 return render_template('register.html', error=f"Invalid tenant ID: {tenant_id}", inferred_tenant=inferred_tenant_id, inferred_tenant_display_name=inferred_tenant_display_name, tenant_display_names=Config.TENANT_DISPLAY_NAMES, show_tenant_dropdown=show_tenant_dropdown), 400

            try:
                with get_tenant_db_session(tenant_id) as s:
                    logger.info(f"Checking for existing user with email: {email}")
                    user = s.query(User).filter_by(email=email).first()
                    if user:
                        return render_template('register.html', error="You are already registered, please use Login.", inferred_tenant=inferred_tenant_id, inferred_tenant_display_name=inferred_tenant_display_name, tenant_display_names=Config.TENANT_DISPLAY_NAMES, show_tenant_dropdown=show_tenant_dropdown), 409
                    
                    logger.info("Creating new user")
                    # Create a user with default empty values for demographic info
                    new_user = User(
                        email=email,
                        first_name=None, middle_initial=None, last_name=None,
                        address_line1=None, address_line2=None, city=None, state=None, zip_code=None,
                        cell_phone=None, company=None,
                        company_address_line1=None, company_address_line2=None,
                        company_city=None, company_state=None, company_zip_code=None,
                        company_phone=None, company_title=None,
                        network_group_title=None, member_anniversary=None
                    )
                    new_user.set_password(password)
                    logger.info("User object created, adding to session")

                    s.add(new_user)
                    s.flush() # Flush to get the new_user.id
                    logger.info(f"New user ID: {new_user.id}")
                    
                    # Create the corresponding UserAuthDetails entry
                    new_auth_details = UserAuthDetails(
                        user_id=new_user.id,
                        is_active=True,
                        last_login_1=datetime.utcnow()
                    )
                    s.add(new_auth_details)
                    s.commit()
                    logger.info("User and auth details committed successfully")

                    # Set session variables
                    session['user_id'] = new_user.id
                    session['tenant_id'] = tenant_id  # Use tenant_id from current context
                    session['user_email'] = new_user.email
                    session['user_name'] = f"{new_user.first_name or ''} {new_user.last_name or ''}".strip() or new_user.email
                    session['tenant_name'] = Config.TENANT_DISPLAY_NAMES.get(tenant_id, tenant_id.capitalize())

                    # Redirect based on tenant
                    if tenant_id in [Config.SUPERADMIN_TENANT_ID, 'member']:
                        flash("Welcome to admin! Access the admin panel.", "info")
                        return redirect(url_for('admin.admin_panel', selected_tenant_id=tenant_id))
                    else:
                        flash("Registration successful! Please fill in your demographic information.", "success")
                        return redirect(url_for('members.my_demographics', tenant_id=tenant_id))
                        
            except Exception as e:
                logger.error(f"Database error during registration: {str(e)}")
                logger.error(f"Error type: {type(e).__name__}")
                flash(f"Registration failed: {str(e)}", "danger")
                return render_template('register.html', error=f"Registration failed: {str(e)}", inferred_tenant=inferred_tenant_id, inferred_tenant_display_name=inferred_tenant_display_name, tenant_display_names=Config.TENANT_DISPLAY_NAMES, show_tenant_dropdown=show_tenant_dropdown), 500

        logger.info("Rendering register.html for GET request")
        return render_template('register.html', inferred_tenant=inferred_tenant_id, inferred_tenant_display_name=inferred_tenant_display_name, tenant_display_names=Config.TENANT_DISPLAY_NAMES, show_tenant_dropdown=show_tenant_dropdown)
        
    except Exception as e:
        logger.error(f"Error in register route: {str(e)}")
        logger.error(f"Error type: {type(e).__name__}")
        flash("An error occurred during registration.", "danger")
        return redirect(url_for('auth.index'))

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
            user = s.query(User).filter_by(email=email).first()
            
            if not user:
                return render_template('login.html', error="You don't have an account. Please register.", inferred_tenant=inferred_tenant_id, inferred_tenant_display_name=inferred_tenant_display_name, tenant_display_names=Config.TENANT_DISPLAY_NAMES, show_tenant_dropdown=show_tenant_dropdown), 401
            
            # Create missing UserAuthDetails for existing users
            if not user.auth_details:
                user.auth_details = UserAuthDetails(
                    user_id=user.id,
                    is_active=True,  # Default existing users to active
                    last_login_1=datetime.utcnow()
                )
                s.add(user.auth_details)
                s.flush()  # Make sure the relationship is established
            
            # Check if account is active
            if not user.auth_details.is_active:
                return render_template('login.html', error="Account is inactive. Please contact support.", inferred_tenant=inferred_tenant_id, inferred_tenant_display_name=inferred_tenant_display_name, tenant_display_names=Config.TENANT_DISPLAY_NAMES, show_tenant_dropdown=show_tenant_dropdown), 401
            
            if user.check_password(password):
                user.auth_details.update_last_login()
                s.commit()
                
                session['user_id'] = user.id
                session['tenant_id'] = tenant_id  # Use tenant_id from current context
                session['user_email'] = user.email
                session['user_name'] = f"{user.first_name or ''} {user.last_name or ''}".strip() or user.email
                session['tenant_name'] = Config.TENANT_DISPLAY_NAMES.get(tenant_id, tenant_id.capitalize())
                
                if tenant_id in [Config.SUPERADMIN_TENANT_ID, 'member']:
                    return redirect(url_for('admin.admin_panel', selected_tenant_id=tenant_id))
                else:
                    return redirect(url_for('members.my_demographics', tenant_id=tenant_id))
            else:
                return render_template('login.html', error="Invalid email or password.", inferred_tenant=inferred_tenant_id, inferred_tenant_display_name=inferred_tenant_display_name, tenant_display_names=Config.TENANT_DISPLAY_NAMES, show_tenant_dropdown=show_tenant_dropdown), 401
    return render_template('login.html', inferred_tenant=inferred_tenant_id, inferred_tenant_display_name=inferred_tenant_display_name, tenant_display_names=Config.TENANT_DISPLAY_NAMES, show_tenant_dropdown=show_tenant_dropdown)

@auth_bp.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('tenant_id', None) 
    session.pop('user_email', None) 
    session.pop('user_name', None)
    session.pop('tenant_name', None)
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
            first_name=data.get('first_name'),
            middle_initial=data.get('middle_initial'),
            last_name=data.get('last_name'),
            email=data.get('email'),
            address_line1=data.get('address_line1'),
            address_line2=data.get('address_line2'),
            city=data.get('city'),
            state=data.get('state'),
            zip_code=data.get('zip_code'),
            cell_phone=data.get('cell_phone'),
            company=data.get('company'),
            company_address_line1=data.get('company_address_line1'),
            company_address_line2=data.get('company_address_line2'),
            company_city=data.get('company_city'),
            company_state=data.get('company_state'),
            company_zip_code=data.get('company_zip_code'),
            company_phone=data.get('company_phone'),
            company_title=data.get('company_title'),
            network_group_title=data.get('network_group_title'),
            member_anniversary=data.get('member_anniversary')
        )
        new_user.set_password(data['password'])

        try:
            with get_tenant_db_session(g.tenant_id) as s:
                s.add(new_user)
                s.flush()
                
                new_auth_details = UserAuthDetails(
                    user_id=new_user.id,
                    is_active=True,
                    last_login_1=datetime.utcnow()
                )
                s.add(new_auth_details)
                s.commit()
                session.refresh(new_user)
            return jsonify({"message": "User added successfully!", "user": {"id": new_user.id, "first_name": new_user.first_name, "last_name": new_user.last_name, "email": new_user.email}}), 201
        except Exception as e:
            s.rollback()
            return jsonify({"error": f"Failed to add user: {str(e)}"}), 500

    elif request.method == 'GET':
        try:
            with get_tenant_db_session(g.tenant_id) as s:
                users = s.query(User).all()
                user_list = [
                    {
                        "id": user.id,
                        "first_name": user.first_name,
                        "middle_initial": user.middle_initial,
                        "last_name": user.last_name,
                        "email": user.email,
                        "address_line1": user.address_line1,
                        "address_line2": user.address_line2,
                        "city": user.city,
                        "state": user.state,
                        "zip_code": user.zip_code,
                        "cell_phone": user.cell_phone,
                        "company": user.company,
                        "company_address_line1": user.company_address_line1,
                        "company_address_line2": user.company_address_line2,
                        "company_city": user.company_city,
                        "company_state": user.company_state,
                        "company_zip_code": user.company_zip_code,
                        "company_phone": user.company_phone,
                        "company_title": user.company_title,
                        "network_group_title": user.network_group_title,
                        "member_anniversary": user.member_anniversary
                    } for user in users
                ]
            return jsonify({"users": user_list})
        except Exception as e:
            return jsonify({"error": f"Failed to retrieve users: {str(e)}"}), 500
