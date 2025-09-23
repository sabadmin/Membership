from flask import Blueprint # type: ignore

attendance_bp = Blueprint('attendance', __name__, url_prefix='/attendance', template_folder='../../templates/attendance')

from . import routes
