from flask import Blueprint

bp = Blueprint('diretor_tecnico', __name__, template_folder='templates/diretor_tecnico')

from . import routes
