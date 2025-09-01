import os
from flask import Flask, request, jsonify, g, render_template, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
from config import Config
from database import db, init_db_for_tenant, get_tenant_db_session, close_db_session, Base
from sqlalchemy import Column, Integer, String, Boolean
from dotenv import load_dotenv
from app.auth.routes import auth_bp

load_dotenv()

# User model
class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    tenant_id = Column(String(50), nullable=False)
    first_name = Column(String(80), nullable=True)
    middle_initial = Column(String(1), nullable=True)
    last_name = Column(String(80), nullable=True)
    email = Column(String(120), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    address = Column(String(255), nullable=True)
    cell_phone = Column(String(20), nullable=True)
    company = Column(String(120), nullable=True)
    company_address = Column(String(255), nullable=True)
    company_phone = Column(String(20), nullable=True)
    company_title = Column(String(80), nullable=True)
    network_group_title = Column(String(120), nullable=True)
    member_anniversary = Column(String(5), nullable=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.email}>'

# Flask app factory
def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)

    with app.app_context():
        for tenant_id in Config.TENANT_DATABASES.keys():
            init_db_for_tenant(app, tenant_id)

    app.teardown_appcontext(close_db_session)

    # Register blueprints
    app.register_blueprint(auth_bp, url_prefix='/auth')

    # Custom Jinja2 filter for phone number formatting
    @app.template_filter('format_phone_number')
    def format_phone_number_filter(phone_number):
        if not phone_number:
            return ""
        digits = ''.join(filter(str.isdigit, phone_number))
        if len(digits) == 10:
            return f"({digits[0:3]}) {digits[3:6]}-{digits[6:10]}"
        elif len(digits) == 11 and digits.startswith('1'):
            return f"1 ({digits[1:4]}) {digits[4:7]}-{digits[7:11]}"
        return phone_number

    # Middleware to set tenant ID
    @app.before_request
    def set_tenant_id_from_session_or_param():
        if 'tenant_id' in session and session['tenant_id'] in Config.TENANT_DATABASES:
            g.tenant_id = session['tenant_id']
        else:
            current_hostname = request.host.split(':')[0]
            inferred_tenant = 'website'
            for tenant_key in Config.TENANT_DATABASES.keys():
                if f"{tenant_key}.unfc.it" == current_hostname:
                    inferred_tenant = tenant_key
                    break
            g.tenant_id = request.headers.get('X-Tenant-ID', request.args.get('tenant_id', inferred_tenant))

        if g.tenant_id not in Config.TENANT_DATABASES:
            return jsonify({"error": f"Invalid tenant ID: {g.tenant_id}"}), 400

    # Routes
    @app.route('/')
    def index():
        if 'user_id' in session and 'tenant_id' in session:
            return redirect(url_for('demographics', tenant_id=session['tenant_id']))
        inferred_tenant = 'website'
        current_hostname = request.host.split(':')[0]
        for tenant_key in Config.TENANT_DATABASES.keys():
            if f"{tenant_key}.unfc.it" == current_hostname:
                inferred_tenant = tenant_key
                break
        inferred_tenant_display_name = Config.TENANT_DISPLAY_NAMES.get(inferred_tenant, inferred_tenant.capitalize())
        show_tenant_dropdown = inferred_tenant in ['website', 'member']
        return render_template('index.html', inferred_tenant=inferred_tenant,
                               inferred_tenant_display_name=inferred_tenant_display_name,
                               show_tenant_dropdown=show_tenant_dropdown)

    @app.route('/register', methods=['GET', 'POST'])
    def register():
        inferred_tenant_id = 'website'
        current_hostname = request.host.split(':')[0]
        for tenant_key in Config.TENANT_DATABASES.keys():
            if f"{tenant_key}.unfc.it" == current_hostname:
                inferred_tenant_id = tenant_key
                break
        inferred_tenant_display_name = Config.TENANT_DISPLAY_NAMES.get(inferred_tenant_id, inferred_tenant_id.capitalize())
        show_tenant_dropdown = inferred_tenant_id in ['website', 'member']

        if request.method == 'POST':
            data = request.form
            tenant_id = data.get('tenant_id', inferred_tenant_id)
            email = data.get('email')
            password = data.get('password')

            if not all([tenant_id, email, password]):
                return render_template('register.html', error="Email and Password are required.",
                                       inferred_tenant=inferred_tenant_id,
                                       inferred_tenant_display_name=inferred_tenant_display_name,
                                       tenant_display_names=Config.TENANT_DISPLAY_NAMES,
                                       show_tenant_dropdown=show_tenant_dropdown), 400

            if tenant_id not in Config.TENANT_DATABASES:
                return render_template('register.html', error=f"Invalid tenant ID: {tenant_id}",
                                       inferred_tenant=inferred_tenant_id,
                                       inferred_tenant_display_name=inferred_tenant_display_name,
                                       tenant_display_names=Config.TENANT_DISPLAY_NAMES,
                                       show_tenant_dropdown=show_tenant_dropdown), 400

            with get_tenant_db_session(tenant_id) as s:
                existing_user = s.query(User).filter_by(tenant_id=tenant_id, email=email).first()
                if existing_user:
                    return render_template('register.html', error="User with this email already exists for this tenant.",
                                           inferred_tenant=inferred_tenant_id,
                                           inferred_tenant_display_name=inferred_tenant_display_name,
                                           tenant_display_names=Config.TENANT_DISPLAY_NAMES,
                                           show_tenant_dropdown=show_tenant_dropdown), 409

                new_user = User(tenant_id=tenant_id, email=email)
                new_user.set_password(password)
                try:
                    s.add(new_user)
                    s.commit()
                    session['user_id'] = new_user.id
                    session['tenant_id'] = new_user.tenant_id
                    session['user_email'] = new_user.email
                    session['user_name'] = new_user.email
                    return redirect(url_for('demographics', tenant_id=new_user.tenant_id))
                except Exception as e:
                    s.rollback()
                    return render_template('register.html', error=f"Registration failed: {str(e)}",
                                           inferred_tenant=inferred_tenant_id,
                                           inferred_tenant_display_name=inferred_tenant_display_name,
                                           tenant_display_names=Config.TENANT_DISPLAY_NAMES,
                                           show_tenant_dropdown=show_tenant_dropdown), 500
        return render_template('register.html', inferred_tenant=inferred_tenant_id,
                               inferred_tenant_display_name=inferred_tenant_display_name,
                               tenant_display_names=Config.TENANT_DISPLAY_NAMES,
                               show_tenant_dropdown=show_tenant_dropdown)

    @app.route('/demographics/<tenant_id>')
    def demographics(tenant_id):
        # Implement demographics logic here
        return render_template('demographics.html', tenant_id=tenant_id)

    # Inject Config and session into all templates
    @app.context_processor
    def inject_globals():
        return dict(Config=Config, session=session)

    return app