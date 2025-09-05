from flask import render_template
from . import bp

@bp.route('/ambiente')
def ambiente():
    return render_template('diretor_tecnico/ambiente_setor.html')
