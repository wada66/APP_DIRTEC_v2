from flask import Blueprint

bp = Blueprint('dplam', __name__, template_folder='templates/dplam')

from . import routes
