from flask import Blueprint

bp = Blueprint('dig', __name__)

from . import routes
