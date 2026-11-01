"""Interfaz del cajero (boceto, páginas 7 y 8). En la Fase 2 solo existe el panel vacío."""
from flask import Blueprint, render_template

from gpizza.seguridad.acceso import rol_requerido

bp = Blueprint('cajero', __name__, url_prefix='/cajero')


@bp.get('/')
@rol_requerido('Cajero')
def inicio():
    return render_template('cajero/inicio.html')
