"""Panel administrativo del gerente (boceto, página 10). En la Fase 2 solo existe el panel vacío."""
from flask import Blueprint, render_template

from gpizza.seguridad.acceso import rol_requerido

bp = Blueprint('gerente', __name__, url_prefix='/gerente')


@bp.get('/')
@rol_requerido('Gerente')
def inicio():
    return render_template('gerente/inicio.html')
