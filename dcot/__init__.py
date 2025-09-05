from flask import Blueprint

bp = Blueprint('dcot', __name__, template_folder='templates/dcot')

from . import routes
