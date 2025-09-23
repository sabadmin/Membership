from flask import Blueprint

referrals_bp = Blueprint('referrals', __name__, url_prefix='/referrals', template_folder='../../templates/referrals')

from . import routes
