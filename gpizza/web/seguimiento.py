"""CU-003 Consultar Seguimiento de Pedido (RF-004) para el personal: búsqueda por folio o teléfono
(pasos 2 y 3) y detalle completo (pasos 4 y 5). Cajero y gerente ven los de su sucursal; el
repartidor, solo los que le asignaron."""
from flask import Blueprint, abort, g, render_template, request

from gpizza.seguridad.acceso import rol_requerido
from gpizza.servicios import ciclo

bp = Blueprint('seguimiento', __name__, url_prefix='/seguimiento')


@bp.get('/')
@rol_requerido('Cajero', 'Gerente')
def buscar():
    texto = request.args.get('q', '')
    resultados = ciclo.buscar(g.usuario.id_sucursal, texto)
    return render_template('seguimiento/buscar.html', q=texto, resultados=resultados)


@bp.get('/<folio>')
@rol_requerido('Cajero', 'Gerente', 'Repartidor')
def detalle(folio):
    pedido = ciclo.por_folio(folio)
    if pedido is None or pedido.id_sucursal != g.usuario.id_sucursal:
        abort(404)
    asignaciones = ciclo.asignaciones_de(pedido)
    if g.usuario.rol == 'Repartidor' and g.usuario.id_empleado not in {a.id_repartidor for a in asignaciones}:
        abort(404)
    return render_template('seguimiento/detalle.html', pedido=pedido, asignaciones=asignaciones)
