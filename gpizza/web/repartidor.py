"""Interfaz del repartidor (boceto, página 9). En la Fase 2 solo existe el panel vacío."""
from flask import Blueprint, render_template

from gpizza.seguridad.acceso import rol_requerido

bp = Blueprint('repartidor', __name__, url_prefix='/repartidor')


@bp.get('/')
@rol_requerido('Repartidor')
def inicio():
    return render_template('repartidor/inicio.html')
