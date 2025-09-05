from flask import render_template, session
from . import bp

@bp.route('/ambiente')
def ambiente():
    # Aqui você pode verificar a sessão e exibir dados específicos do setor DIG
    return render_template('dig/ambiente_setor.html')

