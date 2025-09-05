from flask import render_template
from . import bp

@bp.route('/ambiente')
def ambiente():
    return render_template('dplam/ambiente_setor.html')
