from flask import Blueprint

dues_bp = Blueprint('dues', __name__, url_prefix='/dues', template_folder='../../templates/dues')

from . import routes
