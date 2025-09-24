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
        from app.models import User, UserAuthDetails, AttendanceRecord, AttendanceType, ReferralRecord, ReferralType, MembershipType, DuesRecord, DuesType
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

        # Register template filters
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

        @app.template_filter('utc_to_local')
        def utc_to_local_filter(utc_dt):
            """
            Convert UTC datetime to local time (Eastern Time).
            Assumes UTC datetime input and converts to America/New_York timezone.
            """
            if utc_dt is None:
                return None

            from datetime import timezone, timedelta

            # Eastern Time offset (EDT is UTC-4, EST is UTC-5)
            # For simplicity, using fixed offset. In production, use pytz for proper DST handling
            eastern_offset = timedelta(hours=-4)  # EDT
            local_tz = timezone(eastern_offset)

            # If the datetime is naive (no timezone), assume it's UTC
            if utc_dt.tzinfo is None:
                utc_dt = utc_dt.replace(tzinfo=timezone.utc)

            # Convert to local time
            local_dt = utc_dt.astimezone(local_tz)
            return local_dt

        @app.before_request
        def set_tenant_id_from_session_or_param():
            # Skip tenant validation for auth routes (index, login, register)
            if request.endpoint and request.endpoint.startswith('auth.'):
                # For auth routes, still try to infer tenant but don't enforce validation
                if 'tenant_id' in session and session['tenant_id'] in Config.TENANT_DATABASES:
                    g.tenant_id = session['tenant_id']
                else:
                    current_hostname = request.host.split(':')[0]
                    inferred_tenant_from_host = 'tenant1'
                    for tenant_key in Config.TENANT_DATABASES.keys():
                        if f"{tenant_key}.unfc.it" == current_hostname:
                            inferred_tenant_from_host = tenant_key
                            break
                    g.tenant_id = request.headers.get('X-Tenant-ID', request.args.get('tenant_id', inferred_tenant_from_host))

                # For auth routes, allow any valid tenant or default to tenant1
                if g.tenant_id not in Config.TENANT_DATABASES:
                    g.tenant_id = 'tenant1'

                if g.tenant_id in Config.TENANT_DATABASES:
                    session['tenant_name'] = Config.TENANT_DISPLAY_NAMES.get(g.tenant_id, g.tenant_id.capitalize())
                else:
                    session.pop('tenant_name', None)
                return

            # For all other routes, enforce tenant validation
            if 'tenant_id' in session and session['tenant_id'] in Config.TENANT_DATABASES:
                g.tenant_id = session['tenant_id']
            else:
                current_hostname = request.host.split(':')[0]
                inferred_tenant_from_host = 'tenant1'
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
            from app.attendance import attendance_bp
            from app.dues import dues_bp
            from app.referrals import referrals_bp

            app.register_blueprint(auth_bp)
            app.register_blueprint(members_bp)
            app.register_blueprint(admin_bp)
            app.register_blueprint(attendance_bp)
            app.register_blueprint(dues_bp)
            app.register_blueprint(referrals_bp)
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
