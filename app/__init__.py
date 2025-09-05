# app/__init__.py

import os
import logging
from flask import Flask, session, g, request, jsonify
from config import Config
from database import db, init_db_for_tenant, close_db_session

# Set up logging for debugging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_app():
    try:
        logger.info("Starting Flask app creation...")
        
        template_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'templates'))
        static_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static'))
        logger.info(f"Template dir: {template_dir}")
        logger.info(f"Static dir: {static_dir}")

        app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)
        app.config.from_object(Config)
        logger.info("Flask app instance created successfully")

        # Initialize database
        db.init_app(app)
        logger.info("Database initialized with Flask app")

        # Import models here to ensure they're registered before table creation
        logger.info("Importing all models...")
        from app.models import User, UserAuthDetails, AttendanceRecord, DuesRecord, ReferralRecord, MembershipType
        logger.info("All models imported successfully")

        with app.app_context():
            logger.info("Starting tenant database initialization...")
            for tenant_id in Config.TENANT_DATABASES.keys():
                try:
                    logger.info(f"Initializing database for tenant: {tenant_id}")
                    init_db_for_tenant(app, tenant_id)
                    logger.info(f"Successfully initialized tenant: {tenant_id}")
                except Exception as e:
                    logger.error(f"Failed to initialize tenant {tenant_id}: {str(e)}")
                    raise

        app.teardown_appcontext(close_db_session)
        logger.info("Database teardown handler registered")

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

        @app.before_request
        def set_tenant_id_from_session_or_param():
            if 'tenant_id' in session and session['tenant_id'] in Config.TENANT_DATABASES:
                g.tenant_id = session['tenant_id']
            else:
                current_hostname = request.host.split(':')[0]
                inferred_tenant_from_host = 'website'
                for tenant_key in Config.TENANT_DATABASES.keys():
                    if f"{tenant_key}.unfc.it" == current_hostname:
                        inferred_tenant_from_host = tenant_key
                        break
                g.tenant_id = request.headers.get('X-Tenant-ID', request.args.get('tenant_id', inferred_tenant_from_host))

            if g.tenant_id not in Config.TENANT_DATABASES:
                return jsonify({"error": f"Invalid tenant ID: {g.tenant_id}"}), 400

            if g.tenant_id in Config.TENANT_DATABASES:
                session['tenant_name'] = Config.TENANT_DISPLAY_NAMES.get(g.tenant_id, g.tenant_id.capitalize())
            else:
                session.pop('tenant_name', None)

        # Register Blueprints
        logger.info("Registering blueprints...")
        try:
            from app.auth.routes import auth_bp
            from app.members.routes import members_bp
            from app.admin.routes import admin_bp
            
            app.register_blueprint(auth_bp)
            app.register_blueprint(members_bp)
            app.register_blueprint(admin_bp)
            logger.info("All blueprints registered successfully")
        except Exception as e:
            logger.error(f"Failed to register blueprints: {str(e)}")
            raise

        # Add context processor for global template variables
        @app.context_processor
        def inject_globals():
            return dict(Config=Config, session=session)

        logger.info("Flask app creation completed successfully")
        return app
        
    except Exception as e:
        logger.error(f"Failed to create Flask app: {str(e)}")
        logger.error(f"Error type: {type(e).__name__}")
        raise

