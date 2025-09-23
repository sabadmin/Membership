from flask import Blueprint # type: ignore

dues_bp = Blueprint('dues', __name__, url_prefix='/dues', template_folder='../../templates/dues')

from . import routes
