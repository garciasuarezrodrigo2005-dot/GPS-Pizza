"""Interfaz del cliente (boceto, páginas 1 a 5). En la Fase 0 solo existe la pantalla de inicio."""
from flask import Blueprint, render_template

from gpizza import reglas, reloj

bp = Blueprint('cliente', __name__)


@bp.get('/')
def inicio():
    return render_template('cliente/inicio.html',
                           en_horario=reloj.en_horario(),
                           apertura=reglas.HORA_APERTURA, cierre=reglas.HORA_CIERRE)
