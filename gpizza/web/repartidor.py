"""Interfaz del repartidor (boceto 9): disponibilidad, entregas activas (máx. 2) y aceptación.
La confirmación de entrega con firma o código y el mapa llegan en la Fase 5."""
from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from gpizza import reglas
from gpizza.extensiones import db
from gpizza.modelos import Empleado
from gpizza.seguridad.acceso import rol_requerido
from gpizza.servicios import asignacion

bp = Blueprint('repartidor', __name__, url_prefix='/repartidor')


def _datos():
    yo = db.session.get(Empleado, g.usuario.id_empleado)
    entregas = asignacion.del_repartidor(yo.id_empleado)
    return {'disponible': yo.disponible, 'entregas': entregas, 'maximo': reglas.MAX_PEDIDOS_ACTIVOS_REPARTIDOR,
            'plazo': reglas.PLAZO_ACEPTAR_ASIGNACION_MIN}


@bp.get('/')
@rol_requerido('Repartidor')
def inicio():
    return render_template('repartidor/inicio.html', **_datos())


@bp.get('/entregas')
@rol_requerido('Repartidor')
def entregas():
    """Fragmento que la pantalla vuelve a pedir cada 10 s: así aparece una asignación nueva."""
    return render_template('repartidor/_entregas.html', **_datos())


@bp.post('/disponibilidad')
@rol_requerido('Repartidor')
def disponibilidad():
    disponible = request.form.get('disponible') == 'si'
    asignacion.cambiar_disponibilidad(g.usuario.id_empleado, disponible)
    flash('Estás disponible para recibir pedidos.' if disponible
          else 'No recibirás pedidos nuevos hasta que vuelvas a activarte.', 'exito')
    return redirect(url_for('repartidor.inicio'))


@bp.post('/asignaciones/<int:id_asignacion>/aceptar')
@rol_requerido('Repartidor')
def aceptar(id_asignacion):
    problema = asignacion.aceptar(id_asignacion, g.usuario.id_empleado)
    flash(problema or 'Entrega aceptada: el pedido va en camino y el cliente ya lo sabe.', 'error' if problema else 'exito')
    return redirect(url_for('repartidor.inicio'))
