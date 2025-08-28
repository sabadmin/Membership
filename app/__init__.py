# app/__init__.py

import os
from flask import Flask, session, g, request, jsonify
from config import Config
from database import db, init_db_for_tenant, close_db_session

def create_app():
    # Explicitly define the template folder relative to the project root
    # This assumes 'templates' is in the same directory as 'app' and 'run.py'
    template_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'templates'))
    static_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static'))

    app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)
    app.config.from_object(Config)

    db.init_app(app)

    with app.app_context():
        for tenant_id in Config.TENANT_DATABASES.keys():
            init_db_for_tenant(app, tenant_id)

    app.teardown_appcontext(close_db_session)

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

    from app.auth.routes import auth_bp
    from app.members.routes import members_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(members_bp)

    return app

