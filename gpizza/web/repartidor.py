"""Interfaz del repartidor (boceto 9): disponibilidad, entregas activas (máx. 2), mapa con GPS y
confirmación de entrega en dos pasos (RF-010, RN-013)."""
from flask import Blueprint, flash, g, jsonify, redirect, render_template, request, url_for

from gpizza import reglas
from gpizza.extensiones import db
from gpizza.modelos import Empleado
from gpizza.seguridad.acceso import rol_requerido
from gpizza.servicios import asignacion, entregas

bp = Blueprint('repartidor', __name__, url_prefix='/repartidor')


def _version(lista) -> str:
    """Cambia cuando cambian las entregas (llega una, se acepta, el cliente confirma, se entrega)."""
    return '|'.join(f'{a.id_asignacion}:{a.estado}:{int(a.fecha_confirmacion_cliente is not None)}' for a in lista)


@bp.get('/')
@rol_requerido('Repartidor')
def inicio():
    yo = db.session.get(Empleado, g.usuario.id_empleado)
    lista = asignacion.del_repartidor(yo.id_empleado)
    return render_template('repartidor/inicio.html', yo=yo, entregas=lista, version=_version(lista),
                           maximo=reglas.MAX_PEDIDOS_ACTIVOS_REPARTIDOR, plazo=reglas.PLAZO_ACEPTAR_ASIGNACION_MIN)


@bp.get('/version')
@rol_requerido('Repartidor')
def version():
    """La pantalla pregunta cada 10 s; si cambió, se recarga (pero nunca mientras el cliente firma)."""
    return jsonify(version=_version(asignacion.del_repartidor(g.usuario.id_empleado)))


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


@bp.post('/ubicacion')
@rol_requerido('Repartidor')
def ubicacion():
    """GPS del navegador (cada ~15 s) o del botón "Simular recorrido"."""
    problema = entregas.actualizar_ubicacion(g.usuario.id_empleado, request.form.get('latitud'),
                                             request.form.get('longitud'))
    if problema:
        return jsonify(ok=False, mensaje=problema), 409 if 'Sin entregas' in problema else 400
    return jsonify(ok=True)


@bp.post('/asignaciones/<int:id_asignacion>/confirmacion-cliente')
@rol_requerido('Repartidor')
def confirmacion_cliente(id_asignacion):
    problema = entregas.confirmar_cliente(id_asignacion, g.usuario.id_empleado,
                                          firma=request.form.get('firma', ''), codigo=request.form.get('codigo', ''))
    flash(problema or 'Confirmación del cliente registrada. Ahora marca el pedido como entregado.',
          'error' if problema else 'exito')
    return redirect(url_for('repartidor.inicio'))


@bp.post('/asignaciones/<int:id_asignacion>/entregar')
@rol_requerido('Repartidor')
def entregar(id_asignacion):
    problema = entregas.entregar(id_asignacion, g.usuario.id_empleado)
    flash(problema or 'Pedido entregado. Se guardaron la fecha y la hora.', 'error' if problema else 'exito')
    return redirect(url_for('repartidor.inicio'))


@bp.get('/historial')
@rol_requerido('Repartidor')
def historial():
    return render_template('repartidor/historial.html', entregadas=entregas.historial_hoy(g.usuario.id_empleado))
